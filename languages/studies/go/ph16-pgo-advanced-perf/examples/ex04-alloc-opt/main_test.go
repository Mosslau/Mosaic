// 来源：ph16-pgo-advanced-perf 示例 ex04-alloc-opt（正确性测试 + 前后对比 benchmark）
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行：go test -v ./...；go test -run='^$' -bench=. -benchmem -count=5
// 验证状态：已验证（go1.25.6，2026-09-03）
package main

import (
	"fmt"
	"testing"
)

// 固定输入：1000 条事件，让分配差异可测量。
var benchEvents = func() []Event {
	es := make([]Event, 1000)
	for i := range es {
		es[i] = Event{DeviceID: fmt.Sprintf("dev-%04d", i), LatencyMs: i % 500, Online: i%2 == 0}
	}
	return es
}()

var sinkStr string // sink 落地：防止编译器把格式化整个优化掉（ph13 纪律）

func TestFormatEquivalence(t *testing.T) {
	naive := FormatNaive(benchEvents)
	opt := FormatOpt(benchEvents)
	if naive != opt {
		t.Fatalf("两版输出不一致:\nnaive[:80]=%q\nopt  [:80]=%q", naive[:80], opt[:80])
	}
}

func BenchmarkFormatNaive(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sinkStr = FormatNaive(benchEvents)
	}
}

func BenchmarkFormatOpt(b *testing.B) {
	for i := 0; i < b.N; i++ {
		sinkStr = FormatOpt(benchEvents)
	}
}

var sinkUint uint64

// BenchmarkLayoutBad / BenchmarkLayoutGood：分配 10 万个事件的切片并求和
// （10 万元素超过栈分配上限，必然逃逸到堆，B/op 才能如实反映结构体尺寸差异）。
// B/op 差异 = 结构体尺寸差异 × 100000（padding 的直接代价）；
// ns/op 差异来自更小的内存足迹（缓存更友好）。
func BenchmarkLayoutBad(b *testing.B) {
	for i := 0; i < b.N; i++ {
		evs := make([]BadEvent, 100000)
		for j := range evs {
			evs[j] = BadEvent{Online: true, LatencyMs: j, Valid: true, DeviceID: "d"}
		}
		var sum uint64
		for _, e := range evs {
			sum += uint64(e.LatencyMs)
		}
		sinkUint = sum
	}
}

func BenchmarkLayoutGood(b *testing.B) {
	for i := 0; i < b.N; i++ {
		evs := make([]GoodEvent, 100000)
		for j := range evs {
			evs[j] = GoodEvent{DeviceID: "d", LatencyMs: j, Online: true, Valid: true}
		}
		var sum uint64
		for _, e := range evs {
			sum += uint64(e.LatencyMs)
		}
		sinkUint = sum
	}
}
