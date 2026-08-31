// 来源：ph08-testing 练习 2 参考实现 —— 给 handler 写测试
// 一句话说明：设备查询 handler 工厂，数据源注入，httptest 不起端口测试。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"encoding/json"
	"log"
	"net/http"
)

// Device 设备
type Device struct {
	ID     string `json:"id"`
	Status string `json:"status"`
}

// NewHandler 工厂函数：数据源注入，测试时传入内存 map
func NewHandler(devices map[string]Device) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /devices/{id}", func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id")
		d, ok := devices[id]
		if !ok {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "device not found: " + id})
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
	// 本参考实现聚焦测试；main 仅演示工厂用法，真实服务搭建见 project/
	h := NewHandler(map[string]Device{"car-001": {ID: "car-001", Status: "online"}})
	_ = h
	log.Println("参考实现：请运行 go test -v 查看测试")
}
