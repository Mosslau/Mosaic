// 来源：ph21-data-ingest-gateway project/internal/api/api.go
// 一句话说明：云端接入侧 HTTP 层（薄编排，无业务逻辑）——上行批、健康检查、
// 版本自报、Prometheus 文本指标、车辆/最新速度查询。路由用 Go 1.22 方法路由。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"tenetlang/go/ph21-data-ingest-gateway/project/internal/model"
	"tenetlang/go/ph21-data-ingest-gateway/project/internal/platform"
	"tenetlang/go/ph21-data-ingest-gateway/project/internal/version"
)

// Server 接入 API 服务。
type Server struct {
	Core *platform.Core
}

// NewServer 建 API 服务。
func NewServer(core *platform.Core) *Server { return &Server{Core: core} }

// Handler 路由（可直接挂 net/http / httptest）。
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte("ok"))
	})
	mux.HandleFunc("GET /version", s.handleVersion)
	mux.HandleFunc("GET /metrics", s.handleMetrics)
	mux.HandleFunc("POST /api/v1/batches", s.handleBatches)
	mux.HandleFunc("GET /api/v1/vehicles", s.handleVehicles)
	mux.HandleFunc("GET /api/v1/vehicles/{vin}/speed", s.handleVehicleSpeed)
	return mux
}

func (s *Server) handleVersion(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, map[string]any{
		"version": version.Version, "commit": version.Commit, "build_time": version.BuildTime,
	})
}

func (s *Server) handleMetrics(w http.ResponseWriter, _ *http.Request) {
	ing, clean, dup, authFail, bad, alerts := s.Core.Count.Snapshot()
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	fmt.Fprintf(w, "# HELP fleet_batches_total 接入层收到的上行批总数\n# TYPE fleet_batches_total counter\nfleet_batches_total %d\n", ing)
	fmt.Fprintf(w, "# HELP fleet_samples_cleaned_total 清洗入库的样本总数\n# TYPE fleet_samples_cleaned_total counter\nfleet_samples_cleaned_total %d\n", clean)
	fmt.Fprintf(w, "# HELP fleet_dup_total 重复拦截总数（批/样本）\n# TYPE fleet_dup_total counter\nfleet_dup_total %d\n", dup)
	fmt.Fprintf(w, "# HELP fleet_auth_fail_total 鉴权失败总数\n# TYPE fleet_auth_fail_total counter\nfleet_auth_fail_total %d\n", authFail)
	fmt.Fprintf(w, "# HELP fleet_bad_batch_total 非法上行批总数（死信）\n# TYPE fleet_bad_batch_total counter\nfleet_bad_batch_total %d\n", bad)
	fmt.Fprintf(w, "# HELP fleet_alerts_total 告警命中总数\n# TYPE fleet_alerts_total counter\nfleet_alerts_total %d\n", alerts)
	fmt.Fprintf(w, "# HELP fleet_stored_samples 内存时序库样本数\n# TYPE fleet_stored_samples gauge\nfleet_stored_samples %d\n", s.Core.Store().SampleCount())
}

func (s *Server) handleBatches(w http.ResponseWriter, r *http.Request) {
	gatewayID := r.Header.Get("X-Gateway-ID")
	token := r.Header.Get("X-Token")
	if err := s.Core.VerifyGateway(gatewayID, token, time.Now()); err != nil {
		w.WriteHeader(http.StatusUnauthorized)
		writeJSON(w, map[string]any{"error": "unauthorized"})
		return
	}
	var b model.BatchUpload
	if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		writeJSON(w, map[string]any{"error": "bad json"})
		return
	}
	ack, err := s.Core.HandleBatch(b, time.Now())
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		writeJSON(w, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, map[string]any{"ack": ack})
}

func (s *Server) handleVehicles(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, map[string]any{"vehicles": s.Core.Store().Vehicles()})
}

func (s *Server) handleVehicleSpeed(w http.ResponseWriter, r *http.Request) {
	vin := r.PathValue("vin")
	speed, ok := s.Core.Store().LatestSpeed(vin)
	if !ok {
		w.WriteHeader(http.StatusNotFound)
		writeJSON(w, map[string]any{"error": "vehicle not found"})
		return
	}
	writeJSON(w, map[string]any{"vin": vin, "speed_kmh": speed})
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}
