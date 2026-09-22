// 来源：ph17-architecture-layering exercises/sol-02-store-interface/internal/store/file.go
// 一句话说明：存储接口的第二个实现——JSON 文件版（进程重启数据仍在）。
// 与 Mem 实现同一套方法签名，service 不需要知道"现在是内存还是文件"。
// 实现说明：内存副本 + 写操作后整体落盘（教学实现；真实场景用数据库事务）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package store

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"sort"
	"sync"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-02-store-interface/internal/todo"
)

// File 文件实现：JSON 数组持久化，每次写操作整表落盘。
type File struct {
	path string
	mu   sync.Mutex
	m    map[string]todo.Todo
}

// NewFile 打开（或首次创建）数据文件。
func NewFile(path string) (*File, error) {
	f := &File{path: path, m: make(map[string]todo.Todo)}
	data, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return f, nil // 首次运行：空库
		}
		return nil, fmt.Errorf("read store file %s: %w", path, err)
	}
	var items []todo.Todo
	if len(data) > 0 {
		if err := json.Unmarshal(data, &items); err != nil {
			return nil, fmt.Errorf("parse store file %s: %w", path, err)
		}
		for _, t := range items {
			f.m[t.ID] = t
		}
	}
	return f, nil
}

func (s *File) Get(id string) (todo.Todo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	t, ok := s.m[id]
	if !ok {
		return todo.Todo{}, todo.ErrNotFound
	}
	return t, nil
}

func (s *File) Save(t todo.Todo) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.m[t.ID] = t
	return s.persist()
}

func (s *File) Delete(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.m[id]; !ok {
		return todo.ErrNotFound
	}
	delete(s.m, id)
	return s.persist()
}

func (s *File) List() ([]todo.Todo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]todo.Todo, 0, len(s.m))
	for _, t := range s.m {
		out = append(out, t)
	}
	return out, nil
}

// persist 把整表写成排序后的 JSON 数组（排序让文件 diff 稳定）。
// 调用方须已持有 s.mu（Save/Delete 内调用）。
func (s *File) persist() error {
	items := make([]todo.Todo, 0, len(s.m))
	for _, t := range s.m {
		items = append(items, t)
	}
	sort.Slice(items, func(i, j int) bool { return items[i].ID < items[j].ID })
	data, err := json.MarshalIndent(items, "", "  ")
	if err != nil {
		return fmt.Errorf("encode store: %w", err)
	}
	if err := os.WriteFile(s.path, data, 0o644); err != nil {
		return fmt.Errorf("write store file %s: %w", s.path, err)
	}
	return nil
}
