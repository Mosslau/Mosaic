package device

// 弹性客户端的端到端集成测试：注册中心（进程内）+ 多个设备服务实例 + 网关客户端，
// 覆盖发现、轮询分摊、熔断打开/跳过、故障恢复四条链路。

import (
	"fmt"
	"net"
	"strings"
	"testing"
	"time"

	"tenetlang/go/ph11-microservice-rpc/project/internal/registry"
)

// testEnv 进程内起注册中心
type testEnv struct {
	regClient *registry.Client
	regStop   func()
}

func newTestEnv(t *testing.T, ttl time.Duration) *testEnv {
	t.Helper()
	regAddr, regStop, err := registry.ServeTCP("127.0.0.1:0", ttl)
	if err != nil {
		t.Fatal(err)
	}
	rc, err := registry.Dial(regAddr)
	if err != nil {
		regStop()
		t.Fatal(err)
	}
	return &testEnv{regClient: rc, regStop: regStop}
}

func (e *testEnv) close() { e.regClient.Close(); e.regStop() }

// registerDevice 起一个设备服务实例并注册到注册中心（含心跳）；
// 返回地址、服务对象、优雅停止（Deregister+停心跳+关监听）与"宕机"（只关监听，模拟崩溃）
func registerDevice(t *testing.T, rc *registry.Client, rate int64) (addr string, srv *Server, stop, kill func()) {
	t.Helper()
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	addr = lis.Addr().String()
	srv = NewServer(rate, time.Hour)
	go func() {
		for {
			conn, err := lis.Accept()
			if err != nil {
				return
			}
			go srv.ServeConn(conn)
		}
	}()
	if err := rc.Register(ServiceName, addr); err != nil {
		t.Fatal(err)
	}
	hbStop := make(chan struct{}) // 心跳每 100ms（<< TTL），保持存活
	go func() {
		ticker := time.NewTicker(100 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				_ = rc.Heartbeat(ServiceName, addr)
			case <-hbStop:
				return
			}
		}
	}()
	stop = func() {
		_ = rc.Deregister(ServiceName, addr)
		close(hbStop)
		lis.Close()
	}
	kill = func() { lis.Close() } // 模拟宕机：注册表仍认为存活（TTL 未到），但服务已不可达
	return addr, srv, stop, kill
}

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

// TestDiscoveryAndRoundRobin 两个实例 + 4 次上报 → 两实例各处理 2 次（轮询分摊）
func TestDiscoveryAndRoundRobin(t *testing.T) {
	env := newTestEnv(t, 5*time.Second)
	defer env.close()
	_, srvA, stopA, _ := registerDevice(t, env.regClient, 1000)
	_, srvB, stopB, _ := registerDevice(t, env.regClient, 1000)
	defer stopA()
	defer stopB()

	client := NewClient(env.regClient, time.Second, 1)
	waitFor(t, 2*time.Second, func() bool {
		return client.Refresh() == nil && len(client.breakers) == 2
	}, "应发现 2 个实例")

	for i := 0; i < 4; i++ {
		if err := client.Report(&Status{DeviceID: fmt.Sprintf("car-00%d", i+1), Speed: 60}); err != nil {
			t.Fatalf("Report #%d: %v", i+1, err)
		}
	}
	if srvA.ReportCount() != 2 || srvB.ReportCount() != 2 {
		t.Fatalf("轮询应分摊: A=%d B=%d", srvA.ReportCount(), srvB.ReportCount())
	}
}

// TestGetStatusThroughClient 经客户端查询设备状态
func TestGetStatusThroughClient(t *testing.T) {
	env := newTestEnv(t, 5*time.Second)
	defer env.close()
	_, _, stop, _ := registerDevice(t, env.regClient, 1000)
	defer stop()

	client := NewClient(env.regClient, time.Second, 1)
	waitFor(t, 2*time.Second, func() bool { return client.Refresh() == nil }, "应发现实例")

	if err := client.Report(&Status{DeviceID: "bus-01", Speed: 77}); err != nil {
		t.Fatal(err)
	}
	st, err := client.GetStatus("bus-01")
	if err != nil {
		t.Fatalf("GetStatus: %v", err)
	}
	if st.Speed != 77 {
		t.Fatalf("speed=%v, want 77", st.Speed)
	}
}

// TestBreakerOpensAndSkips 实例故障 → 连续失败熔断打开 → 调度跳过该实例 → 全部熔断时报错
func TestBreakerOpensAndSkips(t *testing.T) {
	env := newTestEnv(t, 10*time.Second) // 长 TTL：故障实例不因 TTL 被摘除，便于观察熔断
	defer env.close()
	addr, _, _, kill := registerDevice(t, env.regClient, 1000)

	client := NewClient(env.regClient, 200*time.Millisecond, 0) // 不重试，便于观察单次行为
	waitFor(t, 2*time.Second, func() bool { return client.Refresh() == nil }, "应发现实例")

	if err := client.Report(&Status{DeviceID: "car-001", Speed: 1}); err != nil {
		t.Fatalf("初始上报应成功: %v", err)
	}

	kill() // 模拟宕机：只关监听、不摘注册表（TTL 未到，注册表仍认为存活）→ 观察熔断而非发现为空

	// 连续失败 → 熔断打开（阈值 2）
	if err := client.Report(&Status{DeviceID: "car-001", Speed: 1}); err == nil {
		t.Fatal("实例故障后上报应失败")
	}
	if err := client.Report(&Status{DeviceID: "car-001", Speed: 1}); err == nil {
		t.Fatal("实例故障后上报应失败")
	}
	if b := client.breakers[addr]; b == nil || b.State() != "open" {
		t.Fatalf("熔断应打开, state=%v", b.State())
	}
	// 打开后：快速失败（Allow 拒绝放行），不再发网络调用
	err := client.Report(&Status{DeviceID: "car-001", Speed: 1})
	if err == nil || !strings.Contains(err.Error(), "熔断开启") {
		t.Fatalf("打开后应快速失败, got %v", err)
	}
}

// TestBreakerRecovery 实例重启（同地址）→ 冷却后半开探针成功 → 恢复 closed
func TestBreakerRecovery(t *testing.T) {
	env := newTestEnv(t, 10*time.Second)
	defer env.close()

	// 先占一个空闲端口：保证"重启"用同一地址
	free, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	addr := free.Addr().String()
	free.Close()

	lis, err := net.Listen("tcp", addr)
	if err != nil {
		t.Fatal(err)
	}
	srv := NewServer(1000, time.Hour)
	go func() {
		for {
			conn, err := lis.Accept()
			if err != nil {
				return
			}
			go srv.ServeConn(conn)
		}
	}()
	if err := env.regClient.Register(ServiceName, addr); err != nil {
		t.Fatal(err)
	}

	client := NewClient(env.regClient, 200*time.Millisecond, 0)
	waitFor(t, 2*time.Second, func() bool { return client.Refresh() == nil }, "应发现实例")
	if err := client.Report(&Status{DeviceID: "car-001", Speed: 1}); err != nil {
		t.Fatalf("初始上报应成功: %v", err)
	}

	lis.Close() // 实例宕机（注册表仍认为存活，TTL 未到）

	if err := client.Report(&Status{DeviceID: "car-001", Speed: 1}); err == nil {
		t.Fatal("宕机后应失败")
	}
	if err := client.Report(&Status{DeviceID: "car-001", Speed: 1}); err == nil {
		t.Fatal("宕机后应失败")
	}
	if b := client.breakers[addr]; b.State() != "open" {
		t.Fatalf("应已熔断, got %s", b.State())
	}

	// 同地址重启（新服务实例）
	lis2, err := net.Listen("tcp", addr)
	if err != nil {
		t.Fatalf("同地址重启失败: %v", err)
	}
	defer lis2.Close()
	srv2 := NewServer(1000, time.Hour)
	go func() {
		for {
			conn, err := lis2.Accept()
			if err != nil {
				return
			}
			go srv2.ServeConn(conn)
		}
	}()

	// 冷却期（500ms）后半开探针成功 → closed → 上报恢复
	waitFor(t, 3*time.Second, func() bool {
		err := client.Report(&Status{DeviceID: "car-002", Speed: 2})
		return err == nil && client.breakers[addr].State() == "closed"
	}, "重启后应恢复上报且熔断关闭")
}

// TestRateLimitedRetriesAnotherInstance 限流是"忙"不是"故障"：换实例重试可成功
func TestRateLimitedRetriesAnotherInstance(t *testing.T) {
	env := newTestEnv(t, 5*time.Second)
	defer env.close()
	busyAddr, _, stopBusy, _ := registerDevice(t, env.regClient, 1)   // 桶只 1 个令牌、不补满
	_, srvFree, stopFree, _ := registerDevice(t, env.regClient, 1000) // 不限流
	defer stopBusy()
	defer stopFree()

	// 先直连 busy 实例消耗它唯一的令牌：之后它的所有上报都会被限流
	raw, err := newRPCClient(busyAddr)
	if err != nil {
		t.Fatal(err)
	}
	if err := raw.Call(MethodReport, &ReportArgs{Status: Status{DeviceID: "drain", Speed: 1}}, &ReportReply{}); err != nil {
		t.Fatalf("drain: %v", err)
	}
	raw.Close()

	client := NewClient(env.regClient, time.Second, 2)
	waitFor(t, 2*time.Second, func() bool {
		return client.Refresh() == nil && len(client.breakers) == 2
	}, "应发现 2 个实例")

	if err := client.Report(&Status{DeviceID: "car-001", Speed: 1}); err != nil {
		t.Fatalf("限流实例应换实例重试成功: %v", err)
	}
	// busy 实例被限流不计数为熔断失败（服务健康，只是忙）
	if b := client.breakers[busyAddr]; b != nil && b.State() == "open" {
		t.Fatal("限流不应触发熔断")
	}
	if srvFree.ReportCount() == 0 {
		t.Fatal("重试应打到了空闲实例")
	}
}

// TestGetAllFanOut 两个实例各自收到不同设备的上报 → GetAll 汇总出全部有记录的实例
func TestGetAllFanOut(t *testing.T) {
	env := newTestEnv(t, 5*time.Second)
	defer env.close()
	_, _, stopA, _ := registerDevice(t, env.regClient, 1000)
	_, _, stopB, _ := registerDevice(t, env.regClient, 1000)
	defer stopA()
	defer stopB()

	client := NewClient(env.regClient, time.Second, 1)
	waitFor(t, 2*time.Second, func() bool {
		return client.Refresh() == nil && len(client.breakers) == 2
	}, "应发现 2 个实例")

	// 连续上报 3 次，让两个实例都收到 car-001（轮询分摊）
	for i := 0; i < 3; i++ {
		if err := client.Report(&Status{DeviceID: "car-001", Speed: float64(50 + i)}); err != nil {
			t.Fatalf("Report #%d: %v", i+1, err)
		}
	}
	results, err := client.GetAll("car-001")
	if err != nil {
		t.Fatalf("GetAll: %v", err)
	}
	// 两个实例都应该有 car-001 的记录（3 次上报轮询分摊到 2 个实例）
	if len(results) != 2 {
		t.Fatalf("GetAll 应汇总 2 个实例, got %d: %+v", len(results), results)
	}
}

// TestGetAllNotFound 设备从未上报 → ErrNotFound
func TestGetAllNotFound(t *testing.T) {
	env := newTestEnv(t, 5*time.Second)
	defer env.close()
	_, _, stop, _ := registerDevice(t, env.regClient, 1000)
	defer stop()

	client := NewClient(env.regClient, time.Second, 1)
	waitFor(t, 2*time.Second, func() bool { return client.Refresh() == nil }, "应发现实例")
	if _, err := client.GetAll("ghost"); err == nil {
		t.Fatal("无记录设备应返回 ErrNotFound")
	}
}
