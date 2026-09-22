// 来源：ph19-mq-event-driven examples/ex01-consumer-group-semantics/group.go
// 一句话说明：消费者组 = 「分区在组成员间分配」+「组级 offset 提交与续读」。
// Kafka 语义：一个分区同一时刻只被组内一个成员消费；组提交的 offset 让
// 成员崩溃后由接管该分区的其他成员从上次提交处续读（主文档 3.1/3.3）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
	"sort"
	"sync"
)

// Group 一个消费者组：把 P 个分区公平分给 C 个成员，并保存组级提交的 offset。
// 提交是"组"的财产而非"成员"的：成员崩溃/被踢后，接管者看到的是同一个提交点。
type Group struct {
	groupID   string
	broker    *Broker
	mu        sync.Mutex
	committed map[int]int // partition -> 已提交的「下一条 offset」（0 = 从头读）
}

// NewGroup 创建一个绑定到某 topic（broker）的消费者组。
func NewGroup(groupID string, broker *Broker) *Group {
	return &Group{
		groupID:   groupID,
		broker:    broker,
		committed: make(map[int]int),
	}
}

// ID 返回组名（用于打印与日志）。
func (g *Group) ID() string { return g.groupID }

// Committed 返回分区的已提交续读位置。
func (g *Group) Committed(partition int) int {
	g.mu.Lock()
	defer g.mu.Unlock()
	return g.committed[partition]
}

// Commit 提交「已处理到 next」：只前进不回退。offset 单调是 at-least-once
// 落地的关键——处理完、提交成功，才算这一条真正"出账"。
func (g *Group) Commit(partition, next int) {
	g.mu.Lock()
	defer g.mu.Unlock()
	if next > g.committed[partition] {
		g.committed[partition] = next
	}
}

// Assign 把 partitions 个分区均分给成员列表（纯函数，便于单测）。
// 语义约束：每个分区恰好给一个成员（无重叠、无遗漏）；成员数多于分区数时
// 多出的成员空转（分配到 0 个分区，参与消费但不拉取）。
// 实现为"轮询取模"：排序成员保证"相同成员集合 → 相同分配"，分配结果可复现。
func Assign(partitions int, members []string) map[string][]int {
	sorted := append([]string(nil), members...)
	sort.Strings(sorted)
	assigned := make(map[string][]int)
	for p := 0; p < partitions; p++ {
		if len(sorted) == 0 {
			break
		}
		m := sorted[p%len(sorted)]
		assigned[m] = append(assigned[m], p)
	}
	return assigned
}

// Consume 让一个成员消费其负责的分区之一：从组提交点读到分区末尾，
// 每处理完一条就提交一条（手动 at-least-once）。返回本次处理条数。
// handle 的返回值语义：返回 nil = 处理成功；返回 error = 处理失败
// （失败时不提交、立即中止——留给更上层的重试/死信逻辑决定，见 ex03）。
func (g *Group) Consume(partition int, handle func(Record) error) (int, error) {
	from := g.Committed(partition)
	n := 0
	for _, rec := range g.broker.Partition(partition).Slice(from) {
		if err := handle(rec); err != nil {
			return n, fmt.Errorf("consume partition %d offset %d: %w", partition, rec.Offset, err)
		}
		g.Commit(partition, rec.Offset+1)
		n++
	}
	return n, nil
}

// PartitionCount 是测试/演示中查看 topic 规模的小工具。
func (g *Group) PartitionCount() int { return g.broker.NumPartitions() }
