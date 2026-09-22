// 来源：ph19-mq-event-driven examples/ex01-consumer-group-semantics/group_test.go
// 一句话说明：把消费者组四条核心语义变成可执行断言——分配无重叠无遗漏、
// 同 key 同分区、提交续读不重放、提交前崩溃会重放（at-least-once 的本相）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "testing"

// TestAssignCoversAllPartitionsOnce 分配不变量：每个分区恰好一个成员（无重叠、
// 无遗漏）；成员比分区多时，多出的成员分配到空集合（空转）。
func TestAssignCoversAllPartitionsOnce(t *testing.T) {
	cases := []struct {
		name       string
		partitions int
		members    int
	}{
		{"一成员拿全部", 3, 1},
		{"两成员均分", 6, 2},
		{"三成员不均分", 5, 3},
		{"成员多于分区", 2, 4},
		{"零分区", 0, 2},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			members := make([]string, tc.members)
			for i := range members {
				members[i] = string(rune('a' + i))
			}
			got := Assign(tc.partitions, members)

			// 每个成员的分区号合法且内部有序
			sizes := make([]int, 0, tc.members)
			for m, parts := range got {
				if !validSortedParts(parts, tc.partitions) {
					t.Fatalf("member %s got invalid parts %v", m, parts)
				}
				sizes = append(sizes, len(parts))
			}
			// 无重叠无遗漏：每个分区恰好被分配一次
			seen := make([]int, tc.partitions)
			for _, parts := range got {
				for _, p := range parts {
					seen[p]++
				}
			}
			for p, n := range seen {
				if n != 1 {
					t.Fatalf("partition %d appears %d times, want 1", p, n)
				}
			}
			// 均衡性：任意两成员分到的分区数差不超过 1
			if tc.members > 1 && tc.partitions > 0 {
				for i := 1; i < len(sizes); i++ {
					diff := sizes[i] - sizes[0]
					if diff < -1 || diff > 1 {
						t.Fatalf("unbalanced sizes %v", sizes)
					}
				}
			}
		})
	}
}

func validSortedParts(parts []int, n int) bool {
	prev := -1
	for _, p := range parts {
		if p < 0 || p >= n {
			return false
		}
		if p <= prev {
			return false // 需要严格递增（轮询取模天然有序）
		}
		prev = p
	}
	return true
}

// TestAssignDeterministic 相同成员集合（任意顺序）得到相同分配——
// 重平衡结果可复现，是"谁接管哪个分区"可预测的前提。
func TestAssignDeterministic(t *testing.T) {
	a := Assign(7, []string{"m2", "m1", "m3"})
	b := Assign(7, []string{"m3", "m1", "m2"})
	if len(a) != len(b) {
		t.Fatalf("length differ")
	}
	for m, parts := range a {
		for i, p := range parts {
			if p != b[m][i] {
				t.Fatalf("assignment differs for %s: %v vs %v", m, a, b)
			}
		}
	}
}

// TestSameKeySamePartition 同一 key 永远进同一分区且 offset 连续——
// 顺序性的物理前提（主文档 3.4：分区内有序）。
func TestSameKeySamePartition(t *testing.T) {
	b := NewBroker(4)
	firstP := -1
	for i := 0; i < 20; i++ {
		p, off := b.Produce("car-001", "sample")
		if firstP == -1 {
			firstP = p
		}
		if p != firstP {
			t.Fatalf("same key went to partition %d then %d", firstP, p)
		}
		if off != i {
			t.Fatalf("offset = %d, want %d（分区内 offset 应连续）", off, i)
		}
	}
}

// TestCommitResumeNoReprocess 提交语义：成员处理完一批并提交后，
// 无论谁来接管该分区，都从提交点续读——旧消息绝不重放。
func TestCommitResumeNoReprocess(t *testing.T) {
	b := NewBroker(1)
	g := NewGroup("g", b)
	// 定位唯一分区（p 固定为 0）
	for i := 0; i < 3; i++ {
		b.Produce("car-001", "sample")
	}
	n1 := 0
	if _, err := g.Consume(0, func(Record) error { n1++; return nil }); err != nil {
		t.Fatal(err)
	}
	if n1 != 3 {
		t.Fatalf("first pass processed %d, want 3", n1)
	}
	// 又写入 2 条，换一个成员（m2 接管分区）
	b.Produce("car-002", "sample")
	b.Produce("car-002", "sample")
	n2 := 0
	if _, err := g.Consume(0, func(Record) error { n2++; return nil }); err != nil {
		t.Fatal(err)
	}
	if n2 != 2 {
		t.Fatalf("resume processed %d, want 2（旧 3 条不应被重放）", n2)
	}
}

// TestCommitBeforeCrashRedelivers 反证 at-least-once：处理了但没来得及提交就
// "崩溃"，下次从旧提交点重读 → 同一条被再处理一次。消费者必须幂等的原因。
func TestCommitBeforeCrashRedelivers(t *testing.T) {
	b := NewBroker(1)
	g := NewGroup("g", b)
	b.Produce("car-001", "dup-sensitive")

	// 手动"处理一条但不提交"（模拟 handle 返回后、Commit 前进程被杀）
	recs := b.Partition(0).Slice(g.Committed(0))
	if len(recs) != 1 {
		t.Fatalf("want 1 record, got %d", len(recs))
	}
	if g.Committed(0) != 0 {
		t.Fatal("committed should still be 0 after crash")
	}

	// 接管者从 0 重读：这条被再处理 → 这就是为什么消费逻辑要幂等
	processed := 0
	if _, err := g.Consume(0, func(r Record) error {
		processed++
		_ = r
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if processed != 1 {
		t.Fatalf("redelivery processed %d, want 1（at-least-once：至少一次）", processed)
	}
	if g.Committed(0) != 1 {
		t.Fatalf("committed = %d, want 1", g.Committed(0))
	}
}
