package registry

import (
	"strings"
	"testing"
	"time"
)

func TestRegisterDiscover(t *testing.T) {
	r := New(time.Second)
	r.Register("device.Service", "127.0.0.1:1")
	r.Register("device.Service", "127.0.0.1:2")
	r.Register("order.Service", "127.0.0.1:3")

	addrs := r.Discover("device.Service")
	if len(addrs) != 2 || addrs[0] != "127.0.0.1:1" || addrs[1] != "127.0.0.1:2" {
		t.Fatalf("Discover 异常: %v", addrs)
	}
	if got := r.Discover("ghost.Service"); len(got) != 0 {
		t.Fatalf("未注册服务应返回空: %v", got)
	}
}

func TestTTLExpiry(t *testing.T) {
	r := New(100 * time.Millisecond)
	r.Register("device.Service", "127.0.0.1:1")
	r.Register("device.Service", "127.0.0.1:2")
	hbStop := make(chan struct{})
	defer close(hbStop)
	go func() { // 只给 1 续约
		ticker := time.NewTicker(30 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				r.Heartbeat("device.Service", "127.0.0.1:1")
			case <-hbStop:
				return
			}
		}
	}()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if addrs := r.Discover("device.Service"); len(addrs) == 1 && addrs[0] == "127.0.0.1:1" {
			return // 实例 2 已被 TTL 摘除，实例 1 靠心跳存活
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal("TTL 过期后应只剩续约的实例 1")
}

func TestDeregister(t *testing.T) {
	r := New(time.Second)
	r.Register("device.Service", "127.0.0.1:1")
	r.Deregister("device.Service", "127.0.0.1:1")
	if r.Count("device.Service") != 0 {
		t.Fatal("Deregister 后应摘除")
	}
}

// TestRPCService 注册中心作为 RPC 服务的完整往返（cmd/registry 的进程内版）
func TestRPCService(t *testing.T) {
	addr, stop, err := ServeTCP("127.0.0.1:0", 5*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer stop()

	c, err := Dial(addr)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()

	if err := c.Register("device.Service", "127.0.0.1:5201"); err != nil {
		t.Fatal(err)
	}
	if err := c.Register("device.Service", "127.0.0.1:5202"); err != nil {
		t.Fatal(err)
	}
	if err := c.Heartbeat("device.Service", "127.0.0.1:5201"); err != nil {
		t.Fatal(err)
	}
	addrs, err := c.Discover("device.Service")
	if err != nil {
		t.Fatal(err)
	}
	if len(addrs) != 2 || !strings.Contains(addrs[0], "5201") {
		t.Fatalf("Discover 经 RPC 结果异常: %v", addrs)
	}
	if err := c.Deregister("device.Service", "127.0.0.1:5202"); err != nil {
		t.Fatal(err)
	}
	addrs, _ = c.Discover("device.Service")
	if len(addrs) != 1 {
		t.Fatalf("Deregister 经 RPC 后应剩 1 个: %v", addrs)
	}
}
