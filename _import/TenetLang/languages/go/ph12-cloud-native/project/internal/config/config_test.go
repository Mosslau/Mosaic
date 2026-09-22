package config

import (
	"errors"
	"log/slog"
	"testing"
	"time"
)

type env map[string]string

func (e env) get(k string) string { return e[k] }

func TestLoadDefaults(t *testing.T) {
	cfg, err := Load(env{"DB_URL": "postgres://u:p@db/app"}.get)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Port != 58010 || cfg.LogLevel != slog.LevelInfo ||
		cfg.ShutdownTimeout != 10*time.Second || !cfg.EnableMetrics {
		t.Fatalf("默认值异常: %+v", cfg)
	}
	if cfg.ListenAddr() != ":58010" {
		t.Fatalf("Addr() = %q", cfg.ListenAddr())
	}
}

func TestLoadOverrides(t *testing.T) {
	cfg, err := Load(env{
		"PORT": "9901", "DB_URL": "x", "LOG_LEVEL": "warn",
		"SHUTDOWN_TIMEOUT": "30s", "ENABLE_METRICS": "false",
	}.get)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Port != 9901 || cfg.LogLevel != slog.LevelWarn ||
		cfg.ShutdownTimeout != 30*time.Second || cfg.EnableMetrics {
		t.Fatalf("覆盖未生效: %+v", cfg)
	}
}

func TestAddrExplicit(t *testing.T) {
	cfg, _ := Load(env{"ADDR": "127.0.0.1:9000", "DB_URL": "x"}.get)
	if cfg.ListenAddr() != "127.0.0.1:9000" {
		t.Fatalf("显式 ADDR 应优先: %q", cfg.ListenAddr())
	}
}

func TestMissingRequired(t *testing.T) {
	_, err := Load(env{}.get)
	if err == nil {
		t.Fatal("缺 DB_URL 应报错")
	}
	var me *MissingError
	if !errors.As(err, &me) || me.Key != "DB_URL" {
		t.Fatalf("errors.As: %v", err)
	}
	if !errors.Is(err, &MissingError{Key: "DB_URL"}) {
		t.Fatalf("errors.Is 应命中: %v", err)
	}
}

func TestInvalidValues(t *testing.T) {
	cases := []struct {
		name string
		env  env
	}{
		{"PORT 非数字", env{"PORT": "abc", "DB_URL": "x"}},
		{"PORT 越界", env{"PORT": "0", "DB_URL": "x"}},
		{"LOG_LEVEL 非法", env{"LOG_LEVEL": "verbose", "DB_URL": "x"}},
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

func TestMaskDBURL(t *testing.T) {
	if got := MaskDBURL("postgres://user:pw@db:5432/app"); got != "postgres://user:***@db:5432/app" {
		t.Fatalf("mask = %q", got)
	}
	if MaskDBURL("plain") != "plain" {
		t.Fatal("无凭据串不应被改")
	}
}
