// Command logbench —— ph13-perf-optimization 阶段项目「日志解析性能优化」的 CLI 入口。
// 一句话说明：生成合成日志 → 用三种解析实现（map/struct/手写扫描）解析同一批数据 →
// 打印耗时与分配对比，验证「先 profile 再优化」的完整闭环。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行（在 project/ 目录下）：
//
//	# 1. 生成 10 万行合成日志
//	go run ./cmd/logbench -gen 100000 -out /tmp/logs.jsonl
//	# 2. 对比三种解析的耗时与分配（-repeat 次取最好）
//	go run ./cmd/logbench -bench /tmp/logs.jsonl -repeat 5
//	# 3. 校验三种解析结果一致（一致退出码 0，否则非 0）
//	go run ./cmd/logbench -verify /tmp/logs.jsonl
//	# 4. 全量验证（测试 + 竞态）
//	go test ./... && go test -race ./...
//
// 验证状态：已验证（go1.25.6，10 万行实测见 README）
package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"runtime"
	"time"

	"tenetlang/go/ph13-perf-optimization/project/internal/genlog"
	"tenetlang/go/ph13-perf-optimization/project/internal/parser"
)

func main() {
	genN := flag.Int("gen", 0, "生成 N 行合成日志写入 -out（固定种子可复现）")
	out := flag.String("out", "/tmp/logs.jsonl", "-gen 的输出文件路径")
	benchFile := flag.String("bench", "", "对指定日志文件跑三种解析的耗时/分配对比")
	verifyFile := flag.String("verify", "", "校验三种解析对指定文件结果一致（不一致退出非 0）")
	repeat := flag.Int("repeat", 5, "-bench 的重复次数，取最好成绩")
	flag.Parse()

	switch {
	case *genN > 0:
		gen(*genN, *out)
	case *benchFile != "":
		bench(*benchFile, *repeat)
	case *verifyFile != "":
		verify(*verifyFile)
	default:
		flag.Usage()
	}
}

// gen 生成日志文件：固定种子 → 可复现（同一命令两次产出逐行一致）
func gen(n int, path string) {
	lines := genlog.Generate(n)
	f, err := os.Create(path)
	if err != nil {
		fmt.Fprintln(os.Stderr, "create:", err)
		os.Exit(1)
	}
	defer f.Close()
	w := bufio.NewWriter(f)
	for _, l := range lines {
		fmt.Fprintln(w, l)
	}
	if err := w.Flush(); err != nil {
		fmt.Fprintln(os.Stderr, "write:", err)
		os.Exit(1)
	}
	fmt.Printf("已生成 %d 行日志 → %s（%.1f MB）\n", n, path, float64(n*110)/1e6)
}

// bench 三种解析的耗时与分配对比：先跑一轮热身，再取 repeat 次中的最好成绩
func bench(path string, repeat int) {
	lines := readLines(path)
	fmt.Printf("文件: %s，%d 行\n\n", path, len(lines))

	parsers := []struct {
		name string
		fn   func([]string) []parser.Record
	}{
		{"naive (map)", parser.ParseNaive},
		{"struct", parser.ParseStruct},
		{"manual", parser.ParseManual},
	}
	for _, p := range parsers {
		p.fn(lines) // 热身：编译/缓存/分配器预热不进入统计

		best := time.Duration(1<<63 - 1)
		var bestAlloc uint64
		for i := 0; i < repeat; i++ {
			runtime.GC() // 清掉上一轮残留，让 MemStats.TotalAlloc 差值只反映本轮
			var m1, m2 runtime.MemStats
			runtime.ReadMemStats(&m1)
			start := time.Now()
			recs := p.fn(lines)
			elapsed := time.Since(start)
			runtime.ReadMemStats(&m2)
			if elapsed < best {
				best = elapsed
				bestAlloc = m2.TotalAlloc - m1.TotalAlloc
			}
			_ = recs
		}
		perLine := float64(best) / float64(len(lines))
		fmt.Printf("%-14s 最好 %8s  %9.1f ns/行  %8.2f MB/轮  %d 条\n",
			p.name, best.Round(time.Microsecond), perLine, float64(bestAlloc)/1e6, len(p.fn(lines)))
	}
}

// verify 三种解析结果必须逐条一致（结果集是「解析」的验收标准）
func verify(path string) {
	lines := readLines(path)
	a, b, c := parser.ParseNaive(lines), parser.ParseStruct(lines), parser.ParseManual(lines)
	if len(a) != len(b) || len(b) != len(c) {
		fmt.Fprintf(os.Stderr, "条数不一致: naive=%d struct=%d manual=%d\n", len(a), len(b), len(c))
		os.Exit(1)
	}
	for i := range a {
		if a[i] != b[i] || b[i] != c[i] {
			fmt.Fprintf(os.Stderr, "第 %d 行结果不一致: %+v / %+v / %+v\n", i, a[i], b[i], c[i])
			os.Exit(1)
		}
	}
	fmt.Printf("✓ 三种解析结果一致（%d 条），manual 解析与 struct/map 版输出相同\n", len(a))
}

// readLines 按行读入日志文件（bufio.Scanner 处理大文件）
func readLines(path string) []string {
	f, err := os.Open(path)
	if err != nil {
		fmt.Fprintln(os.Stderr, "open:", err)
		os.Exit(1)
	}
	defer f.Close()

	var lines []string
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 64*1024), 1024*1024)
	for sc.Scan() {
		lines = append(lines, sc.Text())
	}
	if err := sc.Err(); err != nil {
		fmt.Fprintln(os.Stderr, "read:", err)
		os.Exit(1)
	}
	return lines
}
