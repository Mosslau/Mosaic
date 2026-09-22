// 来源：05-pkg-structure.md 第 6 章示例 1 —— Todo CLI 标准布局最小项目
// 一句话说明：cmd/todo 程序入口，只负责解析参数与打印结果，业务在 internal/todo。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd examples/ex01-todo-cli && go run ./cmd/todo demo           # 单进程演示全流程
//	cd examples/ex01-todo-cli && go run ./cmd/todo add "学习 go mod"
//	cd examples/ex01-todo-cli && go run ./cmd/todo done 1
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"

	"tenetlang/go/ph05-pkg-structure/examples/ex01-todo-cli/internal/todo"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(1)
	}
	store := todo.NewStore()
	switch os.Args[1] {
	case "add":
		if len(os.Args) < 3 {
			fmt.Fprintln(os.Stderr, "用法: todo add <任务描述>")
			os.Exit(1)
		}
		id, err := store.Add(strings.Join(os.Args[2:], " "))
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Printf("已添加 #%d\n", id)
	case "done":
		if len(os.Args) < 3 {
			fmt.Fprintln(os.Stderr, "用法: todo done <任务ID>")
			os.Exit(1)
		}
		id, err := strconv.Atoi(os.Args[2])
		if err != nil {
			fmt.Fprintf(os.Stderr, "无效的任务 ID %q\n", os.Args[2])
			os.Exit(1)
		}
		if err := store.Done(id); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Printf("已完成 #%d\n", id)
	case "list":
		printList(store.List())
	case "demo":
		// 内存 Store 每次 go run 都是新实例，demo 在单进程内跑通完整流程
		for _, t := range []string{"学习 go mod", "理解 internal 可见性", "练习 cmd/internal 布局"} {
			if _, err := store.Add(t); err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
		}
		fmt.Println("=== 添加 3 条后 ===")
		printList(store.List())
		if err := store.Done(1); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Println("=== 完成 #1 后 ===")
		printList(store.List())
	default:
		fmt.Fprintf(os.Stderr, "未知命令: %s\n", os.Args[1])
		usage()
		os.Exit(1)
	}
}

// printList 打印待办列表——main 层职责，业务包不碰打印
func printList(items []todo.Item) {
	if len(items) == 0 {
		fmt.Println("暂无待办事项")
		return
	}
	for _, item := range items {
		status := "[ ]"
		if item.Done {
			status = "[✓]"
		}
		fmt.Printf("%s #%d %s\n", status, item.ID, item.Title)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "用法: todo <add|done|list|demo> [args...]")
}
