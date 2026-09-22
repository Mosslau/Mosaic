// Package config 12-Factor 配置加载：默认值 + 环境变量覆盖 + 必填校验 + 类型解析。
// 设计：Load 接受 getenv 注入（测试不触碰真实环境）；全部校验在此集中 fail-fast，
// 配置错误在启动时暴露而非运行时。
package config

import (
	"fmt"
	"log/slog"
	"os"
	"strconv"
	"strings"
	"time"
)

// Config 全部配置项（注释即文档；环境变量名：大写下划线，前缀可选）
type Config struct {
	// Addr 监听地址（env: ADDR，默认 :58010——容器内由 PORT 注入）
	Addr string
	// Port 业务端口（env: PORT，默认 58010；ADDR 与 PORT 同时给时优先 ADDR）
	Port int
	// DBURL 数据库连接串（env: DB_URL，必填）
	DBURL string
	// LogLevel 日志级别（env: LOG_LEVEL，debug/info/warn/error，默认 info）
	LogLevel slog.Level
	// ShutdownTimeout 优雅退出超时（env: SHUTDOWN_TIMEOUT，默认 10s）
	ShutdownTimeout time.Duration
	// EnableMetrics 是否暴露 /metrics（env: ENABLE_METRICS，默认 true）
	EnableMetrics bool
}

// MissingError 必填配置项缺失（errors.Is/As 可定位 key）
type MissingError struct{ Key string }

func (e *MissingError) Error() string { return fmt.Sprintf("missing required env %q", e.Key) }

// Is 支持 errors.Is 按 key 命中
func (e *MissingError) Is(target error) bool {
	t, ok := target.(*MissingError)
	return ok && t.Key == e.Key
}

// Load 从环境变量加载配置
func Load(getenv func(string) string) (Config, error) {
	cfg := Config{
		Port:            58010,
		LogLevel:        slog.LevelInfo,
		ShutdownTimeout: 10 * time.Second,
		EnableMetrics:   true,
	}
	if v := getenv("PORT"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n < 1 || n > 65535 {
			return cfg, fmt.Errorf("invalid PORT %q: want integer 1-65535", v)
		}
		cfg.Port = n
	}
	if v := getenv("ADDR"); v != "" {
		cfg.Addr = v // 显式地址（如 "127.0.0.1:9000"）优先于 PORT
	}
	if v := getenv("DB_URL"); v != "" {
		cfg.DBURL = v
	}
	if cfg.DBURL == "" {
		return cfg, &MissingError{Key: "DB_URL"} // 必填：防误连开发库
	}
	if v := getenv("LOG_LEVEL"); v != "" {
		lv, err := parseLevel(v)
		if err != nil {
			return cfg, err
		}
		cfg.LogLevel = lv
	}
	if v := getenv("SHUTDOWN_TIMEOUT"); v != "" {
		d, err := time.ParseDuration(v)
		if err != nil || d <= 0 {
			return cfg, fmt.Errorf("invalid SHUTDOWN_TIMEOUT %q: want positive duration like 30s", v)
		}
		cfg.ShutdownTimeout = d
	}
	if v := getenv("ENABLE_METRICS"); v != "" {
		b, err := strconv.ParseBool(v)
		if err != nil {
			return cfg, fmt.Errorf("invalid ENABLE_METRICS %q: want true/false", v)
		}
		cfg.EnableMetrics = b
	}
	return cfg, nil
}

// LoadFromEnv 从真实环境加载（main 入口用）
func LoadFromEnv() (Config, error) { return Load(os.Getenv) }

// ListenAddr 计算最终监听地址（显式 ADDR 优先，否则 ":"+PORT 供容器监听任意网卡）
func (c Config) ListenAddr() string {
	if c.Addr != "" {
		return c.Addr
	}
	return ":" + strconv.Itoa(c.Port)
}

func parseLevel(s string) (slog.Level, error) {
	switch strings.ToLower(s) {
	case "debug":
		return slog.LevelDebug, nil
	case "info":
		return slog.LevelInfo, nil
	case "warn":
		return slog.LevelWarn, nil
	case "error":
		return slog.LevelError, nil
	}
	return 0, fmt.Errorf("invalid LOG_LEVEL %q: want debug/info/warn/error", s)
}

// MaskDBURL 日志脱敏：postgres://user:***@host/db
func MaskDBURL(s string) string {
	i := strings.Index(s, "://")
	if i < 0 {
		return s
	}
	rest := s[i+3:]
	j := strings.Index(rest, "@")
	if j < 0 {
		return s
	}
	userinfo := rest[:j]
	if k := strings.Index(userinfo, ":"); k >= 0 {
		return s[:i+3] + userinfo[:k+1] + "***" + rest[j:]
	}
	return s
}
