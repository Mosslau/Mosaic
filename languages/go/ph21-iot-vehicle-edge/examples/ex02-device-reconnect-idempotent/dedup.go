// 来源：ph21-iot-vehicle-edge examples/ex02-device-reconnect-idempotent/dedup.go
// 一句话说明：(deviceID, seq) 幂等去重窗——设备弱网重试会原样重放同一 seq，
// 平台侧必须保证副作用只生效一次：seen 集合挡窗口内重放，seqCeiling 挡乱序迟到。
// 有界环形裁剪窗口（主文档 3.3；离线形态，生产同语义落 DB 唯一约束）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"fmt"
	"sync"
)

// Deduper (vin, seq) 幂等窗。
type Deduper struct {
	mu         sync.Mutex
	window     int // 窗口内最多保留的 (vin,seq) 条数
	seen       map[string]struct{}
	ring       []string          // FIFO 顺序的 key，超窗最老的先淘汰
	seqCeiling map[string]uint64 // 每设备已见最大 seq：比它小的迟到包一律拒
}

// NewDeduper 建去重窗，window 为保留的最近 (vin,seq) 条目数上限。
func NewDeduper(window int) *Deduper {
	return &Deduper{
		window:     window,
		seen:       make(map[string]struct{}),
		seqCeiling: make(map[string]uint64),
	}
}

// FirstTime 若 (vin,seq) 首次生效返回 true，否则为重复/乱序，返回 false。
func (d *Deduper) FirstTime(vin string, seq uint64) bool {
	d.mu.Lock()
	defer d.mu.Unlock()
	key := fmt.Sprintf("%s:%d", vin, seq)
	if _, ok := d.seen[key]; ok {
		return false // 窗口内重放（弱网原样重试最常见路径）
	}
	if seq <= d.seqCeiling[vin] {
		return false // 乱序迟到：序号不比已见最大还新，视为不可信重放
	}
	d.seen[key] = struct{}{}
	d.ring = append(d.ring, key)
	d.seqCeiling[vin] = seq
	// 有界：超窗淘汰最老条目；但 seqCeiling 单调闸仍拦"已淘汰的旧 seq 重放"，
	// 近窗去重 + 远窗单调闸互补。剩余盲区（如设备整机重启把 seq 重置归零、
	// 恶意构造更大 seq）生产用 DB 唯一约束 + 服务端持久水位补齐。
	if len(d.ring) > d.window {
		old := d.ring[0]
		d.ring = d.ring[1:]
		delete(d.seen, old)
	}
	return true
}

// Len 当前窗口占用（供测试断言有界性）。
func (d *Deduper) Len() int {
	d.mu.Lock()
	defer d.mu.Unlock()
	return len(d.ring)
}
