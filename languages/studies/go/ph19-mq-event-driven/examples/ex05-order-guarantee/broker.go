// 来源：ph19-mq-event-driven examples/ex05-order-guarantee/broker.go
// 一句话说明：同一消息队列上"分区选择策略"是顺序性成败的分水岭：
// 稳定 key 散列 → 同 key 同分区 → 分区内有序；把 key 换来换去（如按时间/随机
// 取模）→ 同 key 散落多分区 → 全局消费顺序被打乱（主文档 3.4 顺序性保证）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"hash/fnv"
	"sync"
)

// Record 一条消息（保留 key，便于按 key 抽子序列验证顺序）。
type Record struct {
	Key   string
	Value string
}

// Partition 有序日志。
type Partition struct {
	mu      sync.Mutex
	records []Record
}

// Append 追加并返回 offset。
func (p *Partition) Append(key, value string) int {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.records = append(p.records, Record{Key: key, Value: value})
	return len(p.records) - 1
}

// All 返回分区内全部记录（副本）。
func (p *Partition) All() []Record {
	p.mu.Lock()
	defer p.mu.Unlock()
	return append([]Record(nil), p.records...)
}

// Broker 一个 N 分区的 topic。
type Broker struct {
	partitions []*Partition
	// round 是"轮询分区"策略的内部计数器（演示用；同一 key 会被分到不同分区）。
	round int
}

// NewBroker 建 N 分区 topic。
func NewBroker(n int) *Broker {
	b := &Broker{partitions: make([]*Partition, n)}
	for i := range b.partitions {
		b.partitions[i] = &Partition{}
	}
	return b
}

// NumPartitions 分区数。
func (b *Broker) NumPartitions() int { return len(b.partitions) }

// PartitionAt 取分区。
func (b *Broker) PartitionAt(i int) *Partition { return b.partitions[i] }

// ProduceStable 稳定 key 散列：同一 key 永远进同一分区（顺序性的正确姿势）。
func (b *Broker) ProduceStable(key, value string) int {
	p := StablePartition(key, b.NumPartitions())
	return b.partitions[p].Append(key, value)
}

// ProduceRoundRobin 轮询分区：同一 key 的不同消息可能进不同分区（顺序性的反面教材）。
// 现实中对应"分区键用了时间戳/随机数/服务实例 id"这类不稳键——看似能摊平流量，
// 实则牺牲了同一实体的分区内有序。
func (b *Broker) ProduceRoundRobin(key, value string) int {
	p := b.round % b.NumPartitions()
	b.round++
	return b.partitions[p].Append(key, value)
}

// StablePartition FNV 散列取模（与 ex01 同款，保证同 key 同分区）。
func StablePartition(key string, n int) int {
	h := fnv.New32a()
	_, _ = h.Write([]byte(key))
	return int(h.Sum32() % uint32(n))
}
