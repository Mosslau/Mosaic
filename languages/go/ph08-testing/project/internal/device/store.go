// 来源：ph08-testing 阶段项目 —— 带测试的设备管理 HTTP API
// 一句话说明：设备存储层，接口 + 内存实现（RWMutex 保护，并发安全）。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -race -v ./internal/device
//
// 验证状态：已验证（go1.25.6）
package device

import (
	"errors"
	"sort"
	"sync"
)

// ErrDuplicate Create 时 ID 已存在
var ErrDuplicate = errors.New("device already exists")

// Device 设备记录
type Device struct {
	ID     string `json:"id"`
	Status string `json:"status"`
}

// Store 设备存储接口：业务与 API 层只依赖它，测试可注入 stub（ph08 必会概念）
type Store interface {
	List() []Device
	Get(id string) (Device, bool)
	Create(d Device) error
	Delete(id string) bool
}

// MemoryStore 内存实现：RWMutex 保护共享 map（真实数据库属 ph10 数据库阶段）
type MemoryStore struct {
	mu   sync.RWMutex
	data map[string]Device
}

// NewMemoryStore 创建内存存储，可传入种子数据
func NewMemoryStore(seed ...Device) *MemoryStore {
	s := &MemoryStore{data: make(map[string]Device, len(seed))}
	for _, d := range seed {
		s.data[d.ID] = d
	}
	return s
}

// List 返回全部设备，按 ID 排序保证输出稳定
func (s *MemoryStore) List() []Device {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]Device, 0, len(s.data))
	for _, d := range s.data {
		out = append(out, d)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out
}

// Get 按 ID 查询；第二个返回值表示是否存在
func (s *MemoryStore) Get(id string) (Device, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	d, ok := s.data[id]
	return d, ok
}

// Create 新增设备；ID 已存在时返回 ErrDuplicate
func (s *MemoryStore) Create(d Device) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.data[d.ID]; ok {
		return ErrDuplicate
	}
	s.data[d.ID] = d
	return nil
}

// Delete 删除设备；返回是否真的删掉了（不存在则为 false）
func (s *MemoryStore) Delete(id string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.data[id]; !ok {
		return false
	}
	delete(s.data, id)
	return true
}
