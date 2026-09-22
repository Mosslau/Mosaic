// 来源：ph18-api-design-compat examples/ex03-pagination-filter/main.go
// 一句话说明：组装点（主文档 3.5）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18103
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"flag"
	"log"
	"net/http"
	"time"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:18103", "监听地址")
	flag.Parse()

	mux := http.NewServeMux()
	NewServer().Register(mux)

	httpSrv := &http.Server{
		Addr:              *addr,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	log.Printf("ex03-pagination-filter listening on %s", *addr)
	if err := httpSrv.ListenAndServe(); err != nil {
		log.Fatal(err)
	}
}
