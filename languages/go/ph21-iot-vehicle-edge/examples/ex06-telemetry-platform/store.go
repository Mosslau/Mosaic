// 来源：ph21-iot-vehicle-edge examples/ex06-telemetry-platform/store.go
// 一句话说明：时序存储最小形态——series(标签) + 时间有序点集；最新值/最近 N 条/
// 区间聚合三种查询模式（主文档 3.8 查询模式表）。生产同语义落时序库/列存，
// 本形态足够教学并离线可测。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"sort"
	"strings"
	"sync"
	"time"
)

// Point 时序数据点。
type Point struct {
	Ts    time.Time
	Value float64
}

// TSStore 时序存储（series 键 = "vehicle|metric"，值是时间有序点集）。
type TSStore struct {
	mu     sync.RWMutex
	series map[string][]Point
}

// NewTSStore 建空时序存储。
func NewTSStore() *TSStore { return &TSStore{series: make(map[string][]Point)} }

// Append 向序列追加一个点（点按时间递增到达，追加前不排序）。
func (s *TSStore) Append(vehicle, metric string, p Point) {
	key := vehicle + "|" + metric
	s.mu.Lock()
	s.series[key] = append(s.series[key], p)
	s.mu.Unlock()
}

func (s *TSStore) get(vehicle, metric string) []Point {
	key := vehicle + "|" + metric
	s.mu.RLock()
	defer s.mu.RUnlock()
	return append([]Point(nil), s.series[key]...)
}

// Latest 最新值（仪表盘"这车现在多快"）。
func (s *TSStore) Latest(vehicle, metric string) (Point, bool) {
	pts := s.get(vehicle, metric)
	if len(pts) == 0 {
		return Point{}, false
	}
	return pts[len(pts)-1], true
}

// Recent 最近 since 以来的点（轨迹回放）。
func (s *TSStore) Recent(vehicle, metric string, since time.Time) []Point {
	pts := s.get(vehicle, metric)
	i := sort.Search(len(pts), func(i int) bool { return !pts[i].Ts.Before(since) })
	return pts[i:]
}

// AggBucket 区间聚合桶。
type AggBucket struct {
	Ts   time.Time // 桶起点
	Avg  float64
	Max  float64
	Hits int
}

// RangeAggregate 把 [from, to) 按 step 分桶聚合（avg/max/hits），时间对齐 in bucket。
func (s *TSStore) RangeAggregate(metric string, from, to time.Time, step time.Duration) []AggBucket {
	// 为了教学简单，聚合所有 vehicle 的同名 metric（真实查询按标签过滤）。
	all := s.all(metric)
	if step <= 0 {
		return nil
	}
	out := []AggBucket{}
	for _, p := range all {
		if p.Ts.Before(from) || !p.Ts.Before(to) {
			continue
		}
		idx := int(p.Ts.Sub(from) / step)
		for len(out) <= idx {
			out = append(out, AggBucket{Ts: from.Add(time.Duration(len(out)) * step)})
		}
		b := &out[idx]
		b.Hits++
		b.Avg += p.Value
		if p.Value > b.Max {
			b.Max = p.Value
		}
	}
	for i := range out {
		if out[i].Hits > 0 {
			out[i].Avg /= float64(out[i].Hits)
		}
	}
	return out
}

func (s *TSStore) all(metric string) []Point {
	s.mu.RLock()
	defer s.mu.RUnlock()
	var out []Point
	for k, pts := range s.series {
		if strings.HasSuffix(k, "|"+metric) {
			out = append(out, pts...)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Ts.Before(out[j].Ts) })
	return out
}

// StatusCache 实时状态缓存（Redis 语义的离线形态：最新值 + TTL 防僵尸）。
type StatusCache struct {
	ttl time.Duration
	mu  sync.RWMutex
	cur map[string]stateEntry
}

type stateEntry struct {
	ts   time.Time
	data map[string]any
}

// NewStatusCache 建状态缓存（ttl 内无更新即视为过期）。
func NewStatusCache(ttl time.Duration) *StatusCache {
	return &StatusCache{ttl: ttl, cur: make(map[string]stateEntry)}
}

// Set 更新某车最新状态。
func (c *StatusCache) Set(vehicle string, ts time.Time, data map[string]any) {
	c.mu.Lock()
	c.cur[vehicle] = stateEntry{ts: ts, data: data}
	c.mu.Unlock()
}

// Latest 返回某车最新状态；TTL 过期视为不存在（僵尸数据不可见）。
func (c *StatusCache) Latest(vehicle string) (map[string]any, bool) {
	c.mu.RLock()
	e, ok := c.cur[vehicle]
	c.mu.RUnlock()
	if !ok {
		return nil, false
	}
	if c.ttl > 0 && time.Since(e.ts) > c.ttl {
		return nil, false
	}
	return e.data, true
}
