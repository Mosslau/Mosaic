// 来源：ph21-data-ingest-gateway examples/ex06-metrics-platform/pipeline.go
// 一句话说明：指标数据平台最小闭环——接入(计数)→清洗(校验/去重/换算)→时序存储
// + 实时状态缓存 → 告警规则 → Prometheus 文本指标/查询。Kafka 段即 ph19 的
// fleet.metrics.v1 消费链路（此处不重复实现，主文档 3.7 数据链路图）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"errors"
	"fmt"
	"strconv"
	"sync"
	"time"
)

// Event 一条接入原始事件（ts_ingest 由接入层打，ts_agent 由采集端带，主文档 3.7）。
type Event struct {
	SourceID string
	Seq      uint64
	Value    float64   // 采集量值 m/s（采集端单位）
	TsDev    int64     // 采集端时钟秒
	Ts       time.Time // 到达时间（平台对齐时基）
}

// CleanEvent 清洗后的规范事件（value 已换算 %%）。
type CleanEvent struct {
	SourceID string
	Seq      uint64
	ValuePct float64
	Ts       time.Time
}

// 清洗错误分类（毒消息进"死信台账"而不是静默丢，主文档 3.7/3.9 纪律）。
var (
	ErrBadSourceID = errors.New("clean: sourceID 非法")
	ErrBadSeq      = errors.New("clean: seq 非法")
	ErrRange       = errors.New("clean: 超量程")
	ErrBadTs       = errors.New("clean: 时间戳非法")
	ErrDuplicate   = errors.New("clean: 重复事件")
)

// Cleaner 清洗器：纯函数流水线，输入事件输出规范事件；坏数据计数分类。
type Cleaner struct {
	mu    sync.Mutex
	seen  map[string]uint64 // (sourceID,seq) 幂等（离线形态；生产同构 ex02 Deduper）
	byErr map[string]int64
}

// NewCleaner 建清洗器。
func NewCleaner() *Cleaner {
	return &Cleaner{seen: map[string]uint64{}, byErr: map[string]int64{}}
}

// Clean 清洗一条：返回 (规范事件 or nil, 错误)。错误即"死信分类"（可审计计数）。
func (c *Cleaner) Clean(ev Event) (*CleanEvent, error) {
	if ev.SourceID == "" {
		return nil, c.markErr(ErrBadSourceID)
	}
	if ev.Seq == 0 {
		return nil, c.markErr(ErrBadSeq)
	}
	if ev.Value < 0 || ev.Value > 1000 { // 原始计数 0.1%% 单位，量程 0~1000（=0~100%%），超量程即坏
		return nil, c.markErr(ErrRange)
	}
	if ev.Ts.IsZero() {
		return nil, c.markErr(ErrBadTs)
	}
	key := ev.SourceID + ":" + strconv.FormatUint(ev.Seq, 10)
	c.mu.Lock()
	if _, dup := c.seen[key]; dup {
		c.mu.Unlock()
		return nil, c.markErr(ErrDuplicate)
	}
	c.seen[key] = ev.Seq
	c.mu.Unlock()
	// m/s → %% 换算：统一为展示单位（换算留 raw 由上游保证，主文档 3.7）。
	return &CleanEvent{SourceID: ev.SourceID, Seq: ev.Seq, ValuePct: ev.Value / 10, Ts: ev.Ts}, nil
}

func (c *Cleaner) markErr(err error) error {
	c.mu.Lock()
	c.byErr[err.Error()]++
	c.mu.Unlock()
	return err
}

// ErrCounts 返回各错误分类计数（坏数据台账）。
func (c *Cleaner) ErrCounts() map[string]int64 {
	c.mu.Lock()
	defer c.mu.Unlock()
	out := make(map[string]int64, len(c.byErr))
	for k, v := range c.byErr {
		out[k] = v
	}
	return out
}

// Dropped 清洗丢弃总数。
func (c *Cleaner) Dropped() int64 {
	c.mu.Lock()
	defer c.mu.Unlock()
	var n int64
	for _, v := range c.byErr {
		n += v
	}
	return n
}

// Platform 平台聚合：接入计数 + 清洗 + 存储/告警/指标 串成一行 Ingest。
type Platform struct {
	Clean   *Cleaner
	Store   *TSStore
	Status  *StatusCache
	Alerts  *AlertEngine
	Metrics *Metrics
}

// NewPlatform 建平台。
func NewPlatform() *Platform {
	m := &Metrics{}
	return &Platform{
		Clean:   NewCleaner(),
		Store:   NewTSStore(),
		Status:  NewStatusCache(3 * time.Second),
		Alerts:  NewAlertEngine(),
		Metrics: m,
	}
}

// Ingest 完整链路：接入计数 → 清洗 → 存储/状态/告警。
func (p *Platform) Ingest(ev Event) error {
	p.Metrics.ingested.Add(1)
	ce, err := p.Clean.Clean(ev)
	if err != nil {
		p.Metrics.cleanErr.Add(1)
		return err // 坏数据：调用方/上层决定死信去向（演示直接返回）
	}
	p.Metrics.cleaned.Add(1)
	p.Store.Append(ce.SourceID, "value", Point{Ts: ce.Ts, Value: ce.ValuePct})
	p.Status.Set(ce.SourceID, ce.Ts, map[string]any{"value_pct": ce.ValuePct})
	if alerts := p.Alerts.Evaluate(ce.SourceID, "value", ce.ValuePct, ce.Ts); len(alerts) > 0 {
		p.Metrics.alerts.Add(int64(len(alerts)))
		_ = alerts // 真实系统把告警推 3.4 的实时通道/写告警表
	}
	return nil
}

// 汇总行（演示辅助）。
func (p *Platform) Summary() string {
	var value float64
	if v, ok := p.Status.Latest("src-001"); ok {
		if f, ok := v["value_pct"]; ok {
			value = f.(float64)
		}
	}
	return fmt.Sprintf("接入=%d 清洗成功=%d 坏数据=%d 告警=%d 在线最新采集量值=%.1f%%",
		p.Metrics.ingested.Load(), p.Metrics.cleaned.Load(),
		p.Clean.Dropped(), p.Metrics.alerts.Load(), value)
}
