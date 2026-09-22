// 来源：ph21-data-ingest-gateway exercises/sol-04-websocket-monitor/sol04.go
// 一句话说明：练习 4 参考实现——WebSocket 实时监控面板的广播核心：车辆状态带
// 单调版本号，每次变更广播给所有订阅会话；版本回退被拒；新会话入会先收当前快照
// （断线重连的补齐语义）。会话抽象为接口，假会话离线可测（主文档 3.4/3.6/4.2）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"errors"
	"fmt"
	"sync"
)

// ErrStaleVersion 版本回退（≤ 已见版本）拒绝。
var ErrStaleVersion = errors.New("monitor: stale version")

// State 一次车辆状态广播（version 单调递增）。
type State struct {
	Vehicle string
	Version int64
	Data    map[string]any
}

// Session 一个面板会话。真实 WebSocket 会话实现 Send/Close；测试用假会话。
type Session interface {
	// Send 推送一帧状态。会话断开/不可写时返回错误（由广播器摘除）。
	Send(State) error
	Close()
}

// Monitor 广播核心：每车保存最新快照 + 订阅会话集合。
type Monitor struct {
	mu       sync.Mutex
	latest   map[string]*State // vehicle → 最新快照（断线重连补齐）
	sessions map[string]map[Session]struct{}
}

// NewMonitor 建广播核心。
func NewMonitor() *Monitor {
	return &Monitor{
		latest:   map[string]*State{},
		sessions: map[string]map[Session]struct{}{},
	}
}

// Subscribe 面板订阅某车：立即推送当前快照（若有），之后持续接收变更。
func (m *Monitor) Subscribe(vehicle string, s Session) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.sessions[vehicle] == nil {
		m.sessions[vehicle] = map[Session]struct{}{}
	}
	m.sessions[vehicle][s] = struct{}{}
	if snap := m.latest[vehicle]; snap != nil {
		_ = s.Send(*snap) // 入会即补最新态：断开期间的状态一条不丢
	}
}

// Unsubscribe 面板退订。
func (m *Monitor) Unsubscribe(vehicle string, s Session) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if set, ok := m.sessions[vehicle]; ok {
		delete(set, s)
	}
}

// Apply 平台侧状态更新：版本必须比该车已见版本新（回退拒绝），否则 ErrStaleVersion。
// 生效后广播给所有订阅会话；发送失败的会话被摘除（断开）。
func (m *Monitor) Apply(st State) error {
	m.mu.Lock()
	cur := m.latest[st.Vehicle]
	if cur != nil && st.Version <= cur.Version {
		m.mu.Unlock()
		return fmt.Errorf("%w: vehicle=%s version=%d <= %d", ErrStaleVersion, st.Vehicle, st.Version, cur.Version)
	}
	cp := st
	cp.Data = cloneMap(st.Data)
	m.latest[st.Vehicle] = &cp
	subs := make([]Session, 0, len(m.sessions[st.Vehicle]))
	for s := range m.sessions[st.Vehicle] {
		subs = append(subs, s)
	}
	m.mu.Unlock()

	// 广播在锁外执行：慢会话不阻塞其他面板的推送。
	for _, s := range subs {
		if err := s.Send(cp); err != nil {
			m.Unsubscribe(st.Vehicle, s) // 断开的会话摘除，等待它重连重新 Subscribe
		}
	}
	return nil
}

// Latest 某车最新快照（供演示与运维查询）。
func (m *Monitor) Latest(vehicle string) (*State, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	st, ok := m.latest[vehicle]
	if !ok {
		return nil, false
	}
	cp := *st
	cp.Data = cloneMap(st.Data)
	return &cp, true
}

func cloneMap(in map[string]any) map[string]any {
	out := make(map[string]any, len(in))
	for k, v := range in {
		out[k] = v
	}
	return out
}

// ---------- 假会话（测试/演示用，真环境换成 WebSocket 连接实现同一接口） ----------

// fakeSession 内存会话：Send 投递到 channel；closed=true 后 Send 报错（模拟断线）。
type fakeSession struct {
	name     string
	inbox    chan State
	closed   bool
	closedMu sync.Mutex
}

func newFakeSession(name string) *fakeSession {
	return &fakeSession{name: name, inbox: make(chan State, 32)}
}

func (f *fakeSession) Send(st State) error {
	f.closedMu.Lock()
	defer f.closedMu.Unlock()
	if f.closed {
		return errors.New("session closed")
	}
	f.inbox <- st
	return nil
}

func (f *fakeSession) Close() {
	f.closedMu.Lock()
	f.closed = true
	f.closedMu.Unlock()
}

// Next 取出下一帧（测试用；Apply 同步广播完成即可读，用非阻塞取保证断言不挂起）。
func (f *fakeSession) Next() (State, bool) {
	select {
	case st := <-f.inbox:
		return st, true
	default:
		return State{}, false
	}
}

func (f *fakeSession) Name() string { return f.name }
