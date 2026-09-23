// 来源：ph18-api-design-compat project/internal/devices/store.go
// 一句话说明：内存存储（本项目的持久层刻意最简——ph18 焦点是 API 契约与兼容，
// 存储形态 ph10/ph17 已覆盖）。对外提供确定的遍历顺序：按 ID 排序返回，翻页
// 契约的前提是底层顺序稳定（主文档 3.5）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package devices

import (
	"fmt"
	"sort"
	"sync"
)

// Store 并发安全的内存设备存储。
type Store struct {
	mu   sync.RWMutex
	next int
	byID map[string]Device
}

// NewStore 构造存储。
func NewStore() *Store {
	return &Store{next: 2, byID: map[string]Device{
		"dev-001": {ID: "dev-001", Name: "1号设备", Online: true, Model: "M300", LastSeen: 1700000000},
		"dev-002": {ID: "dev-002", Name: "2号设备", Online: false, Model: "M200", LastSeen: 0},
	}}
}

// All 返回全部设备（按 ID 升序），返回副本。
func (s *Store) All() []Device {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]Device, 0, len(s.byID))
	for _, d := range s.byID {
		out = append(out, d)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out
}

// Get 取单个设备。
func (s *Store) Get(id string) (Device, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	d, ok := s.byID[id]
	return d, ok
}

// Add 分配 ID 并保存。
func (s *Store) Add(name string) Device {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.next++
	d := Device{ID: fmt.Sprintf("dev-%03d", s.next), Name: name}
	s.byID[d.ID] = d
	return d
}

// Delete 删除设备（幂等）。
func (s *Store) Delete(id string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.byID, id)
}
