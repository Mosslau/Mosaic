// 来源：ph08-testing 阶段项目 —— 带测试的设备管理 HTTP API
// 一句话说明：可运行入口。组装 Store 与 Handler，启动 HTTP 服务。
// 验证环境：go1.25.6（darwin/arm64），go 1.22+（依赖 ServeMux 方法路由）
// 运行：
//
//	go run ./cmd/api
//	curl -s localhost:8080/devices
//	curl -s -X POST localhost:8080/devices -d '{"id":"d-001","status":"online"}'
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"log"
	"net/http"

	"tenetlang/go/ph08-testing/project/internal/api"
	"tenetlang/go/ph08-testing/project/internal/device"
)

func main() {
	store := device.NewMemoryStore()
	handler := api.NewHandler(store)

	addr := "127.0.0.1:8080"
	log.Printf("device API listening on http://%s", addr)
	// 生产注意：此处未加超时与优雅关闭，仅演示组装方式（属于 ph09 Web 后端阶段内容）
	if err := http.ListenAndServe(addr, handler); err != nil {
		log.Fatal(err)
	}
}
