// 来源：project/ —— 标准 Go 项目模板 internal 业务层
// 一句话说明：internal/device 设备管理业务：增删改查 + 状态校验 + JSON 文件持久化。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd project && go run ./cmd/device-cli add -id D01 -name "温度传感器"
// 验证状态：已验证（Go 1.22.2）
package device

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"tenetlang/go/ph05-pkg-structure/project/pkg/status"
)

// ErrNotFound 哨兵错误：操作不存在的设备时返回，调用方用 errors.Is 判断
var ErrNotFound = errors.New("device: not found")

// Device 设备记录
type Device struct {
	ID    string `json:"id"`
	Name  string `json:"name"`
	Type  string `json:"type"`
	State string `json:"state"`
}

// Store 设备存储：内存 map + 每次变更写回 JSON 文件，跨进程数据不丢
type Store struct {
	path    string
	devices map[string]Device
}

// NewStore 从文件加载设备；文件不存在时返回空存储（首次运行）
func NewStore(path string) (*Store, error) {
	s := &Store{path: path, devices: map[string]Device{}}
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return s, nil
	}
	if err != nil {
		return nil, fmt.Errorf("device: read %s: %w", path, err)
	}
	if len(data) == 0 {
		return s, nil
	}
	if err := json.Unmarshal(data, &s.devices); err != nil {
		return nil, fmt.Errorf("device: parse %s: %w", path, err)
	}
	return s, nil
}

// Add 新增设备；ID 冲突、ID/名称为空、状态非法均拒绝
func (s *Store) Add(d Device) error {
	if d.ID == "" || d.Name == "" {
		return fmt.Errorf("device: ID 与名称不能为空")
	}
	if _, ok := s.devices[d.ID]; ok {
		return fmt.Errorf("device: ID %q 已存在", d.ID)
	}
	if d.State == "" {
		d.State = status.Offline // 默认离线
	}
	if !status.Valid(d.State) {
		return fmt.Errorf("device: 非法状态 %q（可选 online/offline/fault）", d.State)
	}
	s.devices[d.ID] = d
	return s.persist()
}

// SetState 更新设备状态；ID 不存在或状态非法返回错误
func (s *Store) SetState(id, st string) error {
	if !status.Valid(st) {
		return fmt.Errorf("device: 非法状态 %q（可选 online/offline/fault）", st)
	}
	d, ok := s.devices[id]
	if !ok {
		return fmt.Errorf("device: 更新 %q: %w", id, ErrNotFound)
	}
	d.State = st
	s.devices[id] = d
	return s.persist()
}

// Delete 删除设备；不存在返回包装的 ErrNotFound
func (s *Store) Delete(id string) error {
	if _, ok := s.devices[id]; !ok {
		return fmt.Errorf("device: 删除 %q: %w", id, ErrNotFound)
	}
	delete(s.devices, id)
	return s.persist()
}

// List 返回全部设备，按 ID 排序保证输出确定性
func (s *Store) List() []Device {
	ids := make([]string, 0, len(s.devices))
	for id := range s.devices {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	out := make([]Device, 0, len(ids))
	for _, id := range ids {
		out = append(out, s.devices[id])
	}
	return out
}

// persist 把当前内存状态写回 JSON 文件——先确保父目录存在
func (s *Store) persist() error {
	if dir := filepath.Dir(s.path); dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return fmt.Errorf("device: mkdir %s: %w", dir, err)
		}
	}
	data, err := json.MarshalIndent(s.devices, "", "  ")
	if err != nil {
		return fmt.Errorf("device: marshal: %w", err)
	}
	if err := os.WriteFile(s.path, data, 0o644); err != nil {
		return fmt.Errorf("device: write %s: %w", s.path, err)
	}
	return nil
}
