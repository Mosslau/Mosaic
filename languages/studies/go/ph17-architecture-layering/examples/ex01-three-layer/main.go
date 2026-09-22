// 来源：ph17-architecture-layering examples/ex01-three-layer/main.go
// 一句话说明：组装点（wiring）。main 是全程序唯一知道"store/service/handler 具体是谁"的地方：
// 换存储实现、换 service 构造参数都只改这里——依赖注入的入口（主文档 3.4）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18081（然后 curl 冒烟，示例见 examples/README.md）
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

	"tenetlang/go/ph17-architecture-layering/examples/ex01-three-layer/internal/handler"
	"tenetlang/go/ph17-architecture-layering/examples/ex01-three-layer/internal/service"
	"tenetlang/go/ph17-architecture-layering/examples/ex01-three-layer/internal/store"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:18081", "监听地址")
	flag.Parse()

	// 组装方向与依赖方向相反：从最内层 store 开始，逐层向上 new。
	// 如果将来 store 换成文件/数据库实现，只有下面三行会变。
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
