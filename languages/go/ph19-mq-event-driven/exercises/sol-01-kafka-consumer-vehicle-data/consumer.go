// 来源：ph19-mq-event-driven exercises/sol-01-kafka-consumer-vehicle-data（练习 1 参考实现）
// 一句话说明：按车聚合的消费统计 store + 组消费循环。store 用锁保护是因为组内
// 各成员并行消费不同分区、共享同一张统计表（golang-patterns：并发共享用 Mutex）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"fmt"
	"sync"
)

// VehicleStats 单辆车的消费统计。
type VehicleStats struct {
	VehicleID string
	Samples   int
	LastTS    int64
	MaxSpeed  float64
}

// StatsStore 线程安全的按车聚合（模拟下游时序/聚合写入）。
type StatsStore struct {
	mu    sync.Mutex
	stats map[string]*VehicleStats
}

// NewStatsStore 建空统计表。
func NewStatsStore() *StatsStore {
	return &StatsStore{stats: make(map[string]*VehicleStats)}
}

// Apply 处理一条遥测：更新统计。
func (s *StatsStore) Apply(t Telemetry) {
	s.mu.Lock()
	defer s.mu.Unlock()
	v, ok := s.stats[t.VehicleID]
	if !ok {
		v = &VehicleStats{VehicleID: t.VehicleID}
		s.stats[t.VehicleID] = v
	}
	v.Samples++
	if t.TS > v.LastTS {
		v.LastTS = t.TS
	}
	if t.Speed > v.MaxSpeed {
		v.MaxSpeed = t.Speed
	}
}

// Snapshot 返回全部统计的拷贝（打印/断言用，调用方可安全读）。
func (s *StatsStore) Snapshot() map[string]VehicleStats {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make(map[string]VehicleStats, len(s.stats))
	for k, v := range s.stats {
		out[k] = *v
	}
	return out
}

// handle 处理一条原始消息：解码失败按错误返回（真实 Kafka 场景解码失败属
// 毒消息、应进 DLQ——错误分类与死信见 examples/ex03 与练习 4 的 sol-04）。
func handle(raw []byte, store *StatsStore) error {
	var t Telemetry
	if err := json.Unmarshal(raw, &t); err != nil {
		return fmt.Errorf("decode telemetry: %w", err)
	}
	store.Apply(t)
	return nil
}

// DrainGroup 组内成员并行消费到各自分区追平为止（离线模拟"跑一轮"）：
// 每个成员只碰自己分配到的分区、逐条 handle、逐条提交。
// 返回 (每成员处理条数, 首个错误)。并发实现用 WaitGroup + 有缓冲错误通道，
// 不忽略错误——任何解码失败都会浮上来。
func DrainGroup(t *Topic, g *Group, members []string, store *StatsStore) (map[string]int, error) {
	counts := make(map[string]int, len(members))
	var mu sync.Mutex
	errCh := make(chan error, len(members))
	var wg sync.WaitGroup
	assign := AssignPartitions(t.NumPartitions(), members)
	for _, m := range members {
		m, parts := m, assign[m]
		wg.Add(1)
		go func() {
			defer wg.Done()
			total := 0
			for _, p := range parts {
				for _, rec := range t.PartitionAt(p).Slice(g.Committed(p)) {
					if err := handle(rec.Payload, store); err != nil {
						errCh <- fmt.Errorf("member %s partition %d offset %d: %w", m, p, rec.Offset, err)
						return
					}
					g.Commit(p, rec.Offset+1)
					total++
				}
			}
			mu.Lock()
			counts[m] = total
			mu.Unlock()
		}()
	}
	wg.Wait()
	close(errCh)
	for err := range errCh {
		return nil, err
	}
	return counts, nil
}
