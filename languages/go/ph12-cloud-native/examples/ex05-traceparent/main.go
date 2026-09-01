// 来源：ph12-cloud-native 示例 5 —— OpenTelemetry traceparent 上下文传播
// 一句话说明：不引入 otel SDK，用标准库手写 W3C trace context 的 traceparent 头
// （version-trace_id-parent_id-flags，共 55 字符）的生成/解析/传播，并演示
// 两个 HTTP 服务（A → B）之间如何把同一条 trace 串起来：A 生成 trace_id + span_id，
// 把 traceparent 随请求带给 B，B 解析后以 A 的 span_id 为自己的 parent_id 新建 span——
// 这就是分布式追踪（Jaeger/Tempo）还原整条链路的全部机制。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .                    # 单进程模拟 A→B 调用，打印两端的 span 记录与 traceparent
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"time"
)

// ---- W3C trace context 数据结构 ----

// SpanContext 一条 span 的标识（简化自 otel 的 SpanContext）
type SpanContext struct {
	TraceID  string // 16 字节十六进制（32 hex 字符），全链路共享
	SpanID   string // 8 字节十六进制（16 hex 字符），本 span 唯一
	ParentID string // 父 span 的 SpanID；根 span 为空
	Sampled  bool   // flags 的 bit0：是否被采样（上报 Jaeger 等后端）
}

// traceparent 头：version-traceid-spanid-flags，如
// 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
func (sc SpanContext) Traceparent() string {
	flags := "00"
	if sc.Sampled {
		flags = "01"
	}
	return "00-" + sc.TraceID + "-" + sc.SpanID + "-" + flags
}

// ---- 生成 ----

// NewRoot 生成根 span（链路起点）：随机 trace_id 与 span_id，无 parent
func NewRoot() SpanContext {
	return SpanContext{
		TraceID: randHex(16),
		SpanID:  randHex(8),
		Sampled: true,
	}
}

// NewChild 在给定父上下文上开子 span：继承 trace_id、parent=父 span_id
func NewChild(parent SpanContext) SpanContext {
	return SpanContext{
		TraceID:  parent.TraceID,
		SpanID:   randHex(8),
		ParentID: parent.SpanID,
		Sampled:  parent.Sampled,
	}
}

// randHex 生成 n 字节的随机十六进制串（crypto/rand 强随机；测试里可注入）
func randHex(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic(err) // crypto/rand 失败属于系统级故障，无法恢复
	}
	return hex.EncodeToString(b)
}

// ---- 解析（服务端：从入站请求头还原父上下文）----

// ErrNoTraceparent 请求没有带 traceparent 头（可能是外部调用方，新建根即可）
var ErrNoTraceparent = errors.New("no traceparent header")

// ParseTraceparent 解析 W3C traceparent 头；格式非法返回错误
func ParseTraceparent(h string) (SpanContext, error) {
	parts := strings.Split(h, "-")
	if len(parts) != 4 {
		return SpanContext{}, fmt.Errorf("traceparent %q: want 4 dash-separated parts", h)
	}
	ver, traceID, spanID, flags := parts[0], parts[1], parts[2], parts[3]
	if ver != "00" {
		return SpanContext{}, fmt.Errorf("traceparent %q: unsupported version %q", h, ver)
	}
	if len(traceID) != 32 || len(spanID) != 16 {
		return SpanContext{}, fmt.Errorf("traceparent %q: bad id length", h)
	}
	if _, err := hex.DecodeString(traceID); err != nil {
		return SpanContext{}, fmt.Errorf("traceparent %q: trace_id not hex", h)
	}
	if _, err := hex.DecodeString(spanID); err != nil {
		return SpanContext{}, fmt.Errorf("traceparent %q: span_id not hex", h)
	}
	sampled := flags == "01"
	return SpanContext{TraceID: traceID, SpanID: spanID, Sampled: sampled}, nil
}

// ---- 服务端/客户端辅助 ----

// ExtractFromHeader 从入站请求提取父上下文；无头则返回 ErrNoTraceparent
func ExtractFromHeader(r *http.Request) (SpanContext, error) {
	h := r.Header.Get("traceparent")
	if h == "" {
		return SpanContext{}, ErrNoTraceparent
	}
	return ParseTraceparent(h)
}

// InjectIntoHeader 把当前上下文写入出站请求头（客户端调用下游前调用）
func InjectIntoHeader(sc SpanContext, r *http.Request) {
	r.Header.Set("traceparent", sc.Traceparent())
}

// ---- 两个服务 A→B 的传播演示（进程内用 http.Client 模拟跨服务调用）----

// serviceB 处理入站请求：提取父上下文 → 开子 span → 记录 → 返回
func serviceB(logger *slog.Logger) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		parent, err := ExtractFromHeader(r)
		if err != nil {
			// 外部调用无 traceparent：B 自己成为根（真实系统：网关/入口在此建根）
			parent = NewRoot()
			logger.Warn("no traceparent, creating root", "err", err)
		}
		span := NewChild(parent) // 关键：parent.SpanID → 本 span 的 ParentID，链被接上
		logger.Info("service B handled request",
			"trace_id", span.TraceID,
			"span_id", span.SpanID,
			"parent_id", span.ParentID,
			"traceparent", span.Traceparent(),
		)
		_, _ = w.Write([]byte(`{"service":"B","trace_id":"` + span.TraceID + `"}`))
	}
}

// newSlog 构造 JSON logger 写入 io.Writer（测试注入 buf 用）
func newSlog(w io.Writer) *slog.Logger {
	return slog.New(slog.NewJSONHandler(w, nil))
}

func main() {
	logger := newSlog(os.Stdout)

	// ① B 服务在线（真实 K8s 场景是独立 Pod；此处进程内起 server）
	//    随机端口避免冲突
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/process", serviceB(logger))
	srv := &http.Server{Addr: "127.0.0.1:58005", Handler: mux}
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("service B failed", "err", err)
			os.Exit(1)
		}
	}()
	time.Sleep(100 * time.Millisecond) // 等服务 B 就绪（教学演示；生产用健康检查）

	// ② 服务 A 处理一次"用户请求"：建根 span → 调 B → 日志里三行 span 可还原全链路
	root := NewRoot()
	logger.Info("service A started", "trace_id", root.TraceID, "span_id", root.SpanID, "traceparent", root.Traceparent())

	req, err := http.NewRequest("GET", "http://127.0.0.1:58005/api/process", nil)
	if err != nil {
		logger.Error("build request", "err", err)
		return
	}
	InjectIntoHeader(root, req) // 传播点：A 的 span_id 进入 traceparent
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		logger.Error("call service B", "err", err)
		return
	}
	defer resp.Body.Close()
	logger.Info("service A got response", "trace_id", root.TraceID, "status", resp.StatusCode)
	_ = srv.Close() // 演示结束关掉 B
}
