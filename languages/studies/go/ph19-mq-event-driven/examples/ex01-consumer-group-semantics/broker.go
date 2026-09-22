// 来源：ph19-mq-event-driven examples/ex01-consumer-group-semantics/broker.go
// 一句话说明：极简「分区日志」模型——Kafka topic 的本质是若干只追加的有序分区，
// 每条消息在分区内拿到单调 offset；producer 按 key 散列选分区（主文档 3.1/3.4）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"hash/fnv"
	"sync"
)

// Record 一条已入分区的消息：offset 在分区内唯一、单调、不空洞（从 0 起）。
type Record struct {
	Offset int
	Key    string
	Value  string
}

// Partition 一个有序日志：只追加（append-only），读取按 offset 前进。
type Partition struct {
	mu      sync.Mutex
	records []Record
}

// Append 追加一条消息并返回其 offset（= 追加前长度）。
func (p *Partition) Append(key, value string) int {
	p.mu.Lock()
	defer p.mu.Unlock()
	rec := Record{Offset: len(p.records), Key: key, Value: value}
	p.records = append(p.records, rec)
	return rec.Offset
}

// Len 返回高水位：下一条消息的 offset（已写 offset ∈ [0, Len)）。
func (p *Partition) Len() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return len(p.records)
}

// Slice 返回 [from, Len) 的有序副本（副本防止调用方改写分区内部）。
func (p *Partition) Slice(from int) []Record {
	p.mu.Lock()
	defer p.mu.Unlock()
	if from < 0 {
		from = 0
	}
	if from > len(p.records) {
		from = len(p.records)
	}
	return append([]Record(nil), p.records[from:]...)
}

// Broker 一个有 N 个分区的 topic（单 topic 已足以演示全部核心语义）。
type Broker struct {
	mu         sync.Mutex
	partitions []*Partition
}

// NewBroker 建一个有 partitions 个分区的 topic，每个分区从空日志开始。
func NewBroker(partitions int) *Broker {
	b := &Broker{partitions: make([]*Partition, partitions)}
	for i := range b.partitions {
		b.partitions[i] = &Partition{}
	}
	return b
}

// NumPartitions 返回分区数（Kafka topic 的分区数创建时定死、只可扩不可缩）。
func (b *Broker) NumPartitions() int { return len(b.partitions) }

// Partition 按索引取分区。
func (b *Broker) Partition(i int) *Partition { return b.partitions[i] }

// Produce 按 key 散列选分区后追加，返回 (分区号, offset)。
// 并发安全：分区内 Append 有锁；跨分区天然可并行——这就是并行度来源。
func (b *Broker) Produce(key, value string) (int, int) {
	p := PartitionForKey(key, b.NumPartitions())
	off := b.partitions[p].Append(key, value)
	return p, off
}

// PartitionForKey 把 key 稳定映射到分区：同一 key 永远进同一分区——
// 这是「同一实体的消息在分区内有序」的前提（主文档 3.4 顺序性保证）。
func PartitionForKey(key string, n int) int {
	h := fnv.New32a()
	_, _ = h.Write([]byte(key))
	return int(h.Sum32() % uint32(n))
}
