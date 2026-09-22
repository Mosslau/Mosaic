// 来源：ph21-data-ingest-gateway exercises/sol-04-websocket-monitor/sol04_test.go
// 一句话说明：练习 4 验收测试——多会话收到顺序一致的状态流、入会即补最新快照
// （重连补齐）、断开会话被摘除不再广播、版本回退提交被拒、快照拷贝隔离。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"errors"
	"testing"
)

func drain(p *fakeSession, n int) []State {
	out := make([]State, 0, n)
	for i := 0; i < n; i++ {
		st, ok := p.Next()
		if !ok {
			break
		}
		out = append(out, st)
	}
	return out
}

func TestBroadcastToAllSubscribers(t *testing.T) {
	m := NewMonitor()
	p1 := newFakeSession("a")
	p2 := newFakeSession("b")
	m.Subscribe("src-001", p1)
	m.Subscribe("src-001", p2)
	for i := int64(1); i <= 3; i++ {
		if err := m.Apply(State{Source: "src-001", Version: i, Data: map[string]any{"value": float64(i) * 10}}); err != nil {
			t.Fatal(err)
		}
	}
	for _, p := range []*fakeSession{p1, p2} {
		got := drain(p, 3)
		if len(got) != 3 {
			t.Fatalf("%s 应收到 3 帧, got %d", p.Name(), len(got))
		}
		for i, st := range got {
			if st.Version != int64(i+1) {
				t.Errorf("%s 顺序错: 第 %d 帧版本 %d", p.Name(), i, st.Version)
			}
		}
	}
}

func TestReconnectCatchesUpToLatest(t *testing.T) {
	m := NewMonitor()
	p1 := newFakeSession("a")
	m.Subscribe("src-001", p1)
	for i := int64(1); i <= 3; i++ {
		_ = m.Apply(State{Source: "src-001", Version: i, Data: map[string]any{}})
	}
	// p1 断开后新面板订阅 → 应立即收到最新快照 v3（含入会快照）。
	p2 := newFakeSession("b")
	m.Subscribe("src-001", p2)
	st, ok := p2.Next()
	if !ok || st.Version != 3 {
		t.Fatalf("重连面板应补 v3, got v%d ok=%v", st.Version, ok)
	}
}

func TestClosedSessionRemoved(t *testing.T) {
	m := NewMonitor()
	p := newFakeSession("a")
	m.Subscribe("src-001", p)
	p.Close()
	// 断开后的广播：Send 报错 → 该会话被摘除；后续广播不再影响其他会话。
	if err := m.Apply(State{Source: "src-001", Version: 1, Data: map[string]any{}}); err != nil {
		t.Fatal(err)
	}
	if err := m.Apply(State{Source: "src-001", Version: 2, Data: map[string]any{}}); err != nil {
		t.Fatal(err)
	}
	m.mu.Lock()
	n := len(m.sessions["src-001"])
	m.mu.Unlock()
	if n != 0 {
		t.Errorf("断开会话应被摘除, 剩 %d", n)
	}
}

func TestStaleVersionRejected(t *testing.T) {
	m := NewMonitor()
	p := newFakeSession("a")
	m.Subscribe("src-001", p)
	_ = m.Apply(State{Source: "src-001", Version: 5, Data: map[string]any{}})
	err := m.Apply(State{Source: "src-001", Version: 4, Data: map[string]any{}}) // 回退
	if !errors.Is(err, ErrStaleVersion) {
		t.Fatalf("版本回退应 ErrStaleVersion, got %v", err)
	}
	// 广播侧不受影响：p 只收到 v5 一帧（Subscribe 无快照因为 v5 前没有）。
	if _, ok := p.Next(); !ok {
		t.Fatal("应有 v5 广播")
	}
	if _, ok := p.Next(); ok {
		t.Fatal("回退提交不应产生广播")
	}
}

func TestSnapshotCopyIsolated(t *testing.T) {
	m := NewMonitor()
	_ = m.Apply(State{Source: "src-001", Version: 1, Data: map[string]any{"value": 10.0}})
	snap, _ := m.Latest("src-001")
	snap.Data["value"] = 999.0 // 篡改快照副本
	again, _ := m.Latest("src-001")
	if again.Data["value"].(float64) != 10.0 {
		t.Error("Latest 应返回副本，调用方改写不得污染内部")
	}
}
