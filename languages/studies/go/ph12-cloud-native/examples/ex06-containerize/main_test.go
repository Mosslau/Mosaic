package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// TestHealthz：/healthz 返回 200 + {"status":"ok"}（容器 HEALTHCHECK 与 K8s liveness 共用）
func TestHealthz(t *testing.T) {
	h := newHandler()
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest("GET", "/healthz", nil))
	if rr.Code != http.StatusOK {
		t.Fatalf("healthz = %d, want 200", rr.Code)
	}
	var m map[string]string
	if err := json.Unmarshal(rr.Body.Bytes(), &m); err != nil || m["status"] != "ok" {
		t.Fatalf("healthz body = %q", rr.Body.String())
	}
}

// TestRoot：根路径返回服务标识（冒烟：容器起来后 curl / 应看到这个 JSON）
func TestRoot(t *testing.T) {
	h := newHandler()
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest("GET", "/", nil))
	body, _ := io.ReadAll(rr.Body)
	if !strings.Contains(string(body), `"service":"ph12-ex06"`) {
		t.Fatalf("root body = %q", body)
	}
}

// TestUnknownPath：未注册路径 404
func TestUnknownPath(t *testing.T) {
	h := newHandler()
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest("GET", "/nope", nil))
	if rr.Code != http.StatusNotFound {
		t.Fatalf("unknown path = %d, want 404", rr.Code)
	}
}
