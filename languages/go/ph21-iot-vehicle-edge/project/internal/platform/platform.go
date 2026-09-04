// 来源：ph21-iot-vehicle-edge project/internal/platform/platform.go
// 一句话说明：云端接入核心——网关级 token 鉴权(3.2)、上行批幂等(3.3)、样本清洗
// 与换算、时序存储与实时状态(3.8)、告警规则(3.7)、指标计数(3.9)。store 与计数在
// 同包内聚，api 包只做薄 HTTP 层。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package platform

import (
	"errors"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"tenetlang/go/ph21-iot-vehicle-edge/project/internal/auth"
	"tenetlang/go/ph21-iot-vehicle-edge/project/internal/model"
)

// ErrBadRequest 业务校验失败（HTTP 4xx，不算网络错误）。
var ErrBadRequest = errors.New("platform: 非法上行")

// 告警规则（规则即数据：阈值/比较/等级，主文档 3.7）。
type rule struct {
	ID        string
	Threshold float64 // km/h
	Severity  string
}

var speedRules = []rule{
	{ID: "speed-warn", Threshold: 120, Severity: "warn"},
	{ID: "speed-critical", Threshold: 160, Severity: "critical"},
}

// Counters 观测计数（吞吐/错误率素材，api /metrics 输出）。
type Counters struct {
	Ingested atomic.Int64 // 收到的上行批数
	Cleaned  atomic.Int64 // 入库样本数
	Dup      atomic.Int64 // 重复拦截（批或样本）
	AuthFail atomic.Int64 // 鉴权失败
	BadData  atomic.Int64 // 非法批（死信台账计数）
	Alerts   atomic.Int64 // 告警命中
}

// Snapshot 计数快照。
func (c *Counters) Snapshot() (ing, clean, dup, authFail, bad, alerts int64) {
	return c.Ingested.Load(), c.Cleaned.Load(), c.Dup.Load(), c.AuthFail.Load(),
		c.BadData.Load(), c.Alerts.Load()
}

// SeriesPoint 一条时序点。
type SeriesPoint struct {
	TsUnix   int64
	SpeedKmh float64
}

// Store 内存时序存储 + 实时状态 + 水位。
type Store struct {
	mu        sync.RWMutex
	series    map[string][]SeriesPoint // "vin|speed"
	latest    map[string]*model.CleanSample
	watermark map[string]uint64 // 每网关最大已应用批号（ack 水位）
	vehicles  map[string]bool
	startAt   time.Time
}

// NewStore 建存储。
func NewStore() *Store {
	return &Store{
		series:    map[string][]SeriesPoint{},
		latest:    map[string]*model.CleanSample{},
		watermark: map[string]uint64{},
		vehicles:  map[string]bool{},
		startAt:   time.Now(),
	}
}

func (s *Store) appendClean(cs model.CleanSample) {
	key := cs.Vin + "|speed"
	s.mu.Lock()
	s.series[key] = append(s.series[key], SeriesPoint{TsUnix: cs.TsUnix, SpeedKmh: cs.SpeedKmh})
	cp := cs
	s.latest[cs.Vin] = &cp
	s.vehicles[cs.Vin] = true
	s.mu.Unlock()
}

// LatestSpeed 某车最新速度（km/h）。
func (s *Store) LatestSpeed(vin string) (float64, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	cs, ok := s.latest[vin]
	if !ok {
		return 0, false
	}
	return cs.SpeedKmh, true
}

// Vehicles 全部已上报车辆。
func (s *Store) Vehicles() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]string, 0, len(s.vehicles))
	for v := range s.vehicles {
		out = append(out, v)
	}
	return out
}

// SampleCount 已入库样本总数（测试/运维视图）。
func (s *Store) SampleCount() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	n := 0
	for _, pts := range s.series {
		n += len(pts)
	}
	return n
}

// Ack 返回某网关注册的最高连续 ack 水位（幂等重放时原样返回）。
func (s *Store) Ack(gatewayID string) uint64 {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.watermark[gatewayID]
}

// Core 平台核心。
type Core struct {
	auth    *auth.Registry
	store   *Store
	Count   Counters
	seenMu  sync.Mutex
	seen    map[string]struct{} // "gw:batch" 与 "vin:seq" 共用的有界去重窗
	ring    []string
	seenCap int
}

// NewCore 建平台核心。
func NewCore(secrets map[string]string) *Core {
	return &Core{
		auth:    auth.NewRegistry(secrets),
		store:   NewStore(),
		seen:    map[string]struct{}{},
		seenCap: 1 << 15,
	}
}

// Store 暴露存储（api/测试查询）。
func (c *Core) Store() *Store { return c.store }

// VerifyGateway 校验网关 token（api 调用；鉴权失败自增计数）。
func (c *Core) VerifyGateway(gatewayID, token string, now time.Time) error {
	if err := c.auth.Verify(gatewayID, token, now); err != nil {
		c.Count.AuthFail.Add(1)
		return err
	}
	return nil
}

// HandleBatch 应用一个上行批：批级幂等 → 样本清洗入库 → ack 水位。
func (c *Core) HandleBatch(b model.BatchUpload, now time.Time) (uint64, error) {
	c.Count.Ingested.Add(1)
	batchKey := b.GatewayID + ":" + fmt.Sprint(b.BatchID)
	if !c.markSeen(batchKey) {
		c.Count.Dup.Add(1)
		// 批重复（网关重放）：直接回已确认水位，不二次生效。
		return c.store.Ack(b.GatewayID), nil
	}
	if err := b.Validate(); err != nil {
		c.Count.BadData.Add(1)
		return 0, fmt.Errorf("%w: %v", ErrBadRequest, err)
	}
	for _, s := range b.Samples {
		if !c.markSeen(s.Vin + ":" + fmt.Sprint(s.Seq)) {
			c.Count.Dup.Add(1)
			continue
		}
		cs := model.CleanSample{Vin: s.Vin, Seq: s.Seq, SpeedKmh: s.Speed * 3.6, TsUnix: now.Unix()}
		c.store.appendClean(cs)
		c.Count.Cleaned.Add(1)
		c.evaluateAlerts(cs)
	}
	c.store.setWatermark(b.GatewayID, b.BatchID)
	return c.store.Ack(b.GatewayID), nil
}

func (c *Core) evaluateAlerts(cs model.CleanSample) {
	for _, r := range speedRules {
		if cs.SpeedKmh > r.Threshold {
			c.Count.Alerts.Add(1)
		}
	}
}

// markSeen 有界去重窗：窗口满时淘汰最老（单调水位语义见 gateway.Spool 注释）。
func (c *Core) markSeen(key string) bool {
	c.seenMu.Lock()
	defer c.seenMu.Unlock()
	if _, ok := c.seen[key]; ok {
		return false
	}
	c.seen[key] = struct{}{}
	c.ring = append(c.ring, key)
	if len(c.ring) > c.seenCap {
		old := c.ring[0]
		c.ring = c.ring[1:]
		delete(c.seen, old)
	}
	return true
}

func (s *Store) setWatermark(gatewayID string, batchID uint64) {
	s.mu.Lock()
	if batchID > s.watermark[gatewayID] {
		s.watermark[gatewayID] = batchID
	}
	s.mu.Unlock()
}
