package main

import (
	"errors"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestDefaults(t *testing.T) {
	// 必填项 DB_URL 必须提供；其余项应取默认值
	cfg, err := Load(func(k string) string {
		if k == "DB_URL" {
			return "postgres://u:p@db/app"
		}
		return ""
	})
	if err != nil {
		t.Fatalf("Load(defaults): %v", err)
	}
	if cfg.Port != 58002 || cfg.LogLevel != slog.LevelInfo ||
		cfg.ShutdownTimeout != 10*time.Second || !cfg.EnableMetrics {
		t.Fatalf("defaults 异常: %+v", cfg)
	}
}

func TestEnvOverrides(t *testing.T) {
	env := map[string]string{
		"PORT":             "9901",
		"DB_URL":           "postgres://user:pw@db:5432/app",
		"LOG_LEVEL":        "DEBUG", // 大小写不敏感
		"SHUTDOWN_TIMEOUT": "30s",
		"ENABLE_METRICS":   "false",
	}
	cfg, err := Load(func(k string) string { return env[k] })
	if err != nil {
		t.Fatalf("Load(overrides): %v", err)
	}
	if cfg.Port != 9901 || cfg.LogLevel != slog.LevelDebug ||
		cfg.ShutdownTimeout != 30*time.Second || cfg.EnableMetrics {
		t.Fatalf("overrides 未生效: %+v", cfg)
	}
}

// 必填项缺失必须 fail fast，且错误可用 errors.Is 判断
func TestMissingRequired(t *testing.T) {
	_, err := Load(func(string) string { return "" })
	if err == nil {
		t.Fatal("缺 DB_URL 应报错")
	}
	var me *missingError
	if !errors.As(err, &me) || me.key != "DB_URL" {
		t.Fatalf("错误类型异常: %v", err)
	}
	if !errors.Is(err, &missingError{key: "DB_URL"}) {
		t.Fatalf("errors.Is 应命中 missingError(DB_URL): %v", err)
	}
}

func TestInvalidValues(t *testing.T) {
	cases := []struct {
		name string
		env  map[string]string
	}{
		{"PORT 非数字", map[string]string{"PORT": "abc", "DB_URL": "x"}},
		{"PORT 越界", map[string]string{"PORT": "70000", "DB_URL": "x"}},
		{"LOG_LEVEL 非法", map[string]string{"LOG_LEVEL": "verbose", "DB_URL": "x"}},
		{"超时非法", map[string]string{"SHUTDOWN_TIMEOUT": "-5s", "DB_URL": "x"}},
		{"布尔非法", map[string]string{"ENABLE_METRICS": "maybe", "DB_URL": "x"}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if _, err := Load(func(k string) string { return tc.env[k] }); err == nil {
				t.Fatal("非法值应报错")
			}
		})
	}
}

// 配置开关影响路由装配
func TestMetricsToggle(t *testing.T) {
	env := map[string]string{"DB_URL": "postgres://u:p@db/app"}
	cfg, err := Load(func(k string) string { return env[k] })
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	h := makeHandler(cfg)
	req := httptest.NewRequest("GET", "/metrics", nil)
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("metrics on: %d, want 200", rr.Code)
	}

	env["ENABLE_METRICS"] = "false"
	cfg2, _ := Load(func(k string) string { return env[k] })
	h2 := makeHandler(cfg2)
	rr2 := httptest.NewRecorder()
	h2.ServeHTTP(rr2, httptest.NewRequest("GET", "/metrics", nil))
	if rr2.Code != http.StatusNotFound {
		t.Fatalf("metrics off: %d, want 404", rr2.Code)
	}
}

// mask 遮蔽密码：postgres://user:***@db:5432/app
func TestMask(t *testing.T) {
	got := mask("postgres://user:pw@db:5432/app")
	want := "postgres://user:***@db:5432/app"
	if got != want {
		t.Fatalf("mask = %q, want %q", got, want)
	}
	if mask("no-scheme") != "no-scheme" {
		t.Fatal("无 scheme 的串不应被改")
	}
}
