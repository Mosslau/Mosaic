package main

import (
	"net/rpc/jsonrpc"
	"strings"
	"testing"
	"time"
)

// waitFor 轮询等待条件成立（注册表/心跳是异步的，断言前要等）
func waitFor(t *testing.T, timeout time.Duration, cond func() bool, msg string) {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("等待超时: %s", msg)
}

func TestRegisterDiscover(t *testing.T) {
	reg := NewRegistry(time.Second)
	reg.Register("user.Service", "127.0.0.1:1")
	reg.Register("user.Service", "127.0.0.1:2")
	reg.Register("order.Service", "127.0.0.1:3")

	addrs := reg.Discover("user.Service")
	if len(addrs) != 2 || addrs[0] != "127.0.0.1:1" || addrs[1] != "127.0.0.1:2" {
		t.Fatalf("Discover 结果异常: %v", addrs)
	}
	if got := reg.Discover("order.Service"); len(got) != 1 {
		t.Fatalf("order.Service 应 1 个实例: %v", got)
	}
	if got := reg.Discover("ghost.Service"); len(got) != 0 {
		t.Fatalf("未注册服务应返回空: %v", got)
	}
}

func TestTTLExpiry(t *testing.T) {
	reg := NewRegistry(150 * time.Millisecond) // 短 TTL 便于测试
	reg.Register("user.Service", "127.0.0.1:1")
	reg.Register("user.Service", "127.0.0.1:2")
	// 实例 1 持续心跳续约（50ms << TTL）；实例 2 从不续约 → 过期摘除
	hbStop := make(chan struct{})
	defer close(hbStop)
	go func() {
		ticker := time.NewTicker(50 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				reg.Heartbeat("user.Service", "127.0.0.1:1")
			case <-hbStop:
				return
			}
		}
	}()

	waitFor(t, 2*time.Second, func() bool {
		return len(reg.Discover("user.Service")) == 1
	}, "TTL 过期后应只剩 1 个实例")
	addrs := reg.Discover("user.Service")
	if addrs[0] != "127.0.0.1:1" {
		t.Fatalf("存活的应是续约的实例: %v", addrs)
	}
}

func TestHeartbeatKeepsAlive(t *testing.T) {
	reg := NewRegistry(200 * time.Millisecond)
	reg.Register("user.Service", "127.0.0.1:1")
	// 每 50ms 心跳一次（<< TTL），实例应长期存活
	stop := make(chan struct{})
	defer close(stop)
	go func() {
		ticker := time.NewTicker(50 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				reg.Heartbeat("user.Service", "127.0.0.1:1")
			case <-stop:
				return
			}
		}
	}()
	time.Sleep(700 * time.Millisecond) // 远大于 TTL，靠心跳续约撑住
	if addrs := reg.Discover("user.Service"); len(addrs) != 1 {
		t.Fatalf("持续心跳的实例不应被摘除: %v", addrs)
	}
}

func TestDeregister(t *testing.T) {
	reg := NewRegistry(time.Second)
	reg.Register("user.Service", "127.0.0.1:1")
	reg.Deregister("user.Service", "127.0.0.1:1")
	if addrs := reg.Discover("user.Service"); len(addrs) != 0 {
		t.Fatalf("Deregister 后应摘除: %v", addrs)
	}
	// 服务名下实例清空后，整个服务名也应消失
	if _, ok := reg.instances["user.Service"]; ok {
		t.Fatal("空服务名应被清理")
	}
}

// TestInstanceLifecycle 完整链路：实例上线 → 客户端按服务名调用 → 优雅下线 → 发现列表变化
func TestInstanceLifecycle(t *testing.T) {
	reg := NewRegistry(2 * time.Second)
	addr1, stop1, err := startInstance(reg, 100*time.Millisecond)
	if err != nil {
		t.Fatal(err)
	}
	_, stop2, err := startInstance(reg, 100*time.Millisecond)
	if err != nil {
		t.Fatal(err)
	}
	defer stop1()
	defer stop2()

	waitFor(t, 2*time.Second, func() bool {
		return len(reg.Discover("user.Service")) == 2
	}, "两个实例都应被发现")

	// 客户端按服务名拿地址，直连第一个实例调用
	client, err := jsonrpc.Dial("tcp", reg.Discover("user.Service")[0])
	if err != nil {
		t.Fatal(err)
	}
	var gr GetUserReply
	if err := client.Call("UserService.GetUser", &GetUserArgs{ID: 1}, &gr); err != nil {
		t.Fatalf("GetUser: %v", err)
	}
	if gr.User.Name != "alice" {
		t.Fatalf("name=%q, want alice", gr.User.Name)
	}
	client.Close()

	// 实例 2 优雅下线：注册表立即摘除，发现列表只剩实例 1
	stop2()
	waitFor(t, 2*time.Second, func() bool {
		addrs := reg.Discover("user.Service")
		return len(addrs) == 1 && strings.Contains(addrs[0], addr1)
	}, "实例 2 下线后只剩实例 1")
}
