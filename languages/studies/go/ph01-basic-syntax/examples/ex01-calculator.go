// examples/ex01-calculator.go —— 命令行计算器：读入算式并求值，处理除零
// 对应主文档 languages/go/ph01-basic-syntax/01-basic-syntax.md 第 6 章示例 1
// 验证环境：Go 1.22.2 darwin/arm64（建议 Go 1.21+）
// 运行：go run ex01-calculator.go  （然后输入如 3 + 4 回车）
// 已验证：go vet 通过，gofmt 无差异；输入 3 + 4 输出 7.00，1 / 0 输出除零提示，5 ^ 2 提示不支持
package main

import "fmt"

func main() {
	var a, b float64
	var op string

	fmt.Print("输入算式 (如 3 + 4): ")
	fmt.Scanf("%f %s %f", &a, &op, &b)

	switch op {
	case "+":
		fmt.Printf("%.2f\n", a+b)
	case "-":
		fmt.Printf("%.2f\n", a-b)
	case "*":
		fmt.Printf("%.2f\n", a*b)
	case "/":
		if b != 0 {
			fmt.Printf("%.2f\n", a/b)
		} else {
			fmt.Println("错误: 除数为零")
		}
	default:
		fmt.Println("不支持的操作符")
	}
}
