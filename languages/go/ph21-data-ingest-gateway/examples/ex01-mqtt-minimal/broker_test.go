// 来源：ph21-data-ingest-gateway examples/ex01-mqtt-minimal/broker_test.go
// 一句话说明：broker + client 的真 TCP 集成测试——鉴权放行/拒绝、订阅→发布→路由
// （含通配符命中）、心跳保活。127.0.0.1 真实端口上跑通即证明协议级自研可用。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"
)

func startBroker(t *testing.T, auth AuthFunc) *Broker {
	t.Helper()
	b, err := NewBroker("127.0.0.1:0", auth)
	if err != nil {
		t.Fatalf("NewBroker: %v", err)
	}
	b.Start()
	t.Cleanup(b.Stop)
	return b
}

func testClient(t *testing.T, broker *Broker, id, token string) *Client {
	t.Helper()
	c := NewClient(ClientOptions{
		Broker: broker.Addr().String(), ClientID: id,
		Username: id, Password: token, KeepAlive: time.Second,
	})
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if err := c.Connect(ctx); err != nil {
		t.Fatalf("%s Connect: %v", id, err)
	}
	t.Cleanup(func() { _ = c.Close() })
	return c
}

func TestAuthAllowsKnownRejectsUnknown(t *testing.T) {
	b := startBroker(t, func(u, p string) bool { return u == "veh-001" && p == "tok-1" })

	// 好设备：鉴权通过
	good := testClient(t, b, "veh-001", "tok-1")
	if good == nil {
		t.Fatal("合法设备应接入成功")
	}
	// 坏 token / 未知设备：返回 ErrNotAuthorized
	for _, tc := range []struct{ id, token string }{
		{"veh-001", "wrong"}, // 好设备坏 token
		{"veh-999", "tok-1"}, // 未知设备
	} {
		bad := NewClient(ClientOptions{Broker: b.Addr().String(), ClientID: tc.id, Username: tc.id, Password: tc.token})
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		err := bad.Connect(ctx)
		cancel()
		if !errors.Is(err, ErrNotAuthorized) {
			t.Errorf("设备 %s token %q 应被拒（ErrNotAuthorized），got %v", tc.id, tc.token, err)
		}
	}
}

func TestPublishSubscribeRoundTrip(t *testing.T) {
	b := startBroker(t, nil) // 无鉴权：只测路由
	sub := testClient(t, b, "sub-1", "x")
	got := make(chan string, 4)
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if err := sub.Subscribe(ctx, "veh/veh-001/telemetry", func(_ string, payload []byte) {
		got <- string(payload)
	}); err != nil {
		t.Fatalf("订阅: %v", err)
	}

	// 发布者（独立连接）发两帧 → 订阅者按序收两帧（单连接 FIFO，序号可断言）。
	pub := testClient(t, b, "pub-1", "x")
	if err := pub.Publish("veh/veh-001/telemetry", []byte(`{"seq":1,"speed":40}`)); err != nil {
		t.Fatalf("Publish: %v", err)
	}
	if err := pub.Publish("veh/veh-001/telemetry", []byte(`{"seq":2,"speed":45}`)); err != nil {
		t.Fatalf("Publish: %v", err)
	}
	for i, want := range []string{`"seq":1`, `"seq":2`} {
		select {
		case m := <-got:
			if !strings.Contains(m, want) {
				t.Errorf("第 %d 帧收到 %s, want 含 %s", i+1, m, want)
			}
		case <-ctx.Done():
			t.Fatal("等待路由消息超时")
		}
	}
}

func TestWildcardRouting(t *testing.T) {
	b := startBroker(t, nil)
	a := testClient(t, b, "a", "x")  // 订阅 veh/+/telemetry（单层通配）
	c1 := testClient(t, b, "c", "x") // 订阅 veh/#（多层通配）
	gotA := make(chan string, 4)
	gotC := make(chan string, 4)
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if err := a.Subscribe(ctx, "veh/+/telemetry", func(_ string, p []byte) { gotA <- string(p) }); err != nil {
		t.Fatal(err)
	}
	if err := c1.Subscribe(ctx, "veh/#", func(_ string, p []byte) { gotC <- string(p) }); err != nil {
		t.Fatal(err)
	}
	pub := testClient(t, b, "pub", "x")
	if err := pub.Publish("veh/veh-001/telemetry", []byte("speed-66")); err != nil {
		t.Fatal(err)
	}
	if err := pub.Publish("veh/veh-001/cmd/ack", []byte("ack-7")); err != nil { // 只命中 veh/#
		t.Fatal(err)
	}
	select {
	case m := <-gotA:
		if m != "speed-66" {
			t.Errorf("A 收到 %q", m)
		}
	case <-ctx.Done():
		t.Fatal("A 未收到遥测")
	}
	for _, want := range []string{"speed-66", "ack-7"} {
		select {
		case m := <-gotC:
			if m != want {
				t.Errorf("C 收到 %q, want %q", m, want)
			}
		case <-ctx.Done():
			t.Fatal("C 未收全消息")
		}
	}
}

func TestKeepAliveKeepsConnectionAlive(t *testing.T) {
	b := startBroker(t, nil)
	c := NewClient(ClientOptions{
		Broker: b.Addr().String(), ClientID: "ka-1",
		Username: "ka-1", Password: "x", KeepAlive: 200 * time.Millisecond,
	})
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if err := c.Connect(ctx); err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	got := make(chan string, 2)
	if err := c.Subscribe(ctx, "ping/topic", func(_ string, p []byte) { got <- string(p) }); err != nil {
		t.Fatal(err)
	}
	// 跨多个 keepalive 周期后仍能正常收发 → 心跳循环没让连接死掉。
	time.Sleep(650 * time.Millisecond)
	if err := c.Publish("ping/topic", []byte("alive")); err != nil {
		t.Fatalf("keepalive 后发布失败: %v", err)
	}
	select {
	case m := <-got:
		if m != "alive" {
			t.Errorf("收到 %q", m)
		}
	case <-ctx.Done():
		t.Fatal("keepalive 后连接已不可用")
	}
}
