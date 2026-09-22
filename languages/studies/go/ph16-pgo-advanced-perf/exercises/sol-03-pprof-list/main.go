// 来源：ph16-pgo-advanced-perf 练习 3 参考实现（sol-03-pprof-list，热点路径/行级定位）
// 一句话说明：一个"设备事件分类 → 渲染"程序，埋了三类热点——
// (1) score：对 ok 事件行做 120 轮乘加混合（纯 CPU、零分配，flat 最热，稳定占 ~9 成）；
// (2) renderRows 的 `+=` 拼接：flat≈0%，症状全在 runtime.concatstring2（peek 才看得到）；
// (3) auditExport：函数体看起来重（逐行 Sprintf）但每 500 轮才调一次——"假热点"。
// 练习要做的正是 ex03 之外的下钻闭环：top（谁最热）→ peek（renderRows 的病根在哪）
// → list（score 的热点行是哪一行、为什么热），并解释 auditExport 为何不该先优化。
// 验证环境：go1.25.6（darwin/arm64，Apple M4 Pro），依赖：零第三方
// 运行（cd sol-03-pprof-list；产物一律 /tmp）：
//
//	# 1. 测试 + 构建
//	go test ./... && go vet ./... && go build -o /tmp/ph16/sol03 .
//	# 2. 采集 profile（-iters 决定窗口长度；采样太稀就调大重采——这是 pprof 的常态）
//	/tmp/ph16/sol03 -iters 8000 -cpuprofile /tmp/ph16/sol03.pprof
//	# 3. top：最热函数一眼可见
//	go tool pprof -top -nodecount=6 /tmp/ph16/sol03 /tmp/ph16/sol03.pprof
//	# 4. peek：renderRows 的 callee——症状帧在 runtime，病根要沿调用链找
//	go tool pprof -peek='renderRows' /tmp/ph16/sol03 /tmp/ph16/sol03.pprof
//	# 5. list：把最热函数下钻到行——热点集中在 score 的内层 120 轮循环
//	go tool pprof -list='score' /tmp/ph16/sol03 /tmp/ph16/sol03.pprof
//
// 验证块（go1.25.6 实测，2026-09-02，采样计数随机器波动，百分比量级稳定）：
//
//	$ /tmp/ph16/sol03 -iters 8000 -cpuprofile /tmp/ph16/sol03.pprof
//	iters=8000 digest=37b901d3e6623e00 rendered=1346
//	$ go tool pprof -top -nodecount=6 ...
//		80.77%  main.score           ← flat 最热：内层 120 轮乘加混合（O(轮数×行数×120)）
//		 7.69%  runtime.kevent        ← 渲染少量分配触发的空转线程采样（重跑占比 70~90% 波动，结构稳定）
//		（auditExport 不在 top——每 500 轮才跑一次，属"假热点"，别被函数体大小骗了）
//	$ go tool pprof -peek='renderRows' ...
//		cum 50ms（~6%）：callee = runtime.concatstring2 80% + runtime.convTstring 20%
//		—— renderRows 自身 flat≈0%，"症状帧"全在 runtime；归因要到业务函数，
//		再到行内 `+=`（concatstring2 的调用者就是它）
//	$ go tool pprof -list='score' ...
//		flat/cum 集中在内层循环两行（340ms 在 for k 行、280ms 在 h ^= 行）：
//			for k := 0; k < 120; k++ {  ← 热点行区间
//	热点答案：score 的内层 120 轮循环是热点行；优化顺序 score 优先（~8~9 成），
//	renderRows 用 Builder 改写（参考 ex04 的 FormatOpt），auditExport 不值得先动。
//
// 验证状态：已验证（go1.25.6，2026-09-02）
package main

import (
	"flag"
	"fmt"
	"os"
	"runtime/pprof"
	"strings"
)

// classify 按前缀把事件行分三类：ok（正常，走最热的 score 路径）、warn、err。
// 前缀判定是 O(len(前缀)) 的廉价操作——profile 里它不该有存在感，这正是对照。
func classify(line string) (kind string, hot bool) {
	switch {
	case strings.HasPrefix(line, "ok:"):
		return "ok", true
	case strings.HasPrefix(line, "warn:"):
		return "warn", false
	default:
		return "err", false
	}
}

// score 是 flat 最热函数：对每个字节做 120 轮 FNV 风格乘加混合。
// 纯整数运算、零分配——profile 里它独占 top，list 下钻能看到热点行就在内层循环。
// 120 轮是刻意的：让 score 的成本压过渲染与 GC，top 归因干净（对照 ex03 的 validateRow）。
func score(f string) uint64 {
	var h uint64 = 1469598103934665603
	for i := 0; i < len(f); i++ {
		for k := 0; k < 120; k++ { // 内层循环：list 下钻后的热点行区间
			h ^= uint64(f[i]) + uint64(k)
			h *= 1099511628211
		}
	}
	return h
}

// renderRows 是第二热点：`+=` 逐行拼接（O(n²) 拷贝，ph13 已证）。
// 它在 profile 里 flat≈0%，症状全在 runtime.concatstring2——peek 的教学对象。
func renderRows(rows []string) string {
	s := ""
	for _, r := range rows {
		s += fmt.Sprintf("<tr><td>%s</td></tr>\n", r) // 每次 += 都整体拷贝已有内容
	}
	return s
}

// auditExport 是"假热点"：函数体看起来重（逐行 Sprintf + 拼接），
// 但调用频率被压到每 500 轮一次——体重大 ≠ 值得先优化，频率 × 单次成本才决定。
func auditExport(rows []string) string {
	s := "<!-- audit -->\n"
	for _, r := range rows {
		s += fmt.Sprintf("<!-- %s -->\n", r)
	}
	return s
}

func main() {
	events := flag.Int("events", 40, "每轮事件行数")
	iters := flag.Int("iters", 8000, "处理轮数（决定 profile 窗口长度）")
	prof := flag.String("cpuprofile", "", "非空则采集 CPU profile 到该文件")
	flag.Parse()

	// 输入在采集前一次性生成好：profile 窗口只装"处理"，不装"造数据"的分配噪音。
	rows := make([]string, 0, *events)
	for i := 0; i < *events; i++ {
		kind := "ok"
		if i%10 == 0 {
			kind = "warn"
		}
		rows = append(rows, fmt.Sprintf("%s:device-%05d,latency=%d", kind, i, i%97))
	}

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

	var digest uint64
	var rendered string
	for it := 0; it < *iters; it++ {
		for _, line := range rows {
			if _, hot := classify(line); hot {
				// 乘加折叠进 digest：依赖迭代序号，digest 恒非零（防止被优化成 0）。
				digest = digest*1099511628211 + score(line)
			}
		}
		rendered = renderRows(rows[:30]) // 只渲染前 30 行：有 concat 成本但不喧宾夺主
		if it%500 == 0 {                 // 假热点：500 轮才触发一次
			_ = auditExport(rows)
		}
	}

	fmt.Printf("iters=%d digest=%x rendered=%d\n", *iters, digest, len(rendered))
}
