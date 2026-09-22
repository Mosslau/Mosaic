package main

import (
	"errors"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// env 测试用最小环境变量表
type env map[string]string

func (e env) get(k string) string { return e[k] }

func TestDefaults(t *testing.T) {
	cfg, err := Load(env{"DB_URL": "postgres://u:p@db/app"}.get)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Port != 58002 || cfg.LogLevel != slog.LevelInfo ||
		cfg.ShutdownTimeout != 10*time.Second || !cfg.EnableMetrics {
		t.Fatalf("默认值异常: %+v", cfg)
	}
}

func TestOverrides(t *testing.T) {
	cfg, err := Load(env{
		"PORT": "9901", "DB_URL": "x", "LOG_LEVEL": "debug",
		"SHUTDOWN_TIMEOUT": "30s", "ENABLE_METRICS": "false",
	}.get)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Port != 9901 || cfg.LogLevel != slog.LevelDebug ||
		cfg.ShutdownTimeout != 30*time.Second || cfg.EnableMetrics {
		t.Fatalf("覆盖未生效: %+v", cfg)
	}
}

func TestMissingDBURL(t *testing.T) {
	_, err := Load(env{}.get)
	if err == nil {
		t.Fatal("缺 DB_URL 应报错")
	}
	var me *MissingEnvError
	if !errors.As(err, &me) || me.Key != "DB_URL" {
		t.Fatalf("errors.As 异常: %v", err)
	}
	if !errors.Is(err, &MissingEnvError{Key: "DB_URL"}) {
		t.Fatalf("errors.Is 应命中: %v", err)
	}
}

func TestInvalidValues(t *testing.T) {
	cases := []struct {
		name string
		env  env
	}{
		{"PORT 非数字", env{"PORT": "abc", "DB_URL": "x"}},
		{"PORT 越界", env{"PORT": "70000", "DB_URL": "x"}},
		{"PORT 为 0", env{"PORT": "0", "DB_URL": "x"}},
		{"LOG_LEVEL 非法", env{"LOG_LEVEL": "verbose", "DB_URL": "x"}},
		{"超时负值", env{"SHUTDOWN_TIMEOUT": "-5s", "DB_URL": "x"}},
		{"超时非法", env{"SHUTDOWN_TIMEOUT": "abc", "DB_URL": "x"}},
		{"布尔非法", env{"ENABLE_METRICS": "maybe", "DB_URL": "x"}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if _, err := Load(tc.env.get); err == nil {
				t.Fatal("非法值应报错")
			}
		})
	}
}

// 错误信息应带字段名（可定位是哪个配置项错了）
func TestErrorHasFieldContext(t *testing.T) {
	_, err := Load(env{"PORT": "abc", "DB_URL": "x"}.get)
	if err == nil || !contains(err.Error(), "PORT") {
		t.Fatalf("错误应带字段名 PORT: %v", err)
	}
}

func contains(s, sub string) bool {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}

func TestMetricsToggle(t *testing.T) {
	cfg, _ := Load(env{"DB_URL": "x"}.get)
	if cfg.EnableMetrics {
		h := newHandler(cfg)
		rr := httptest.NewRecorder()
		h.ServeHTTP(rr, httptest.NewRequest("GET", "/metrics", nil))
		if rr.Code != http.StatusOK {
			t.Fatalf("metrics on: %d, want 200", rr.Code)
		}
	}

	cfgOff, _ := Load(env{"DB_URL": "x", "ENABLE_METRICS": "false"}.get)
	h2 := newHandler(cfgOff)
	rr2 := httptest.NewRecorder()
	h2.ServeHTTP(rr2, httptest.NewRequest("GET", "/metrics", nil))
	if rr2.Code != http.StatusNotFound {
		t.Fatalf("metrics off: %d, want 404", rr2.Code)
	}
}

func TestMask(t *testing.T) {
	if got := mask("postgres://user:pw@db:5432/app"); got != "postgres://user:***@db:5432/app" {
		t.Fatalf("mask = %q", got)
	}
	if mask("plain") != "plain" {
		t.Fatal("无凭据串不应被改")
	}
}
