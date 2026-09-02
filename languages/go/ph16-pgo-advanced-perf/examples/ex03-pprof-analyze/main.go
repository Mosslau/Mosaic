// 来源：ph16-pgo-advanced-perf 示例 ex03-pprof-analyze（热点路径识别）
// 一句话说明：一个埋了两类热点的报表程序（validateRow 逐字节校验占 ~87%、renderBody 的 += 拼接
// 以 runtime.concatstring2 的形态占 ~7%），演示 `go tool pprof` 的三件套下钻流程——
// top（谁最热）→ peek（谁调用它/它调用谁）→ list（热在哪一行）。
// 验证环境：go1.25.6（darwin/arm64，Apple M4 Pro），依赖：零第三方
// 运行（cd ex03-pprof-analyze；产物一律 /tmp）：
//
//	# 1. 构建并采集 profile
//	go build -o /tmp/ph16/ex03 . && /tmp/ph16/ex03 -cpuprofile /tmp/ph16/ex03.pprof
//	# 2. top：看平铺占比最高的函数
//	go tool pprof -top -nodecount=6 /tmp/ph16/ex03 /tmp/ph16/ex03.pprof
//	# 3. peek：看热点函数的调用上下文（谁调它、它调谁）
//	go tool pprof -peek='validateRow' /tmp/ph16/ex03 /tmp/ph16/ex03.pprof
//	go tool pprof -peek='renderBody'  /tmp/ph16/ex03 /tmp/ph16/ex03.pprof
//	# 4. list：下钻到源码行级，热点行一目了然
//	go tool pprof -list='validateRow' /tmp/ph16/ex03 /tmp/ph16/ex03.pprof
//
// 验证块（go1.25.6 实测，2026-09-03，采样计数随机器波动）：
//
//	-top：       91.23%  main.validateRow        ← 业务热点一眼可见
//	              1.75%  runtime 长尾（lfstack/spanSet 等 GC 基础设施）
//	-peek validateRow：caller = main.render（100%，inline）；callee 只有 asyncPreempt 1.89%
//	-peek renderBody ：caller = main.render；callee = runtime.concatstring2 100%
//	                  ← += 拼接的"症状帧"：病因（业务函数）flat≈0%，症状全在 runtime
//	-list validateRow（flat/cum 集中在内层循环）：
//	     190ms  190ms  for k := 0; k < 100; k++ {
//	     300ms  310ms      h ^= uint64(r[i]) + uint64(k)
//	     120ms  120ms      h *= 1099511628211（等，采样点在三行间摆动）
//	教学点：renderBody 自身 flat ≈ 0%，病因藏在 concatstring2/Sprintf 这些"runtime 症状帧"
//	背后——用 peek 沿调用链找回业务函数；但真正值得先动手的是占 87% 的 validateRow：
//	"热点代码更值得优化"（roadmap 必会概念）。
//	环境备注：本机（darwin/arm64）对分配密集的单线程程序，CPU profile 会有一部分采样
//	落在 runtime.kevent / pthread_cond 等"被打断的空转线程"帧上——本示例故意把分配压到
//	极低（+= 拼接仅 ~7%）以获得干净归因；线上服务多goroutine 场景（ex01）无此问题。
//
// 验证状态：已验证（go1.25.6，2026-09-03）
package main

import (
	"flag"
	"fmt"
	"os"
	"runtime/pprof"
)

// validateRow 是人为制造的第一热点：对行内每个字节做 100 轮混合，纯 CPU、零分配——
// 它在 flat top 里以业务函数身份直接登顶（与"症状落在 runtime 帧"的第二热点对照）。
func validateRow(r string) uint64 {
	var h uint64 = 1469598103934665603
	for i := 0; i < len(r); i++ {
		for k := 0; k < 100; k++ { // 内层循环：list 下钻后的热点行
			h ^= uint64(r[i]) + uint64(k)
			h *= 1099511628211
			h ^= h >> 13
		}
	}
	return h
}

// renderBody 是第二热点：故意用 `+=` 逐行拼接（ph13 已证明它是 O(n²) 拷贝）。
// 它在 profile 里 flat ≈ 0%，"症状"落在 runtime.concatstring2 / fmt.Sprintf 上——
// 这正是需要 peek 沿调用链找回病因的典型形态。
func renderBody(rows []string) string {
	s := "<table>\n"
	for _, r := range rows {
		s += fmt.Sprintf("<tr><td>%s</td></tr>\n", r) // 热点行：每次 += 都整体拷贝 s
	}
	return s + "</table>\n"
}

// render 是调用入口：peek 里能看到它是 validateRow 与 renderBody 共同的 caller。
func render(rows []string) (string, uint64) {
	var h uint64
	for _, r := range rows {
		h ^= validateRow(r)
	}
	return renderBody(rows), h
}

func main() {
	rows := flag.Int("rows", 30, "报表行数")
	iters := flag.Int("iters", 4000, "渲染轮数")
	prof := flag.String("cpuprofile", "", "非空则采集 CPU profile 到该文件")
	flag.Parse()

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
			pprof.StopCPUProfile()
			f.Close()
		}()
	}

	data := make([]string, *rows)
	for i := range data {
		data[i] = fmt.Sprintf("device-%05d online latency=%dms fw=v%d.%d", i, i%97, i%7, i%13)
	}

	var sinkS string
	var sinkU uint64
	for k := 0; k < *iters; k++ {
		sinkS, sinkU = render(data)
	}
	fmt.Printf("report bytes=%d digest=%d\n", len(sinkS), sinkU)
}
