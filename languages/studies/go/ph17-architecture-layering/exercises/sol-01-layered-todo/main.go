// 来源：ph17-architecture-layering exercises/sol-01-layered-todo/main.go
// 一句话说明：练习 1 参考实现的组装点：从 store 到 service 到 handler 逐层 new，
// 与依赖方向相反（主文档 3.4：组装只在 main）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18083
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"flag"
	"log"
	"net/http"
	"os"
	"time"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-01-layered-todo/internal/handler"
	"tenetlang/go/ph17-architecture-layering/exercises/sol-01-layered-todo/internal/service"
	"tenetlang/go/ph17-architecture-layering/exercises/sol-01-layered-todo/internal/store"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:18083", "监听地址")
	flag.Parse()

	st := store.New()
	svc := service.New(st)
	h := handler.New(svc)

	mux := http.NewServeMux()
	h.Register(mux)

	srv := &http.Server{
		Addr:              *addr,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	log.Printf("listening on %s", *addr)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Printf("server error: %v", err)
		os.Exit(1)
	}
}
