// 来源：04-method-interface.md 第 6 章示例 3 —— Storage 接口：可替换存储层的 Todo 服务
// 一句话说明：演示接口由使用方定义——TodoService 依赖 Storage 接口而非具体实现。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：go run ex03-storage-todo.go
// 验证状态：已验证（Go 1.22.2）
//
// 教学简化说明：为聚焦接口定义与依赖注入，本示例省略了 error 返回值；
// 生产实现应显式返回 error（见 exercises/sol-02-storage.go 与 project/）。
package main

import "fmt"

// Storage 由使用方定义
type Storage interface {
	Save(key, value string)
	Load(key string) (string, bool)
	Delete(key string)
}

type MemStorage struct {
	data map[string]string
}

func (m *MemStorage) Save(key, value string) {
	if m.data == nil {
		m.data = make(map[string]string)
	}
	m.data[key] = value
}

func (m *MemStorage) Load(key string) (string, bool) {
	v, ok := m.data[key]
	return v, ok
}

func (m *MemStorage) Delete(key string) {
	delete(m.data, key)
}

// TodoService 依赖接口而非具体实现
type TodoService struct {
	store Storage
}

func (t *TodoService) Add(id, task string) {
	t.store.Save(id, task)
	fmt.Printf("[添加] %s → %s\n", id, task)
}

func (t *TodoService) Done(id string) {
	t.store.Delete(id)
	fmt.Printf("[完成] %s 已删除\n", id)
}

func (t *TodoService) List(ids []string) {
	fmt.Println("\n=== Todo 列表 ===")
	for _, id := range ids {
		if v, ok := t.store.Load(id); ok {
			fmt.Printf("  [ ] %s: %s\n", id, v)
		}
	}
}

func main() {
	svc := &TodoService{store: &MemStorage{}}
	svc.Add("1", "学习 Go 接口的隐式实现")
	svc.Add("2", "实现可替换存储层的 Todo 服务")
	svc.Add("3", "理解 nil 接口与 nil 指针的区别")
	svc.Done("2")
	svc.List([]string{"1", "2", "3"})
}
