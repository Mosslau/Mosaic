// 来源：exercises/README.md 练习 3 参考实现 —— HTTP API server（方法校验 + 显式超时 + httptest 可测）
// 一句话说明：路由挂在自定义 mux 上便于 httptest 测试，GET 之外返回 405，三档超时显式设置。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go run .                          # 启动服务
//	curl http://127.0.0.1:8080/devices/car-001
//	go test -v                        # 运行 handler 单元测试
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"time"
)

// Device 设备模型：JSON tag 决定接口报文
type Device struct {
	ID     string  `json:"id"`
	Status string  `json:"status"`
	Speed  float64 `json:"speed"`
}

// writeJSON 统一 JSON 响应：Content-Type 与状态码
func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Println("写入响应失败:", err)
	}
}

// newMux 构建路由表。返回 *http.ServeMux 而非直接挂 DefaultServeMux，
// 便于测试用 httptest.NewServer/httptest.NewRecorder 直接驱动。
func newMux(devices map[string]Device) *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /devices", func(w http.ResponseWriter, r *http.Request) {
		list := make([]Device, 0, len(devices))
		for _, d := range devices {
			list = append(list, d)
		}
		writeJSON(w, http.StatusOK, list)
	})
	mux.HandleFunc("GET /devices/{id}", func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id") // Go 1.22+ 通配符取值
		if d, ok := devices[id]; ok {
			writeJSON(w, http.StatusOK, d)
			return
		}
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "device not found"})
	})
	// 兜底：其余方法/路径统一 405/404（Go 1.22 方法模式不匹配时默认 405 由 mux 处理，
	// 这里显式兜底非 GET 到 /devices 的情形）
	mux.HandleFunc("/devices", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Allow", "GET")
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
	})
	return mux
}

func main() {
	devices := map[string]Device{
		"car-001": {ID: "car-001", Status: "online", Speed: 60.5},
		"car-002": {ID: "car-002", Status: "offline", Speed: 0},
	}
	srv := &http.Server{
		Addr:         "127.0.0.1:8080",
		Handler:      newMux(devices),
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}
	log.Println("API 服务启动: http://127.0.0.1:8080")
	log.Fatal(srv.ListenAndServe())
}
