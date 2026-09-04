// 来源：ph21-iot-vehicle-edge examples/ex04-ota-service/firmware.go
// 一句话说明：OTA 固件版本台账——版本登记、按版本查询、sha256 校验。
// 固件包的完整性校验是 OTA 的生命线：设备只能装"版本台账里 sha256 对得上"的包
// （防中间人/包被篡改，主文档 3.10）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"sort"
	"time"
)

// ErrFirmwareNotFound 版本台账里没有该版本。
var ErrFirmwareNotFound = errors.New("ota: 固件版本不存在")

// Firmware 一个固件版本条目。
type Firmware struct {
	Version    string
	SHA256     string // 整包校验值（生产常配合分片 hash，见主文档 3.10）
	Size       int64
	ReleasedAt time.Time
}

// FirmwareStore 固件版本台账。
type FirmwareStore struct {
	byVersion map[string]Firmware
}

// NewFirmwareStore 建空台账。
func NewFirmwareStore() *FirmwareStore {
	return &FirmwareStore{byVersion: make(map[string]Firmware)}
}

// Register 登记一个新版本；版本号必须全局唯一（重复登记报错）。
func (s *FirmwareStore) Register(f Firmware) error {
	if _, ok := s.byVersion[f.Version]; ok {
		return fmt.Errorf("ota: 版本 %s 已登记", f.Version)
	}
	if len(f.SHA256) != 64 {
		return fmt.Errorf("ota: 版本 %s 的 sha256 非法", f.Version)
	}
	s.byVersion[f.Version] = f
	return nil
}

// Get 按版本号取条目。
func (s *FirmwareStore) Get(version string) (Firmware, error) {
	f, ok := s.byVersion[version]
	if !ok {
		return Firmware{}, fmt.Errorf("%w: %s", ErrFirmwareNotFound, version)
	}
	return f, nil
}

// Versions 返回全部版本（升序，方便找"上一个可用版本"做回滚目标）。
func (s *FirmwareStore) Versions() []string {
	out := make([]string, 0, len(s.byVersion))
	for v := range s.byVersion {
		out = append(out, v)
	}
	sort.Strings(out)
	return out
}

// VerifyContent 校验一段候选固件内容的 sha256 是否与台账一致。
func (s *FirmwareStore) VerifyContent(version string, data []byte) error {
	f, err := s.Get(version)
	if err != nil {
		return err
	}
	sum := sha256.Sum256(data)
	if hex.EncodeToString(sum[:]) != f.SHA256 {
		return fmt.Errorf("ota: 版本 %s 内容校验失败（包被篡改或下载损坏）", version)
	}
	return nil
}
