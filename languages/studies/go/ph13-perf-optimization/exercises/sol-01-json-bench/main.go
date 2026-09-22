// 来源：ph13-perf-optimization 练习 1 参考实现 —— 优化 JSON 解析
// 一句话说明：同一批 JSON 日志行，分别用 map[string]any（通用但反射重、分配多）与
// 具名 struct（编译期定字段、一次分配）解析，benchmark 量化差异；两个优化点：
// ① map -> struct ② 结果 slice 预分配。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go test -run='^$' -bench=. -benchmem -benchtime=2000x
//
// 验证状态：已验证（go1.25.6）
// 覆盖率：go test -cover 实测 **85.0%**（缺口为 main 演示入口；NaiveParse/FastParse/genLines 全覆盖）
// benchmark 实测（go1.25.6，Apple M4 Pro，-benchtime=2000x，1000 行/次）：
//
//	BenchmarkNaiveParse-14    2000    663846 ns/op    786575 B/op    20910 allocs/op
//	BenchmarkFastParse-14     2000    416743 ns/op    369281 B/op     8009 allocs/op
//
// 结论：struct 版快约 1.6 倍、分配次数 20910 -> 8009（-62%）、B/op -53%；
// 数字随机器波动，以本机重跑为准
package main

import (
	"encoding/json"
	"fmt"
)

// Record 日志记录：具名 struct 让 json 包跳过 map 的反射路径
type Record struct {
	Level     string `json:"level"`
	Msg       string `json:"msg"`
	LatencyMs int    `json:"latency_ms"`
}

// NaiveParse 朴素版：每行解析进 map[string]any——每行分配一个 map + 每个字段装箱一次
func NaiveParse(lines []string) []Record {
	var out []Record // 不预分配：append 扩容再叠一层成本
	for _, line := range lines {
		var m map[string]any
		if err := json.Unmarshal([]byte(line), &m); err != nil {
			continue
		}
		rec := Record{Level: fmt.Sprint(m["level"]), Msg: fmt.Sprint(m["msg"])}
		if v, ok := m["latency_ms"].(float64); ok { // JSON 数字进 map 一律是 float64
			rec.LatencyMs = int(v)
		}
		out = append(out, rec)
	}
	return out
}

// FastParse 优化版：具名 struct（编译期字段表）+ 结果 slice 预分配
func FastParse(lines []string) []Record {
	out := make([]Record, 0, len(lines)) // 一次分配装下全部结果
	for _, line := range lines {
		var rec Record
		if err := json.Unmarshal([]byte(line), &rec); err != nil {
			continue
		}
		out = append(out, rec)
	}
	return out
}

func main() {
	lines := []string{
		`{"level":"info","msg":"request ok","latency_ms":12}`,
		`{"level":"warn","msg":"slow query","latency_ms":870}`,
	}
	fmt.Println(NaiveParse(lines))
	fmt.Println(FastParse(lines))
}
