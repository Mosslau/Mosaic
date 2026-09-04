// 来源：ph21-iot-vehicle-edge examples/ex02-device-reconnect-idempotent/platform.go
// 一句话说明：云接入侧最小平台——HTTP POST 遥测端点：校验动态 token（3.2）、
// (vin,seq) 幂等去重（3.3）、计数吞吐/重复/鉴权失败（3.9 的 metric 素材）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"encoding/json"
	"net/http"
	"sync/atomic"
	"time"
)

const tokenSlotDur = 5 * time.Minute

// Telemetry 上行报文：seq 单调递增（设备侧保证），其余字段是业务样例。
type Telemetry struct {
	Vin   string  `json:"vin"`
	Seq   uint64  `json:"seq"`
	Speed float64 `json:"speed"`
	Ts    int64   `json:"ts_device"` // 设备时钟时间戳；平台侧排序应优先用到达时间
}

// Platform 云接入服务（无框架、纯 net/http，可被 httptest 直接挂载）。
type Platform struct {
	secrets map[string]string // deviceID → 种子密钥（allowlist；生产存 DB/KMS）
	dedup   *Deduper
	slotDur time.Duration

	ingest atomic.Int64 // 收到并生效的报文数
	dup    atomic.Int64 // 重复/乱序拦截数
	auth   atomic.Int64 // 鉴权失败数（指标要带 reason，见主文档 3.9）
}

// NewPlatform 建平台；secrets 是设备密钥表（每车一密）。
func NewPlatform(secrets map[string]string) *Platform {
	return &Platform{secrets: secrets, dedup: NewDeduper(4096), slotDur: tokenSlotDur}
}

// Handler 返回路由：POST /api/v1/telemetry。
func (p *Platform) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/v1/telemetry", p.handleTelemetry)
	return mux
}

type telemetryResponse struct {
	Accepted bool   `json:"accepted"` // false = 重复/乱序，设备可放心不再补
	Status   string `json:"status"`
}

func (p *Platform) handleTelemetry(w http.ResponseWriter, r *http.Request) {
	deviceID := r.Header.Get("X-Device-ID")
	token := r.Header.Get("X-Token")
	secret, ok := p.secrets[deviceID]
	if !ok || VerifyToken(secret, deviceID, token, p.slotDur, time.Now()) != nil {
		p.auth.Add(1)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"error":"unauthorized"}`))
		return
	}
	var t Telemetry
	if err := json.NewDecoder(r.Body).Decode(&t); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"error":"bad body"}`))
		return
	}
	resp := telemetryResponse{Status: "accepted"}
	if p.dedup.FirstTime(t.Vin, t.Seq) {
		p.ingest.Add(1)
		resp.Accepted = true
	} else {
		p.dup.Add(1) // 重复/乱序：计数可观测，不产生副作用
		resp.Status = "duplicate"
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(resp)
}

// Stats 返回三个计数，供 main/测试打印与断言。
func (p *Platform) Stats() (ingest, dup, authFail int64) {
	return p.ingest.Load(), p.dup.Load(), p.auth.Load()
}
