// 来源：ph16-pgo-advanced-perf 示例 ex01-profserver（hashChain 与 handler 的单测）
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行：go test -v ./...
// 验证状态：已验证（go1.25.6，2026-09-03）
package main

import (
	"net/http/httptest"
	"strings"
	"testing"
)

func TestHashChainDeterministic(t *testing.T) {
	// 同一输入必须得到同一结果（PGO 前后语义一致的检查思路同源）
	a := hashChain(42, 100000)
	b := hashChain(42, 100000)
	if a != b {
		t.Fatalf("hashChain 不确定: %d != %d", a, b)
	}
	if a == 42 {
		t.Fatal("hashChain 似乎没有做任何混合")
	}
}

func TestWorkHandler(t *testing.T) {
	req := httptest.NewRequest("GET", "/work?n=1000", nil)
	rec := httptest.NewRecorder()
	workHandler(rec, req)
	body := rec.Body.String()
	if !strings.Contains(body, `"n":1000`) {
		t.Fatalf("响应缺少 n 字段: %s", body)
	}
	if !strings.Contains(body, `"sum":`) {
		t.Fatalf("响应缺少 sum 字段: %s", body)
	}
}

func TestWorkHandlerDefaultN(t *testing.T) {
	req := httptest.NewRequest("GET", "/work", nil)
	rec := httptest.NewRecorder()
	workHandler(rec, req)
	if !strings.Contains(rec.Body.String(), `"n":100000`) {
		t.Fatalf("缺省 n 应为 100000: %s", rec.Body.String())
	}
}
