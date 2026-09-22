// 来源：ph21-data-ingest-gateway examples/ex03-websocket-configState/configState.go
// 一句话说明：采集端配置状态——每个数据源一份 desired/reported JSON + 单调 version。
// 版本单调是本例的核心纪律：并发操作各自带 baseVersion 提交，旧版本被拒
// （ErrStaleUpdate），防止"后到的旧指令覆盖新状态"（主文档 3.6）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18880   验证状态：已验证（127.0.0.1 真 TCP 实测）
package main

import (
	"errors"
	"fmt"
	"sync"
)

// ErrStaleUpdate 提交携带的 baseVersion 已过期。
var ErrStaleUpdate = errors.New("configState: stale update")

// ConfigState 每个数据源一份的配置状态。
type ConfigState struct {
	mu       sync.Mutex
	desired  map[string]any // 云端想让它成为的（指令/配置目标）
	reported map[string]any // 采集端自报的现状
	version  int64          // 每次变更 +1，单调；面板"后到覆盖先到"的依据
}

// NewConfigState 从初始 reported 建配置状态（version 从 1 起）。
func NewConfigState(reported map[string]any) *ConfigState {
	return &ConfigState{desired: map[string]any{}, reported: clone(reported), version: 1}
}

// Report 采集端上报 reported（合并字段级覆盖，ph20 合并语义同构），返回新版本。
func (s *ConfigState) Report(reported map[string]any) int64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.reported = merge(s.reported, reported)
	s.version++
	return s.version
}

// ApplyDesired 云端设置 desired；baseVersion 必须等于当前版本（CAS 语义），
// 否则返回 ErrStaleUpdate——调用方（指令服务）据此重拉配置状态再重试。
func (s *ConfigState) ApplyDesired(desired map[string]any, baseVersion int64) (int64, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if baseVersion != s.version {
		return 0, fmt.Errorf("%w: base=%d 当前=%d", ErrStaleUpdate, baseVersion, s.version)
	}
	s.desired = merge(s.desired, desired)
	s.version++
	return s.version, nil
}

// Snapshot 读当前配置状态（用于推送给订阅方/查询 API）。
func (s *ConfigState) Snapshot() (desired, reported map[string]any, version int64) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return clone(s.desired), clone(s.reported), s.version
}

// merge 字段级覆盖：b 的同名键覆盖 a，非同名键保留（浅层 map 即够教学）。
func merge(a, b map[string]any) map[string]any {
	out := make(map[string]any, len(a)+len(b))
	for k, v := range a {
		out[k] = v
	}
	for k, v := range b {
		out[k] = v
	}
	return out
}

func clone(m map[string]any) map[string]any {
	out := make(map[string]any, len(m))
	for k, v := range m {
		out[k] = v
	}
	return out
}
