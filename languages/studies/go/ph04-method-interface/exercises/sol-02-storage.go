// 来源：exercises/README.md 练习 2 —— Storage 接口参考实现
// 一句话说明：带 error 的 Storage 接口 + 零值可用的 MemStorage + 依赖接口的 TodoService。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：go run sol-02-storage.go
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"errors"
	"fmt"
)

// ErrNotFound 哨兵错误：Load 未命中时返回，调用方用 errors.Is 判断
var ErrNotFound = errors.New("storage: key not found")

// Storage 接口由使用方 TodoService 定义——消费侧定义，实现方无需感知
type Storage interface {
	Save(key, value string) error
	Load(key string) (string, error)
	Delete(key string) error
}

// MemStorage 零值可用：data 为 nil 时 Save 惰性初始化
type MemStorage struct {
	data map[string]string
}

func (m *MemStorage) Save(key, value string) error {
	if m.data == nil {
		m.data = make(map[string]string)
	}
	m.data[key] = value
	return nil
}

func (m *MemStorage) Load(key string) (string, error) {
	v, ok := m.data[key]
	if !ok {
		return "", ErrNotFound
	}
	return v, nil
}

// Delete 幂等：key 不存在也不报错
func (m *MemStorage) Delete(key string) error {
	delete(m.data, key)
	return nil
}

// TodoService 只依赖 Storage 接口，不感知存储的具体实现
type TodoService struct {
	store Storage
}

func (t *TodoService) Add(id, task string) error {
	if task == "" {
		return fmt.Errorf("任务内容不能为空")
	}
	return t.store.Save(id, task)
}

func (t *TodoService) Done(id string) error {
	if err := t.store.Delete(id); err != nil {
		return fmt.Errorf("删除任务 %s: %w", id, err)
	}
	return nil
}

func (t *TodoService) List(ids []string) error {
	for _, id := range ids {
		v, err := t.store.Load(id)
		if errors.Is(err, ErrNotFound) {
			fmt.Printf("  [ ] %s: (未找到)\n", id)
			continue
		}
		if err != nil {
			return fmt.Errorf("读取任务 %s: %w", id, err)
		}
		fmt.Printf("  [ ] %s: %s\n", id, v)
	}
	return nil
}

func main() {
	svc := &TodoService{store: &MemStorage{}}

	fmt.Println("1) 添加任务:")
	svc.Add("1", "学习 Storage 接口")
	svc.Add("2", "实现可替换存储层")
	fmt.Println("2) 列表:")
	svc.List([]string{"1", "2"})

	fmt.Println("3) 完成 2 号任务:")
	svc.Done("2")
	svc.List([]string{"1", "2"})

	fmt.Println("4) Load 未命中 → ErrNotFound:")
	if _, err := svc.store.Load("no-such-key"); err != nil {
		fmt.Printf("   err=%v, errors.Is=%v\n", err, errors.Is(err, ErrNotFound))
	}
}
