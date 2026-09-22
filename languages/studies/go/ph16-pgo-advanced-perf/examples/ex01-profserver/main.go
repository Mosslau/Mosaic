// 来源：ph16-pgo-advanced-perf 示例 ex01-profserver（CPU profile 采集）
// 一句话说明：同一个 CPU 密集型服务，演示两种 profile 采集路径——
// 常驻服务用 net/http/pprof（边服务边采，/debug/pprof/profile?seconds=N），
// 批处理/一次性程序用 runtime/pprof（StartCPUProfile/StopCPUProfile 包一段代码）。
// 验证环境：go1.25.6（darwin/arm64，Apple M4 Pro），依赖：零第三方
// 运行（cd ex01-profserver；产物一律 /tmp）：
//
//	# 路径 A：net/http/pprof（常驻服务，边压测边采集）
//	go build -o /tmp/ph16/ex01 . && /tmp/ph16/ex01 -addr 127.0.0.1:18080 &
//	# 另开 4 路并行 curl 持续压测（每请求 n=20000000 约 30ms 纯 CPU）
//	for w in 1 2 3 4; do (while true; do curl -s 'http://127.0.0.1:18080/work?n=20000000' > /dev/null; done) & done
//	curl -s 'http://127.0.0.1:18080/debug/pprof/profile?seconds=3' > /tmp/ph16/ex01-http.pprof
//	go tool pprof -top -nodecount=5 /tmp/ph16/ex01 /tmp/ph16/ex01-http.pprof
//	kill %1 %2 %3 %4 %5   # 停掉服务器与 4 路压测
//	# 路径 B：runtime/pprof（一次性程序，程序自己采）
//	/tmp/ph16/ex01 -batch -n 40000000 -cpuprofile /tmp/ph16/ex01-batch.pprof
//	go tool pprof -top -nodecount=5 /tmp/ph16/ex01-batch.pprof
//
// 验证块（go1.25.6 实测，2026-09-03；采样计数随负载波动）：
//
//	路径 A 的 -top（4 路并行 curl 持续压测 n=20000000 期间采 3s，profile 与二进制一起喂给 pprof）：
//		82.51%  main.hashChain (inline)   ← 业务热点：纯 CPU 混合循环（4 核合计 5.40s/3s）
//		 9.17%  runtime.asyncPreempt      ← 热循环被抢占检查的采样
//		 7.64%  syscall.syscall           ← 每个请求一次 socket 写
//	路径 B 的 -top（-batch -n 40000000）：
//		  100%  main.hashChain (inline)
//	两条路径采到的是同一份 pprof 格式文件，分析命令完全一致
//
// 验证状态：已验证（go1.25.6，2026-09-03）
package main

import (
	"flag"
	"fmt"
	"net/http"
	_ "net/http/pprof" // 注册 /debug/pprof/* 到 DefaultServeMux——服务侧采集的唯一准备工作
	"os"
	"runtime/pprof"
	"strconv"
	"time"
)

// hashChain 是人为的 CPU 热点：对种子做 n 轮 FNV 风格的乘加混合。
// 纯整数运算、无内存分配——这样 CPU profile 里热点干净，教学焦点不被 GC 干扰。
func hashChain(seed uint64, n int) uint64 {
	x := seed
	for i := 0; i < n; i++ {
		x ^= x << 13
		x *= 1099511628211
		x ^= x >> 17
	}
	return x
}

// workHandler 模拟真实服务里"每次请求做一段 CPU 工作"的接口。
// 响应里带上结果（fmt.Fprintf 到 ResponseWriter），防止请求被优化成空调用。
func workHandler(w http.ResponseWriter, r *http.Request) {
	n, err := strconv.Atoi(r.URL.Query().Get("n"))
	if err != nil || n <= 0 {
		n = 100000
	}
	sum := hashChain(uint64(n), n)
	fmt.Fprintf(w, `{"sum":%d,"n":%d}`+"\n", sum, n)
}

func main() {
	addr := flag.String("addr", "127.0.0.1:18080", "HTTP 监听地址")
	batch := flag.Bool("batch", false, "一次性批处理模式（用 runtime/pprof 采集）")
	n := flag.Int("n", 40_000_000, "批处理模式的迭代次数")
	prof := flag.String("cpuprofile", "", "批处理模式：采集 CPU profile 到该文件")
	flag.Parse()

	if *batch {
		// 路径 B：runtime/pprof 包揽一段代码——适合 CLI、压测工具、离线任务
		if *prof != "" {
			f, err := os.Create(*prof)
			if err != nil {
				fmt.Fprintln(os.Stderr, "创建 profile 文件失败:", err)
				os.Exit(1)
			}
			if err := pprof.StartCPUProfile(f); err != nil {
				fmt.Fprintln(os.Stderr, "启动 CPU profile 失败:", err)
				os.Exit(1)
			}
			defer func() {
				pprof.StopCPUProfile() // 必须等 Stop 返回后文件才完整
				f.Close()
			}()
		}
		start := time.Now()
		sum := hashChain(42, *n)
		fmt.Printf("sum=%d elapsed=%s\n", sum, time.Since(start))
		return
	}

	// 路径 A：net/http/pprof——import 即注册，无需额外代码。
	// /debug/pprof/profile?seconds=N 在"服务正常接流量的同时"采样 N 秒，
	// 这就是"采集压测 profile"的标准动作（roadmap §16 练习 1）。
	http.HandleFunc("/work", workHandler)
	fmt.Println("listening on", *addr, "（pprof 在 /debug/pprof/）")
	if err := http.ListenAndServe(*addr, nil); err != nil {
		fmt.Fprintln(os.Stderr, "服务退出:", err)
		os.Exit(1)
	}
}
