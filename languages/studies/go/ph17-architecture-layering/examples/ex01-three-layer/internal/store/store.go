// 来源：ph17-architecture-layering examples/ex01-three-layer/internal/store
// 一句话说明：数据访问层（repository）的内存实现。封装"Todo 存哪、怎么查"的全部细节，
// service/handler 不感知 map、锁、未来的数据库——换实现只需在 main 换构造（依赖倒置雏形，
// 抽象成接口的完整版见 ex02/ex04 与 project/）。
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

	"tenetlang/go/ph17-architecture-layering/examples/ex01-three-layer/internal/todo"
)

// ErrNotFound 是存储层哨兵错误（仿 sql.ErrNoRows 的角色）：表示"没有这条数据"。
// service 通过 errors.Is 把它翻译成业务语义，handler 再映射成 HTTP 404——
// 每一层只认自己那一级的错误词汇（主文档 3.6 错误码与错误包装）。
var ErrNotFound = errors.New("todo not found")

// Store 是内存版 repository：map + 互斥锁，线程安全。
type Store struct {
	mu    sync.Mutex
	items map[string]todo.Todo
}

func New() *Store {
	return &Store{items: make(map[string]todo.Todo)}
}

// Get 找不到返回 ErrNotFound（值错误用哨兵，类型错误用自定义类型，见主文档 3.6）。
func (s *Store) Get(id string) (todo.Todo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	t, ok := s.items[id]
	if !ok {
		return todo.Todo{}, ErrNotFound
	}
	return t, nil
}

// Save 是 upsert：新增与更新走同一条路，让 service 不必区分。
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
