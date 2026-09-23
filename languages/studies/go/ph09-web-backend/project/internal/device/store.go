// 来源：ph09-web-backend 阶段项目 —— 设备数据上报 API（internal/device 包）
// 一句话说明：内存设备存储（RWMutex 保护，ph10 换数据库）；Store 接口隔离存储细节，
// 测试可注入 stub（ph08「接口有助于隔离测试依赖」落地）。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go test -v ./internal/device
//	go test -race ./internal/device
//
// 验证状态：已验证（go1.25.6）
package device

import (
	"errors"
	"sync"
	"time"
)

// ErrNotFound 设备不存在（哨兵错误，调用方用 errors.Is 判断）
var ErrNotFound = errors.New("device not found")

// Device 设备状态（对外 JSON 字段）；Secret 不参与序列化
type Device struct {
	ID        string    `json:"id"`
	Status    string    `json:"status"`
	Speed     float64   `json:"speed"`
	Lat       float64   `json:"lat"`
	Lng       float64   `json:"lng"`
	UpdatedAt time.Time `json:"updated_at"`
	Secret    string    `json:"-"`
}

// Store 设备数据访问接口：api 层只依赖这个接口
type Store interface {
	// List 按状态过滤（status 为空返回全部）
	List(status string) []Device
	// Get 查询单个
	Get(id string) (Device, bool)
	// Report 上报：校验通过后更新速度/位置/状态
	Report(id string, speed, lat, lng float64) (Device, error)
	// ValidSecret 校验设备密钥（设备认证用）
	ValidSecret(id, secret string) bool
}

// memoryStore 并发安全的内存实现
type memoryStore struct {
	mu       sync.RWMutex
	devices map[string]Device
}

// NewMemoryStore 用种子设备构建内存存储（Seeds 传入预置设备，Secret 一并预置）
func NewMemoryStore(seeds ...Device) Store {
	vs := make(map[string]Device, len(seeds))
	for _, v := range seeds {
		vs[v.ID] = v
	}
	return &memoryStore{devices: vs}
}

func (s *memoryStore) List(status string) []Device {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]Device, 0, len(s.devices))
	for _, v := range s.devices {
		if status == "" || v.Status == status {
			out = append(out, v)
		}
	}
	return out
}

func (s *memoryStore) Get(id string) (Device, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	v, ok := s.devices[id]
	return v, ok
}

// Report 更新设备状态（业务层已完成校验，这里只做写入）
func (s *memoryStore) Report(id string, speed, lat, lng float64) (Device, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	v, ok := s.devices[id]
	if !ok {
		return Device{}, ErrNotFound
	}
	v.Speed = speed
	v.Lat = lat
	v.Lng = lng
	v.Status = "online" // 上报即视为在线
	v.UpdatedAt = time.Now()
	s.devices[id] = v
	return v, nil
}

func (s *memoryStore) ValidSecret(id, secret string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	v, ok := s.devices[id]
	return ok && v.Secret != "" && v.Secret == secret
}
