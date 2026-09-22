package gmp

import "testing"

func TestParamsSanity(t *testing.T) {
	procs, cpus, gos := Params()
	if procs < 1 || cpus < 1 {
		t.Errorf("procs=%d cpus=%d 应 ≥1", procs, cpus)
	}
	if gos < 1 {
		t.Errorf("goroutine 数应 ≥1（至少主 goroutine）: %d", gos)
	}
}

// TestSpawnAndJoinNoLeak：8 个 goroutine 汇合后计数回到初始值（无泄漏）。
func TestSpawnAndJoinNoLeak(t *testing.T) {
	before, after := SpawnAndJoin(8)
	if after != before {
		t.Errorf("goroutine 泄漏: before=%d after=%d", before, after)
	}
}

// TestSpawnAndJoinLarge：1000 goroutine 汇合后不应出现量级泄漏。
// 注意 NumGoroutine 含运行时后台 goroutine（GC 助手等），会有 ±1~2 抖动——
// 断言"差 <10"，泄漏的话差会是 ~1000。
func TestSpawnAndJoinLarge(t *testing.T) {
	before, after := SpawnAndJoin(1000)
	if delta := after - before; delta < 0 || delta >= 10 {
		t.Errorf("1000 goroutine 汇合后不应量级泄漏: before=%d after=%d (delta=%d)", before, after, delta)
	}
}
