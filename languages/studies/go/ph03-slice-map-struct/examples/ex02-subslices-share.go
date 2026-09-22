// examples/ex02-subslices-share.go —— 子切片共享底层数组：cap 范围内共享，扩容后解除共享
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run ex02-subslices-share.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import "fmt"

func main() {
	// 创建底层数组容量较大的 slice
	original := make([]int, 0, 10)
	original = append(original, 1, 2, 3, 4, 5)

	// 子切片共享底层数组（cap 从 low 位置算起）
	sub := original[1:3] // len=2 cap=9
	fmt.Println("--- 修改子切片 ---")
	sub[0] = 99
	fmt.Println("original:", original) // [1 99 3 4 5] — 被影响
	fmt.Println("sub:     ", sub)      // [99 3]

	// append 在 cap 范围内仍然共享
	sub = append(sub, 100)
	fmt.Println("\n--- 子切片 append（未超 cap）---")
	fmt.Println("original:", original) // [1 99 3 100 5] — 仍被影响
	fmt.Println("sub:     ", sub)      // [99 3 100]

	// append 超出 cap 触发扩容，分配新底层数组
	sub = append(sub, 200, 300, 400, 500, 600, 700, 800)
	sub[0] = 0 // 修改新的底层数组
	fmt.Println("\n--- 扩容后修改 ---")
	fmt.Println("original:", original) // [1 99 3 100 5] — 不受影响
	fmt.Println("sub:     ", sub)      // [0 3 100 200 300 400 500 600 700 800]
}
