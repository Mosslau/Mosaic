// 来源：09-web-backend.md 第 6 章示例 1 —— 路由与 JSON API
// 一句话说明：Go 1.22 ServeMux 方法路由（GET/POST/DELETE）+ 通配符 {id} + r.PathValue
// + query 过滤 + 统一 JSON 响应，覆盖 200/201/204/400/404/405。
// 验证环境：go1.25.6（darwin/arm64），仅标准库，依赖 Go 1.22+ 方法路由
// 运行：
//
//	go run .
//	curl -s http://127.0.0.1:18080/devices
//	curl -s http://127.0.0.1:18080/devices/car-001
//	curl -s -X POST http://127.0.0.1:18080/devices -d '{"id":"car-009","status":"online"}'
//
// 测试：
//
//	go test -v ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"sync"
)

// Device 设备数据模型——JSON tag 决定对外字段名（ph07 已学）
type Device struct {
	ID     string  `json:"id"`
	Status string  `json:"status"`
	Speed  float64 `json:"speed"`
}

// store 内存存储：map 不是并发安全的，读写都加 Mutex（ph06 必会概念落地）。
// 与 main 解耦成可注入的 store（ph08 依赖注入）：测试每用例新建独立 store，用例间零状态污染。
type store struct {
	mu      sync.RWMutex
	devices map[string]Device
}

// newStore 带种子数据的存储——main 与测试共用同一入口
func newStore() *store {
	return &store{devices: map[string]Device{
		"car-001": {ID: "car-001", Status: "online", Speed: 60.5},
		"car-002": {ID: "car-002", Status: "offline", Speed: 0},
	}}
}

func main() {
	addr := "127.0.0.1:18080"
	log.Printf("设备 API 监听 http://%s", addr)
	if err := http.ListenAndServe(addr, newMux(newStore())); err != nil {
		log.Fatal(err)
	}
}

// newMux 组装路由——main 与测试共用同一注册逻辑，测试通过它直接拿 handler
func newMux(s *store) http.Handler {
	mux := http.NewServeMux()
	// 方法 + 路径模式：Go 1.22 起 ServeMux 支持 "GET /devices" 这种写法，
	// 方法不匹配时自动返回 405 并带 Allow 头
	mux.HandleFunc("GET /devices", listDevices(s))
	mux.HandleFunc("GET /devices/{id}", getDevice(s))
	mux.HandleFunc("POST /devices", createDevice(s))
	mux.HandleFunc("DELETE /devices/{id}", deleteDevice(s))
	return mux
}

// listDevices 列表：支持 ?status=online 过滤（query 参数用 r.URL.Query）
func listDevices(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		status := r.URL.Query().Get("status")
		s.mu.RLock()
		list := make([]Device, 0, len(s.devices))
		for _, d := range s.devices {
			if status == "" || d.Status == status {
				list = append(list, d)
			}
		}
		s.mu.RUnlock()
		writeJSON(w, http.StatusOK, list)
	}
}

// getDevice 详情：r.PathValue 取通配符 {id} 的值
func getDevice(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id")
		s.mu.RLock()
		d, ok := s.devices[id]
		s.mu.RUnlock()
		if !ok {
			writeError(w, http.StatusNotFound, "NOT_FOUND", "设备不存在: "+id)
			return
		}
		writeJSON(w, http.StatusOK, d)
	}
}

// createDevice 创建：Decode 失败 400；必填与枚举校验手写（标准库无声明式 validator）
func createDevice(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var d Device
		if err := json.NewDecoder(r.Body).Decode(&d); err != nil {
			writeError(w, http.StatusBadRequest, "INVALID_JSON", "请求体不是合法 JSON")
			return
		}
		if d.ID == "" {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "id 不能为空")
			return
		}
		if d.Status != "online" && d.Status != "offline" {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "status 只能是 online 或 offline")
			return
		}
		s.mu.Lock()
		if _, exists := s.devices[d.ID]; exists {
			s.mu.Unlock()
			writeError(w, http.StatusConflict, "DUPLICATE", "设备已存在: "+d.ID)
			return
		}
		s.devices[d.ID] = d
		s.mu.Unlock()
		writeJSON(w, http.StatusCreated, d) // 201 创建成功
	}
}

// deleteDevice 删除：成功返回 204 无内容
func deleteDevice(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id")
		s.mu.Lock()
		if _, ok := s.devices[id]; !ok {
			s.mu.Unlock()
			writeError(w, http.StatusNotFound, "NOT_FOUND", "设备不存在: "+id)
			return
		}
		delete(s.devices, id)
		s.mu.Unlock()
		w.WriteHeader(http.StatusNoContent)
	}
}

// writeJSON 统一 JSON 响应入口（Content-Type + 状态码 + 编码）
func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Printf("响应编码失败: %v", err)
	}
}

// writeError 统一错误结构 {code, message}（3.4 的落地）
func writeError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, map[string]string{"code": code, "message": msg})
}
