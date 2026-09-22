// examples/ex01-slice-grow.go —— Slice 扩容实验：观察 append 过程中 len/cap 的变化规律
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run ex01-slice-grow.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import "fmt"

func main() {
	var s []int
	for i := 0; i < 12; i++ {
		s = append(s, i)
		fmt.Printf("append %2d: len=%2d cap=%2d val=%v\n", i, len(s), cap(s), s)
	}
}
