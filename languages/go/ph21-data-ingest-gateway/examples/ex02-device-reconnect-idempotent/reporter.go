// 来源：ph21-data-ingest-gateway examples/ex02-device-reconnect-idempotent/reporter.go
// 一句话说明：设备侧上报器——每个样本带单调 seq；SendOnce 走 HTTP（带动态 token）；
// SendWithRetry 把重连循环套在发送上：网络错误退避重试、鉴权失败直达上报。
// 若网络真的断开，SendWithRetry 返回错误，调用方把该 seq 写入本地 spool——
// 那是 ex05 边缘网关的职责（主文档 3.3/3.11）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"sync/atomic"
	"time"
)

// Reporter 设备侧 HTTP 上报器。
type Reporter struct {
	Endpoint string // 平台 /api/v1/telemetry 的完整 URL
	DeviceID string
	Secret   string
	Client   *http.Client
	seq      atomic.Uint64
}

// NextSeq 取下一个单调序号（设备重启后若从 1 重来会撞平台 seqCeiling，
// 生产由网关持久化游标，见 ex05 spool——此处演示单进程语义）。
func (r *Reporter) NextSeq() uint64 { return r.seq.Add(1) }

// SendOnce 单次上报：成功返回 nil；401 → ErrUnauthorized；网络错原样返回。
func (r *Reporter) SendOnce(ctx context.Context, t Telemetry) error {
	token := SignToken(r.Secret, r.DeviceID, tokenSlotDur, time.Now())
	body, err := json.Marshal(t)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, r.Endpoint, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Device-ID", r.DeviceID)
	req.Header.Set("X-Token", token)
	resp, err := r.Client.Do(req)
	if err != nil {
		return fmt.Errorf("上报网络失败: %w", err) // 可重试类
	}
	defer func() { _ = resp.Body.Close() }()
	_, _ = io.Copy(io.Discard, resp.Body) // 读完 body 以便连接复用
	switch {
	case resp.StatusCode == http.StatusUnauthorized:
		return fmt.Errorf("%w: 设备 %s", ErrUnauthorized, r.DeviceID)
	case resp.StatusCode != http.StatusOK:
		return fmt.Errorf("平台返回 HTTP %d", resp.StatusCode)
	}
	return nil
}

// SendWithRetry 带退避重试的上报：默认策略（1s 起、封顶 30s、最多 5 次）。
func (r *Reporter) SendWithRetry(ctx context.Context, t Telemetry) error {
	loop := &ReconnectLoop{
		Try:         func() error { return r.SendOnce(ctx, t) },
		BaseBackoff: time.Second,
		MaxBackoff:  30 * time.Second,
		MaxAttempts: 5,
		Jitter:      defaultJitter,
	}
	return loop.Run(ctx)
}

// IsUnauthorized 判断错误是否鉴权失败（供上层决定上报还是重试）。
func IsUnauthorized(err error) bool { return errors.Is(err, ErrUnauthorized) }
