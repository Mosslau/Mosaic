// 来源：ph17-architecture-layering exercises/sol-01-layered-todo/internal/store
// 一句话说明：练习 1 参考实现的 repository（内存实现）。职责 = 存与取，
// 不含"标题非空""优先级合法"这类业务判断（那是 service 的事）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package store

import (
	"errors"
	"sync"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-01-layered-todo/internal/todo"
)

// ErrNotFound 存储层哨兵：service 用 errors.Is 判断，handler 映射 404。
var ErrNotFound = errors.New("todo not found")

type Store struct {
	mu    sync.Mutex
	items map[string]todo.Todo
}

func New() *Store {
	return &Store{items: make(map[string]todo.Todo)}
}

func (s *Store) Get(id string) (todo.Todo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	t, ok := s.items[id]
	if !ok {
		return todo.Todo{}, ErrNotFound
	}
	return t, nil
}

func (s *Store) Save(t todo.Todo) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.items[t.ID] = t
	return nil
}

func (s *Store) Delete(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.items[id]; !ok {
		return ErrNotFound
	}
	delete(s.items, id)
	return nil
}

func (s *Store) List() ([]todo.Todo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]todo.Todo, 0, len(s.items))
	for _, t := range s.items {
		out = append(out, t)
	}
	return out, nil
}
