// Package slicegrow 实验：slice 扩容机制——从 cap=1 起反复 append，记录容量
// 每次变化的成长点序列；对比三种元素大小（1B / 8B / 32B）在分配器 size class
// 取整下的不同结果。结论：cap<256 翻倍、cap≥256 约 1.25 倍后按 size class 取整；
// 小元素首轮被抬到 8。测试断言结构性规则（跨机器可移植），精确数字见 README。
package slicegrow

import "fmt"

// GrowSequence 返回从 cap=1 起反复 append n 次期间，容量每次变化的成长点序列。
// 元素类型是类型参数：一个实现、三种元素大小。
func GrowSequence[T any](n int) []int {
	s := make([]T, 0, 1)
	seq := []int{cap(s)}
	for i := 0; i < n; i++ {
		var v T
		s = append(s, v)
		if c := cap(s); c != seq[len(seq)-1] {
			seq = append(seq, c)
		}
	}
	return seq
}

// Report 生成三种元素大小的扩容序列报告。
func Report() string {
	return fmt.Sprintf("[]int     : %v\n[]byte    : %v\n[][32]byte: %v",
		GrowSequence[int](2000),
		GrowSequence[byte](2000),
		GrowSequence[[32]byte](2000))
}

// RulesOK 结构性断言：① 严格增长；② prev<256 翻倍（下界 2×，size class 只上取整）；
// ③ prev≥256 比率落在 [1.25, 2)（约 1.25 倍 + 取整，不会翻倍）。
func RulesOK(seq []int) bool {
	for i := 1; i < len(seq); i++ {
		prev, cur := seq[i-1], seq[i]
		if cur <= prev {
			return false
		}
		if prev < 256 {
			if cur < prev*2 {
				return false
			}
		} else if cur < prev*5/4 || cur > prev*2 {
			return false
		}
	}
	return true
}
