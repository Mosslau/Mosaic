// 来源：ph12-cloud-native 示例 6 —— 容器化的最小服务（Dockerfile 多阶段构建）
// 一句话说明：一个可被 Dockerfile 打包的极简服务——/healthz（容器 HEALTHCHECK 与
// K8s liveness 共用）、slog JSON 日志、环境变量端口。配套 Dockerfile 演示多阶段构建
// （builder 编译 → scratch 运行，镜像只含静态二进制），compose.yaml 演示
// 单命令起服务 + 端口映射 + 环境变量。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...                       # 服务本身（与 Docker 无关，可直接验证）
//	go run .                               # 本机直接跑（PORT 环境变量可覆盖端口）
//
//	Docker 相关命令（本机有 docker daemon 时执行；未在本环境验证则如实标注）：
//	docker build -t ph12-ex06:latest .
//	docker run --rm -p 58006:58006 ph12-ex06:latest
//	docker compose up --build              # compose.yaml 定义的服务
//	curl -s http://127.0.0.1:58006/healthz
//
// 验证状态：服务本身已验证（go1.25.6）；Docker 构建/运行见 examples/README.md 实测记录
package main

import (
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"time"
)

// newHandler 组装全部路由（与 Docker/网络解耦，可直接单测）
func newHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})
	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, _ *http.Request) { // {$}：仅精确匹配根路径
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"service":"ph12-ex06","message":"hello from container"}`))
	})
	return mux
}

func main() {
	port := os.Getenv("PORT") // 12-Factor：端口来自环境变量（compose/K8s 注入）
	if port == "" {
		port = "58006"
	}
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           newHandler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	logger.Info("server listening", "port", port)
	if err := srv.ListenAndServe(); err != nil {
		logger.Error("serve failed", "err", err)
		fmt.Fprintln(os.Stderr, "serve failed:", err)
		os.Exit(1)
	}
}
