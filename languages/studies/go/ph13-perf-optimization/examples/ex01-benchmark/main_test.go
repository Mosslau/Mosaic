package main

import "testing"

// ---- 正确性：三种拼接写法与两种 append 写法结果必须一致 ----

func TestConcatEqual(t *testing.T) {
	for _, n := range []int{0, 1, 7, 1000} {
		a, b, c := ConcatPlus(n), ConcatBuilder(n), ConcatJoin(n)
		if a != b || b != c {
			t.Fatalf("n=%d 三种写法结果不一致: len=%d/%d/%d", n, len(a), len(b), len(c))
		}
		if len(a) != n {
			t.Fatalf("n=%d 结果长度=%d", n, len(a))
		}
	}
}

func TestAppendEqual(t *testing.T) {
	a, b := AppendNoPrealloc(1000), AppendPrealloc(1000)
	if len(a) != len(b) {
		t.Fatalf("长度不一致: %d vs %d", len(a), len(b))
	}
	for i := range a {
		if a[i] != b[i] {
			t.Fatalf("下标 %d: %d vs %d", i, a[i], b[i])
		}
	}
}

// ---- 基准：benchmark 的结果必须「落地」到包级变量，防止编译器把整个计算优化掉 ----

var (
	sinkStr string
	sinkInt []int
)

func BenchmarkConcatPlus(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sinkStr = ConcatPlus(1000)
	}
}

func BenchmarkConcatBuilder(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sinkStr = ConcatBuilder(1000)
	}
}

func BenchmarkConcatJoin(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sinkStr = ConcatJoin(1000)
	}
}

func BenchmarkAppendNoPrealloc(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sinkInt = AppendNoPrealloc(1000)
	}
}

func BenchmarkAppendPrealloc(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sinkInt = AppendPrealloc(1000)
	}
}
