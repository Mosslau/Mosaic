// exercises/sol-01-slice-grow.go —— 练习 1 参考实现：slice 扩容实验
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run sol-01-slice-grow.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import "fmt"

func main() {
	// 场景 1：从 nil slice 开始，容量按 1→2→4→8→16 翻倍
	fmt.Println("=== 从 nil slice 开始（容量翻倍）===")
	var s []int
	for i := 0; i < 10; i++ {
		s = append(s, i)
		fmt.Printf("append %2d: len=%2d cap=%2d\n", i, len(s), cap(s))
	}

	// 场景 2：预分配 cap=8，前 8 次 append 不触发扩容
	fmt.Println("\n=== 预分配 cap=8（前 8 次不扩容）===")
	p := make([]int, 0, 8)
	for i := 0; i < 10; i++ {
		p = append(p, i)
		fmt.Printf("append %2d: len=%2d cap=%2d\n", i, len(p), cap(p))
	}
}
