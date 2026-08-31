// 来源：ph10-database 阶段项目 —— 车辆轨迹存储服务（internal/api 包）
// 一句话说明：HTTP 接口层——POST /api/devices/{id}/points（批量上报）、
// GET /api/devices/{id}/latest（最新位置，走旁路缓存）、GET /api/devices/{id}/trajectory
// （时间段轨迹）。handler 四段式（解析→校验→业务→响应）+ 统一错误 {code, message}
// （ph09 延续），数据层只依赖 Store/Cache 接口（可注入测试替身）。
// 验证环境：go1.25.6（darwin/arm64），仅标准库 net/http
// 运行：
//
//	go test -v ./internal/api
//
// 验证状态：已验证（go1.25.6，httptest 全流程）
package api

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"time"

	"tenetlang/go/ph10-database/project/internal/cache"
	"tenetlang/go/ph10-database/project/internal/store"
)

// Service 组装 Store + Cache，提供业务方法
type Service struct {
	store store.Store
	cache cache.Cache
}

// NewService 构造 Service
func NewService(s store.Store, c cache.Cache) *Service {
	return &Service{store: s, cache: c}
}

// reportRequest 批量上报请求体
type reportRequest struct {
	Points []pointReq `json:"points"`
}

type pointReq struct {
	Lat   float64 `json:"lat"`
	Lng   float64 `json:"lng"`
	Speed float64 `json:"speed"`
	TS    string  `json:"ts"` // RFC3339
}

// NewHandler 注册全部路由
func NewHandler(svc *Service) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/devices/{id}/points", svc.handleReport)
	mux.HandleFunc("GET /api/devices/{id}/latest", svc.handleLatest)
	mux.HandleFunc("GET /api/devices/{id}/trajectory", svc.handleTrajectory)
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("ok"))
	})
	return mux
}

// handleReport 批量上报：校验 + 事务写入 + 更新最新位置缓存
func (s *Service) handleReport(w http.ResponseWriter, r *http.Request) {
	deviceID := r.PathValue("id")
	var req reportRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_JSON", "请求体不是合法 JSON")
		return
	}
	if len(req.Points) == 0 {
		writeError(w, http.StatusBadRequest, "INVALID_PARAM", "points 不能为空")
		return
	}
	points := make([]store.Point, 0, len(req.Points))
	for _, p := range req.Points {
		if !validCoord(p.Lat, p.Lng) || p.Speed < 0 || p.Speed > 300 {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "坐标或速度非法（lat∈[-90,90]、lng∈[-180,180]、speed∈[0,300]）")
			return
		}
		ts, err := time.Parse(time.RFC3339, p.TS)
		if err != nil {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "ts 必须是 RFC3339 时间")
			return
		}
		points = append(points, store.Point{DeviceID: deviceID, Lat: p.Lat, Lng: p.Lng, Speed: p.Speed, TS: ts})
	}
	if err := s.store.BatchInsert(r.Context(), points); err != nil {
		writeError(w, http.StatusInternalServerError, "INTERNAL", "批量写入失败")
		return
	}
	// 写路径：更新最新位置缓存（短 TTL 30s）
	last := points[len(points)-1]
	_ = s.cache.Set(r.Context(), deviceID, cache.Entry{
		DeviceID: last.DeviceID, Lat: last.Lat, Lng: last.Lng, Speed: last.Speed, TS: last.TS,
	}, 30*time.Second)
	writeJSON(w, http.StatusCreated, map[string]any{"inserted": len(points)})
}

// handleLatest 最新位置：旁路缓存——先缓存，未命中查库并回填
func (s *Service) handleLatest(w http.ResponseWriter, r *http.Request) {
	deviceID := r.PathValue("id")
	if e, ok := s.cache.Get(r.Context(), deviceID); ok { // 缓存命中
		writeJSON(w, http.StatusOK, e)
		return
	}
	p, err := s.store.Latest(r.Context(), deviceID)
	if errors.Is(err, store.ErrDeviceNotFound) {
		writeError(w, http.StatusNotFound, "NOT_FOUND", "设备不存在或未上报过")
		return
	}
	if err != nil {
		writeError(w, http.StatusInternalServerError, "INTERNAL", "查询失败")
		return
	}
	// 回填缓存（短 TTL）
	e := cache.Entry{DeviceID: p.DeviceID, Lat: p.Lat, Lng: p.Lng, Speed: p.Speed, TS: p.TS}
	_ = s.cache.Set(r.Context(), deviceID, e, 30*time.Second)
	writeJSON(w, http.StatusOK, e)
}

// handleTrajectory 时间段轨迹：?from=RFC3339&to=RFC3339
func (s *Service) handleTrajectory(w http.ResponseWriter, r *http.Request) {
	deviceID := r.PathValue("id")
	from, err := parseTimeParam(r, "from")
	if err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_PARAM", "from 必须是 RFC3339 时间")
		return
	}
	to, err := parseTimeParam(r, "to")
	if err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_PARAM", "to 必须是 RFC3339 时间")
		return
	}
	if !to.After(from) {
		writeError(w, http.StatusBadRequest, "INVALID_PARAM", "to 必须晚于 from")
		return
	}
	points, err := s.store.Trajectory(r.Context(), deviceID, from, to)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "INTERNAL", "查询失败")
		return
	}
	writeJSON(w, http.StatusOK, points)
}

// --- 辅助函数 ---

func validCoord(lat, lng float64) bool {
	return lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180
}

func parseTimeParam(r *http.Request, name string) (time.Time, error) {
	v := r.URL.Query().Get(name)
	if v == "" {
		return time.Time{}, errors.New("missing")
	}
	return time.Parse(time.RFC3339, v)
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
