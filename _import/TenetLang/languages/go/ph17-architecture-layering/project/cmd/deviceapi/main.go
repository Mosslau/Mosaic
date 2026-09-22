// 来源：ph17-architecture-layering project/cmd/deviceapi/main.go
// 一句话说明：组装点（wiring）+ 启动。全程序只有这里知道
// store/service/handler "具体是谁"：读配置 → 选存储 → 组装 → 起服务。
// 换存储/换日志等级只改这里；业务代码零改动（依赖注入，主文档 3.4）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：
//
//	go run ./cmd/deviceapi -addr 127.0.0.1:18084 -store mem
//	go run ./cmd/deviceapi -addr 127.0.0.1:18084 -store file -store-file /tmp/ph17-nodes.json
//
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"time"

	"tenetlang/go/ph17-architecture-layering/project/internal/config"
	"tenetlang/go/ph17-architecture-layering/project/internal/handler"
	"tenetlang/go/ph17-architecture-layering/project/internal/service"
	"tenetlang/go/ph17-architecture-layering/project/internal/store"
)

// 编译期断言：两个存储实现都满足消费方接口 service.NodeStore。
// 断言放组装点，不在实现包里 import 消费方（依赖方向保持单向向内，主文档 3.7）。
var (
	_ service.NodeStore = (*store.Mem)(nil)
	_ service.NodeStore = (*store.File)(nil)
)

func main() {
	cfg := config.Load()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	st, err := newStore(cfg)
	if err != nil {
		logger.Error("open store", "err", err)
		os.Exit(1) // 配置/存储打不开：启动期 fail-fast，不带病运行
	}

	svc := service.New(st)
	h := handler.New(svc, logger)

	mux := http.NewServeMux()
	h.Register(mux)

	srv := &http.Server{
		Addr:              cfg.Addr,
		Handler:           accessLog(logger, mux),
		ReadHeaderTimeout: 5 * time.Second,
	}
	logger.Info("node api listening", "addr", cfg.Addr, "store", cfg.Store)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		logger.Error("server error", "err", err)
		os.Exit(1)
	}
}

// newStore 是"存储选型"的唯一落点：新增实现（如数据库）只扩展这里。
func newStore(cfg config.Config) (service.NodeStore, error) {
	switch cfg.Store {
	case "mem":
		return store.NewMem(), nil
	case "file":
		return store.NewFile(cfg.StoreFile)
	default:
		return nil, fmt.Errorf("unknown store %q (want mem|file)", cfg.Store)
	}
}

// accessLog 是横切逻辑的落点（中间件，主文档 3.5 日志纪律）：
// 记录 method/path/duration，不掺进任何一层业务代码。
func accessLog(logger *slog.Logger, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		logger.Info("http_access",
			"method", r.Method,
			"path", r.URL.Path,
			"duration", time.Since(start).String(),
		)
	})
}
