// 来源：ph19-mq-event-driven examples/ex05-order-guarantee/order_test.go
// 一句话说明：顺序性保证的可执行断言——稳定 key 下同 key 子序列严格保序；
// 跨分区交错消费不破坏单 key 顺序；轮询 key 会破坏同一实体顺序（反例钉死）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
	"testing"
)

func writeStable(b *Broker, key string, n int) {
	for i := 1; i <= n; i++ {
		b.ProduceStable(key, fmt.Sprintf("%s-%d", key, i))
	}
}

// TestStableKeyPerKeyOrder 稳定 key：同 key 消息全部落在同一分区 → 严格保序。
func TestStableKeyPerKeyOrder(t *testing.T) {
	b := NewBroker(3)
	writeStable(b, "A", 3)
	writeStable(b, "B", 3)
	writeStable(b, "A", 2) // A 再追加

	consumed := ConsumeSerially(b)
	got := Values(PerKey(consumed, "A"))
	want := []string{"A-1", "A-2", "A-3", "A-1", "A-2"}
	if !ValuesEqual(got, want) {
		t.Fatalf("key A order broken: got %v want %v", got, want)
	}
}

// TestSameKeySamePartition 同一 key 的所有消息落在同一分区（顺序性的物理前提）。
func TestSameKeySamePartition(t *testing.T) {
	b := NewBroker(5)
	first := -1
	for i := 0; i < 10; i++ {
		p := StablePartition("vehicle-9", b.NumPartitions())
		if first == -1 {
			first = p
		}
		if p != first {
			t.Fatalf("same key mapped to %d and %d", first, p)
		}
	}
}

// TestRoundRobinKeyBreaksOrder 轮询 key（同 key 分到不同分区）跨分区拼接后顺序被打乱。
// 2 分区 + 连发 3 条：A-1→p0、A-2→p1、A-3→p0，按分区号合并得到 A-1 A-3 A-2。
func TestRoundRobinKeyBreaksOrder(t *testing.T) {
	b := NewBroker(2)
	for i := 1; i <= 3; i++ {
		b.ProduceRoundRobin("A", fmt.Sprintf("A-%d", i))
	}
	got := Values(PerKey(ConsumeSerially(b), "A"))
	want := []string{"A-1", "A-3", "A-2"} // 明确断言"被打乱成什么样"——可复现
	if !ValuesEqual(got, want) {
		t.Fatalf("got %v, want broken order %v", got, want)
	}
}

// TestInterleavingAcrossPartitionsIsNormal 不同 key 落在不同分区、交错消费是常态——
// 只承诺单 key 顺序，不承诺跨 key 全局顺序。这里验证 A/B 子序列各自正确即可。
func TestInterleavingAcrossPartitionsIsNormal(t *testing.T) {
	b := NewBroker(2)
	writeStable(b, "A", 3)
	writeStable(b, "B", 3)
	consumed := ConsumeSerially(b)
	for _, key := range []string{"A", "B"} {
		got := Values(PerKey(consumed, key))
		want := []string{key + "-1", key + "-2", key + "-3"}
		if !ValuesEqual(got, want) {
			t.Fatalf("key %s sub-sequence broken: %v", key, got)
		}
	}
}

// TestKeysSpreadAcrossPartitions 稳定散列下不同 key 尽量铺开，让组内并行度
// 不集中在单个分区（大量 key 至少分布在 >1 个分区，保证可并行前提）。
func TestKeysSpreadAcrossPartitions(t *testing.T) {
	b := NewBroker(4)
	for i := 0; i < 40; i++ {
		b.ProduceStable(fmt.Sprintf("vehicle-%03d", i), "sample")
	}
	nonEmpty := 0
	for i := 0; i < b.NumPartitions(); i++ {
		if len(b.PartitionAt(i).All()) > 0 {
			nonEmpty++
		}
	}
	if nonEmpty < 2 {
		t.Fatalf("all traffic landed in %d partition, want spread", nonEmpty)
	}
}
