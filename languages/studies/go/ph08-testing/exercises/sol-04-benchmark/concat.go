// 来源：ph08-testing 练习 4 参考实现 —— 给核心模块写 benchmark
// 一句话说明：+= 拼接 vs strings.Builder 拼接，benchmem 对比分配差异。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...                        # 正确性测试
//	go test -bench=. -benchmem -run=^$      # benchmark
//
// 验证状态：已验证（go1.25.6）
//
// 结论（go1.25.6, darwin/arm64, 100 个元素）：
// ConcatBuilder 比 ConcatPlus 快一个数量级以上，且 allocs/op 从约 100 次降到个位数——
// += 每轮都分配新字符串并拷贝已有内容（O(n²) 总拷贝量），Builder 内部缓冲按需倍增。
package main

import (
	"fmt"
	"strings"
)

// ConcatPlus 用 += 循环拼接（每轮分配新字符串）
func ConcatPlus(parts []string) string {
	s := ""
	for _, p := range parts {
		s += p
	}
	return s
}

// ConcatBuilder 用 strings.Builder 拼接（内部缓冲，按需增长）
func ConcatBuilder(parts []string) string {
	var sb strings.Builder
	for _, p := range parts {
		sb.WriteString(p)
	}
	return sb.String()
}

func main() {
	parts := []string{"hello", " ", "world"}
	fmt.Println(ConcatPlus(parts))
	fmt.Println(ConcatBuilder(parts))
}
