// 来源：ph21-data-ingest-gateway examples/ex06-metrics-platform/ex06_test.go
// 一句话说明：平台四类测试——清洗分类（缺 sourceID/坏 seq/超量程/重复）、时序存储
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

func ev(sourceID string, seq uint64, value float64, ts time.Time) Event {
	return Event{SourceID: sourceID, Seq: seq, Value: value, Ts: ts}
}

func TestCleanerClassifiesBadData(t *testing.T) {
	c := NewCleaner()
	now := time.Now()
	if _, err := c.Clean(ev("", 1, 10, now)); !errors.Is(err, ErrBadSourceID) {
		t.Errorf("空 sourceID 应 ErrBadSourceID, got %v", err)
	}
	if _, err := c.Clean(ev("src-1", 0, 10, now)); !errors.Is(err, ErrBadSeq) {
		t.Errorf("seq=0 应 ErrBadSeq, got %v", err)
	}
	if _, err := c.Clean(ev("src-1", 2, 1200, now)); !errors.Is(err, ErrRange) {
		t.Errorf("超量程应 ErrRange, got %v", err)
	}
	if _, err := c.Clean(ev("src-1", 3, 10, time.Time{})); !errors.Is(err, ErrBadTs) {
		t.Errorf("零时间应 ErrBadTs, got %v", err)
	}
	// 正常一条 + 同 seq 重复 → ErrDuplicate。
	if _, err := c.Clean(ev("src-1", 4, 10, now)); err != nil {
		t.Fatalf("正常清洗应通过: %v", err)
	}
	if _, err := c.Clean(ev("src-1", 4, 10, now)); !errors.Is(err, ErrDuplicate) {
		t.Errorf("重复应 ErrDuplicate, got %v", err)
	}
	if c.Dropped() != 5 {
		t.Errorf("丢弃应 5, got %d", c.Dropped())
	}
}

func TestCleanerConvertsUnits(t *testing.T) {
	c := NewCleaner()
	ce, err := c.Clean(ev("src-1", 1, 1000, time.Now())) // 原始计数 1000（=100%）
	if err != nil {
		t.Fatal(err)
	}
	if ce.ValuePct != 100 {
		t.Errorf("原始计数 1000 应换算 100%%, got %v", ce.ValuePct)
	}
}

func TestTSStoreQueries(t *testing.T) {
	s := NewTSStore()
	base := time.Unix(1700000000, 0)
	for i, v := range []float64{10, 20, 30, 40} {
		s.Append("src-1", "value", Point{Ts: base.Add(time.Duration(i) * time.Second), Value: v})
	}
	latest, ok := s.Latest("src-1", "value")
	if !ok || latest.Value != 40 {
		t.Errorf("Latest 应 40, got %v ok=%v", latest.Value, ok)
	}
	recent := s.Recent("src-1", "value", base.Add(2*time.Second))
	if len(recent) != 2 {
		t.Errorf("Recent 应 2 条, got %d", len(recent))
	}
	buckets := s.RangeAggregate("value", base, base.Add(4*time.Second), 2*time.Second)
	if len(buckets) != 2 {
		t.Fatalf("应 2 桶, got %d", len(buckets))
	}
	if buckets[0].Avg != 15 || buckets[0].Max != 20 || buckets[0].Hits != 2 {
		t.Errorf("桶 0 异常: %+v", buckets[0])
	}
}

func TestStatusCacheTTL(t *testing.T) {
	c := NewStatusCache(100 * time.Millisecond)
	c.Set("src-1", time.Now(), map[string]any{"value_pct": 60.0})
	if _, ok := c.Latest("src-1"); !ok {
		t.Fatal("TTL 内应可见")
	}
	time.Sleep(150 * time.Millisecond)
	if _, ok := c.Latest("src-1"); ok {
		t.Error("TTL 过期应不可见（僵尸状态被清除）")
	}
}

func TestAlertRulesAndCooldown(t *testing.T) {
	a := NewAlertEngine()
	now := time.Now()
	// 85% 只命中 warn；95% 命中 warn+critical。
	low := a.Evaluate("src-1", "value", 85, now)
	if len(low) != 1 || low[0].RuleID != "value-warn" {
		t.Errorf("85%% 应只命中 warn 规则, got %+v", low)
	}
	high := a.Evaluate("src-1", "value", 95, now.Add(100*time.Millisecond))
	if len(high) != 1 || high[0].RuleID != "value-critical" {
		t.Errorf("95%% 应命中 critical 规则(另一条在冷却), got %+v", high)
	}
	// 冷却期内同规则不再重复告警。
	if got := a.Evaluate("src-1", "value", 98, now.Add(200*time.Millisecond)); len(got) != 0 {
		t.Errorf("冷却期内不应再告警, got %+v", got)
	}
}

func TestPlatformPipelineEndToEnd(t *testing.T) {
	p := NewPlatform()
	now := time.Now()
	// 4 正常(含 2 条超阈值触发告警) + 1 坏数据 + 1 重复。
	feed := []Event{
		ev("src-1", 1, 300, now.Add(time.Second)),
		ev("src-1", 2, 900, now.Add(2*time.Second)),
		ev("src-1", 3, 850, now.Add(3*time.Second)),
		ev("src-1", 4, 950, now.Add(4*time.Second)),
		ev("src-1", 5, 1200, now.Add(5*time.Second)),
		ev("src-1", 1, 300, now.Add(6*time.Second)),
	}
	for _, e := range feed {
		_ = p.Ingest(e)
	}
	ing, clean, errs, alerts := p.Metrics.Counters()
	if ing != 6 || clean != 4 || errs != 2 {
		t.Errorf("链路计数异常: ing=%d clean=%d errs=%d", ing, clean, errs)
	}
	// 两次超阈值都在冷却期内算同规则：告警 = warn(135) + critical(180) 两条且各在冷却 → alerts=2。
	if alerts != 2 {
		t.Errorf("告警应 2, got %d", alerts)
	}
	if _, ok := p.Store.Latest("src-1", "value"); !ok {
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
		"# TYPE ingest_received_total counter",
		"ingest_received_total 0",
		`ingest_clean_errors_total{reason="any"} 0`,
		"# TYPE ingest_online_sources gauge",
		"ingest_online_sources 3",
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
