// 来源：exercises/README.md 练习 4 —— 建立标准项目结构参考实现
// 一句话说明：internal/task 业务包：任务管理（Add/List/Search），搜索复用 pkg/text。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd sol-04-project-layout && go run ./cmd/app <add|list|search>
// 验证状态：已验证（Go 1.22.2）
package task

import (
	"fmt"
	"strings"

	"tenetlang/go/ph05-pkg-structure/exercises/sol-04-project-layout/pkg/text"
)

// Task 单条任务
type Task struct {
	ID    int
	Title string
	Body  string
}

// Store 任务存储——业务逻辑独立于入口
type Store struct {
	tasks  []Task
	nextID int
}

// NewStore 新建存储，ID 从 1 开始
func NewStore() *Store { return &Store{nextID: 1} }

// Add 新增任务，返回分配的 ID；标题为空拒绝
func (s *Store) Add(title, body string) (int, error) {
	title = strings.TrimSpace(title)
	if title == "" {
		return 0, fmt.Errorf("task: 标题不能为空")
	}
	id := s.nextID
	s.tasks = append(s.tasks, Task{ID: id, Title: title, Body: body})
	s.nextID++
	return id, nil
}

// List 返回全部任务（副本语义）
func (s *Store) List() []Task {
	out := make([]Task, len(s.tasks))
	copy(out, s.tasks)
	return out
}

// Search 在标题与正文中查找关键词（大小写不敏感），返回命中的任务
func (s *Store) Search(kw string) []Task {
	var hits []Task
	for _, t := range s.tasks {
		if text.ContainsFold(t.Title+" "+t.Body, kw) {
			hits = append(hits, t)
		}
	}
	return hits
}
