// 来源：ph21-iot-vehicle-edge project/internal/gateway/transport.go
// 一句话说明：HTTP 上行传输——把聚合批 POST 到平台 /api/v1/batches，带网关级
// 动态 token；解析云端 ack 水位。鉴权失败(401)包 auth.ErrUnauthorized，其余网络/
// 5xx 视为可重试瞬断错误（主文档 3.2/3.11）。换 MQTT 接入时实现同一 Uplink 接口。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package gateway

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"tenetlang/go/ph21-iot-vehicle-edge/project/internal/auth"
	"tenetlang/go/ph21-iot-vehicle-edge/project/internal/model"
)

// HTTPUplink 经 HTTP 上报批的传输。
type HTTPUplink struct {
	BaseURL   string // 如 http://127.0.0.1:8080
	GatewayID string
	Secret    string
	Client    *http.Client
}

// NewHTTPUplink 建上行传输。
func NewHTTPUplink(baseURL, gatewayID, secret string) *HTTPUplink {
	return &HTTPUplink{
		BaseURL: baseURL, GatewayID: gatewayID, Secret: secret,
		Client: &http.Client{Timeout: 10 * time.Second},
	}
}

type ackResponse struct {
	Ack uint64 `json:"ack"`
}

// SendBatch 实现 Uplink。
func (u *HTTPUplink) SendBatch(ctx context.Context, b model.BatchUpload) (uint64, error) {
	body, err := json.Marshal(b)
	if err != nil {
		return 0, fmt.Errorf("编码批: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, u.BaseURL+"/api/v1/batches", bytes.NewReader(body))
	if err != nil {
		return 0, err
	}
	token := auth.SignToken(u.Secret, u.GatewayID, 10*time.Minute, time.Now())
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Gateway-ID", u.GatewayID)
	req.Header.Set("X-Token", token)
	resp, err := u.Client.Do(req)
	if err != nil {
		return 0, fmt.Errorf("上行网络错误: %w", err) // 可重试类
	}
	defer func() { _ = resp.Body.Close() }()
	data, _ := io.ReadAll(resp.Body)
	switch {
	case resp.StatusCode == http.StatusUnauthorized:
		return 0, fmt.Errorf("%w: 网关 %s", auth.ErrUnauthorized, u.GatewayID)
	case resp.StatusCode != http.StatusOK:
		return 0, fmt.Errorf("云端返回 HTTP %d: %s", resp.StatusCode, truncate(data, 120))
	}
	var ar ackResponse
	if err := json.Unmarshal(data, &ar); err != nil {
		return 0, fmt.Errorf("解析 ack: %w", err)
	}
	return ar.Ack, nil
}

func truncate(b []byte, n int) string {
	if len(b) > n {
		b = b[:n]
	}
	return string(b)
}

// 断言 HTTPUplink 实现接口（编译期检查）。
var _ Uplink = (*HTTPUplink)(nil)
