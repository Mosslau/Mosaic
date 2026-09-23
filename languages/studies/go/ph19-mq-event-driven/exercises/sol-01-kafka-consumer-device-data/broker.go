// 来源：ph19-mq-event-driven exercises/sol-01-kafka-consumer-device-data（练习 1 参考实现）
// 一句话说明：极简"Kafka 语义 broker"——分区日志 + 按 key 散列 + 组级 offset。
// 这是用标准库把 Kafka 的消费模型做出来供离线测试；连真 Kafka 时这段由
// kafka-go 的 Reader/Commit 替代，语义不变（见 main.go 尾注）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"hash/fnv"
	"sort"
	"sync"
)

// Record 分区里的一条消息：offset 分区内单调；Key 决定进哪个分区。
type Record struct {
	Offset  int
	Key     string
	Payload []byte
}

// Partition 有序日志。
type Partition struct {
	mu      sync.Mutex
	records []Record
}

// Append 追加并返回 offset。
func (p *Partition) Append(key string, payload []byte) int {
	p.mu.Lock()
	defer p.mu.Unlock()
	rec := Record{Offset: len(p.records), Key: key, Payload: append([]byte(nil), payload...)}
	p.records = append(p.records, rec)
	return rec.Offset
}

// Slice 返回 [from, Len) 的副本。
func (p *Partition) Slice(from int) []Record {
	p.mu.Lock()
	defer p.mu.Unlock()
	if from < 0 || from > len(p.records) {
		from = len(p.records)
	}
	return append([]Record(nil), p.records[from:]...)
}

// Topic 一个有 partitions 个分区的 topic（本练习场景即 fleet.telemetry）。
type Topic struct {
	partitions []*Partition
}

// NewTopic 建 topic。
func NewTopic(n int) *Topic {
	t := &Topic{partitions: make([]*Partition, n)}
	for i := range t.partitions {
		t.partitions[i] = &Partition{}
	}
	return t
}

// Publish 按 key 稳定散列写进某分区，返回 (partition, offset)。
func (t *Topic) Publish(key string, payload []byte) (int, int) {
	p := PartitionForKey(key, t.NumPartitions())
	return p, t.partitions[p].Append(key, payload)
}

// NumPartitions 分区数。
func (t *Topic) NumPartitions() int { return len(t.partitions) }

// PartitionAt 取分区。
func (t *Topic) PartitionAt(i int) *Partition { return t.partitions[i] }

// PartitionForKey FNV 散列取模：同 key 同分区（顺序性前提，examples/ex05）。
func PartitionForKey(key string, n int) int {
	h := fnv.New32a()
	_, _ = h.Write([]byte(key))
	return int(h.Sum32() % uint32(n))
}

// AssignPartitions 把 N 个分区均分给成员（无重叠无遗漏；纯函数）。
func AssignPartitions(partitions int, members []string) map[string][]int {
	sorted := append([]string(nil), members...)
	sort.Strings(sorted)
	out := make(map[string][]int)
	for p := 0; p < partitions && len(sorted) > 0; p++ {
		m := sorted[p%len(sorted)]
		out[m] = append(out[m], p)
	}
	return out
}

// Group 消费者组：保存组级提交 offset（成员崩溃由接管者续读）。
type Group struct {
	mu        sync.Mutex
	committed map[int]int
}

// NewGroup 建空组。
func NewGroup() *Group {
	return &Group{committed: make(map[int]int)}
}

// Committed 分区已提交续读位置。
func (g *Group) Committed(p int) int {
	g.mu.Lock()
	defer g.mu.Unlock()
	return g.committed[p]
}

// Commit 提交下一条位置（单调前进）。
func (g *Group) Commit(p, next int) {
	g.mu.Lock()
	defer g.mu.Unlock()
	if next > g.committed[p] {
		g.committed[p] = next
	}
}
