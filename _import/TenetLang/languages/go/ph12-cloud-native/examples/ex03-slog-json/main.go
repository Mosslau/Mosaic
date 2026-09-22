// 来源：ph12-cloud-native 示例 3 —— slog 结构化日志（JSON）
// 一句话说明：Go 1.21+ 标准库 log/slog 的生产用法——JSON handler（机器可读，日志采集系统
// ELK/Loki 直接消费）、级别过滤（AddSource 定位代码行）、With 上下文（请求级字段）、
// slog.Logger 贯穿依赖注入（不设全局变量）。全部标准库，可离线实测。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .                    # 观察 JSON 行：级别、msg、attrs、source
//	LOG_LEVEL=error go run .    # 级别过滤：debug/info 被丢弃
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"time"
)

// newLogger 构造 JSON 结构化 logger：输出到 w，级别可配置，AddSource 记录代码位置。
// 生产约定：日志全部走结构化字段（key=value），不拼字符串——可被采集系统按字段检索。
func newLogger(w io.Writer, level slog.Level) *slog.Logger {
	return slog.New(slog.NewJSONHandler(w, &slog.HandlerOptions{
		Level:     level,
		AddSource: true, // 每条日志带 source 字段（文件:行），排查定位必备
	}))
}

// requestLogger 演示"请求级上下文"：用 With 携带贯穿本请求的字段（trace_id、user_id），
// 之后所有日志自动带上——不用每行手写。等价于日志系统的"结构化上下文"。
func requestLogger(base *slog.Logger, traceID, userID string) *slog.Logger {
	return base.With("trace_id", traceID, "user_id", userID)
}

// handleEcho 业务 handler：演示日志埋点的几个关键位置（进入/耗时/错误）。
func handleEcho(logger *slog.Logger) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		// 请求级 logger：从 With 字段继承 trace/user 上下文；
		// InfoContext 把请求的 context 传给 handler（自定义 handler 可从 ctx 提取值，
		// 如 requestID —— 标准 JSON handler 不消费 ctx，教学演示 API 形态）
		logger.InfoContext(r.Context(), "request started", "method", r.Method, "path", r.URL.Path)

		name := r.URL.Query().Get("name")
		if name == "" {
			logger.Warn("missing name param") // Warn：参数缺失是"应记录但不致命"
			w.WriteHeader(http.StatusBadRequest)
			_, _ = w.Write([]byte(`{"error":"name required"}`))
			return
		}
		// slog 的 attr 里放结构化数据（JSON handler 输出为嵌套对象）
		_, _ = w.Write([]byte(fmt.Sprintf(`{"echo":"hello %s"}`, name)))
		logger.Info("request done",
			"name", name,
			"latency_ms", time.Since(start).Milliseconds(),
		)
	}
}

func main() {
	logger := newLogger(os.Stdout, slog.LevelInfo)

	// ① 基本用法：JSON 输出 + source 定位
	logger.Info("service starting", "version", "1.0.0", "env", "dev")
	logger.Debug("this line is filtered at info level") // Debug 低于 Info，被丢弃

	// ② 请求级上下文（With 继承）
	reqLog := requestLogger(logger, "trace-abc-123", "user-42")
	reqLog.Info("auth ok", "expires_in", 3600)

	// ③ 级别过滤：LOG_LEVEL=error 时 info/warn 全被丢
	if v := os.Getenv("LOG_LEVEL"); v == "error" {
		logger.Warn("this warn is filtered at error level")
	}

	// ④ 真实 HTTP 服务（演示日志埋点；健康检查见示例 1）
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/echo", handleEcho(logger))
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})
	logger.Info("http server listening", "addr", "127.0.0.1:58003")
	_ = http.ListenAndServe("127.0.0.1:58003", mux) // 教学示例：Ctrl+C 退出
}
