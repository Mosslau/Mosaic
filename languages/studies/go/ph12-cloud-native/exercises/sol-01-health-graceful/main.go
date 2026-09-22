// 来源：ph12-cloud-native 练习 1 参考实现 —— 健康检查与优雅退出
// 一句话说明：roadmap「能配置环境变量和健康检查」的落地——liveness（/healthz 恒 200）
// 与 readiness（/readyz 未就绪 503）语义区分、atomic.Bool 就绪状态、SIGTERM 优雅退出
// （先摘 readiness 再 Shutdown 等在途请求）、业务接口与探针口径一致。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .                    # 默认 127.0.0.1:59001，Ctrl+C 观察优雅退出日志
//
// 验证状态：已验证（go1.25.6）
// 覆盖率：go test -cover 实测 **80.0%**（go1.25.6，6 个测试函数全过：healthz 恒 200/readyz 未就绪
// 503 与就绪 200/业务接口口径/Shutdown 等在途/run 信号退出/未知路径 404）
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

// server 持有就绪状态：atomic.Bool —— 探针被高频轮询，读路径零锁零分配
type server struct {
	ready atomic.Bool
}

func newServer() *server {
	s := &server{}
	s.ready.Store(false)
	return s
}

// MarkReady 应用在依赖就绪后调用（如 DB ping 通过）
func (s *server) MarkReady() { s.ready.Store(true) }

// handleHealthz 存活探针：进程活着即 200，不检查依赖（依赖全断也 200，
// 那是 readiness 的职责——liveness 失败 = 进程级故障，交给 K8s 重启 Pod）
func (s *server) handleHealthz(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}

// handleReadyz 就绪探针：未就绪 503（流量摘除），就绪 200
func (s *server) handleReadyz(w http.ResponseWriter, _ *http.Request) {
	status := http.StatusOK
	body := `{"status":"ready"}`
	if !s.ready.Load() {
		status = http.StatusServiceUnavailable
		body = `{"status":"not_ready"}`
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write([]byte(body))
}

// newHandler 路由：业务接口也自查 readiness，避免"探针 200 但业务不可用"窗口
func (s *server) newHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.handleHealthz)
	mux.HandleFunc("GET /readyz", s.handleReadyz)
	mux.HandleFunc("GET /api/ping", func(w http.ResponseWriter, _ *http.Request) {
		if !s.ready.Load() {
			w.WriteHeader(http.StatusServiceUnavailable)
			_, _ = w.Write([]byte(`{"error":"not ready"}`))
			return
		}
		_, _ = w.Write([]byte(`{"pong":true}`))
	})
	return mux
}

// run 起服务并阻塞到信号：返回后进程应退出（main 与测试共用，便于注入信号通道）
func run(logger *slog.Logger, addr string, sigCh <-chan os.Signal) error {
	srv := newServer()
	httpSrv := &http.Server{
		Addr:              addr,
		Handler:           srv.newHandler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return err
	}
	// 模拟依赖 300ms 后就绪
	go func() {
		time.Sleep(300 * time.Millisecond)
		srv.MarkReady()
		logger.Info("dependencies ready")
	}()
	go func() {
		if err := httpSrv.Serve(ln); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("serve failed", "err", err)
		}
	}()
	logger.Info("server started", "addr", addr)

	<-sigCh
	logger.Info("signal received, shutting down")
	// ① 先摘 readiness：让负载均衡/K8s 先把流量挪走
	srv.ready.Store(false)
	// ② 优雅关闭：等在途请求处理完（10s 兜底）
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := httpSrv.Shutdown(ctx); err != nil {
		return err
	}
	logger.Info("server exited")
	return nil
}

func main() {
	addr := flag.String("addr", "127.0.0.1:59001", "监听地址")
	flag.Parse()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	if err := run(logger, *addr, sigCh); err != nil {
		logger.Error("run failed", "err", err)
		os.Exit(1)
	}
}
