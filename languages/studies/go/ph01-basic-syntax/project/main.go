// project/main.go —— Todo CLI：增删查改待办事项，用 slice 存储
// 对应 Roadmap（languages/go/go.md）ph01 推荐项目「Todo CLI」；需求见 project/README.md
// 验证环境：Go 1.22.2 darwin/arm64（建议 Go 1.21+）
// 运行：go run main.go
// 编译：go build -o todo main.go  （然后 ./todo）
// 已验证：go vet 通过，gofmt 无差异；add/list/done/quit 及编号越界、非数字路径均验证
package main

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

func main() {
	var todos []string
	scanner := bufio.NewScanner(os.Stdin)

	fmt.Println("Todo CLI —— 命令: add <内容> | list | done <编号> | quit")

	for {
		fmt.Print("> ")
		if !scanner.Scan() {
			break // EOF（Ctrl+D）
		}
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}

		// 拆分命令与参数
		cmd, rest, _ := strings.Cut(line, " ")

		switch cmd {
		case "add":
			content := strings.TrimSpace(rest)
			if content == "" {
				fmt.Println("用法: add <内容>")
				continue
			}
			todos = append(todos, content)
			fmt.Printf("已添加 %d: %s\n", len(todos), content)

		case "list":
			if len(todos) == 0 {
				fmt.Println("（空）")
				continue
			}
			for i, todo := range todos {
				fmt.Printf("  %d. %s\n", i+1, todo)
			}

		case "done":
			n, err := strconv.Atoi(strings.TrimSpace(rest))
			if err != nil || n < 1 || n > len(todos) {
				fmt.Println("用法: done <编号>，编号为 list 中显示的有效序号")
				continue
			}
			removed := todos[n-1]
			// 删除第 n 项：拼接前后两段
			todos = append(todos[:n-1], todos[n:]...)
			fmt.Printf("已完成: %s\n", removed)

		case "quit", "exit":
			fmt.Println("再见")
			return

		default:
			fmt.Println("未知命令。支持: add <内容> | list | done <编号> | quit")
		}
	}

	if err := scanner.Err(); err != nil {
		fmt.Fprintln(os.Stderr, "读取输入出错:", err)
	}
}
