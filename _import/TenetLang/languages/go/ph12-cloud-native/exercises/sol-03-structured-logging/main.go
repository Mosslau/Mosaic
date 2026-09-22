// 来源：ph12-cloud-native 练习 3 参考实现 —— slog 结构化日志
// 一句话说明：roadmap「能查看日志」的落地——JSON handler（采集系统直接消费）、
// 级别过滤、AddSource（日志带 file:line）、With 请求级上下文、handler 三处埋点
// （进入/参数缺失 Warn/完成含 latency）、InfoContext 传 ctx。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .                        # JSON 日志行输出到 stdout
//	LOG_LEVEL=error go run .        # 级别过滤：info/warn 被丢弃
//
// 验证状态：已验证（go1.25.6）
// 覆盖率：go test -cover 实测 **60.7%**（go1.25.6，6 个用例全过：JSON 行合法/级别过滤/
// With 继承/handler 双分支日志/InfoContext/LOG_LEVEL 映射）
package main

import (
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"time"
)

// newLogger JSON 结构化 logger：级别可配、带 source 定位
func newLogger(w io.Writer, level slog.Level) *slog.Logger {
	return slog.New(slog.NewJSONHandler(w, &slog.HandlerOptions{
		Level:     level,
		AddSource: true,
	}))
}

// requestLogger 请求级上下文：With 注入的字段（trace_id/user_id）自动带到后续所有日志
func requestLogger(base *slog.Logger, traceID, userID string) *slog.Logger {
	return base.With("trace_id", traceID, "user_id", userID)
}

// handleEcho 埋点示例：进入（InfoContext 带 ctx）/参数缺失（Warn + 400）/完成（latency_ms）
func handleEcho(logger *slog.Logger) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		logger.InfoContext(r.Context(), "request started", "method", r.Method, "path", r.URL.Path)

		name := r.URL.Query().Get("name")
		if name == "" {
			logger.Warn("missing name param") // 业务异常但非致命 → Warn
			w.WriteHeader(http.StatusBadRequest)
			_, _ = w.Write([]byte(`{"error":"name required"}`))
			return
		}
		_, _ = w.Write([]byte(fmt.Sprintf(`{"echo":"hello %s"}`, name)))
		logger.Info("request done", "name", name,
			"latency_ms", time.Since(start).Milliseconds())
	}
}

func main() {
	logger := newLogger(os.Stdout, levelFromEnv())
	logger.Info("service starting", "version", "1.0.0")

	reqLog := requestLogger(logger, "trace-abc", "user-42")
	reqLog.Info("auth ok", "expires_in", 3600)

	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/echo", handleEcho(logger))
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})
	logger.Info("listening", "addr", "127.0.0.1:59003")
	_ = http.ListenAndServe("127.0.0.1:59003", mux)
}

// levelFromEnv 从 LOG_LEVEL 读级别（默认 info）
func levelFromEnv() slog.Level {
	switch os.Getenv("LOG_LEVEL") {
	case "debug":
		return slog.LevelDebug
	case "warn":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	}
	return slog.LevelInfo
}
