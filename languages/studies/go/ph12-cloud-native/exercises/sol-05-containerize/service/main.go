// 来源：ph12-cloud-native 练习 5 参考实现 —— 容器化与部署清单（服务本体）
// 一句话说明：练习 1 健康检查服务的容器版：/healthz + /readyz + SIGTERM 优雅退出 +
// 环境变量端口。配套同目录 Dockerfile（多阶段构建 → scratch）、compose.yaml、
// deploy/k8s/ 的 Deployment + Service 清单——探针写进 K8s 清单（kubelet 用 HTTP 探针），
// 而不是 Dockerfile HEALTHCHECK（scratch 镜像没有 shell/wget）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	cd service && go test -v ./...          # 服务本体（与 Docker 无关，已验证）
//	cd service && go run .                  # PORT 环境变量可覆盖端口
//
//	Docker/K8s 命令（需 docker/kubectl 环境；本机未验证则如实标注）：
//	docker build -t sol05:latest .          # 在 sol-05-containerize/ 目录执行
//	docker compose up --build
//	kubectl apply -f deploy/k8s/
//
// 验证状态：服务本体已验证（go1.25.6）；Docker/K8s 清单（同目录 Dockerfile、compose.yaml、
// deploy/k8s/deployment.yaml）各自的文件头已如实标注验证状态——本机 docker daemon 未就绪、
// kubectl 无集群时一律为「未在本环境验证（需 Docker/Kubernetes 环境）」，不虚构验证
// 覆盖率：go test -cover 实测 **44.2%**（go1.25.6，2 个用例全过：healthz 恒 200/readyz
// 未就绪 503→就绪 200 转换；main 为入口不计量）
package main

import (
	"context"
	"errors"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"
)

type server struct {
	ready atomic.Bool
}

func newServer() *server {
	s := &server{}
	s.ready.Store(false)
	return s
}

func (s *server) MarkReady() { s.ready.Store(true) }

func (s *server) handleHealthz(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}

func (s *server) handleReadyz(w http.ResponseWriter, _ *http.Request) {
	status, body := http.StatusOK, `{"status":"ready"}`
	if !s.ready.Load() {
		status, body = http.StatusServiceUnavailable, `{"status":"not_ready"}`
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write([]byte(body))
}

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

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "59005"
	}
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	srv := newServer()
	httpSrv := &http.Server{
		Addr:              ":" + port,
		Handler:           srv.newHandler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	ln, err := net.Listen("tcp", httpSrv.Addr)
	if err != nil {
		logger.Error("listen failed", "err", err)
		os.Exit(1)
	}
	// 模拟依赖 300ms 后就绪（真实场景：DB ping 通过后 MarkReady）
	go func() {
		time.Sleep(300 * time.Millisecond)
		srv.MarkReady()
		logger.Info("dependencies ready")
	}()
	go func() {
		if err := httpSrv.Serve(ln); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("serve failed", "err", err)
			os.Exit(1)
		}
	}()
	logger.Info("server started", "port", port)

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)
	<-quit
	logger.Info("shutting down")
	srv.ready.Store(false) // 先摘 readiness（K8s 停 Pod 发 SIGTERM 前已把流量挪走，双保险）
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := httpSrv.Shutdown(ctx); err != nil {
		logger.Error("shutdown forced", "err", err)
	}
	logger.Info("server exited")
}
