// 来源：project/ 可替换存储层的 Todo 服务 —— 程序入口
// 一句话说明：通过 -backend 切换存储后端做演示，-selfcheck 对两个后端跑同一组断言验证行为一致。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go run . -backend=mem
//	go run . -backend=file -path=/tmp/todo.txt
//	go run . -selfcheck
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
)

// newStore 按后端名构造存储实现——工厂函数只在这里感知具体类型
func newStore(backend, path string) (Storage, error) {
	switch backend {
	case "mem":
		return &MemStorage{}, nil
	case "file":
		if path == "" {
			return nil, fmt.Errorf("file 后端需要 -path 指定存储文件")
		}
		return NewFileStorage(path)
	default:
		return nil, fmt.Errorf("未知后端 %q（可选 mem / file）", backend)
	}
}

// demo 对指定后端跑一遍业务演示
func demo(backend, path string) error {
	store, err := newStore(backend, path)
	if err != nil {
		return err
	}
	svc := NewTodoService(store)

	fmt.Printf("存储后端: %s\n", backend)
	if err := svc.Add("1", "学习 Go 接口的隐式实现"); err != nil {
		return err
	}
	if err := svc.Add("2", "实现可替换存储层的 Todo 服务"); err != nil {
		return err
	}
	if err := svc.Add("3", "理解 nil 接口与 nil 指针的区别"); err != nil {
		return err
	}
	fmt.Println("=== Todo 列表 ===")
	if err := svc.List([]string{"1", "2", "3"}); err != nil {
		return err
	}
	if err := svc.Done("2"); err != nil {
		return err
	}
	fmt.Println("=== 完成 2 号后 ===")
	if err := svc.List([]string{"1", "2", "3"}); err != nil {
		return err
	}
	if backend == "file" {
		fmt.Printf("落盘文件: %s（可打开查看持久化内容）\n", path)
	}
	return nil
}

// runSelfCheck 对 mem / file 两个后端跑同一组断言，验证行为一致与文件持久化
func runSelfCheck() error {
	if err := checkBackend("mem", ""); err != nil {
		return fmt.Errorf("mem 后端: %w", err)
	}
	dir, err := os.MkdirTemp("", "todo-storage-*")
	if err != nil {
		return err
	}
	defer os.RemoveAll(dir)
	if err := checkBackend("file", filepath.Join(dir, "store.txt")); err != nil {
		return fmt.Errorf("file 后端: %w", err)
	}
	return nil
}

// checkBackend 验证单后端：保存/读取、未命中 ErrNotFound、删除幂等
func checkBackend(backend, path string) error {
	store, err := newStore(backend, path)
	if err != nil {
		return err
	}
	svc := NewTodoService(store)

	// 1. 保存与读取
	if err := svc.Add("a", "任务 A"); err != nil {
		return fmt.Errorf("Add: %w", err)
	}
	v, err := svc.store.Load("a")
	if err != nil || v != "任务 A" {
		return fmt.Errorf("Load 期望 %q 得到 %q（err=%v）", "任务 A", v, err)
	}

	// 2. 未命中必须命中 ErrNotFound
	if _, err := svc.store.Load("missing"); !errors.Is(err, ErrNotFound) {
		return fmt.Errorf("期望 ErrNotFound，得到 %v", err)
	}

	// 3. 删除与幂等删除
	if err := svc.Done("a"); err != nil {
		return fmt.Errorf("Done: %w", err)
	}
	if err := svc.store.Delete("a"); err != nil {
		return fmt.Errorf("幂等 Delete: %w", err)
	}

	// 4. file 后端：重开存储实例后数据仍在（持久化验证）
	if backend == "file" {
		reopened, err := NewFileStorage(path)
		if err != nil {
			return err
		}
		if _, err := reopened.Load("a"); !errors.Is(err, ErrNotFound) {
			return fmt.Errorf("重开实例后 a 应已被删除")
		}
		if err := reopened.Save("p", "persist"); err != nil {
			return err
		}
		again, err := NewFileStorage(path)
		if err != nil {
			return err
		}
		v, err := again.Load("p")
		if err != nil || v != "persist" {
			return fmt.Errorf("持久化校验失败: %q（err=%v）", v, err)
		}
	}
	return nil
}

func main() {
	backend := flag.String("backend", "mem", "存储后端: mem 或 file")
	path := flag.String("path", "", "file 后端的存储文件路径")
	selfCheck := flag.Bool("selfcheck", false, "运行内置自检（mem + file 两个后端）")
	flag.Parse()

	if *selfCheck {
		if err := runSelfCheck(); err != nil {
			fmt.Fprintln(os.Stderr, "自检失败:", err)
			os.Exit(1)
		}
		fmt.Println("自检通过: mem 与 file 两个后端行为一致，文件持久化正常")
		return
	}

	if err := demo(*backend, *path); err != nil {
		fmt.Fprintln(os.Stderr, "演示失败:", err)
		os.Exit(1)
	}
}
