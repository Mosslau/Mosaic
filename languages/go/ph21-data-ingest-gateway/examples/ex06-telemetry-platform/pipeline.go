// 来源：ph21-data-ingest-gateway examples/ex06-telemetry-platform/pipeline.go
// 一句话说明：遥测数据平台最小闭环——接入(计数)→清洗(校验/去重/换算)→时序存储
// + 实时状态缓存 → 告警规则 → Prometheus 文本指标/查询。Kafka 段即 ph19 的
// fleet.telemetry.v1 消费链路（此处不重复实现，主文档 3.7 数据链路图）。
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

// Event 一条接入原始事件（ts_ingest 由接入层打，ts_device 由设备带，主文档 3.7）。
type Event struct {
	Vin   string
	Seq   uint64
	Speed float64   // 车速 m/s（设备单位）
	TsDev int64     // 设备时钟秒
	Ts    time.Time // 到达时间（平台对齐时基）
}

// CleanEvent 清洗后的规范事件（speed 已换算 km/h）。
type CleanEvent struct {
	Vin      string
	Seq      uint64
	SpeedKmh float64
	Ts       time.Time
}

// 清洗错误分类（毒消息进"死信台账"而不是静默丢，主文档 3.7/3.9 纪律）。
var (
	ErrBadVin    = errors.New("clean: vin 非法")
	ErrBadSeq    = errors.New("clean: seq 非法")
	ErrRange     = errors.New("clean: 超量程")
	ErrBadTs     = errors.New("clean: 时间戳非法")
	ErrDuplicate = errors.New("clean: 重复事件")
)

// Cleaner 清洗器：纯函数流水线，输入事件输出规范事件；坏数据计数分类。
type Cleaner struct {
	mu    sync.Mutex
	seen  map[string]uint64 // (vin,seq) 幂等（离线形态；生产同构 ex02 Deduper）
	byErr map[string]int64
}

// NewCleaner 建清洗器。
func NewCleaner() *Cleaner {
	return &Cleaner{seen: map[string]uint64{}, byErr: map[string]int64{}}
}

// Clean 清洗一条：返回 (规范事件 or nil, 错误)。错误即"死信分类"（可审计计数）。
func (c *Cleaner) Clean(ev Event) (*CleanEvent, error) {
	if ev.Vin == "" {
		return nil, c.markErr(ErrBadVin)
	}
	if ev.Seq == 0 {
		return nil, c.markErr(ErrBadSeq)
	}
	if ev.Speed < 0 || ev.Speed > 100 { // m/s 量程 0~100（360km/h），超量程即坏
		return nil, c.markErr(ErrRange)
	}
	if ev.Ts.IsZero() {
		return nil, c.markErr(ErrBadTs)
	}
	key := ev.Vin + ":" + strconv.FormatUint(ev.Seq, 10)
	c.mu.Lock()
	if _, dup := c.seen[key]; dup {
		c.mu.Unlock()
		return nil, c.markErr(ErrDuplicate)
	}
	c.seen[key] = ev.Seq
	c.mu.Unlock()
	// m/s → km/h 换算：统一为展示单位（换算留 raw 由上游保证，主文档 3.7）。
	return &CleanEvent{Vin: ev.Vin, Seq: ev.Seq, SpeedKmh: ev.Speed * 3.6, Ts: ev.Ts}, nil
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
	p.Store.Append(ce.Vin, "speed", Point{Ts: ce.Ts, Value: ce.SpeedKmh})
	p.Status.Set(ce.Vin, ce.Ts, map[string]any{"speed_kmh": ce.SpeedKmh})
	if alerts := p.Alerts.Evaluate(ce.Vin, "speed", ce.SpeedKmh, ce.Ts); len(alerts) > 0 {
		p.Metrics.alerts.Add(int64(len(alerts)))
		_ = alerts // 真实系统把告警推 3.4 的实时通道/写告警表
	}
	return nil
}

// 汇总行（演示辅助）。
func (p *Platform) Summary() string {
	var speed float64
	if v, ok := p.Status.Latest("veh-001"); ok {
		if f, ok := v["speed_kmh"]; ok {
			speed = f.(float64)
		}
	}
	return fmt.Sprintf("接入=%d 清洗成功=%d 坏数据=%d 告警=%d 在线最新车速=%.1fkm/h",
		p.Metrics.ingested.Load(), p.Metrics.cleaned.Load(),
		p.Clean.Dropped(), p.Metrics.alerts.Load(), speed)
}
