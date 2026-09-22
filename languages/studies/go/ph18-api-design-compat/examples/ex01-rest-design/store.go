// 来源：ph18-api-design-compat examples/ex01-rest-design/store.go
// 一句话说明：内存存储。本示例的存储刻意保持最简（ph17 已教过分层与存储隔离），
// 把篇幅留给 REST 语义本身——这里只要求"能存能取、并发安全"即可（主文档 3.1）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18101
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"fmt"
	"sync"
)

// ErrNotFound 表示资源不存在（哨兵错误：调用方用 errors.Is 判断，不用字符串比较）。
var ErrNotFound = fmt.Errorf("device not found")

// Store 线程安全的内存设备存储。
type Store struct {
	mu   sync.RWMutex
	next int
	byID map[string]Device
}

// NewStore 返回一个空的设备存储。
func NewStore() *Store {
	return &Store{byID: make(map[string]Device)}
}

// List 返回全部设备，按 ID 排序，避免 map 遍历顺序污染响应（ph18 分页示例 ex03 展开）。
func (s *Store) List() []Device {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]Device, 0, len(s.byID))
	for _, d := range s.byID {
		out = append(out, d) // 值拷贝：调用方改返回切片不影响内部状态
	}
	sortByID(out)
	return out
}

// Get 返回单个设备。
func (s *Store) Get(id string) (Device, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	d, ok := s.byID[id]
	if !ok {
		return Device{}, ErrNotFound
	}
	return d, nil
}

// Create 分配新 ID 并保存，返回创建后的资源。
func (s *Store) Create(name string) Device {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.next++
	d := Device{ID: fmt.Sprintf("dev-%03d", s.next), Name: name}
	s.byID[d.ID] = d
	return d
}

// Replace 全量替换：PUT 语义下请求体是完整表示，缺的字段落零值（主文档 3.1）。
func (s *Store) Replace(id string, d Device) {
	s.mu.Lock()
	defer s.mu.Unlock()
	d.ID = id // ID 以路径为准，不接受 body 改写
	s.byID[id] = d
}

// PatchName 仅更新名字（本示例演示"部分更新只动给出的字段"的最小形态）。
func (s *Store) PatchName(id, name string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	d, ok := s.byID[id]
	if !ok {
		return ErrNotFound
	}
	d.Name = name
	s.byID[id] = d
	return nil
}

// Delete 删除设备。幂等设计：不存在也返回 nil（主文档 3.1 的 DELETE 幂等约定）。
func (s *Store) Delete(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.byID[id]; !ok {
		return nil
	}
	delete(s.byID, id)
	return nil
}
