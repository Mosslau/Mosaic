// 来源：ph19-mq-event-driven examples/ex02-idempotent-consumer/dedup_test.go
// 一句话说明：幂等消费的可执行断言——去重表行为、重复投递副作用只一次、
// 记账顺序（先记账后副作用会丢效果，见 ProcessOnce 注释）等。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "testing"

// TestDeduperSeenThenMark 见过与记过的语义：Mark 前 Seen=false，Mark 后 Seen=true。
func TestDeduperSeenThenMark(t *testing.T) {
	d := NewDeduper(10)
	if d.Seen("m1") {
		t.Fatal("m1 not marked yet, Seen should be false")
	}
	d.Mark("m1")
	if !d.Seen("m1") {
		t.Fatal("m1 marked, Seen should be true")
	}
}

// TestDeduperEvictsOldest 容量回收：满了之后最早记的键被淘汰，新键保留。
func TestDeduperEvictsOldest(t *testing.T) {
	d := NewDeduper(3)
	d.Mark("a")
	d.Mark("b")
	d.Mark("c")
	d.Mark("d") // 超过容量：淘汰最旧的 a
	if d.Seen("a") {
		t.Fatal("a should be evicted")
	}
	for _, k := range []string{"b", "c", "d"} {
		if !d.Seen(k) {
			t.Fatalf("%s should still be remembered", k)
		}
	}
	if d.Len() != 3 {
		t.Fatalf("Len=%d, want 3", d.Len())
	}
}

// TestMarkIdempotent 重复 Mark 同一键不重复排队：order 长度 == 唯一键数。
func TestMarkIdempotent(t *testing.T) {
	d := NewDeduper(5)
	d.Mark("a")
	d.Mark("a")
	d.Mark("a")
	if d.Len() != 1 {
		t.Fatalf("Len=%d, want 1", d.Len())
	}
}

// TestDuplicateDeliveryEffectOnce 重复投递幂等：副作用（快照计数）只 +1。
func TestDuplicateDeliveryEffectOnce(t *testing.T) {
	log := []TelemetryEvent{
		NewEvent("car-001", 100, 50, 1),
		NewEvent("car-001", 100, 50, 1), // 同 MsgID 重复（redelivery）
		NewEvent("car-001", 100, 50, 1), // 再一次重复
		NewEvent("car-001", 101, 55, 2),
	}
	d := NewDeduper(100)
	store := NewSnapshotStore()
	processed, skipped := ProcessLog(log, d, store.Apply)

	if processed != 2 {
		t.Fatalf("processed=%d, want 2（只有 2 个唯一事件）", processed)
	}
	if skipped != 2 {
		t.Fatalf("skipped=%d, want 2（2 条重复应被拦截）", skipped)
	}
	v, ok := store.Get("car-001")
	if !ok {
		t.Fatal("snapshot missing")
	}
	if v.Samples != 2 {
		t.Fatalf("Samples=%d, want 2（重复投递不得让副作用生效两次）", v.Samples)
	}
}

// TestDifferentConsumersShareDeduper 消费者组内不同成员可能先后处理同一分区
// （重平衡接管），去重表必须跨成员共享（真实工程落 DB/Redis），否则重复生效。
func TestDifferentConsumersShareDeduper(t *testing.T) {
	d := NewDeduper(100) // 共享：模拟"幂等表在服务外"
	log := []TelemetryEvent{
		NewEvent("car-001", 100, 50, 1),
		NewEvent("car-001", 100, 50, 1), // 崩后重投：由"另一个"消费者实例接手
	}
	store := NewSnapshotStore()
	// 第一次"消费"处理第 1 条后假死（第 2 条没处理到），提交丢失
	ProcessOnce(log[0], d, store.Apply)
	// 新的消费者实例从头重放：重复事件被共享去重表拦下
	processed, _ := ProcessLog(log[1:], d, store.Apply)
	if processed != 0 {
		t.Fatalf("redelivered event processed=%d, want 0（共享去重表应拦截）", processed)
	}
	if v, _ := store.Get("car-001"); v.Samples != 1 {
		t.Fatalf("Samples=%d, want 1", v.Samples)
	}
}

// TestCrashWindowDoubleEffect 诚实标注边界：若处理与记账之间崩溃，
// 重放仍可能造成二次副作用（先副作用后记账的顺序）——这正是需要 outbox/
// 事务把"效果与记账"做成原子的原因（主文档 4 章 exactly-once 的现实）。
func TestCrashWindowDoubleEffect(t *testing.T) {
	e := NewEvent("car-001", 100, 50, 1)
	store := NewSnapshotStore()
	applyButCrashBeforeMark := func() {
		store.Apply(e) // 副作用已发生……
		// ……进程在这里崩溃，Mark 没执行
	}
	applyButCrashBeforeMark()
	// 重投：去重表不认识该键（从未记账）→ 副作用第二次发生
	applyButCrashBeforeMark()
	if v, _ := store.Get("car-001"); v.Samples != 2 {
		t.Fatalf("Samples=%d, want 2（诚实演示：非原子记账的窗口期）", v.Samples)
	}
}
