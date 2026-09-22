// 来源：exercises/README.md 练习 4 参考实现 —— 命令行 Todo 工具（add/list/done + JSON 持久化）
// 一句话说明：flag 收三个动作，TodoStore 抽象存储路径便于测试用 t.TempDir() 隔离。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go run . -add "写周报"
//	go run . -list
//	go run . -done 1
//	go test -v
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
)

// Todo 单条待办
type Todo struct {
	Text string `json:"text"`
	Done bool   `json:"done"`
}

// Store 待办存储：路径显式传入（不用包级常量），测试可指向临时目录
type Store struct {
	path string
}

func NewStore(path string) *Store { return &Store{path: path} }

func (s *Store) load() ([]Todo, error) {
	data, err := os.ReadFile(s.path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil // 首次使用：文件不存在 → 空列表
	}
	if err != nil {
		return nil, fmt.Errorf("读取 %s: %w", s.path, err)
	}
	var todos []Todo
	if err := json.Unmarshal(data, &todos); err != nil {
		return nil, fmt.Errorf("解析 %s: %w", s.path, err)
	}
	return todos, nil
}

func (s *Store) save(todos []Todo) error {
	data, err := json.MarshalIndent(todos, "", "  ")
	if err != nil {
		return fmt.Errorf("序列化: %w", err)
	}
	return os.WriteFile(s.path, data, 0644)
}

// markDone 把第 n 条（1 起始）标记完成；越界返回错误而非 panic
func (s *Store) markDone(n int) error {
	todos, err := s.load()
	if err != nil {
		return err
	}
	if n < 1 || n > len(todos) {
		return fmt.Errorf("编号 %d 越界：当前共 %d 条待办", n, len(todos))
	}
	todos[n-1].Done = true
	return s.save(todos)
}

const defaultPath = "/tmp/ph07_sol04_todo.json"

func main() {
	add := flag.String("add", "", "添加一条待办")
	list := flag.Bool("list", false, "列出全部待办")
	done := flag.Int("done", 0, "把第 N 条标记为已完成")
	flag.Parse()

	store := NewStore(defaultPath)
	switch {
	case *add != "":
		todos, err := store.load()
		if err != nil {
			exitErr(err)
		}
		todos = append(todos, Todo{Text: *add})
		if err := store.save(todos); err != nil {
			exitErr(err)
		}
		fmt.Println("已添加:", *add)
	case *list:
		todos, err := store.load()
		if err != nil {
			exitErr(err)
		}
		for i, t := range todos {
			mark := " "
			if t.Done {
				mark = "x"
			}
			fmt.Printf("%d. [%s] %s\n", i+1, mark, t.Text)
		}
	case *done > 0:
		if err := store.markDone(*done); err != nil {
			exitErr(err)
		}
		fmt.Printf("已完成第 %d 条\n", *done)
	default:
		fmt.Println("用法:")
		flag.PrintDefaults()
	}
}

func exitErr(err error) {
	fmt.Fprintln(os.Stderr, "错误:", err)
	os.Exit(1)
}
