// 来源：ph17-architecture-layering exercises/sol-03-service-unit-tests/internal/service
// 一句话说明：被测试对象——纯业务层，不含 HTTP、不含具体存储。
// service_test.go 用 stub 替身替掉 Store 后，规则（去空白、非空、唯一、存在才切换）
// 就能被表驱动单测覆盖，无需起服务器或真数据库。
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

	"tenetlang/go/ph17-architecture-layering/exercises/sol-03-service-unit-tests/internal/todo"
)

// Store 消费方声明的存储接口（只有 service 用得到的方法）。
type Store interface {
	Get(id string) (todo.Todo, error)
	Save(t todo.Todo) error
	Delete(id string) error
	List() ([]todo.Todo, error)
}

var (
	ErrBadRequest = errors.New("bad request")
	ErrExists     = errors.New("todo already exists")
)

type Service struct {
	store Store
}

func New(store Store) *Service {
	return &Service{store: store}
}

// Add 的规则：id/title 去空白后非空；id 不得与已有记录重复。
func (s *Service) Add(id, title string) (todo.Todo, error) {
	id = strings.TrimSpace(id)
	title = strings.TrimSpace(title)
	if id == "" || title == "" {
		return todo.Todo{}, fmt.Errorf("%w: id and title are required", ErrBadRequest)
	}
	if _, err := s.store.Get(id); err == nil {
		return todo.Todo{}, fmt.Errorf("%w: %s", ErrExists, id)
	} else if !errors.Is(err, todo.ErrNotFound) {
		return todo.Todo{}, fmt.Errorf("check existing %s: %w", id, err)
	}
	t := todo.Todo{ID: id, Title: title}
	if err := s.store.Save(t); err != nil {
		return todo.Todo{}, fmt.Errorf("save %s: %w", id, err)
	}
	return t, nil
}

func (s *Service) Get(id string) (todo.Todo, error) {
	t, err := s.store.Get(id)
	if err != nil {
		return todo.Todo{}, fmt.Errorf("get %s: %w", id, err)
	}
	return t, nil
}

// Toggle 的规则：只切换存在的 todo。
func (s *Service) Toggle(id string) (todo.Todo, error) {
	t, err := s.store.Get(id)
	if err != nil {
		return todo.Todo{}, fmt.Errorf("toggle %s: %w", id, err)
	}
	t.Done = !t.Done
	if err := s.store.Save(t); err != nil {
		return todo.Todo{}, fmt.Errorf("toggle %s: %w", id, err)
	}
	return t, nil
}
