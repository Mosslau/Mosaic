// 来源：ph19-mq-event-driven project/internal/store/store.go
// 一句话说明：消费侧状态落地——每车快照（时序表一行）+ 有界幂等窗口（MsgID 去重）
// + 死信台账。三者的组合回答 roadmap 必会概念 1/4：at-least-once 投递下的幂等、
// 事件按 schema 版本解码后的可靠落库与失败留证。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package store

import (
	"sync"

	"tenetlang/go/ph19-mq-event-driven/project/internal/model"
)

// VehicleState 单辆车的最新快照 + 统计（模拟时序/状态库的一行）。
type VehicleState struct {
	VehicleID string
	Samples   int   // 已生效唯一事件数（重复投递不重复计数）
	Overspeed int   // 超速(>=120km/h)采样数
	LastTS    int64 // 最近采样时刻
	LastSpeed float64
}

// SnapshotStore 每车快照表。Apply 与只读查询均加锁（消费者组内可多成员并发）。
type SnapshotStore struct {
	mu   sync.Mutex
	byID map[string]*VehicleState
}

// NewSnapshotStore 建空快照表。
func NewSnapshotStore() *SnapshotStore {
	return &SnapshotStore{byID: make(map[string]*VehicleState)}
}

// Apply 合并一条已通过幂等检查的事件到快照（副作用入口，只被消费端调用一次/键）。
func (s *SnapshotStore) Apply(e model.TelemetryEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	v, ok := s.byID[e.VehicleID]
	if !ok {
		v = &VehicleState{VehicleID: e.VehicleID}
		s.byID[e.VehicleID] = v
	}
	v.Samples++
	if e.Speed >= 120 {
		v.Overspeed++
	}
	if e.TS > v.LastTS {
		v.LastTS = e.TS
		v.LastSpeed = e.Speed
	}
}

// State 读单辆车快照。
func (s *SnapshotStore) State(vehicleID string) (VehicleState, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	v, ok := s.byID[vehicleID]
	if !ok {
		return VehicleState{}, false
	}
	return *v, true
}

// Vehicles 返回全部快照副本（排序由调用方负责）。
func (s *SnapshotStore) Vehicles() map[string]VehicleState {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make(map[string]VehicleState, len(s.byID))
	for id, v := range s.byID {
		out[id] = *v
	}
	return out
}

// SeenWindow 有界幂等窗口（按 MsgID 记"已生效"，容量受限时淘汰最旧）。
// 真实工程此表落在 Redis/DB（带 TTL）；离线形态用进程内存 + FIFO 容量，
// 语义一致：窗口内重复投递 → 跳过副作用（主文档 3.5）。
type SeenWindow struct {
	mu    sync.Mutex
	max   int
	order []string
	seen  map[string]struct{}
}

// NewSeenWindow 建窗口，最多记住 max 个键。
func NewSeenWindow(max int) *SeenWindow {
	if max <= 0 {
		max = 1 << 30
	}
	return &SeenWindow{max: max, seen: make(map[string]struct{})}
}

// Seen 报告 MsgID 是否已在窗口内。
func (w *SeenWindow) Seen(id string) bool {
	w.mu.Lock()
	defer w.mu.Unlock()
	_, ok := w.seen[id]
	return ok
}

// Mark 记录 MsgID 已生效；超容量淘汰最旧。
func (w *SeenWindow) Mark(id string) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if _, ok := w.seen[id]; ok {
		return
	}
	w.seen[id] = struct{}{}
	w.order = append(w.order, id)
	for len(w.order) > w.max {
		delete(w.seen, w.order[0])
		w.order = w.order[1:]
	}
}

// DeadEntry 一条死信：原因分类 + 原始消息信息 + 已尝试次数。
type DeadEntry struct {
	MsgID     string
	VehicleID string
	Reason    string // poison-decode / poison-schema / exhausted
	Attempts  int
}

// DeadLog 死信台账（线程安全）。真实工程死信落在专门 topic/表供补偿任务重放。
type DeadLog struct {
	mu    sync.Mutex
	items []DeadEntry
}

// NewDeadLog 建空台账。
func NewDeadLog() *DeadLog { return &DeadLog{} }

// Add 记一条死信。
func (d *DeadLog) Add(e DeadEntry) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.items = append(d.items, e)
}

// Len 死信条数。
func (d *DeadLog) Len() int {
	d.mu.Lock()
	defer d.mu.Unlock()
	return len(d.items)
}

// Entries 返回死信副本。
func (d *DeadLog) Entries() []DeadEntry {
	d.mu.Lock()
	defer d.mu.Unlock()
	return append([]DeadEntry(nil), d.items...)
}
