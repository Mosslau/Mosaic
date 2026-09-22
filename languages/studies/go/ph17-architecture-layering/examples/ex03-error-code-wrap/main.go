// 来源：ph17-architecture-layering examples/ex03-error-code-wrap/main.go
// 一句话说明：入口。挂一条演示路由并播种一条 demo 数据，
// 供 curl 冒烟："改名不存在的 todo" 应返回 404 + {"code":"TODO_NOT_FOUND",...}。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18082，然后：
//
//	curl -X POST http://127.0.0.1:18082/todos/nope/rename -d '{"title":"x"}'   # 404 TODO_NOT_FOUND
//	curl -X POST http://127.0.0.1:18082/todos/demo-1/rename -d '{"title":" "}'  # 400 INVALID_ARGUMENT
//
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
)

func main() {
	addr := flag.String("addr", "127.0.0.1:18082", "监听地址")
	flag.Parse()

	a := &api{todos: newTodos()}
	a.todos.items["demo-1"] = "写 ph17 主文档" // 播种演示数据（教学演示）

	mux := http.NewServeMux()
	mux.HandleFunc("POST /todos/{id}/rename", a.renameHandler)

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
