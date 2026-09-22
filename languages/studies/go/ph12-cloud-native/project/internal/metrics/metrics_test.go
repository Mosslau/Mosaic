package metrics

import (
	"strings"
	"sync"
	"testing"
)

func TestCounterRender(t *testing.T) {
	c := NewCounter("req_total", "requests", map[string]string{"handler": "api"})
	c.Inc()
	c.Add(2)
	var sb strings.Builder
	c.Render(&sb)
	want := "# HELP req_total requests\n# TYPE req_total counter\nreq_total{handler=\"api\"} 3\n"
	if sb.String() != want {
		t.Fatalf("counter render:\n%q\nwant:\n%q", sb.String(), want)
	}
}

func TestGaugeRender(t *testing.T) {
	g := NewGauge("inflight", "in flight")
	g.Inc()
	g.Inc()
	g.Dec()
	var sb strings.Builder
	g.Render(&sb)
	if !strings.Contains(sb.String(), "inflight 1") {
		t.Fatalf("gauge render: %q", sb.String())
	}
}

func TestHistogramRender(t *testing.T) {
	h := NewHistogram("latency_seconds", "latency", []float64{0.1, 0.5})
	h.Observe(0.05)
	h.Observe(0.2)
	h.Observe(2.0)
	var sb strings.Builder
	h.Render(&sb)
	text := sb.String()
	for _, want := range []string{
		`latency_seconds_bucket{le="0.1"} 1`,
		`latency_seconds_bucket{le="0.5"} 2`,
		`latency_seconds_bucket{le="+Inf"} 3`,
		"latency_seconds_sum 2.25",
		"latency_seconds_count 3",
	} {
		if !strings.Contains(text, want) {
			t.Fatalf("缺 %q:\n%s", want, text)
		}
	}
}

func TestConcurrentCounter(t *testing.T) {
	c := NewCounter("c_total", "h", nil)
	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); c.Inc() }()
	}
	wg.Wait()
	c.mu.Lock()
	if c.value != 100 {
		t.Fatalf("counter = %v, want 100", c.value)
	}
	c.mu.Unlock()
}

func TestLabelsSortedAndEscaped(t *testing.T) {
	var sb strings.Builder
	writeLabels(&sb, map[string]string{"zone": "b", "method": "GET"})
	if sb.String() != `{method="GET",zone="b"}` {
		t.Fatalf("labels: %q", sb.String())
	}
	sb.Reset()
	writeLabels(&sb, nil)
	if sb.String() != "" {
		t.Fatalf("空标签应无输出: %q", sb.String())
	}
	if escape(`a"b`) != `a\"b` {
		t.Fatal("转义失败")
	}
}
