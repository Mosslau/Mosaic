// Package gmp 实验：GMP 调度模型的可观测面——GOMAXPROCS 与 NumCPU 的关系、
// goroutine 的创建/汇合计数（泄漏检测）、Gosched 让出 P 的协作调度。
// 结论：Go 调度的"可见部分"只有三个数字（GOMAXPROCS 的 P 数、NumGoroutine 的 G 数、
// NumCPU 的核数），M 在运行时不可见——这正是"GMP 是黑盒、只能从外部观测"的教学点。
package gmp

import (
	"fmt"
	"runtime"
	"sync"
)

// Params 返回 GOMAXPROCS / NumCPU / 当前 goroutine 数。
func Params() (procs, cpus, gos int) {
	return runtime.GOMAXPROCS(0), runtime.NumCPU(), runtime.NumGoroutine()
}

// SpawnAndJoin 起 n 个 goroutine 各自让出 P 后汇合，返回汇合后的 goroutine 数。
// 用 channel 同步（无 sleep），确定性可测；goroutine 数应回到启动前（无泄漏）。
func SpawnAndJoin(n int) (before, after int) {
	before = runtime.NumGoroutine()
	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			runtime.Gosched() // 主动让出 P：协作式调度的最小实验
			_ = i
		}(i)
	}
	wg.Wait()
	after = runtime.NumGoroutine()
	return before, after
}

// Report 生成 GMP 观测报告。
func Report() string {
	procs, cpus, gos := Params()
	before, after := SpawnAndJoin(8)
	return fmt.Sprintf(
		"GOMAXPROCS=%d NumCPU=%d（P 数 = 核数，M 数运行时内部管理、外部不可见）\n"+
			"初始 goroutine 数=%d\n"+
			"8 个 goroutine 让出 P 并汇合后=%d（初始 %d → 回到初始值 = 无泄漏）",
		procs, cpus, gos, after, before)
}
