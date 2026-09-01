// 来源：ph12-cloud-native 练习 2 参考实现 —— 12-Factor 配置加载器
// 一句话说明：roadmap「能配置环境变量」的落地——集中式 Config、默认值 + 环境变量覆盖、
// 必填项（DB_URL）缺失 fail-fast、五类配置项的类型解析与校验（错误带字段上下文）、
// 配置驱动路由装配（ENABLE_METRICS 关掉 /metrics）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .                                  # DB_URL 缺失 → 启动即报错（fail fast）
//	DB_URL=postgres://u:p@db/app go run .     # 通过
//
// 验证状态：已验证（go1.25.6）
// 覆盖率：go test -cover 实测 **75.8%**（go1.25.6，9 个用例全过：默认值/覆盖/必填缺失
// errors.As+Is/五类非法值×7/错误带字段上下文/指标开关/脱敏）
package main

import (
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

// Config 全部配置项集中定义（注释即文档）
type Config struct {
	Port            int           // PORT，默认 58002
	DBURL           string        // DB_URL，必填
	LogLevel        slog.Level    // LOG_LEVEL：debug/info/warn/error
	ShutdownTimeout time.Duration // SHUTDOWN_TIMEOUT，默认 10s
	EnableMetrics   bool          // ENABLE_METRICS，默认 true
}

// MissingEnvError 必填项缺失（errors.As 可定位是哪个 key）
type MissingEnvError struct{ Key string }

func (e *MissingEnvError) Error() string { return fmt.Sprintf("missing required env %q", e.Key) }

// Is 让 errors.Is 按"同类 + 同 key"命中
func (e *MissingEnvError) Is(target error) bool {
	t, ok := target.(*MissingEnvError)
	return ok && t.Key == e.Key
}

// Load 从环境变量加载配置。getenv 注入使测试不触碰真实环境。
func Load(getenv func(string) string) (Config, error) {
	cfg := Config{
		Port:            58002,
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
	if v := getenv("DB_URL"); v != "" {
		cfg.DBURL = v
	}
	if cfg.DBURL == "" {
		return cfg, &MissingEnvError{Key: "DB_URL"} // fail fast：比运行时连不上库早暴露
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

// parseLevel 解析日志级别（大小写不敏感）
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

// newHandler 按配置装配路由：ENABLE_METRICS 决定 /metrics 是否暴露
func newHandler(cfg Config) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})
	if cfg.EnableMetrics {
		mux.HandleFunc("GET /metrics", func(w http.ResponseWriter, _ *http.Request) {
			w.Header().Set("Content-Type", "text/plain; version=0.0.4")
			_, _ = w.Write([]byte("# metrics enabled\n"))
		})
	}
	return mux
}

func main() {
	cfg, err := Load(os.Getenv)
	if err != nil {
		fmt.Fprintln(os.Stderr, "config error:", err)
		os.Exit(1)
	}
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: cfg.LogLevel}))
	logger.Info("config loaded", "port", cfg.Port, "db_url", mask(cfg.DBURL),
		"shutdown_timeout", cfg.ShutdownTimeout.String(), "metrics", cfg.EnableMetrics)
	// 服务启动（演示到配置生效为止；完整 HTTP 服务见 project/）
	_ = newHandler(cfg)
}

// mask 日志脱敏：postgres://user:***@db:5432/app（密码不进日志）
func mask(s string) string {
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
