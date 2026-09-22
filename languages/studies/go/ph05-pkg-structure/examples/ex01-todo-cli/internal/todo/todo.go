// 来源：05-pkg-structure.md 第 6 章示例 1 —— Todo CLI 标准布局最小项目
// 一句话说明：internal/todo 业务包：内存待办存储（Add/Done/List），显式返回 error。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd examples/ex01-todo-cli && go run ./cmd/todo <add|done|list>
// 验证状态：已验证（Go 1.22.2）
package todo

import (
	"errors"
	"fmt"
	"strings"
)

// ErrNotFound 哨兵错误：标记不存在的任务 ID，调用方用 errors.Is 判断
var ErrNotFound = errors.New("todo: item not found")

// Item 单条待办
type Item struct {
	ID    int
	Title string
	Done  bool
}

// Store 内存待办存储——业务与 main 分离，可独立复用与测试
type Store struct {
	items  []Item
	nextID int
}

// NewStore 新建存储，ID 从 1 开始
func NewStore() *Store { return &Store{nextID: 1} }

// Add 新增待办，返回分配的任务 ID；空标题直接拒绝（fail fast）
func (s *Store) Add(title string) (int, error) {
	title = strings.TrimSpace(title)
	if title == "" {
		return 0, fmt.Errorf("todo: 任务标题不能为空")
	}
	id := s.nextID
	s.items = append(s.items, Item{ID: id, Title: title})
	s.nextID++
	return id, nil
}

// Done 把指定 ID 标记为完成；ID 不存在时包装 ErrNotFound
func (s *Store) Done(id int) error {
	for i := range s.items {
		if s.items[i].ID == id {
			s.items[i].Done = true
			return nil
		}
	}
	return fmt.Errorf("todo: 标记 #%d: %w", id, ErrNotFound)
}

// List 返回当前全部待办——副本语义，调用方修改不影响内部存储
func (s *Store) List() []Item {
	out := make([]Item, len(s.items))
	copy(out, s.items)
	return out
}
