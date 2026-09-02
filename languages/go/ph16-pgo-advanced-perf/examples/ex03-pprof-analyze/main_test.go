// 来源：ph16-pgo-advanced-perf 示例 ex03-pprof-analyze（render/summarize 的单测）
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行：go test -v ./...
// 验证状态：已验证（go1.25.6，2026-09-03）
package main

import (
	"strings"
	"testing"
)

func TestRenderBody(t *testing.T) {
	got := renderBody([]string{"a", "b"})
	if !strings.HasPrefix(got, "<table>") || !strings.HasSuffix(got, "</table>\n") {
		t.Fatalf("报表结构不对: %q", got)
	}
	if strings.Count(got, "<tr>") != 2 {
		t.Fatalf("应有 2 行: %q", got)
	}
}

func TestSummarizeDeterministic(t *testing.T) {
	rows := []string{"x", "yz"}
	var a, b uint64
	for _, r := range rows {
		a ^= validateRow(r)
	}
	for _, r := range rows {
		b ^= validateRow(r)
	}
	if a != b {
		t.Fatal("validateRow 不确定")
	}
	if validateRow("x") == validateRow("y") {
		t.Fatal("不同输入得到相同 digest（极小概率事件，视为实现有误）")
	}
}
