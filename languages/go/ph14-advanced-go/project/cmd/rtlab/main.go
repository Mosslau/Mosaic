// Command rtlab —— ph14-advanced-go 阶段项目「Go runtime 机制实验台」的 CLI 入口。
// 一句话说明：把本阶段"Go runtime 机制实验笔记"落地为可运行工具——五个实验包
// （slicegrow 扩容序列 / deferx defer 与 panic 语义 / gmp 调度观测 / gcstats GC
// 触发对比 / chanx channel 语义）各产出一份报告，`go run . -exp all` 一键跑完，
// 也可单独跑某个实验。所有实验是"黑盒可观测"：不碰 runtime 内部结构，只用公开
// API（cap/NumGoroutine/ReadMemStats/channel 行为）把底层机制"逼"出来。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行（在 project/ 目录下）：
//
//	# 1. 全量验证（测试 + 竞态）
//	go test ./... && go test -race ./...
//	# 2. 一键跑全部实验
//	go run ./cmd/rtlab -exp all
//	# 3. 单独跑某个实验
//	go run ./cmd/rtlab -exp slice   # slicegrow 扩容序列
//	go run ./cmd/rtlab -exp defer   # defer/panic-recover 语义
//	go run ./cmd/rtlab -exp gmp     # GMP 调度观测
//	go run ./cmd/rtlab -exp gc      # GOGC 对 GC 次数的影响
//	go run ./cmd/rtlab -exp chan    # channel 语义
//
// 验证状态：已验证（go1.25.6，实测输出见 README）
package main

import (
	"flag"
	"fmt"
	"os"

	"tenetlang/go/ph14-advanced-go/project/internal/chanx"
	"tenetlang/go/ph14-advanced-go/project/internal/deferx"
	"tenetlang/go/ph14-advanced-go/project/internal/gcstats"
	"tenetlang/go/ph14-advanced-go/project/internal/gmp"
	"tenetlang/go/ph14-advanced-go/project/internal/slicegrow"
)

func main() {
	exp := flag.String("exp", "all", "实验选择：slice|defer|gmp|gc|chan|all")
	flag.Parse()

	run := map[string]func(){
		"slice": func() {
			fmt.Println("== [slice] slice 扩容步长实测（cap 成长点序列）==")
			fmt.Println(slicegrow.Report())
		},
		"defer": func() {
			fmt.Println("== [defer] defer / panic-recover 语义实测 ==")
			fmt.Println(deferx.Report())
		},
		"gmp": func() {
			fmt.Println("== [gmp] GMP 调度模型可观测面 ==")
			fmt.Println(gmp.Report())
		},
		"gc": func() {
			fmt.Println("== [gc] GOGC 与 GC 触发次数 ==")
			fmt.Println(gcstats.Report())
		},
		"chan": func() {
			fmt.Println("== [chan] channel 底层语义 ==")
			fmt.Println(chanx.Report())
		},
	}

	if *exp == "all" {
		for _, name := range []string{"slice", "defer", "gmp", "gc", "chan"} {
			run[name]()
			fmt.Println()
		}
		return
	}
	f, ok := run[*exp]
	if !ok {
		fmt.Fprintf(os.Stderr, "未知实验 %q（可选：slice|defer|gmp|gc|chan|all）\n", *exp)
		os.Exit(2)
	}
	f()
}
