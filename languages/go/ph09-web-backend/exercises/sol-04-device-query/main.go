// 来源：ph09-web-backend 练习 4 参考实现 —— 设备状态查询 API
// 一句话说明：列表（?status=online|offline 过滤，非法值 400）+ 单个查询（200/404）
// + 统一错误 {code, message}——把 ph07 的 JSON 接口升级为规范形态的最小示例。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go test -v ./...
//	go test -cover ./...
//	go run .          # 监听 127.0.0.1:18080
//	curl -s "http://127.0.0.1:18080/api/devices?status=online"
//	curl -s http://127.0.0.1:18080/api/devices/car-001
//
// 验证状态：已验证（go1.25.6，覆盖率 80%+）
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"sync"
)

// Device 设备状态
type Device struct {
	ID     string  `json:"id"`
	Status string  `json:"status"`
	Speed  float64 `json:"speed"`
}

var (
	mu      sync.RWMutex
	devices = map[string]Device{
		"car-001": {ID: "car-001", Status: "online", Speed: 60.5},
		"car-002": {ID: "car-002", Status: "offline", Speed: 0},
		"car-003": {ID: "car-003", Status: "online", Speed: 88.0},
	}
)

func main() {
	addr := "127.0.0.1:18080"
	log.Printf("设备查询 API 监听 http://%s", addr)
	if err := http.ListenAndServe(addr, newMux()); err != nil {
		log.Fatal(err)
	}
}

func newMux() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/devices", listDevices)
	mux.HandleFunc("GET /api/devices/{id}", getDevice)
	return mux
}

func listDevices(w http.ResponseWriter, r *http.Request) {
	status := r.URL.Query().Get("status")
	if status != "" && status != "online" && status != "offline" { // 枚举白名单校验
		writeError(w, http.StatusBadRequest, "INVALID_PARAM", "status 只能是 online 或 offline")
		return
	}
	mu.RLock()
	list := make([]Device, 0, len(devices))
	for _, d := range devices {
		if status == "" || d.Status == status {
			list = append(list, d)
		}
	}
	mu.RUnlock()
	writeJSON(w, http.StatusOK, list)
}

func getDevice(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	mu.RLock()
	d, ok := devices[id]
	mu.RUnlock()
	if !ok {
		writeError(w, http.StatusNotFound, "NOT_FOUND", "设备不存在: "+id)
		return
	}
	writeJSON(w, http.StatusOK, d)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Printf("响应编码失败: %v", err)
	}
}

func writeError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, map[string]string{"code": code, "message": msg})
}
