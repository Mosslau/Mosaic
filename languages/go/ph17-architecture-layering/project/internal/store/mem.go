// 来源：ph17-architecture-layering project/internal/store/mem.go
// 一句话说明：存储实现之一——内存版（进程重启即丢）。
// 本包不 import internal/service：Mem 是否满足 service.DeviceStore
// 由组装点 cmd/deviceapi 的 var _ 断言保证（依赖方向保持单向向内）。
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

	"tenetlang/go/ph17-architecture-layering/project/internal/domain"
)

// Mem 内存 repository：map + 互斥锁。
type Mem struct {
	mu sync.Mutex
	m  map[string]domain.Device
}

func NewMem() *Mem {
	return &Mem{m: make(map[string]domain.Device)}
}

func (s *Mem) Get(id string) (domain.Device, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	d, ok := s.m[id]
	if !ok {
		return domain.Device{}, domain.ErrNotFound
	}
	return d, nil
}

func (s *Mem) List() ([]domain.Device, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]domain.Device, 0, len(s.m))
	for _, d := range s.m {
		out = append(out, d)
	}
	return out, nil
}

// Save 是 upsert：新增与更新统一走这里。
func (s *Mem) Save(d domain.Device) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.m[d.ID] = d
	return nil
}

func (s *Mem) Delete(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.m[id]; !ok {
		return domain.ErrNotFound
	}
	delete(s.m, id)
	return nil
}
