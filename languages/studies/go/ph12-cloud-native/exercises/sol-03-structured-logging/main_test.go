package main

import (
	"bytes"
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

// TestJSONLine：每行是合法 JSON 且含 msg/level/time/source
func TestJSONLine(t *testing.T) {
	var buf bytes.Buffer
	logger := newLogger(&buf, slog.LevelDebug)
	logger.Info("hello", "k", "v")

	line := strings.TrimSpace(buf.String())
	var m map[string]any
	if err := json.Unmarshal([]byte(line), &m); err != nil {
		t.Fatalf("非 JSON: %v (%s)", err, line)
	}
	if m["msg"] != "hello" || m["k"] != "v" {
		t.Fatalf("字段缺失: %v", m)
	}
	if _, ok := m["time"]; !ok {
		t.Fatal("缺 time")
	}
	if m["level"] != "INFO" {
		t.Fatalf("level = %v", m["level"])
	}
	if _, ok := m["source"]; !ok {
		t.Fatal("AddSource 应输出 source 字段")
	}
}

// TestLevelFilter：低于配置级别的日志被丢弃
func TestLevelFilter(t *testing.T) {
	var buf bytes.Buffer
	logger := newLogger(&buf, slog.LevelWarn)
	logger.Info("dropped")
	logger.Warn("kept")
	if strings.Contains(buf.String(), "dropped") {
		t.Fatal("info 不应输出")
	}
	if !strings.Contains(buf.String(), "kept") {
		t.Fatal("warn 应输出")
	}
}

// TestWithInherits：With 字段出现在后续每条日志
func TestWithInherits(t *testing.T) {
	var buf bytes.Buffer
	reqLog := requestLogger(newLogger(&buf, slog.LevelInfo), "trace-1", "user-9")
	reqLog.Info("event")

	var m map[string]any
	if err := json.Unmarshal(bytes.TrimSpace(buf.Bytes()), &m); err != nil {
		t.Fatalf("JSON: %v", err)
	}
	if m["trace_id"] != "trace-1" || m["user_id"] != "user-9" {
		t.Fatalf("With 未继承: %v", m)
	}
}

// TestHandlerBranches：成功/失败路径日志与状态码
func TestHandlerBranches(t *testing.T) {
	var buf bytes.Buffer
	h := handleEcho(newLogger(&buf, slog.LevelDebug))

	// 缺 name → 400 + warn
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest("GET", "/api/echo", nil))
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("缺 name: %d", rr.Code)
	}
	if !strings.Contains(buf.String(), "missing name param") {
		t.Fatal("缺 name 应记 warn")
	}

	// 带 name → 200 + 完成日志含 latency_ms
	buf.Reset()
	rr2 := httptest.NewRecorder()
	h.ServeHTTP(rr2, httptest.NewRequest("GET", "/api/echo?name=alice", nil))
	if rr2.Code != http.StatusOK {
		t.Fatalf("带 name: %d", rr2.Code)
	}
	if !strings.Contains(buf.String(), "request done") || !strings.Contains(buf.String(), "latency_ms") {
		t.Fatalf("完成日志缺失: %s", buf.String())
	}
}

// TestInfoContext：InfoContext 可用且输出正常（context 版本 API）
func TestInfoContext(t *testing.T) {
	var buf bytes.Buffer
	logger := newLogger(&buf, slog.LevelInfo)
	logger.InfoContext(context.Background(), "ctx event", "n", 1)
	if !strings.Contains(buf.String(), "ctx event") {
		t.Fatalf("InfoContext 输出缺失: %s", buf.String())
	}
}

// TestLevelFromEnv：LOG_LEVEL 环境变量映射
func TestLevelFromEnv(t *testing.T) {
	old := os.Getenv("LOG_LEVEL")
	defer os.Setenv("LOG_LEVEL", old)
	os.Setenv("LOG_LEVEL", "debug")
	if levelFromEnv() != slog.LevelDebug {
		t.Fatal("debug 映射失败")
	}
	os.Setenv("LOG_LEVEL", "error")
	if levelFromEnv() != slog.LevelError {
		t.Fatal("error 映射失败")
	}
	os.Setenv("LOG_LEVEL", "unknown")
	if levelFromEnv() != slog.LevelInfo {
		t.Fatal("未知级别应回退 info")
	}
}
