// 来源：ph17-architecture-layering exercises/sol-02-store-interface/internal/store/mem.go
// 一句话说明：存储接口的第一个实现——内存版。本包不 import service：
// Mem 是否满足 service.Store 由 main 里的 var _ 断言保证（组装点见 main.go）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package store

import (
	"sync"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-02-store-interface/internal/todo"
)

// Mem 内存实现：进程重启即丢失（与 File 形成对照——换实现证明接口真的隔离了存储）。
type Mem struct {
	mu    sync.Mutex
	items map[string]todo.Todo
}

func NewMem() *Mem {
	return &Mem{items: make(map[string]todo.Todo)}
}

func (s *Mem) Get(id string) (todo.Todo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	t, ok := s.items[id]
	if !ok {
		return todo.Todo{}, todo.ErrNotFound
	}
	return t, nil
}

func (s *Mem) Save(t todo.Todo) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.items[t.ID] = t
	return nil
}

func (s *Mem) Delete(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.items[id]; !ok {
		return todo.ErrNotFound
	}
	delete(s.items, id)
	return nil
}

func (s *Mem) List() ([]todo.Todo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]todo.Todo, 0, len(s.items))
	for _, t := range s.items {
		out = append(out, t)
	}
	return out, nil
}
