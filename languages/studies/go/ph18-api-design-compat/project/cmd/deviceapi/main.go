// 来源：ph18-api-design-compat project/cmd/deviceapi/main.go
// 一句话说明：组装点。契约测试之外，本项目也要能真的跑起来做 curl 冒烟——
// 启动命令与冒烟步骤见 project/README.md。main 只做组装，业务全在 internal/。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run ./cmd/deviceapi -addr 127.0.0.1:18110
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"flag"
	"log"
	"net/http"
	"time"

	"tenetlang/go/ph18-api-design-compat/project/internal/devices"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:18110", "监听地址")
	flag.Parse()

	mux := http.NewServeMux()
	devices.New(devices.NewStore()).Register(mux)

	srv := &http.Server{
		Addr:              *addr,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	log.Printf("deviceapi (spec-first, v1+v2) listening on %s", *addr)
	if err := srv.ListenAndServe(); err != nil {
		log.Fatal(err)
	}
}
