// examples/ex03-is-prime.go —— 判断素数：打印 1~100 内全部素数
// 对应主文档 languages/go/ph01-basic-syntax/01-basic-syntax.md 第 6 章示例 3
// 验证环境：Go 1.22.2 darwin/arm64（建议 Go 1.21+）
// 运行：go run ex03-is-prime.go
// 已验证：go vet 通过，gofmt 无差异；输出 2~97 共 25 个素数
package main

import "fmt"

func isPrime(n int) bool {
	if n < 2 {
		return false
	}
	for i := 2; i*i <= n; i++ {
		if n%i == 0 {
			return false
		}
	}
	return true
}

func main() {
	fmt.Print("1-100 的素数: ")
	for i := 1; i <= 100; i++ {
		if isPrime(i) {
			fmt.Printf("%d ", i)
		}
	}
	fmt.Println()
}
