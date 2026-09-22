package main

import (
	"fmt"
	"testing"
)

// genLines 生成 n 行合法 JSON 日志（含 1 行坏行验证容错）
func genLines(n int) []string {
	lines := make([]string, 0, n+1)
	for i := 0; i < n; i++ {
		lines = append(lines, fmt.Sprintf(`{"level":"info","msg":"req-%d","latency_ms":%d}`, i, i%100))
	}
	lines = append(lines, `{bad json`)
	return lines
}

func TestBothEqual(t *testing.T) {
	lines := genLines(1000)
	a, b := NaiveParse(lines), FastParse(lines)
	if len(a) != len(b) {
		t.Fatalf("条数不一致: %d vs %d", len(a), len(b))
	}
	for i := range a {
		if a[i] != b[i] {
			t.Fatalf("第 %d 条不一致: %+v vs %+v", i, a[i], b[i])
		}
	}
}

func TestBadLineSkipped(t *testing.T) {
	lines := []string{`{bad`, `{"level":"info","msg":"ok","latency_ms":1}`}
	if got := FastParse(lines); len(got) != 1 {
		t.Fatalf("坏行应跳过: got %d 条", len(got))
	}
}

var sink []Record

func BenchmarkNaiveParse(b *testing.B) {
	lines := genLines(1000)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		sink = NaiveParse(lines)
	}
}

func BenchmarkFastParse(b *testing.B) {
	lines := genLines(1000)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		sink = FastParse(lines)
	}
}
