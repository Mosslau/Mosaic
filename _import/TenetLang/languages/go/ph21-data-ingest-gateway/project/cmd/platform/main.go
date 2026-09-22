// 来源：ph21-data-ingest-gateway project/cmd/platform/main.go
// 一句话说明：云端接入平台进程入口——env 配置 + API 服务 + 优雅退出。构建注入：
//
//	go build -ldflags "-X tenetlang/go/ph21-data-ingest-gateway/project/internal/version.Version=v1.0.0 -X tenetlang/go/ph21-data-ingest-gateway/project/internal/version.Commit=abc123 -X tenetlang/go/ph21-data-ingest-gateway/project/internal/version.BuildTime=2026-09-04T00:00:00Z" -o /tmp/relay-platform ./cmd/platform
//
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测：vet/build/test 全绿；运行需本地起服务）
package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"tenetlang/go/ph21-data-ingest-gateway/project/internal/api"
	"tenetlang/go/ph21-data-ingest-gateway/project/internal/config"
	"tenetlang/go/ph21-data-ingest-gateway/project/internal/platform"
	"tenetlang/go/ph21-data-ingest-gateway/project/internal/version"
)

func main() {
	log.SetFlags(log.LstdFlags | log.Lmsgprefix)
	log.SetPrefix("[platform] ")
	cfg, err := config.LoadFromEnv()
	if err != nil {
		log.Fatalf("配置加载失败: %v", err)
	}
	log.Printf("relay-platform 启动（版本 %s / commit %s / %s）", version.Version, version.Commit, version.BuildTime)

	core := platform.NewCore(cfg.Secrets)
	srv := &http.Server{
		Addr:              cfg.Addr,
		Handler:           api.NewServer(core).Handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Printf("监听 %s", cfg.Addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("HTTP 服务: %v", err)
		}
	}()

	// 优雅退出（SIGINT/SIGTERM，主文档 ph12 纪律）。
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("收到退出信号，优雅关闭…")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Printf("关闭异常: %v", err)
	}
	log.Println("已退出")
}
