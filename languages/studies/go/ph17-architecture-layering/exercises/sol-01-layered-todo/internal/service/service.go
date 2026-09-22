// 来源：ph17-architecture-layering exercises/sol-01-layered-todo/internal/service
// 一句话说明：练习 1 参考实现的业务层。优先级合法性、标题非空、存在才可切换——
// 这些从单体 handler 里"救"出来的规则全部在此，handler 只剩翻译。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package service

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"sort"
	"strings"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-01-layered-todo/internal/store"
	"tenetlang/go/ph17-architecture-layering/exercises/sol-01-layered-todo/internal/todo"
)

// ErrBadRequest：调用方参数不合规（handler 据此回 400）。
var ErrBadRequest = errors.New("bad request")

type Service struct {
	store *store.Store
}

func New(s *store.Store) *Service {
	return &Service{store: s}
}

// Add 的规则：标题去空白非空；优先级必须是三档之一。
func (s *Service) Add(title string, priority todo.Priority) (todo.Todo, error) {
	title = strings.TrimSpace(title)
	if title == "" {
		return todo.Todo{}, fmt.Errorf("%w: title is required", ErrBadRequest)
	}
	switch priority {
	case todo.PriorityHigh, todo.PriorityNormal, todo.PriorityLow:
	default:
		return todo.Todo{}, fmt.Errorf("%w: unknown priority %q", ErrBadRequest, priority)
	}
	id, err := newID()
	if err != nil {
		return todo.Todo{}, fmt.Errorf("generate id: %w", err)
	}
	t := todo.Todo{ID: id, Title: title, Priority: priority}
	if err := s.store.Save(t); err != nil {
		return todo.Todo{}, fmt.Errorf("save todo: %w", err)
	}
	return t, nil
}

func (s *Service) Get(id string) (todo.Todo, error) {
	t, err := s.store.Get(id)
	if err != nil {
		return todo.Todo{}, fmt.Errorf("get todo %s: %w", id, err)
	}
	return t, nil
}

// List 排序返回（先按优先级档位，再按 ID），输出稳定。
func (s *Service) List() ([]todo.Todo, error) {
	items, err := s.store.List()
	if err != nil {
		return nil, fmt.Errorf("list todos: %w", err)
	}
	rank := map[todo.Priority]int{todo.PriorityHigh: 0, todo.PriorityNormal: 1, todo.PriorityLow: 2}
	sort.Slice(items, func(i, j int) bool {
		if rank[items[i].Priority] != rank[items[j].Priority] {
			return rank[items[i].Priority] < rank[items[j].Priority]
		}
		return items[i].ID < items[j].ID
	})
	return items, nil
}

func (s *Service) Toggle(id string) (todo.Todo, error) {
	t, err := s.store.Get(id)
	if err != nil {
		return todo.Todo{}, fmt.Errorf("toggle todo %s: %w", id, err)
	}
	t.Done = !t.Done
	if err := s.store.Save(t); err != nil {
		return todo.Todo{}, fmt.Errorf("toggle todo %s: %w", id, err)
	}
	return t, nil
}

func (s *Service) Delete(id string) error {
	if err := s.store.Delete(id); err != nil {
		return fmt.Errorf("delete todo %s: %w", id, err)
	}
	return nil
}

func newID() (string, error) {
	b := make([]byte, 8)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}
