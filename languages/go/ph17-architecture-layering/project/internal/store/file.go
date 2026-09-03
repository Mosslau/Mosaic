// 来源：ph17-architecture-layering project/internal/store/file.go
// 一句话说明：存储实现之二——JSON 文件版（重启数据仍在，与 Mem 形成对照）。
// 与 Mem 同一套方法签名，service 无感知：换存储只改 cmd/deviceapi 的一处 switch。
// 实现：内存副本 + 每次写操作后整表落盘（教学实现；真实场景应换数据库）。
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

	"tenetlang/go/ph17-architecture-layering/project/internal/domain"
)

// File 文件 repository：JSON 数组持久化。
type File struct {
	path string
	mu   sync.Mutex
	m    map[string]domain.Device
}

// NewFile 打开（或首次创建）数据文件；文件损坏时启动期即报错（fail-fast）。
func NewFile(path string) (*File, error) {
	f := &File{path: path, m: make(map[string]domain.Device)}
	data, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return f, nil // 首次运行：空库
		}
		return nil, fmt.Errorf("read store file %s: %w", path, err)
	}
	var devices []domain.Device
	if len(data) > 0 {
		if err := json.Unmarshal(data, &devices); err != nil {
			return nil, fmt.Errorf("parse store file %s: %w", path, err)
		}
		for _, d := range devices {
			f.m[d.ID] = d
		}
	}
	return f, nil
}

func (s *File) Get(id string) (domain.Device, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	d, ok := s.m[id]
	if !ok {
		return domain.Device{}, domain.ErrNotFound
	}
	return d, nil
}

func (s *File) List() ([]domain.Device, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]domain.Device, 0, len(s.m))
	for _, d := range s.m {
		out = append(out, d)
	}
	return out, nil
}

func (s *File) Save(d domain.Device) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.m[d.ID] = d
	return s.persist()
}

func (s *File) Delete(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.m[id]; !ok {
		return domain.ErrNotFound
	}
	delete(s.m, id)
	return s.persist()
}

// persist 整表写盘（调用方须已持有 s.mu）。排序后写入让文件 diff 稳定。
func (s *File) persist() error {
	devices := make([]domain.Device, 0, len(s.m))
	for _, d := range s.m {
		devices = append(devices, d)
	}
	sort.Slice(devices, func(i, j int) bool { return devices[i].ID < devices[j].ID })
	data, err := json.MarshalIndent(devices, "", "  ")
	if err != nil {
		return fmt.Errorf("encode store: %w", err)
	}
	if err := os.WriteFile(s.path, data, 0o644); err != nil {
		return fmt.Errorf("write store file %s: %w", s.path, err)
	}
	return nil
}
