// 可部署 API 服务模板入口：配置加载 → 日志 → 服务装配 → 优雅退出。
// 云原生部署闭环：/healthz+/readyz（K8s 探针）+/metrics（Prometheus 抓取）+ 12-Factor 配置 +
// 结构化日志 + SIGTERM 优雅退出。配套 Dockerfile 与 deploy/k8s/ 清单见 project/ 根目录。
//
// 运行：
//
//	go test ./... && go vet ./...                       # 测试与静态检查
//	DB_URL=postgres://u:p@db/app go run ./cmd/api       # 本机直接跑（ADDR/PORT 可覆盖）
//	curl -i http://127.0.0.1:58010/healthz              # 200
//	curl -i http://127.0.0.1:58010/readyz               # 200（依赖就绪后）
//	curl -s http://127.0.0.1:58010/metrics              # exposition 文本
//	kill -TERM <pid>                                     # 优雅退出日志
//
// 验证状态：本机 go1.25.6 验证通过；Docker/K8s 部署见 project/README.md 实测记录
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
	"syscall"
	"time"

	"tenetlang/go/ph12-cloud-native/project/internal/config"
	"tenetlang/go/ph12-cloud-native/project/internal/server"
)

func main() {
	// 支持 -addr 覆盖环境变量（本机调试便利；容器/K8s 用环境变量注入）
	addrFlag := flag.String("addr", "", "监听地址（覆盖环境变量 ADDR/PORT）")
	flag.Parse()

	cfg, err := config.LoadFromEnv()
	if err != nil {
		// 配置错误在启动时 fail-fast：stderr 必打（容器日志采集捕获 stdout+stderr）
		slog.Error("config error", "err", err)
		os.Exit(1)
	}
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level:     cfg.LogLevel,
		AddSource: true,
	}))

	addr := cfg.ListenAddr()
	if *addrFlag != "" {
		addr = *addrFlag
	}

	m := server.NewMetrics()
	srv := server.New(logger, m)

	httpSrv := &http.Server{
		Addr:              addr,
		Handler:           srv.Handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		logger.Error("listen failed", "err", err)
		os.Exit(1)
	}

	// 依赖就绪：真实项目在此 ping 数据库/缓存，通过后 MarkReady；
	// 模板用 500ms 模拟，保证 /readyz 一开始是 503（探针语义可见）
	go func() {
		time.Sleep(500 * time.Millisecond)
		srv.MarkReady()
		logger.Info("dependencies ready, /readyz now 200")
	}()

	go func() {
		if err := httpSrv.Serve(ln); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("serve failed", "err", err)
			os.Exit(1)
		}
	}()
	logger.Info("server started", "addr", addr,
		"db_url", config.MaskDBURL(cfg.DBURL), "metrics", cfg.EnableMetrics)

	// 优雅退出：等 SIGINT/SIGTERM → 摘 readiness → Shutdown 等在途 → 兜底超时
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)
	sig := <-quit
	logger.Info("shutting down", "signal", sig.String())
	srv.SetReady(false) // 先摘流量：/readyz 立即 503，K8s 把 Pod 从 Service 摘除
	ctx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
	defer cancel()
	if err := httpSrv.Shutdown(ctx); err != nil {
		logger.Error("shutdown forced", "err", err)
	}
	logger.Info("server exited")
}
