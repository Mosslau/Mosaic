// 来源：ph21-data-ingest-gateway exercises/sol-01-mqtt-agent-access/sol01_test.go
// 一句话说明：练习 1 验收测试——好 token 接入/坏 token 拒绝、订阅主题符合约定、
// 消息路由按 sourceID 回调、心跳超时判离线、主题解析边界。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"errors"
	"fmt"
	"testing"
	"time"
)

func newTestCore(timeout time.Duration) *AccessCore {
	return NewAccess(timeout, func(id, token string) bool { return token == "tok-"+id })
}

func TestAttachAuth(t *testing.T) {
	core := newTestCore(time.Second)
	if err := core.Attach("src-001", "tok-src-001", newMemTransport()); err != nil {
		t.Fatalf("合法采集端应接入: %v", err)
	}
	if err := core.Attach("src-001", "bad", newMemTransport()); !errors.Is(err, ErrUnauthorized) {
		t.Fatalf("坏 token 应 ErrUnauthorized, got %v", err)
	}
}

func TestRoutingAndSubscription(t *testing.T) {
	core := newTestCore(time.Second)
	mt := newMemTransport()
	if err := core.Attach("src-007", "tok-src-007", mt); err != nil {
		t.Fatal(err)
	}
	// 接入时应订阅了 ingest/src-007/metrics。
	if len(mt.subs) != 1 || mt.subs[0] != "ingest/src-007/metrics" {
		t.Fatalf("订阅不符合主题约定: %v", mt.subs)
	}
	received := make(chan string, 4)
	core.OnMetrics(func(sourceID string, payload []byte) {
		received <- fmt.Sprintf("%s:%s", sourceID, payload)
	})
	// 模拟 broker 投递两帧到该采集端订阅。
	mt.simulate("ingest/src-007/metrics", []byte(`{"seq":1}`))
	mt.simulate("ingest/src-007/metrics", []byte(`{"seq":2}`))
	for i := 1; i <= 2; i++ {
		select {
		case got := <-received:
			if got != fmt.Sprintf("src-007:{\"seq\":%d}", i) {
				t.Errorf("路由回调内容异常: %s", got)
			}
		case <-time.After(time.Second):
			t.Fatal("回调超时")
		}
	}
}

func TestHeartbeatTimeoutOffline(t *testing.T) {
	core := newTestCore(2 * time.Second)
	mt := newMemTransport()
	if err := core.Attach("src-001", "tok-src-001", mt); err != nil {
		t.Fatal(err)
	}
	// 推进所有采集端 lastSeen 到 3 秒前 → 超时判离线。
	core.mu.Lock()
	for _, s := range core.agents {
		s.lastSeen = time.Now().Add(-3 * time.Second)
	}
	core.mu.Unlock()
	down := core.CheckHeartbeats(time.Now())
	if len(down) != 1 || down[0] != "src-001" {
		t.Errorf("应判 src-001 离线, got %v", down)
	}
	if core.OnlineCount() != 0 {
		t.Error("离线后在线数应为 0")
	}
	// 判离线后旧连接不再复活：消息到达只刷新 lastSeen，不改变 online；
	// 恢复在线 = 采集端重连（重新 Attach，新会话）。
	mt.simulate("ingest/src-001/metrics", []byte(`{"seq":3}`))
	if core.OnlineCount() != 0 {
		t.Error("判离线后旧连接不应自行复活")
	}
	if err := core.Attach("src-001", "tok-src-001", newMemTransport()); err != nil {
		t.Fatalf("重连应成功: %v", err)
	}
	if core.OnlineCount() != 1 {
		t.Error("重连后应在线上")
	}
}

func TestSourceIDOfTopic(t *testing.T) {
	cases := map[string]string{
		"ingest/src-001/metrics": "src-001",
		"ingest/src-001/cmd":     "", // 非 metrics 不解析为指标 sourceID
		"oops/src-001/metrics":   "",
	}
	for topic, want := range cases {
		if got := sourceIDOfTopic(topic); got != want {
			t.Errorf("sourceIDOfTopic(%q) = %q, want %q", topic, got, want)
		}
	}
}
