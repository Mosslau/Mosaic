package main

import (
	"errors"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// TestTraceparentFormat：traceparent 必须恰为 00-<32hex>-<16hex>-flags 55 字符
func TestTraceparentFormat(t *testing.T) {
	root := NewRoot()
	tp := root.Traceparent()
	if len(tp) != 55 {
		t.Fatalf("traceparent len = %d, want 55: %s", len(tp), tp)
	}
	parts := strings.Split(tp, "-")
	if len(parts) != 4 || parts[0] != "00" || len(parts[1]) != 32 || len(parts[2]) != 16 {
		t.Fatalf("traceparent 结构错误: %s", tp)
	}
	if parts[3] != "01" {
		t.Fatalf("root 应默认 sampled, flags = %s", parts[3])
	}
}

// TestChildInheritsTraceID：子 span 继承 trace_id，parent 指向父 span_id
func TestChildInheritsTraceID(t *testing.T) {
	root := NewRoot()
	child := NewChild(root)
	if child.TraceID != root.TraceID {
		t.Fatalf("child trace_id = %s, want %s", child.TraceID, root.TraceID)
	}
	if child.ParentID != root.SpanID {
		t.Fatalf("child parent_id = %s, want root span_id %s", child.ParentID, root.SpanID)
	}
	if child.SpanID == root.SpanID {
		t.Fatal("child span_id 不应与父相同")
	}
}

// TestParseRoundTrip：生成 → 解析 → 还原，字段全等
func TestParseRoundTrip(t *testing.T) {
	root := NewRoot()
	parsed, err := ParseTraceparent(root.Traceparent())
	if err != nil {
		t.Fatalf("ParseTraceparent: %v", err)
	}
	if parsed.TraceID != root.TraceID || parsed.SpanID != root.SpanID || !parsed.Sampled {
		t.Fatalf("round-trip 不一致: %+v vs %+v", parsed, root)
	}
}

// TestParseInvalid：非法头必须报错（防注入：长度/版本/hex 校验）
func TestParseInvalid(t *testing.T) {
	bad := []string{
		"",                                // 空
		"00-deadbeef-00f067aa0ba902b7-01", // trace_id 太短
		"01-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01", // 版本不支持
		"00-4bf92f3577b34da6a3ce929d0e0e4736-zzz-01",              // span_id 非 hex
		"00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7",    // 只有 3 段
	}
	for _, h := range bad {
		if _, err := ParseTraceparent(h); err == nil {
			t.Fatalf("应拒绝非法头 %q", h)
		}
	}
}

// TestNoTraceparent：缺头返回 ErrNoTraceparent（调用方可决定新建根）
func TestNoTraceparent(t *testing.T) {
	req := httptest.NewRequest("GET", "/", nil)
	_, err := ExtractFromHeader(req)
	if !errors.Is(err, ErrNoTraceparent) {
		t.Fatalf("err = %v, want ErrNoTraceparent", err)
	}
}

// TestInjectExtract：注入出站请求头 → 对端解析还原（跨服务传播的最小闭环）
func TestInjectExtract(t *testing.T) {
	root := NewRoot()
	outReq, _ := http.NewRequest("GET", "http://example.test/", nil)
	InjectIntoHeader(root, outReq)
	if got := outReq.Header.Get("traceparent"); got != root.Traceparent() {
		t.Fatalf("注入头 = %q, want %q", got, root.Traceparent())
	}

	// 模拟服务端收到这个请求
	inReq := httptest.NewRequest("GET", "/", nil)
	inReq.Header.Set("traceparent", outReq.Header.Get("traceparent"))
	got, err := ExtractFromHeader(inReq)
	if err != nil {
		t.Fatalf("ExtractFromHeader: %v", err)
	}
	if got.TraceID != root.TraceID || got.SpanID != root.SpanID {
		t.Fatalf("传播还原失败: %+v", got)
	}
}

// TestServiceBChain：真实 HTTP 调用，B 返回的 trace_id 与 A 的根一致（链路打通）
func TestServiceBChain(t *testing.T) {
	var buf strings.Builder
	logger := slog.New(slog.NewJSONHandler(&buf, nil))

	// B 起真实 server（handler 用同一个 logger，日志进 buf）
	bHandler := serviceB(logger)
	srv := httptest.NewServer(bHandler)
	defer srv.Close()

	// A 建根并注入
	root := NewRoot()
	req, _ := http.NewRequest("GET", srv.URL+"/api/process", nil)
	InjectIntoHeader(root, req)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("call B: %v", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if !strings.Contains(string(body), root.TraceID) {
		t.Fatalf("B 响应应回显同一 trace_id %s: %s", root.TraceID, body)
	}
	// B 的日志应包含同一 trace_id（链没有被断开）
	if !strings.Contains(buf.String(), root.TraceID) {
		t.Fatalf("B 日志缺 trace_id %s: %s", root.TraceID, buf.String())
	}
}
