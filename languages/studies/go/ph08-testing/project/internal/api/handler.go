// 来源：ph08-testing 阶段项目 —— 带测试的设备管理 HTTP API
// 一句话说明：API 层，NewHandler 工厂 + 依赖注入 Store 接口，JSON 统一响应。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./internal/api
//
// 验证状态：已验证（go1.25.6）
package api

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"

	"tenetlang/go/ph08-testing/project/internal/device"
)

// NewHandler 返回带路由的 handler；Store 注入，测试可替换为 stub
func NewHandler(s device.Store) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /devices", listDevices(s))
	mux.HandleFunc("GET /devices/{id}", getDevice(s))
	mux.HandleFunc("POST /devices", createDevice(s))
	mux.HandleFunc("DELETE /devices/{id}", deleteDevice(s))
	return mux
}

func listDevices(s device.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, s.List())
	}
}

func getDevice(s device.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id")
		d, ok := s.Get(id)
		if !ok {
			writeError(w, http.StatusNotFound, "device not found: "+id)
			return
		}
		writeJSON(w, http.StatusOK, d)
	}
}

func createDevice(s device.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var d device.Device
		if err := json.NewDecoder(r.Body).Decode(&d); err != nil {
			writeError(w, http.StatusBadRequest, "请求体不是合法 JSON")
			return
		}
		if d.ID == "" || d.Status == "" {
			writeError(w, http.StatusBadRequest, "id 与 status 均不能为空")
			return
		}
		if err := s.Create(d); err != nil {
			if errors.Is(err, device.ErrDuplicate) {
				writeError(w, http.StatusConflict, "device already exists: "+d.ID)
				return
			}
			writeError(w, http.StatusInternalServerError, "内部错误")
			return
		}
		writeJSON(w, http.StatusCreated, d)
	}
}

func deleteDevice(s device.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id")
		if !s.Delete(id) {
			writeError(w, http.StatusNotFound, "device not found: "+id)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	}
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Printf("响应编码失败: %v", err)
	}
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}
