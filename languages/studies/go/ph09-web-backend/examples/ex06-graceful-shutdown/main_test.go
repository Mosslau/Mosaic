// 来源：09-web-backend.md 第 6 章示例 6 —— 优雅关闭与超时
// 一句话说明：buildServer 的可测试部分——handler 行为 + 超时配置断言；
// 信号处理与 Shutdown 流程用本地端口冒烟测试验证（见 main.go 头部注释）。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestHealthz(t *testing.T) {
	srv := buildServer("127.0.0.1:0")
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	srv.Handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK || rec.Body.String() != "ok" {
		t.Errorf("healthz = %d %q, 期望 200 ok", rec.Code, rec.Body.String())
	}
}

// TestServerTimeouts 显式超时都已配置（生产服务防慢客户端的基本功）
func TestServerTimeouts(t *testing.T) {
	srv := buildServer("127.0.0.1:0")
	cases := []struct {
		name string
		got  time.Duration
	}{
		{"ReadHeaderTimeout", srv.ReadHeaderTimeout},
		{"ReadTimeout", srv.ReadTimeout},
		{"WriteTimeout", srv.WriteTimeout},
		{"IdleTimeout", srv.IdleTimeout},
	}
	for _, tc := range cases {
		if tc.got <= 0 {
			t.Errorf("%s 未配置（= %v）", tc.name, tc.got)
		}
	}
}
