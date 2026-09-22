// 来源：ph09-web-backend 阶段项目 —— 车辆数据上报 API（internal/vehicle 包）
// 一句话说明：内存车辆存储（RWMutex 保护，ph10 换数据库）；Store 接口隔离存储细节，
// 测试可注入 stub（ph08「接口有助于隔离测试依赖」落地）。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go test -v ./internal/vehicle
//	go test -race ./internal/vehicle
//
// 验证状态：已验证（go1.25.6）
package vehicle

import (
	"errors"
	"sync"
	"time"
)

// ErrNotFound 车辆不存在（哨兵错误，调用方用 errors.Is 判断）
var ErrNotFound = errors.New("vehicle not found")

// Vehicle 车辆状态（对外 JSON 字段）；Secret 不参与序列化
type Vehicle struct {
	ID        string    `json:"id"`
	Status    string    `json:"status"`
	Speed     float64   `json:"speed"`
	Lat       float64   `json:"lat"`
	Lng       float64   `json:"lng"`
	UpdatedAt time.Time `json:"updated_at"`
	Secret    string    `json:"-"`
}

// Store 车辆数据访问接口：api 层只依赖这个接口
type Store interface {
	// List 按状态过滤（status 为空返回全部）
	List(status string) []Vehicle
	// Get 查询单个
	Get(id string) (Vehicle, bool)
	// Report 上报：校验通过后更新速度/位置/状态
	Report(id string, speed, lat, lng float64) (Vehicle, error)
	// ValidSecret 校验设备密钥（设备认证用）
	ValidSecret(id, secret string) bool
}

// memoryStore 并发安全的内存实现
type memoryStore struct {
	mu       sync.RWMutex
	vehicles map[string]Vehicle
}

// NewMemoryStore 用种子车辆构建内存存储（Seeds 传入预置车辆，Secret 一并预置）
func NewMemoryStore(seeds ...Vehicle) Store {
	vs := make(map[string]Vehicle, len(seeds))
	for _, v := range seeds {
		vs[v.ID] = v
	}
	return &memoryStore{vehicles: vs}
}

func (s *memoryStore) List(status string) []Vehicle {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]Vehicle, 0, len(s.vehicles))
	for _, v := range s.vehicles {
		if status == "" || v.Status == status {
			out = append(out, v)
		}
	}
	return out
}

func (s *memoryStore) Get(id string) (Vehicle, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	v, ok := s.vehicles[id]
	return v, ok
}

// Report 更新车辆状态（业务层已完成校验，这里只做写入）
func (s *memoryStore) Report(id string, speed, lat, lng float64) (Vehicle, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	v, ok := s.vehicles[id]
	if !ok {
		return Vehicle{}, ErrNotFound
	}
	v.Speed = speed
	v.Lat = lat
	v.Lng = lng
	v.Status = "online" // 上报即视为在线
	v.UpdatedAt = time.Now()
	s.vehicles[id] = v
	return v, nil
}

func (s *memoryStore) ValidSecret(id, secret string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	v, ok := s.vehicles[id]
	return ok && v.Secret != "" && v.Secret == secret
}
