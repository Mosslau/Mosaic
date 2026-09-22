// 来源：ph21-data-ingest-gateway exercises/sol-02-metrics-receiver/sol02.go
// 一句话说明：练习 2 参考实现——数据源指标数据接收服务的清洗核心：解析 JSON、
// 校验 sourceID/seq/value 量程、按 (sourceID, seq) 有界去重、m/s → %% 换算，输出
// 生效/重复/坏数据三路计数（主文档 3.7 清洗段纪律）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"encoding/json"
	"fmt"
	"strconv"
	"sync"
)

// RawMetrics 上行报文（字段最小集；缺字段即坏数据）。
type RawMetrics struct {
	SourceID string  `json:"sourceID"`
	Seq      uint64  `json:"seq"`
	Value    float64 `json:"value"` // 原始计数（采集端单位：0.1%）
}

// Received 生效（清洗通过）的一条指标。
type Received struct {
	SourceID string
	Seq      uint64
	ValuePct float64 // 换算后统一单位
}

// Receiver 接收/清洗核心。
type Receiver struct {
	window  int // 去重窗口条数（有界）
	mu      sync.Mutex
	seen    map[string]struct{}
	ring    []string
	ceiling map[string]uint64 // 单调水位：乱序迟到拒绝

	okCount   int64
	dupCount  int64
	badCount  int64
	badDetail map[string]int64 // 坏数据按原因分类
}

// NewReceiver 建接收核心，window 为去重窗口上限。
func NewReceiver(window int) *Receiver {
	return &Receiver{
		window:    window,
		seen:      make(map[string]struct{}),
		ceiling:   make(map[string]uint64),
		badDetail: make(map[string]int64),
	}
}

// Handle 处理一条原始报文（[]byte 输入便于接网络层）。返回生效指标或错误。
func (r *Receiver) Handle(raw []byte) (*Received, error) {
	var t RawMetrics
	if err := json.Unmarshal(raw, &t); err != nil {
		return nil, r.bad("json 解析失败")
	}
	switch {
	case t.SourceID == "":
		return nil, r.bad("sourceID 为空")
	case t.Seq == 0:
		return nil, r.bad("seq 非法")
	case t.Value < 0 || t.Value > 1000: // 原始计数 0.1%% 单位，量程 0~1000
		return nil, r.bad("value 超量程")
	}
	key := t.SourceID + ":" + strconv.FormatUint(t.Seq, 10)
	r.mu.Lock()
	if _, ok := r.seen[key]; ok {
		r.mu.Unlock()
		r.dupCount++
		return nil, fmt.Errorf("重复报文")
	}
	if t.Seq <= r.ceiling[t.SourceID] {
		r.mu.Unlock()
		r.dupCount++
		return nil, fmt.Errorf("乱序迟到报文")
	}
	r.seen[key] = struct{}{}
	r.ring = append(r.ring, key)
	r.ceiling[t.SourceID] = t.Seq
	if len(r.ring) > r.window { // 有界窗：裁掉最老
		old := r.ring[0]
		r.ring = r.ring[1:]
		delete(r.seen, old)
	}
	r.mu.Unlock()

	r.okCount++
	return &Received{SourceID: t.SourceID, Seq: t.Seq, ValuePct: t.Value / 10}, nil
}

func (r *Receiver) bad(reason string) error {
	r.mu.Lock()
	r.badCount++
	r.badDetail[reason]++
	r.mu.Unlock()
	return fmt.Errorf("坏数据: %s", reason)
}

// Summary 三路计数汇总。
func (r *Receiver) Summary() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	return fmt.Sprintf("生效 %d / 重复 %d / 坏数据 %d（明细 %v）",
		r.okCount, r.dupCount, r.badCount, r.badDetail)
}
