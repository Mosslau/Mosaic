// 来源：ph08-testing 练习 4 参考实现 —— 给核心模块写 benchmark
// 一句话说明：正确性对照 strings.Join；benchmark 结果写入包级 sink 防优化消除。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...                             # 正确性
//	go test -bench=. -benchmem -run=^$ -count=3  # benchmark 重复 3 次
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"fmt"
	"strings"
	"testing"
)

var sinkString string // 包级 sink：防止 benchmark 结果被编译器优化消除

func benchParts() []string {
	parts := make([]string, 0, 100)
	for i := 0; i < 100; i++ {
		parts = append(parts, fmt.Sprintf("part-%d", i))
	}
	return parts
}

func TestConcatConsistent(t *testing.T) {
	parts := benchParts()
	want := strings.Join(parts, "")
	if got := ConcatPlus(parts); got != want {
		t.Errorf("ConcatPlus 结果与 strings.Join 不一致")
	}
	if got := ConcatBuilder(parts); got != want {
		t.Errorf("ConcatBuilder 结果与 strings.Join 不一致")
	}
}

func TestConcatEmpty(t *testing.T) {
	if got := ConcatPlus(nil); got != "" {
		t.Errorf("ConcatPlus(nil) = %q, 期望空串", got)
	}
	if got := ConcatBuilder(nil); got != "" {
		t.Errorf("ConcatBuilder(nil) = %q, 期望空串", got)
	}
}

func BenchmarkConcatPlus(b *testing.B) {
	parts := benchParts()
	b.ResetTimer() // 排除 setup 耗时
	for i := 0; i < b.N; i++ {
		sinkString = ConcatPlus(parts)
	}
}

func BenchmarkConcatBuilder(b *testing.B) {
	parts := benchParts()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		sinkString = ConcatBuilder(parts)
	}
}
