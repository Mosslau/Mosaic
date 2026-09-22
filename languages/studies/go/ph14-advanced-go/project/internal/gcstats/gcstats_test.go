package gcstats

import (
	"runtime/debug"
	"testing"
)

// TestGOGCEffect：GOGC=100 下的 GC 次数应明显多于 GOGC=-1。
// 比较式断言（而非精确 0）是为了跨机器稳健：运行时可能因其他原因触发零星 GC。
func TestGOGCEffect(t *testing.T) {
	nOn, _ := Run(100)
	nOff, _ := Run(-1)
	if nOff >= nOn {
		t.Errorf("GOGC=-1 的 GC 次数应少于 GOGC=100: off=%d on=%d", nOff, nOn)
	}
	if nOn < 1 {
		t.Errorf("GOGC=100 下 200 MiB 分配压力应触发至少 1 次 GC: %d", nOn)
	}
}

// TestPauseNonNegative：累计暂停时长非负。
func TestPauseNonNegative(t *testing.T) {
	_, pOn := Run(100)
	if pOn < 0 {
		t.Errorf("暂停时长不应为负: %v", pOn)
	}
}

// TestRunRestoresGOGC：Run 结束时把 GOGC 恢复为进入时的值（defer SetGCPercent(old)）。
func TestRunRestoresGOGC(t *testing.T) {
	old := debug.SetGCPercent(100) // 测试自身把全局 GOGC 定为 100（记录原值）
	defer debug.SetGCPercent(old)  // 测试结束恢复
	_, _ = Run(42)                 // Run 进入时 GOGC=100，退出应恢复为 100
	got := debug.SetGCPercent(100) // 读出当前值（并设回 100，避免污染）
	if got != 100 {
		t.Errorf("Run 未恢复 GOGC: want 100, got %d", got)
	}
}
