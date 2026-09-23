// 来源：ph09-web-backend 阶段项目 —— 设备数据上报 API（internal/api 包）
// 一句话说明：路由组装（NewHandler 依赖注入 Store + 密钥 + 限流参数）+ 各接口实现：
// 设备认证换 JWT / 列表与详情 / 上报（鉴权 + 校验 + 限流 + 统一错误）/ 健康检查。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
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
	"time"

	"tenetlang/go/ph09-web-backend/project/internal/auth"
	"tenetlang/go/ph09-web-backend/project/internal/device"
)

// ReportReq 上报请求体
type ReportReq struct {
	Speed float64 `json:"speed"`
	Lat   float64 `json:"lat"`
	Lng   float64 `json:"lng"`
}

// NewHandler 组装全部路由；依赖注入：Store 可换实现，限流参数可调
func NewHandler(store device.Store, secret []byte, reportLimit int, window time.Duration) http.Handler {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /healthz", handleHealthz)

	// 设备认证：拿预置密钥换 JWT（有状态设备密钥 → 无状态 token，一次换、多次用）
	mux.HandleFunc("POST /api/devices/auth", handleDeviceAuth(store, secret))

	// 查询接口：公开（或按产品策略决定；此处演示公开只读）
	mux.HandleFunc("GET /api/devices", handleList(store))
	mux.HandleFunc("GET /api/devices/{id}", handleGet(store))

	// 上报接口：JWT 鉴权 + 限流（子 mux 分组挂中间件）
	limiter := newDeviceLimiter(reportLimit, window)
	report := http.NewServeMux()
	report.HandleFunc("POST /devices/{id}/report", handleReport(store, limiter))
	mux.Handle("/api/", auth.Middleware(secret)(http.StripPrefix("/api", report)))

	return mux
}

func handleHealthz(w http.ResponseWriter, r *http.Request) {
	w.Write([]byte("ok"))
}

// handleDeviceAuth 设备认证：{device_id, secret} → {token}（JWT，24h 有效）
func handleDeviceAuth(store device.Store, secret []byte) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			DeviceID string `json:"device_id"`
			Secret   string `json:"secret"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeError(w, http.StatusBadRequest, "INVALID_JSON", "请求体不是合法 JSON")
			return
		}
		if req.DeviceID == "" || req.Secret == "" {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "device_id 与 secret 必填")
			return
		}
		if !store.ValidSecret(req.DeviceID, req.Secret) {
			writeError(w, http.StatusUnauthorized, "UNAUTHORIZED", "设备密钥错误")
			return
		}
		token, err := auth.Sign(map[string]any{"device_id": req.DeviceID}, secret, 24*time.Hour)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "INTERNAL", "签发 token 失败")
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"token": token})
	}
}

func handleList(store device.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		status := r.URL.Query().Get("status")
		if status != "" && status != "online" && status != "offline" {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "status 只能是 online 或 offline")
			return
		}
		writeJSON(w, http.StatusOK, store.List(status))
	}
}

func handleGet(store device.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id")
		v, ok := store.Get(id)
		if !ok {
			writeError(w, http.StatusNotFound, "NOT_FOUND", "设备不存在: "+id)
			return
		}
		writeJSON(w, http.StatusOK, v)
	}
}

// handleReport 上报：四段式（解析 → 校验 → 业务 → 响应），限流在中间件层
func handleReport(store device.Store, limiter *deviceLimiter) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// 归属校验：token 里的 device_id 必须等于路径 id（设备只能上报自己的数据）
		deviceID := auth.ClaimsDeviceID(r.Context())
		if deviceID == "" || deviceID != r.PathValue("id") {
			writeError(w, http.StatusForbidden, "FORBIDDEN", "token 归属与路径设备不一致")
			return
		}
		// 限流：每设备每窗口 N 次（roadmap「限流（每设备每分钟 N 次）」）
		if !limiter.allow(deviceID) {
			writeError(w, http.StatusTooManyRequests, "RATE_LIMITED", "上报过于频繁，请稍后再试")
			return
		}

		var req ReportReq
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeError(w, http.StatusBadRequest, "INVALID_JSON", "请求体不是合法 JSON")
			return
		}
		// 参数校验：速度范围 + 坐标合法（roadmap「参数校验（速度范围、坐标合法）」）
		if req.Speed < 0 || req.Speed > 300 {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "speed 必须在 0~300 之间")
			return
		}
		if req.Lat < -90 || req.Lat > 90 {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "lat 必须在 -90~90 之间")
			return
		}
		if req.Lng < -180 || req.Lng > 180 {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "lng 必须在 -180~180 之间")
			return
		}

		v, err := store.Report(deviceID, req.Speed, req.Lat, req.Lng)
		if err != nil {
			if errors.Is(err, device.ErrNotFound) {
				writeError(w, http.StatusNotFound, "NOT_FOUND", "设备不存在: "+deviceID)
				return
			}
			writeError(w, http.StatusInternalServerError, "INTERNAL", "上报失败")
			return
		}
		writeJSON(w, http.StatusOK, v)
	}
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
