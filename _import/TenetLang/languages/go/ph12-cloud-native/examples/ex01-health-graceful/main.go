// 来源：ph12-cloud-native 示例 1 —— 健康检查 + 优雅退出
// 一句话说明：生产级服务的三件套——/healthz（存活探针）与 /readyz（就绪探针）的语义与状态码
// 区分、SIGINT/SIGTERM 信号驱动的优雅退出（server.Shutdown 等存量请求处理完）、
// readiness 可被"依赖未就绪"置为 503。全部标准库，可离线实测。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .                    # 默认 127.0.0.1:58001，Ctrl+C 观察优雅退出日志
//	curl -i http://127.0.0.1:58001/healthz   # 200 {"status":"ok"}
//	curl -i http://127.0.0.1:58001/readyz    # 200（依赖未就绪时 503）
//	kill -TERM <pid>            # 观察 "shutting down" 日志与在途请求被处理完
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"context"
	"errors"
	"flag"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"
)

// server 持有健康状态。ready 用 atomic.Bool：/readyz 被高频轮询（K8s 每 10s 一次），
// 读路径不能加锁也不能有额外分配。
type server struct {
	ready atomic.Bool // false = 依赖未就绪，/readyz 返回 503
}

// newServer 启动时未就绪，直到 app 主动调用 MarkReady（如数据库连接成功后）
func newServer() *server {
	s := &server{}
	s.ready.Store(false)
	return s
}

// MarkReady 由应用在依赖就绪后调用（示例 2 的配置加载、project 的"依赖检查"同理）
func (s *server) MarkReady() { s.ready.Store(true) }

// handleHealthz 存活探针（liveness probe）：进程活着即 200。
// 语义：容器/实例"还活着吗"——活但不一定能服务（如依赖全断）也返回 200。
// 判据：不检查依赖，只确认"进程未死"；若进程死锁，探针超时由 K8s 侧判定。
func (s *server) handleHealthz(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}

// handleReadyz 就绪探针（readiness probe）：只有 ready 才 200，否则 503。
// 语义：实例"能接收流量吗"——依赖未就绪（DB 连不上、缓存未预热）时把实例从负载均衡摘掉，
// 而不是让请求打到半死实例上等超时。K8s 用它决定是否把流量路由进 Pod。
func (s *server) handleReadyz(w http.ResponseWriter, _ *http.Request) {
	if !s.ready.Load() {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusServiceUnavailable) // 503：K8s 摘除本实例
		_, _ = w.Write([]byte(`{"status":"not_ready"}`))
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ready"}`))
}

// newHandler 组装全部路由（业务路由示例 /api/echo 顺带演示"就绪前拒绝业务流量"）
func (s *server) newHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.handleHealthz)
	mux.HandleFunc("GET /readyz", s.handleReadyz)
	mux.HandleFunc("GET /api/echo", func(w http.ResponseWriter, r *http.Request) {
		// 业务接口自己也查一次 readiness：就绪前直接 503，避免"探针过了但业务不可用"的窗口
		if !s.ready.Load() {
			w.WriteHeader(http.StatusServiceUnavailable)
			_, _ = w.Write([]byte(`{"error":"not ready"}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"echo":"pong"}`))
	})
	return mux
}

func main() {
	addr := flag.String("addr", "127.0.0.1:58001", "监听地址")
	flag.Parse()

	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil)) // 结构化日志（示例 3 详解）
	srv := newServer()
	httpSrv := &http.Server{
		Addr:              *addr,
		Handler:           srv.newHandler(),
		ReadHeaderTimeout: 5 * time.Second, // 防慢连接拖死 goroutine（golangci-lint gosec 提示项）
	}

	// 模拟"启动后 500ms 依赖就绪"（真实场景：DB ping 通过后调 MarkReady）
	go func() {
		time.Sleep(500 * time.Millisecond)
		srv.MarkReady()
		logger.Info("dependencies ready, /readyz now 200")
	}()

	// 监听：Serve 返回非 ErrServerClosed 的错误都是致命错误
	ln, err := netListen(*addr)
	if err != nil {
		logger.Error("listen failed", "err", err)
		os.Exit(1)
	}
	go func() {
		if err := httpSrv.Serve(ln); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("serve failed", "err", err)
			os.Exit(1)
		}
	}()
	logger.Info("server started", "addr", *addr)

	// 优雅退出：等信号 → 停止接收新连接 → 在途请求处理完（超时兜底）→ 退出
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM) // Ctrl+C = SIGINT；K8s 停 Pod 发 SIGTERM
	sig := <-quit
	logger.Info("shutting down", "signal", sig.String())

	// 先摘 readiness：优雅退出窗口内 /readyz 立即 503，让负载均衡/K8s 先把流量挪走
	srv.ready.Store(false)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := httpSrv.Shutdown(ctx); err != nil {
		logger.Error("shutdown forced", "err", err) // 超时未处理完：强制关闭
	}
	logger.Info("server exited")
}

// netListen 用 net.Listen 单独监听并把 listener 交给 http.Server，
// 便于在测试里复用（随机端口 + 可关闭），与 main 的 flag 解耦
func netListen(addr string) (net.Listener, error) {
	return net.Listen("tcp", addr)
}
