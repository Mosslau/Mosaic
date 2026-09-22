// 来源：ph14-advanced-go 练习 2 参考实现 —— 观察 slice 扩容（扩容步长实测）
// 一句话说明：roadmap 练习「观察 slice 扩容」的落地——写一个观察器，从 cap=1 起反复
// append，记录容量每次发生变化的成长点；再用三种元素大小（1B / 8B / 32B）对比同一规则
// 在 size class 取整下的不同结果。观察结论：cap<256 翻倍、cap≥256 按 ~1.25 增长后按
// 分配器 size class 向上取整；小元素首轮被抬到 8。测试断言结构性规则（不绑定具体数）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go vet ./...
//	go run .
//
// 验证状态：已验证（go1.25.6）
// 验证块（go test ./... 实测，2026-09-01）：
//
//	PASS  ok  tenetlang/go/ph14-advanced-go/exercises/sol-02-slice-growth  0.006s
//	go vet ./... 零输出；go test -race ./... 通过
//	go run . 输出（go1.25.6 / darwin / arm64）：
//	  []int     : [1 2 4 8 16 32 64 128 256 512 848 1280 1792 2560]
//	  []byte    : [1 8 16 32 64 128 256 512 896 1408 2048]
//	  [][32]byte: [1 2 4 8 16 32 64 128 256 512 852 1280 1792 2560]
package main

import "fmt"

// GrowSequence 返回从 cap=1 起反复 append n 次期间，容量每次变化的成长点序列。
// 元素类型由调用方决定——同一算法、不同元素大小，扩容取整结果不同。
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

// GrowthReport 把三种元素大小的扩容序列整理成报告行。
func GrowthReport() string {
	return fmt.Sprintf("[]int     : %v\n[]byte    : %v\n[][32]byte: %v",
		GrowSequence[int](2000),
		GrowSequence[byte](2000),
		GrowSequence[[32]byte](2000))
}

// rulesOK 结构性断言：① 严格增长；② prev<256 翻倍（下界 2×）；③ prev≥256 约 1.25 倍
// + size class 取整（[1.25, 2)）。跨机器/架构可移植，精确数字见运行输出。
func rulesOK(seq []int) bool {
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

func main() {
	fmt.Println(GrowthReport())
}
