// 来源：ph17-architecture-layering exercises/sol-02-store-interface/internal/service
// 一句话说明：本练习的核心——Store 接口定义在消费方（service 包），
// 内存实现与文件实现（internal/store 的两个结构）隐式满足它，service 代码里
// 不出现任何具体存储类型。换存储 = main 里换一行构造。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package service

import (
	"errors"
	"fmt"
	"strings"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-02-store-interface/internal/todo"
)

// Store 是 Service 对存储的全部需求——只含用得到的方法，接口在消费方声明（主文档 3.3）。
// 实现方（internal/store 的 Mem/File）不 import 本包，靠方法签名隐式满足。
type Store interface {
	Get(id string) (todo.Todo, error)
	Save(t todo.Todo) error
	Delete(id string) error
	List() ([]todo.Todo, error)
}

// 业务哨兵错误：参数问题与唯一性冲突（handler/CLI 据此给用户不同反馈）。
var (
	ErrBadRequest = errors.New("bad request")
	ErrExists     = errors.New("todo already exists")
)

type Service struct {
	store Store
}

// New 注入接口而不是具体类型：这是"能换存储"的接缝。
func New(store Store) *Service {
	return &Service{store: store}
}

// Add 的规则：id/title 去空白后非空；id 不能与已存在记录重复。
func (s *Service) Add(id, title string) error {
	id = strings.TrimSpace(id)
	title = strings.TrimSpace(title)
	if id == "" || title == "" {
		return fmt.Errorf("%w: id and title are required", ErrBadRequest)
	}
	if _, err := s.store.Get(id); err == nil {
		return fmt.Errorf("%w: %s", ErrExists, id)
	} else if !errors.Is(err, todo.ErrNotFound) {
		return fmt.Errorf("check existing %s: %w", id, err)
	}
	return s.store.Save(todo.Todo{ID: id, Title: title})
}

// Toggle 的规则：只切换存在的 todo；不存在透出领域哨兵并带上下文。
func (s *Service) Toggle(id string) error {
	t, err := s.store.Get(id)
	if err != nil {
		if errors.Is(err, todo.ErrNotFound) {
			return fmt.Errorf("todo %s 不存在（%w）", id, todo.ErrNotFound)
		}
		return fmt.Errorf("load todo %s: %w", id, err)
	}
	t.Done = !t.Done
	return s.store.Save(t)
}

func (s *Service) List() ([]todo.Todo, error) {
	items, err := s.store.List()
	if err != nil {
		return nil, fmt.Errorf("list todos: %w", err)
	}
	return items, nil
}
