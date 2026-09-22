// 来源：exercises/README.md 练习 1 —— 拆分单文件程序参考实现
// 一句话说明：拆分后的 cmd/student-mgr 入口，demo 在单进程内演示 Add/Delete/List 全流程。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd sol-01-split-program && go run ./cmd/student-mgr demo
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"fmt"
	"os"

	"tenetlang/go/ph05-pkg-structure/exercises/sol-01-split-program/internal/student"
)

func main() {
	if len(os.Args) < 2 || os.Args[1] != "demo" {
		fmt.Fprintln(os.Stderr, "用法: student-mgr demo")
		os.Exit(1)
	}
	m := student.NewManager()
	// 含非法输入：空姓名、超范围年龄应被拒绝
	for _, s := range []struct {
		name string
		age  int
	}{
		{"Alice", 20}, {"Bob", 22}, {"", 18}, {"Carol", 300},
	} {
		id, err := m.Add(s.name, s.age)
		if err != nil {
			fmt.Printf("Add(%q, %d) 拒绝: %v\n", s.name, s.age, err)
			continue
		}
		fmt.Printf("已添加 #%d %s\n", id, s.name)
	}
	fmt.Println("=== 学生列表 ===")
	for _, s := range m.List() {
		fmt.Printf("#%d %s (%d 岁)\n", s.ID, s.Name, s.Age)
	}
	fmt.Println("=== 删除 #1 ===")
	if err := m.Delete(1); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	for _, s := range m.List() {
		fmt.Printf("#%d %s (%d 岁)\n", s.ID, s.Name, s.Age)
	}
	// 删除不存在的 ID 应返回 ErrNotFound
	if err := m.Delete(99); err != nil {
		fmt.Printf("删除不存在的学生: %v\n", err)
	}
}
