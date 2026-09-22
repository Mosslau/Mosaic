package main

import (
	"bytes"
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// TestJSONFormat：JSON handler 输出的每行都是合法 JSON 且含关键字段
func TestJSONFormat(t *testing.T) {
	var buf bytes.Buffer
	logger := newLogger(&buf, slog.LevelDebug)
	logger.Info("hello", "key", "value")

	line := strings.TrimSpace(buf.String())
	if !strings.HasPrefix(line, "{") || !strings.HasSuffix(line, "}") {
		t.Fatalf("非 JSON 行: %q", line)
	}
	var m map[string]any
	if err := json.Unmarshal([]byte(line), &m); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if m["msg"] != "hello" || m["key"] != "value" {
		t.Fatalf("字段缺失: %v", m)
	}
	if _, ok := m["time"]; !ok {
		t.Fatal("缺 time 字段")
	}
	if m["level"] != "INFO" {
		t.Fatalf("level = %v, want INFO", m["level"])
	}
}

// TestLevelFilter：低于配置级别的日志必须被丢弃（生产按环境调级别，dev 全开、prod 只留 warn+）
func TestLevelFilter(t *testing.T) {
	var buf bytes.Buffer
	logger := newLogger(&buf, slog.LevelWarn)
	logger.Info("should be dropped")
	logger.Warn("kept")
	if strings.Contains(buf.String(), "should be dropped") {
		t.Fatal("info 日志在 warn 级别下不应输出")
	}
	if !strings.Contains(buf.String(), "kept") {
		t.Fatal("warn 日志应输出")
	}
}

// TestWithInheritsFields：With 注入的字段必须出现在后续每条日志
func TestWithInheritsFields(t *testing.T) {
	var buf bytes.Buffer
	base := newLogger(&buf, slog.LevelInfo)
	reqLog := requestLogger(base, "trace-xyz", "user-7")
	reqLog.Info("event")

	var m map[string]any
	if err := json.Unmarshal(bytes.TrimSpace(buf.Bytes()), &m); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if m["trace_id"] != "trace-xyz" || m["user_id"] != "user-7" {
		t.Fatalf("With 字段未继承: %v", m)
	}
}

// TestHandleEcho：handler 的成功/失败路径 + 日志侧验证
func TestHandleEcho(t *testing.T) {
	var buf bytes.Buffer
	logger := newLogger(&buf, slog.LevelDebug)
	h := handleEcho(logger)

	// 缺 name → 400 + warn 日志
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest("GET", "/api/echo", nil))
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("缺 name: %d, want 400", rr.Code)
	}
	if !strings.Contains(buf.String(), "missing name param") {
		t.Fatal("缺 name 应记录 warn 日志")
	}

	// 带 name → 200 + 成功日志（含 latency_ms）
	buf.Reset()
	rr2 := httptest.NewRecorder()
	h.ServeHTTP(rr2, httptest.NewRequest("GET", "/api/echo?name=alice", nil))
	if rr2.Code != http.StatusOK {
		t.Fatalf("带 name: %d, want 200", rr2.Code)
	}
	if !strings.Contains(buf.String(), "request done") || !strings.Contains(buf.String(), "latency_ms") {
		t.Fatalf("成功路径日志缺失: %s", buf.String())
	}
}

// TestInfoContext：InfoContext 把 context 传给日志 handler（API 形态验证，
// 标准 JSON handler 不消费 ctx 但方法签名可用）
func TestInfoContext(t *testing.T) {
	var buf bytes.Buffer
	logger := newLogger(&buf, slog.LevelInfo)
	logger.InfoContext(context.Background(), "ctx event", "k", "v")
	var m map[string]any
	if err := json.Unmarshal(bytes.TrimSpace(buf.Bytes()), &m); err != nil {
		t.Fatalf("JSON 解析失败: %v", err)
	}
	if m["msg"] != "ctx event" || m["k"] != "v" {
		t.Fatalf("InfoContext 字段异常: %v", m)
	}
}
