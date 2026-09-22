// 来源：ph08-testing 主文档示例 2 —— HTTP handler 测试（httptest + 断言 JSON）
// 一句话说明：可注入依赖的 handler 工厂（Go 1.22+ 路由通配符），测试零网络开销。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go run .          # 启动服务后另开终端 curl http://127.0.0.1:8080/devices/car-001
//	go test -v ./...  # 不起端口直接测 handler
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"time"
)

// Device 设备（与 ph07 标准库阶段示例同领域）
type Device struct {
	ID     string `json:"id"`
	Status string `json:"status"`
}

// NewHandler 返回带路由的 handler；数据源作为参数注入，测试时可替换
func NewHandler(devices map[string]Device) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /devices/{id}", func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id")
		d, ok := devices[id]
		if !ok {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "device not found"})
			return
		}
		writeJSON(w, http.StatusOK, d)
	})
	return mux
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Printf("响应编码失败: %v", err)
	}
}

func main() {
	devices := map[string]Device{"car-001": {ID: "car-001", Status: "online"}}
	srv := &http.Server{
		Addr:         ":8080",
		Handler:      NewHandler(devices),
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}
	log.Println("listening on :8080")
	log.Fatal(srv.ListenAndServe())
}
