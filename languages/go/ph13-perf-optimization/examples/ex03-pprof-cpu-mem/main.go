// 来源：ph13-perf-optimization 示例 3 —— runtime/pprof 采集 CPU 与 heap profile
// 一句话说明：故意构造一个 CPU 热点（递归 fib）和一个堆分配热点（反复造 string），
// 用 runtime/pprof 把 profile 写到文件，再用 go tool pprof -top 定位热点函数。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go build -o /tmp/ex03 .
//	/tmp/ex03 -cpuprofile=/tmp/ex03-cpu.pprof
//	go tool pprof -top -nodecount=3 /tmp/ex03 /tmp/ex03-cpu.pprof   # CPU 热点（实测输出见 README）
//	/tmp/ex03 -memprofile=/tmp/ex03-heap.pprof
//	go tool pprof -top -nodecount=3 /tmp/ex03 /tmp/ex03-heap.pprof  # 堆分配热点（实测输出见 README）
//
// 注意：CPU profile 基于 100Hz 采样，程序运行太短会采不到样本（Total samples = 0）——
// 本例的 cpuWork 特意跑满约 1 秒。memprofile 建议在不开 cpuprofile 的单独一次运行里采集，
// 否则 pprof 运行时自身的分配会混进结果（实测里 runtime/pprof.StartCPUProfile 会占一行）。
// 验证状态：已验证（go1.25.6，pprof -top 已实际执行）；数字与百分比随机器波动
package main

import (
	"flag"
	"fmt"
	"os"
	"runtime/pprof"
	"strings"
)

// fib 是故意的 CPU 热点：指数递归，CPU profile 里应占据绝对主导
//
//go:noinline
func fib(n int) int {
	if n < 2 {
		return n
	}
	return fib(n-1) + fib(n-2)
}

// makeGarbage 是故意的堆分配热点：每次调用拼接一个长 string 并留在堆里
//
//go:noinline
func makeGarbage(i int) string {
	return strings.Repeat("x", 1024) + fmt.Sprint(i) // Repeat + Sprint 各分配一次
}

// cpuWork 跑满约 1 秒的 CPU 工作，保证 100Hz 采样能采到足够样本
func cpuWork() int {
	sum := 0
	for i := 0; i < 60; i++ {
		sum += fib(35)
	}
	return sum
}

// memWork 造出一批「还活着」的堆对象，让 heap profile 的 inuse 视角能看到分配来源
func memWork() int {
	keep := make([]string, 0, 8192)
	for i := 0; i < 8192; i++ {
		keep = append(keep, makeGarbage(i)) // 保留引用：不被 GC 回收，inuse 才可见
	}
	return len(keep)
}

func main() {
	cpuProfile := flag.String("cpuprofile", "", "CPU profile 输出文件路径")
	memProfile := flag.String("memprofile", "", "heap profile 输出文件路径")
	flag.Parse()

	if *cpuProfile != "" {
		f, err := os.Create(*cpuProfile)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		if err := pprof.StartCPUProfile(f); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Println("cpuWork:", cpuWork())
		pprof.StopCPUProfile()
		f.Close()
	}

	if *memProfile != "" {
		fmt.Println("memWork:", memWork())
		f, err := os.Create(*memProfile)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		// WriteHeapProfile 记录「当前还在堆里活着」的分配（inuse 视角）
		if err := pprof.WriteHeapProfile(f); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		f.Close()
	}

	if *cpuProfile == "" && *memProfile == "" {
		fmt.Println("demo:", fib(28)) // 无参数时的快速自检
	}
}
