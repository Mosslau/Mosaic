package parser

import (
	"testing"

	"tenetlang/go/ph13-perf-optimization/project/internal/genlog"
)

// ---- 正确性：三种解析对同一批生成日志结果必须一致 ----

func TestAllEqual(t *testing.T) {
	lines := genlog.Generate(2000)
	a, b, c := ParseNaive(lines), ParseStruct(lines), ParseManual(lines)
	if len(a) != len(b) || len(b) != len(c) {
		t.Fatalf("条数不一致: naive=%d struct=%d manual=%d", len(a), len(b), len(c))
	}
	for i := range a {
		if a[i] != b[i] || b[i] != c[i] {
			t.Fatalf("第 %d 条不一致: %+v / %+v / %+v", i, a[i], b[i], c[i])
		}
	}
}

// 生成日志应全部合法（无坏行）；坏行跳过行为用显式坏行验证
func TestGeneratedAllValid(t *testing.T) {
	lines := genlog.Generate(500)
	if got := len(ParseManual(lines)); got != 500 {
		t.Fatalf("生成日志 %d 行中只解析出 %d 行", len(lines), got)
	}
}

func TestBadLineSkipped(t *testing.T) {
	lines := []string{
		`{bad json`,
		`{"ts":"x","level":"info","device_id":"car-0001","msg":"ok","latency_ms":12}`,
		`{"ts":"x","level":"error"`, // 字段缺失
	}
	for name, f := range map[string]func([]string) []Record{
		"naive":  ParseNaive,
		"struct": ParseStruct,
		"manual": ParseManual,
	} {
		if got := f(lines); len(got) != 1 {
			t.Fatalf("%s: 坏行应跳过, got %d 条", name, len(got))
		}
	}
}

// 边界：latency_ms 为 0 时 manual 解析不应失败
func TestManualZeroLatency(t *testing.T) {
	rec, ok := parseLineManual(`{"ts":"x","level":"info","device_id":"car-0001","msg":"ok","latency_ms":0}`)
	if !ok || rec.LatencyMs != 0 {
		t.Fatalf("latency_ms:0 解析失败: %+v ok=%v", rec, ok)
	}
}

var sink []Record

// ---- 基准：1000 行/次，三版对比（实测数字见 README）----

func BenchmarkParseNaive(b *testing.B) {
	lines := genlog.Generate(1000)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		sink = ParseNaive(lines)
	}
}

func BenchmarkParseStruct(b *testing.B) {
	lines := genlog.Generate(1000)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		sink = ParseStruct(lines)
	}
}

func BenchmarkParseManual(b *testing.B) {
	lines := genlog.Generate(1000)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		sink = ParseManual(lines)
	}
}
