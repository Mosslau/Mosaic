// 来源：07-stdlib.md 第 6 章示例 4 —— 命令行 Todo 工具（flag 解析 + 文件持久化）
// 一句话说明：flag 收 add/list 动作，JSON 持久化到 /tmp/ph07_todo.json，MarshalIndent 美化。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go run . -add "写周报"
//	go run . -list
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
)

type Todo struct {
	Text string `json:"text"`
	Done bool   `json:"done"`
}

const storePath = "/tmp/ph07_todo.json"

func load() []Todo {
	data, _ := os.ReadFile(storePath) // 文件不存在或损坏 → 空列表
	var todos []Todo
	_ = json.Unmarshal(data, &todos)
	return todos
}

func save(todos []Todo) error {
	data, err := json.MarshalIndent(todos, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(storePath, data, 0644)
}

func must(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, "保存失败:", err)
		os.Exit(1)
	}
}

func main() {
	add := flag.String("add", "", "添加一条待办")
	list := flag.Bool("list", false, "列出全部待办")
	flag.Parse()
	todos := load()
	switch {
	case *add != "":
		todos = append(todos, Todo{Text: *add})
		must(save(todos))
		fmt.Println("已添加:", *add)
	case *list:
		for i, t := range todos {
			mark := " "
			if t.Done {
				mark = "x"
			}
			fmt.Printf("%d. [%s] %s\n", i+1, mark, t.Text)
		}
	default:
		fmt.Println("用法:")
		flag.PrintDefaults()
	}
}
