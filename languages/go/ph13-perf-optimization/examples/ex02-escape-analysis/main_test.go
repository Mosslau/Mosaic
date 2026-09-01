package main

import "testing"

func TestSumTo(t *testing.T) {
	if got := SumTo(100); got != 5050 {
		t.Fatalf("SumTo(100)=%d, want 5050", got)
	}
}

func TestMakePoint(t *testing.T) {
	p := makePoint()
	if p.X != 1 || p.Y != 2 {
		t.Fatalf("makePoint()=%+v", p)
	}
}

func TestMakePointVal(t *testing.T) {
	p := makePointVal()
	if p.X != 1 || p.Y != 2 {
		t.Fatalf("makePointVal()=%+v", p)
	}
}

func TestBigBuf(t *testing.T) {
	if got := bigBuf(); got != 1 {
		t.Fatalf("bigBuf()=%d, want 1", got)
	}
}

func TestPrintLen(t *testing.T) {
	printLen("ok") // 只验证不 panic；逃逸行为由 -gcflags='-m' 静态验证
}

// 基准对照：逃逸到堆（makePoint，1 allocs/op）vs 留在栈上（makePointVal，0 allocs/op）
// go test -run='^$' -bench=. -benchmem -benchtime=1000000x
func BenchmarkEscaped(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sinkP = makePoint()
	}
}

func BenchmarkStack(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sinkV = makePointVal()
	}
}

var (
	sinkP *Point
	sinkV Point
)
