// examples/ex04-todo-cli.go —— Todo CLI 最小版：用 slice 增、列、删待办事项
// 对应主文档 languages/go/ph01-basic-syntax/01-basic-syntax.md 第 6 章示例 4
// 验证环境：Go 1.22.2 darwin/arm64（建议 Go 1.21+）
// 运行：go run ex04-todo-cli.go
// 已验证：go vet 通过，gofmt 无差异；输出 3 条待办、删除首条后剩 2 条
package main

import "fmt"

func main() {
	todos := []string{} // 空切片

	// 添加
	todos = append(todos, "学习 Go 基础语法")
	todos = append(todos, "写一个命令行工具")
	todos = append(todos, "学习 Go 并发")

	// 列出
	fmt.Println("Todo 列表：")
	for i, todo := range todos {
		fmt.Printf("  %d. %s\n", i+1, todo)
	}

	// 删除第一个
	if len(todos) > 0 {
		todos = todos[1:]
	}

	fmt.Println("\n完成一项后：")
	for i, todo := range todos {
		fmt.Printf("  %d. %s\n", i+1, todo)
	}
}
