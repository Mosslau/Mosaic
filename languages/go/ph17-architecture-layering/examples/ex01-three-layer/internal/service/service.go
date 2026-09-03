// 来源：ph17-architecture-layering examples/ex01-three-layer/internal/service
// 一句话说明：业务层。Todo 的规则（标题非空、存在才可删除/切换）全部在这里，
// 不出现 HTTP 词汇（w/r/状态码/JSON），也不直接知道数据怎么存（操作 *store.Store，
// 抽象成接口见 ex04）。
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

	"tenetlang/go/ph17-architecture-layering/examples/ex01-three-layer/internal/store"
	"tenetlang/go/ph17-architecture-layering/examples/ex01-three-layer/internal/todo"
)

// ErrBadRequest 是"调用方参数不合规"的业务错误（handler 据此回 400）。
// ex01 只用一个哨兵做粗略划分，完整的错误码体系见 ex03 与 project/。
var ErrBadRequest = errors.New("bad request")

// Service 依赖具体 *store.Store——"针对接口编程"的升级版见 ex04：
// 那里 Service 只声明自己需要的 Store 接口，main 负责注入。
type Service struct {
	store *store.Store
}

func New(s *store.Store) *Service {
	return &Service{store: s}
}

// Add 的业务规则：标题去除首尾空白后非空才允许创建。
func (s *Service) Add(title string) (todo.Todo, error) {
	title = strings.TrimSpace(title)
	if title == "" {
		return todo.Todo{}, fmt.Errorf("%w: title is required", ErrBadRequest)
	}
	id, err := newID()
	if err != nil {
		return todo.Todo{}, fmt.Errorf("generate id: %w", err)
	}
	t := todo.Todo{ID: id, Title: title}
	if err := s.store.Save(t); err != nil {
		return todo.Todo{}, fmt.Errorf("save todo: %w", err)
	}
	return t, nil
}

func (s *Service) Get(id string) (todo.Todo, error) {
	t, err := s.store.Get(id)
	if err != nil {
		// 包装时带上"操作对象"上下文；store 的哨兵错误仍可被 errors.Is 命中
		return todo.Todo{}, fmt.Errorf("get todo %s: %w", id, err)
	}
	return t, nil
}

// List 按 ID 排序返回，保证响应顺序稳定（map 遍历无序，见 store.List）。
func (s *Service) List() ([]todo.Todo, error) {
	items, err := s.store.List()
	if err != nil {
		return nil, fmt.Errorf("list todos: %w", err)
	}
	sort.Slice(items, func(i, j int) bool { return items[i].ID < items[j].ID })
	return items, nil
}

// Toggle 的业务规则：只有存在的 todo 才能切换完成态。
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

// Delete 的业务规则：只有存在的 todo 才能删除（store.Delete 已保证）。
func (s *Service) Delete(id string) error {
	if err := s.store.Delete(id); err != nil {
		return fmt.Errorf("delete todo %s: %w", id, err)
	}
	return nil
}

// newID 生成 64 位随机 hex 作为 ID（教学实现；真实项目常用数据库自增/UUID）。
func newID() (string, error) {
	b := make([]byte, 8)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}
