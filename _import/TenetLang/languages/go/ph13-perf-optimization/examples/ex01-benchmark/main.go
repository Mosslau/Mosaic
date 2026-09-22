// 来源：ph13-perf-optimization 示例 1 —— benchmark 与 -benchmem
// 一句话说明：用 testing.B 量化「字符串拼接三写法」与「slice 预分配」的性能差异，
// 读三列指标 ns/op（每次耗时）、B/op（每次分配字节数）、allocs/op（每次分配次数）——
// 分配次数是 GC 压力的源头，本阶段全部优化都靠这三列验证。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...                                        # 正确性测试
//	go test -run='^$' -bench=. -benchmem -benchtime=2000x   # 只跑基准（固定迭代数，便于复现）
//
// 验证状态：已验证（go1.25.6）；benchmark 数字随机器波动，以 README 实测记录为准
package main

import (
	"fmt"
	"strings"
)

// ---- 被测对象 1：字符串拼接的三种写法 ----

// ConcatPlus 用 += 拼接：每轮产生一个新字符串（旧串整体拷贝），O(n²) 且每轮分配
func ConcatPlus(n int) string {
	var s string
	for i := 0; i < n; i++ {
		s += "x"
	}
	return s
}

// ConcatBuilder 用 strings.Builder：内部 []byte 原地追加，Builder.Grow 可预分配
func ConcatBuilder(n int) string {
	var sb strings.Builder
	sb.Grow(n) // 预分配容量：避免追加时反复扩容
	for i := 0; i < n; i++ {
		sb.WriteByte('x')
	}
	return sb.String()
}

// ConcatJoin 用 strings.Join：一次计算总长度、一次分配、一次拷贝
func ConcatJoin(n int) string {
	parts := make([]string, n)
	for i := range parts {
		parts[i] = "x"
	}
	return strings.Join(parts, "")
}

// ---- 被测对象 2：slice 是否预分配 ----

// AppendNoPrealloc 不预分配：底层数组反复扩容 + 旧数组拷贝，且每次扩容都产生一次堆分配
func AppendNoPrealloc(n int) []int {
	var out []int
	for i := 0; i < n; i++ {
		out = append(out, i)
	}
	return out
}

// AppendPrealloc 预分配容量：一次分配装下全部元素
func AppendPrealloc(n int) []int {
	out := make([]int, 0, n)
	for i := 0; i < n; i++ {
		out = append(out, i)
	}
	return out
}

func main() {
	// go run 演示模式：打印三写法结果一致性（性能数字请跑 benchmark）
	fmt.Println(len(ConcatPlus(1000)), len(ConcatBuilder(1000)), len(ConcatJoin(1000)))
	fmt.Println(len(AppendNoPrealloc(1000)), len(AppendPrealloc(1000)))
}
