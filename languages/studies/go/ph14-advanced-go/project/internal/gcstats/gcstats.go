// Package gcstats 实验：GC 触发条件与 GOGC 的关系——同一份分配压力下，
// GOGC=100（默认，堆翻倍即触发）与 GOGC=-1（关闭自动 GC）的 GC 次数与累计
// 暂停对比。结论：GC 不是定时器，是"堆增长到阈值就触发"；GOGC 决定阈值。
// 观测手段：runtime.ReadMemStats 的 NumGC（累计次数）与 PauseTotalNs（累计暂停）。
package gcstats

import (
	"fmt"
	"runtime"
	"runtime/debug"
	"time"
)

// pressure 制造分配压力：200 × 1 MiB 堆对象，足以推动默认 GOGC 触发若干次 GC。
func pressure() {
	var sink [][]byte
	for i := 0; i < 200; i++ {
		sink = append(sink, make([]byte, 1<<20))
	}
	runtime.KeepAlive(sink)
}

// stats 返回当前 NumGC 与 PauseTotalNs 快照。
func stats() (n uint32, pause uint64) {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	return m.NumGC, m.PauseTotalNs
}

// Run 在给定 GOGC（百分比；-1 = 关闭自动 GC）下跑一次分配压力，
// 返回压力期间发生的 GC 次数与累计暂停时长。
func Run(gogc int) (numGC uint32, pause time.Duration) {
	old := debug.SetGCPercent(gogc)
	defer debug.SetGCPercent(old)
	bN, bP := stats()
	pressure()
	aN, aP := stats()
	return aN - bN, time.Duration(aP - bP)
}

// Report 生成 GOGC 对比报告。
func Report() string {
	nOn, pOn := Run(100)  // 默认
	nOff, pOff := Run(-1) // 关闭
	return fmt.Sprintf(
		"GOGC=100（默认，堆翻倍触发）: 压力期间 GC %d 次, 累计暂停 %v\n"+
			"GOGC=-1 （关闭自动 GC）  : 压力期间 GC %d 次, 累计暂停 %v\n"+
			"结论：GC 次数/暂停随 GOGC 增大而减少；GOGC 越大越省 GC 开销、堆峰值越高",
		nOn, pOn, nOff, pOff)
}
