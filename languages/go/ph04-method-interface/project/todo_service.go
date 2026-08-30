// 来源：project/ 可替换存储层的 Todo 服务 —— 业务层
// 一句话说明：TodoService 只依赖 Storage 接口，提供 Add / Done / List，后端可一键切换。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：go run . -backend=mem|file
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"errors"
	"fmt"
)

// TodoService 依赖接口而非具体实现——换存储后端无需改业务代码
type TodoService struct {
	store Storage
}

func NewTodoService(store Storage) *TodoService {
	return &TodoService{store: store}
}

func (t *TodoService) Add(id, task string) error {
	if task == "" {
		return fmt.Errorf("任务内容不能为空")
	}
	if err := t.store.Save(id, task); err != nil {
		return fmt.Errorf("保存任务 %s: %w", id, err)
	}
	return nil
}

func (t *TodoService) Done(id string) error {
	if _, err := t.store.Load(id); err != nil {
		return fmt.Errorf("任务 %s 不存在: %w", id, err)
	}
	if err := t.store.Delete(id); err != nil {
		return fmt.Errorf("删除任务 %s: %w", id, err)
	}
	return nil
}

func (t *TodoService) List(ids []string) error {
	for _, id := range ids {
		v, err := t.store.Load(id)
		if errors.Is(err, ErrNotFound) {
			fmt.Printf("  [x] %s: 已完成\n", id)
			continue
		}
		if err != nil {
			return fmt.Errorf("读取任务 %s: %w", id, err)
		}
		fmt.Printf("  [ ] %s: %s\n", id, v)
	}
	return nil
}
