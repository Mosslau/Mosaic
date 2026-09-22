// 来源：exercises/README.md 练习 4 —— 建立标准项目结构参考实现
// 一句话说明：cmd/app 入口：add / list / search 三个子命令，组装 internal/task 与 pkg/text。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd sol-04-project-layout && go run ./cmd/app demo
//	cd sol-04-project-layout && go run ./cmd/app add "学习 Go" "internal 与 pkg 的边界"
//	cd sol-04-project-layout && go run ./cmd/app list
//	cd sol-04-project-layout && go run ./cmd/app search go
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"fmt"
	"os"
	"strings"

	"tenetlang/go/ph05-pkg-structure/exercises/sol-04-project-layout/internal/task"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "用法: app <add|list|search> [args...]")
		os.Exit(1)
	}
	store := task.NewStore()
	switch os.Args[1] {
	case "add":
		if len(os.Args) < 3 {
			fmt.Fprintln(os.Stderr, "用法: app add <标题> [正文]")
			os.Exit(1)
		}
		body := ""
		if len(os.Args) > 3 {
			body = strings.Join(os.Args[3:], " ")
		}
		id, err := store.Add(os.Args[2], body)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Printf("已添加 #%d %s\n", id, os.Args[2])
	case "list":
		for _, t := range store.List() {
			fmt.Printf("#%d %s — %s\n", t.ID, t.Title, t.Body)
		}
	case "search":
		if len(os.Args) < 3 {
			fmt.Fprintln(os.Stderr, "用法: app search <关键词>")
			os.Exit(1)
		}
		hits := store.Search(os.Args[2])
		if len(hits) == 0 {
			fmt.Printf("未找到包含 %q 的任务\n", os.Args[2])
			return
		}
		for _, t := range hits {
			fmt.Printf("#%d %s — %s\n", t.ID, t.Title, t.Body)
		}
	case "demo":
		// 内存 Store 每次 go run 都是新实例，demo 在单进程内跑通 add/list/search
		if _, err := store.Add("学习 Go", "internal 与 pkg 的边界"); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		if _, err := store.Add("写 CLI 工具", "flag 包解析参数"); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Println("=== 全部任务 ===")
		for _, t := range store.List() {
			fmt.Printf("#%d %s — %s\n", t.ID, t.Title, t.Body)
		}
		fmt.Println(`=== 搜索 "go" ===`)
		for _, t := range store.Search("go") {
			fmt.Printf("#%d %s — %s\n", t.ID, t.Title, t.Body)
		}
	default:
		fmt.Fprintf(os.Stderr, "未知命令: %s\n", os.Args[1])
		os.Exit(1)
	}
}
