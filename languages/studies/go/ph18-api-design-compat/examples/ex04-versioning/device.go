// 来源：ph18-api-design-compat examples/ex04-versioning/device.go
// 一句话说明：领域对象与按版本裁剪的 DTO。本示例演示 URI 版本共存的核心形态：
// /v1/devices/{id} 与 /v2/devices/{id} 共享同一份领域数据与同一个 service，
// 差异只在"入口各自把领域对象裁剪成自己版本承诺的 DTO 形状"（主文档 3.3）。
// 版本演进：v1 只有 name+online；v2 新增 model 与 lastSeen —— v1 响应不得泄漏 v2 新字段。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18104
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"fmt"
	"sync"
)

// Device 领域模型：服务内部唯一真相源，字段用业务语言，无 json tag——
// 它不属于任何版本，对外长什么样由各版本的 DTO 决定（ph17 3.2 的"domain 不该被
// HTTP 格式绑架"，本示例兑现成"每个版本一个 DTO"）。
type Device struct {
	ID       string
	Name     string
	Online   bool
	Model    string // v2 才对外暴露
	LastSeen int64  // v2 才对外暴露：unix 秒
}

// deviceV1 v1 版本的响应 DTO：只含 v1 发布时承诺的字段。
type deviceV1 struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Online bool   `json:"online"`
}

// deviceV2 v2 版本的响应 DTO：v1 字段 + 追加字段（字段只增不删的落地形态）。
type deviceV2 struct {
	ID       string `json:"id"`
	Name     string `json:"name"`
	Online   bool   `json:"online"`
	Model    string `json:"model"`
	LastSeen int64  `json:"lastSeen"`
}

// toV1 / toV2 是显式裁剪函数：v2 加字段时，v1 的裁剪函数一个字节都不改。
func toV1(d Device) deviceV1 { return deviceV1{ID: d.ID, Name: d.Name, Online: d.Online} }

func toV2(d Device) deviceV2 {
	return deviceV2{ID: d.ID, Name: d.Name, Online: d.Online, Model: d.Model, LastSeen: d.LastSeen}
}

// Store 内存存储（版本演示够用即可，并发安全）。
type Store struct {
	mu   sync.RWMutex
	next int
	byID map[string]Device
}

// NewStore 构造存储。
func NewStore() *Store { return &Store{byID: make(map[string]Device)} }

// Seed 注入预置数据，便于 curl 冒烟。
func (s *Store) Seed() {
	s.next = 3
	s.byID = map[string]Device{
		"car-001": {ID: "car-001", Name: "1号设备", Online: true, Model: "M300", LastSeen: 1700000000},
		"car-002": {ID: "car-002", Name: "2号设备", Online: false, Model: "M300", LastSeen: 0},
	}
}

// Get 取单个设备。
func (s *Store) Get(id string) (Device, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	d, ok := s.byID[id]
	if !ok {
		return Device{}, fmt.Errorf("device %s not found", id)
	}
	return d, nil
}
