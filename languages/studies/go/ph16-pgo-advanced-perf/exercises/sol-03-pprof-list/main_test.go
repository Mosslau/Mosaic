// 来源：ph16-pgo-advanced-perf 练习 3 参考实现（classify/score/renderRows 的单测）
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行：go test -v ./...
// 验证状态：已验证（go1.25.6，2026-09-02）
package main

import (
	"strings"
	"testing"
)

func TestClassify(t *testing.T) {
	cases := []struct {
		line string
		kind string
		hot  bool
	}{
		{"ok:device-00001,latency=10", "ok", true},
		{"warn:device-00002,latency=200", "warn", false},
		{"err:device-00003", "err", false},
		{"unknown format", "err", false},
	}
	for _, c := range cases {
		kind, hot := classify(c.line)
		if kind != c.kind || hot != c.hot {
			t.Errorf("classify(%q) = (%q, %v), want (%q, %v)", c.line, kind, hot, c.kind, c.hot)
		}
	}
}

func TestScoreDeterministic(t *testing.T) {
	if score("device-00001") != score("device-00001") {
		t.Fatal("score 不确定")
	}
	if score("device-00001") == score("device-00002") {
		t.Fatal("不同输入得到相同结果")
	}
	if score("") == 0 {
		t.Fatal("空串不应坍缩到 0 常量")
	}
}

func TestRenderRows(t *testing.T) {
	got := renderRows([]string{"a", "b"})
	if !strings.HasPrefix(got, "<tr><td>a") {
		t.Fatalf("渲染结果不对: %q", got)
	}
	if strings.Count(got, "<tr>") != 2 {
		t.Fatalf("应有 2 行: %q", got)
	}
}
