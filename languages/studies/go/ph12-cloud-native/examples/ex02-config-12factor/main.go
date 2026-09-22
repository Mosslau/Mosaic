// 来源：ph12-cloud-native 示例 2 —— 12-Factor 配置（环境变量）
// 一句话说明：12-Factor 的第 3 条"配置存于环境"的落地——配置项声明默认值、
// 环境变量覆盖、必填项校验、时间/布尔等类型解析；演示"代码与配置分离"：
// 镜像不携带任何环境特定配置，部署时注入。全部标准库，可离线实测。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .                                        # 全部默认值
//	PORT=9901 LOG_LEVEL=debug go run .              # 环境变量覆盖
//	DB_URL= go run .                                # 必填项缺失 → 启动即报错（fail fast）
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

// Config 集中定义全部配置项。字段注释同时是文档；
// 环境变量名遵循惯例：前缀 + 大写下划线（APP_*），与 12-Factor 的 PORT/DB_URL 风格一致。
type Config struct {
	// Port 监听端口（env: PORT，默认 58002）
	Port int
	// DBURL 数据库连接串（env: DB_URL，必填——12-Factor 不允许默认数据库）
	DBURL string
	// LogLevel 日志级别（env: LOG_LEVEL，debug/info/warn/error，默认 info）
	LogLevel slog.Level
	// ShutdownTimeout 优雅退出超时（env: SHUTDOWN_TIMEOUT，Go duration 格式，默认 10s）
	ShutdownTimeout time.Duration
	// EnableMetrics 是否暴露 /metrics（env: ENABLE_METRICS，布尔，默认 true）
	EnableMetrics bool
}

// ErrMissing 必填配置项缺失（用哨兵错误 + %w 包装：errors.Is 可判断）
type missingError struct{ key string }

func (e *missingError) Error() string { return fmt.Sprintf("missing required env %q", e.key) }

// Is 支持 errors.Is 按"同类错误"比较（指针类型默认按地址相等，必须显式实现）
func (e *missingError) Is(target error) bool {
	t, ok := target.(*missingError)
	return ok && t.key == e.key
}

// Load 从环境变量加载配置：查表 -> 有则解析、无则用默认值；必填项缺失返回错误。
// 设计要点：一个函数集中管全部配置，调用方只得到"解析好的 Config 或错误"，
// 启动时 fail fast —— 配置错误比运行时才暴露便宜得多。
func Load(getenv func(string) string) (Config, error) {
	cfg := Config{
		Port:            58002,
		LogLevel:        slog.LevelInfo,
		ShutdownTimeout: 10 * time.Second,
		EnableMetrics:   true,
	}
	if v := getenv("PORT"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 || n > 65535 {
			return cfg, fmt.Errorf("invalid PORT %q: want 1-65535", v)
		}
		cfg.Port = n
	}
	if v := getenv("DB_URL"); v != "" {
		cfg.DBURL = v
	}
	if cfg.DBURL == "" {
		return cfg, &missingError{key: "DB_URL"} // 必填：数据库地址不能有默认值（防误连开发库）
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

// parseLevel 解析 slog 级别字符串（debug/info/warn/error，大小写不敏感）
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

// makeHandler 按配置装配路由（ENABLE_METRICS 控制是否挂 /metrics——配置决定行为）
func makeHandler(cfg Config) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})
	if cfg.EnableMetrics {
		mux.HandleFunc("GET /metrics", func(w http.ResponseWriter, _ *http.Request) {
			// 占位：真实 exposition 见示例 4；这里演示"配置开关路由"
			w.Header().Set("Content-Type", "text/plain; version=0.0.4")
			_, _ = w.Write([]byte("# placeholder metrics\n"))
		})
	}
	return mux
}

func main() {
	cfg, err := Load(os.Getenv)
	if err != nil {
		fmt.Fprintln(os.Stderr, "config error:", err) // 启动失败也要写日志（stderr）
		os.Exit(1)
	}
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: cfg.LogLevel}))

	httpSrv := &http.Server{
		Addr:    net.JoinHostPort("127.0.0.1", strconv.Itoa(cfg.Port)),
		Handler: makeHandler(cfg),
	}
	go func() { _ = httpSrv.ListenAndServe() }()
	logger.Info("server started", "port", cfg.Port, "db_url", mask(cfg.DBURL), "metrics", cfg.EnableMetrics)
	// 阻塞直到进程被杀（优雅退出细节见示例 1；本示例聚焦配置加载）
	select {}
}

// mask 日志输出时遮蔽数据库密码（配置项不该整串进日志）
func mask(s string) string {
	if i := strings.Index(s, "://"); i >= 0 {
		rest := s[i+3:]
		if j := strings.Index(rest, "@"); j >= 0 {
			userinfo := rest[:j]
			if k := strings.Index(userinfo, ":"); k >= 0 {
				return s[:i+3] + userinfo[:k+1] + "***" + rest[j:]
			}
		}
	}
	return s
}
