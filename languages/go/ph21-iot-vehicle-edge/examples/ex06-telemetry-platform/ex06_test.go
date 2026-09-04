// 来源：ph21-iot-vehicle-edge examples/ex06-telemetry-platform/ex06_test.go
// 一句话说明：平台四类测试——清洗分类（缺 vin/坏 seq/超量程/重复）、时序存储
// 三种查询、实时状态 TTL、告警规则与冷却期、完整链路指标与死信计数。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"errors"
	"net/http"
	"strings"
	"testing"
	"time"
)

func ev(vin string, seq uint64, speed float64, ts time.Time) Event {
	return Event{Vin: vin, Seq: seq, Speed: speed, Ts: ts}
}

func TestCleanerClassifiesBadData(t *testing.T) {
	c := NewCleaner()
	now := time.Now()
	if _, err := c.Clean(ev("", 1, 10, now)); !errors.Is(err, ErrBadVin) {
		t.Errorf("空 vin 应 ErrBadVin, got %v", err)
	}
	if _, err := c.Clean(ev("veh-1", 0, 10, now)); !errors.Is(err, ErrBadSeq) {
		t.Errorf("seq=0 应 ErrBadSeq, got %v", err)
	}
	if _, err := c.Clean(ev("veh-1", 2, 500, now)); !errors.Is(err, ErrRange) {
		t.Errorf("超量程应 ErrRange, got %v", err)
	}
	if _, err := c.Clean(ev("veh-1", 3, 10, time.Time{})); !errors.Is(err, ErrBadTs) {
		t.Errorf("零时间应 ErrBadTs, got %v", err)
	}
	// 正常一条 + 同 seq 重复 → ErrDuplicate。
	if _, err := c.Clean(ev("veh-1", 4, 10, now)); err != nil {
		t.Fatalf("正常清洗应通过: %v", err)
	}
	if _, err := c.Clean(ev("veh-1", 4, 10, now)); !errors.Is(err, ErrDuplicate) {
		t.Errorf("重复应 ErrDuplicate, got %v", err)
	}
	if c.Dropped() != 5 {
		t.Errorf("丢弃应 5, got %d", c.Dropped())
	}
}

func TestCleanerConvertsUnits(t *testing.T) {
	c := NewCleaner()
	ce, err := c.Clean(ev("veh-1", 1, 100, time.Now())) // 100 m/s
	if err != nil {
		t.Fatal(err)
	}
	if ce.SpeedKmh != 360 {
		t.Errorf("100m/s 应换算 360km/h, got %v", ce.SpeedKmh)
	}
}

func TestTSStoreQueries(t *testing.T) {
	s := NewTSStore()
	base := time.Unix(1700000000, 0)
	for i, v := range []float64{10, 20, 30, 40} {
		s.Append("veh-1", "speed", Point{Ts: base.Add(time.Duration(i) * time.Second), Value: v})
	}
	latest, ok := s.Latest("veh-1", "speed")
	if !ok || latest.Value != 40 {
		t.Errorf("Latest 应 40, got %v ok=%v", latest.Value, ok)
	}
	recent := s.Recent("veh-1", "speed", base.Add(2*time.Second))
	if len(recent) != 2 {
		t.Errorf("Recent 应 2 条, got %d", len(recent))
	}
	buckets := s.RangeAggregate("speed", base, base.Add(4*time.Second), 2*time.Second)
	if len(buckets) != 2 {
		t.Fatalf("应 2 桶, got %d", len(buckets))
	}
	if buckets[0].Avg != 15 || buckets[0].Max != 20 || buckets[0].Hits != 2 {
		t.Errorf("桶 0 异常: %+v", buckets[0])
	}
}

func TestStatusCacheTTL(t *testing.T) {
	c := NewStatusCache(100 * time.Millisecond)
	c.Set("veh-1", time.Now(), map[string]any{"speed_kmh": 60.0})
	if _, ok := c.Latest("veh-1"); !ok {
		t.Fatal("TTL 内应可见")
	}
	time.Sleep(150 * time.Millisecond)
	if _, ok := c.Latest("veh-1"); ok {
		t.Error("TTL 过期应不可见（僵尸状态被清除）")
	}
}

func TestAlertRulesAndCooldown(t *testing.T) {
	a := NewAlertEngine()
	now := time.Now()
	// 135km/h 只命中 warn；180km/h 命中 warn+critical。
	low := a.Evaluate("veh-1", "speed", 135, now)
	if len(low) != 1 || low[0].RuleID != "speed-too-fast" {
		t.Errorf("135km/h 应只命中 warn 规则, got %+v", low)
	}
	high := a.Evaluate("veh-1", "speed", 180, now.Add(100*time.Millisecond))
	if len(high) != 1 || high[0].RuleID != "speed-extreme" {
		t.Errorf("180km/h 应命中 critical 规则(另一条在冷却), got %+v", high)
	}
	// 冷却期内同规则不再重复告警。
	if got := a.Evaluate("veh-1", "speed", 185, now.Add(200*time.Millisecond)); len(got) != 0 {
		t.Errorf("冷却期内不应再告警, got %+v", got)
	}
}

func TestPlatformPipelineEndToEnd(t *testing.T) {
	p := NewPlatform()
	now := time.Now()
	// 4 正常(含 2 条超速触发告警) + 1 坏数据 + 1 重复。
	feed := []Event{
		ev("veh-1", 1, 30.0/3.6, now.Add(time.Second)),
		ev("veh-1", 2, 90.0/3.6, now.Add(2*time.Second)),
		ev("veh-1", 3, 135.0/3.6, now.Add(3*time.Second)),
		ev("veh-1", 4, 180.0/3.6, now.Add(4*time.Second)),
		ev("veh-1", 5, 999, now.Add(5*time.Second)),
		ev("veh-1", 1, 30.0/3.6, now.Add(6*time.Second)),
	}
	for _, e := range feed {
		_ = p.Ingest(e)
	}
	ing, clean, errs, alerts := p.Metrics.Counters()
	if ing != 6 || clean != 4 || errs != 2 {
		t.Errorf("链路计数异常: ing=%d clean=%d errs=%d", ing, clean, errs)
	}
	// 两次超速都在冷却期内算同规则：告警 = warn(135) + critical(180) 两条且各在冷却 → alerts=2。
	if alerts != 2 {
		t.Errorf("告警应 2, got %d", alerts)
	}
	if _, ok := p.Store.Latest("veh-1", "speed"); !ok {
		t.Error("正常数据应已入库")
	}
	if ec := p.Clean.ErrCounts(); ec["clean: 超量程"] != 1 || ec["clean: 重复事件"] != 1 {
		t.Errorf("坏数据台账异常: %v", ec)
	}
}

func TestMetricsTextFormat(t *testing.T) {
	p := NewPlatform()
	p.Metrics.SetOnline(3)
	rec := newRecorder()
	p.Metrics.ServeHTTP(rec, nil)
	body := rec.String()
	for _, want := range []string{
		"# TYPE fleet_ingested_total counter",
		"fleet_ingested_total 0",
		`fleet_clean_errors_total{reason="any"} 0`,
		"# TYPE fleet_online_vehicles gauge",
		"fleet_online_vehicles 3",
	} {
		if !strings.Contains(body, want) {
			t.Errorf("metrics 文本缺 %q\n%s", want, body)
		}
	}
}

// recorder 迷你 http.ResponseWriter（避免 httptest 依赖，保持纯标准库）。
type recorder struct{ buf strings.Builder }

func (r *recorder) Header() http.Header         { return http.Header{} }
func (r *recorder) Write(p []byte) (int, error) { return r.buf.Write(p) }
func (r *recorder) WriteHeader(int)             {}
func (r *recorder) String() string              { return r.buf.String() }

func newRecorder() *recorder { return &recorder{} }
