// exercises/sol-01-calculator.go —— 练习 1 参考实现：命令行计算器
// 对应 exercises/README.md 练习 1；对应主文档 01-basic-syntax.md 第 6 章示例 1 的完整版
// 验证环境：Go 1.22.2 darwin/arm64（建议 Go 1.21+）
// 运行：go run sol-01-calculator.go  （然后输入如 3 + 4 回车）
// 已验证：go vet 通过，gofmt 无差异；输入 10 / 4 输出 2.50，abc 提示格式错误
package main

import "fmt"

func main() {
	var a, b float64
	var op string

	fmt.Print("输入算式 (如 3 + 4): ")
	n, err := fmt.Scanf("%f %s %f", &a, &op, &b)
	if err != nil || n != 3 {
		fmt.Println("错误: 输入格式不正确，应为 `数字 运算符 数字`")
		return
	}

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
		fmt.Printf("不支持的操作符: %s\n", op)
	}
}
