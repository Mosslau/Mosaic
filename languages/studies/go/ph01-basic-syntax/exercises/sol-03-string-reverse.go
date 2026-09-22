// exercises/sol-03-string-reverse.go —— 练习 3 参考实现：按字符（rune）反转字符串
// 对应 exercises/README.md 练习 3
// 验证环境：Go 1.22.2 darwin/arm64（建议 Go 1.21+）
// 运行：go run sol-03-string-reverse.go
// 已验证：go vet 通过，gofmt 无差异；"hello, 世界" 反转为 "界世 ,olleh"，Unicode 正确
package main

import "fmt"

// reverse 按 rune（Unicode 码点）反转字符串，正确处理中文等多字节字符
func reverse(s string) string {
	runes := []rune(s) // 转成 rune 切片，每个元素是一个完整字符
	for i, j := 0, len(runes)-1; i < j; i, j = i+1, j-1 {
		runes[i], runes[j] = runes[j], runes[i]
	}
	return string(runes)
}

func main() {
	s := "hello, 世界"
	fmt.Println("原串:", s)
	fmt.Println("反转:", reverse(s))
}
