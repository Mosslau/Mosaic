// 来源：ph19-mq-event-driven examples/ex06-backlog-watch/backlog.go
// 一句话说明：积压水位（consumer lag）的观测器——消费者组的健康指标是
// "partition 高水位(HW) − 组已提交 offset"，即每个分区还有多少条没被处理。
// 监控脚本周期性采样，越过告警阈值就触发（边沿触发，恢复后重新武装）。
// 真实工具（Kafka 的 consumer lag 指标 / Prometheus exporter）做的正是这件事
// （主文档 3.7 积压处理与监控）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "sync"

// PartitionLag 单个分区的水位快照：Lag = HighWater(已生产) - Committed(已提交)。
type PartitionLag struct {
	Partition int
	HighWater int // 分区高水位：已写入的消息条数（offset 天花板）
	Committed int // 组已提交 offset：处理成功的下一条位置
	Lag       int // 积压：HighWater - Committed，>=0
}

// Snapshot 一次采样：所有分区那一刻的水位。
type Snapshot struct {
	Step       int
	Partitions []PartitionLag
	TotalLag   int
}

// Alert 一次越过阈值的告警（边沿触发：进警戒线报一次，恢复前不重复报）。
type Alert struct {
	Step      int
	Partition int
	Lag       int
}

// Watcher 积压水位观测器（线程安全，供监控采集 goroutine 与业务并行）。
type Watcher struct {
	warn    int // 告警阈值：单分区 lag >= warn 触发
	mu      sync.Mutex
	history []Snapshot
	alerts  []Alert
	armed   map[int]bool // partition 是否处于"已告警待恢复"状态
}

// NewWatcher 建观测器，warn 为单分区告警阈值（<=0 表示不告警）。
func NewWatcher(warn int) *Watcher {
	return &Watcher{warn: warn, armed: make(map[int]bool)}
}

// Observe 采样一次：给定高水位与已提交序列，计算各分区 lag 并判定告警边沿。
// produced[i]/committed[i] 分别来自 broker 元数据与消费者组的提交记录。
func (w *Watcher) Observe(step int, produced, committed []int) Snapshot {
	w.mu.Lock()
	defer w.mu.Unlock()

	var snap Snapshot
	snap.Step = step
	snap.Partitions = make([]PartitionLag, 0, len(produced))
	for i := range produced {
		lag := produced[i] - committed[i]
		if lag < 0 {
			lag = 0 // 防御：提交超过高水位属异常状态，按 0 处理
		}
		pl := PartitionLag{Partition: i, HighWater: produced[i], Committed: committed[i], Lag: lag}
		snap.Partitions = append(snap.Partitions, pl)
		snap.TotalLag += lag

		// 边沿触发告警：lag 从 <warn 升到 >=warn 时报一次；降回 <warn 才重武装。
		if w.warn > 0 {
			if lag >= w.warn && !w.armed[i] {
				w.alerts = append(w.alerts, Alert{Step: step, Partition: i, Lag: lag})
				w.armed[i] = true
			} else if lag < w.warn && w.armed[i] {
				w.armed[i] = false
			}
		}
	}
	w.history = append(w.history, snap)
	return snap
}

// Alerts 已触发告警列表（按时间序）。
func (w *Watcher) Alerts() []Alert {
	w.mu.Lock()
	defer w.mu.Unlock()
	return append([]Alert(nil), w.alerts...)
}

// LastSnapshot 最近一次采样的水位（运维/API 查询用）。
func (w *Watcher) LastSnapshot() (Snapshot, bool) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if len(w.history) == 0 {
		return Snapshot{}, false
	}
	return w.history[len(w.history)-1], true
}
