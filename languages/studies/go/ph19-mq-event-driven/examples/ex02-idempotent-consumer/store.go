// 来源：ph19-mq-event-driven examples/ex02-idempotent-consumer/store.go
// 一句话说明：副作用落地目标——按设备保存"最新快照 + 已生效采样计数"。
// 演示目的：若重复事件漏网被二次 Apply，Samples 会被重复累加、统计失真；
// 幂等消费把重复挡在外面，这里只能看到"真正生效过的每次采样"。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "sync"

// DeviceSnapshot 设备的最新遥测快照。
type DeviceSnapshot struct {
	DeviceID string
	LastTS    int64
	LastSpeed float64
	Samples   int // 已生效采样计数：重复投递不应让它变多
}

// SnapshotStore 每设备快照表（模拟时序库/状态表的一行；按设备有序写入时 TS 单调）。
type SnapshotStore struct {
	mu   sync.Mutex
	byID map[string]DeviceSnapshot
}

// NewSnapshotStore 建一个空快照表。
func NewSnapshotStore() *SnapshotStore {
	return &SnapshotStore{byID: make(map[string]DeviceSnapshot)}
}

// Apply 把一条事件合并进快照：TS 更新（>= 才覆盖，防止乱序旧数据回退状态），
// Samples 计数 +1。真实工程里这里是一次有副作用的事务（写 DB/调下游）。
func (s *SnapshotStore) Apply(e TelemetryEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	cur := s.byID[e.DeviceID]
	cur.DeviceID = e.DeviceID
	if e.TS >= cur.LastTS {
		cur.LastTS = e.TS
		cur.LastSpeed = e.Speed
	}
	cur.Samples++
	s.byID[e.DeviceID] = cur
}

// Get 读单台设备的快照。
func (s *SnapshotStore) Get(deviceID string) (DeviceSnapshot, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	v, ok := s.byID[deviceID]
	return v, ok
}
