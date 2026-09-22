// 来源：ph21-data-ingest-gateway examples/ex02-agent-reconnect-idempotent/reconnector.go
// 一句话说明：指数退避 + 抖动的重连循环——网络类错误按 1s→2s→4s 退避重试
// （抖动防海量采集端同刻重连），鉴权失败直接上报不重试，退避可注入 clock 离线测。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"context"
	"errors"
	"fmt"
	"math/rand"
	"time"
)

// ReconnectLoop 可测试的重连循环：Try 每轮要做的单次动作（建连/上报），
// Sleep 与 Jitter 可注入以便测试不真睡（离线确定性）。
type ReconnectLoop struct {
	Try         func() error
	BaseBackoff time.Duration
	MaxBackoff  time.Duration
	MaxAttempts int
	// Sleep 默认按 ctx 可取消计时；测试可注入函数采集退避序列。
	Sleep  func(ctx context.Context, d time.Duration) error
	Jitter func() int64
}

// Run 执行带退避的重连：成功返回 nil；ErrUnauthorized 立即返回不重试；
// 其余错误退避重试至 MaxAttempts 次后返回最后一次错误。
func (r *ReconnectLoop) Run(ctx context.Context) error {
	backoff := r.BaseBackoff
	var last error
	for attempt := 1; attempt <= r.MaxAttempts; attempt++ {
		err := r.Try()
		if err == nil {
			return nil
		}
		if errors.Is(err, ErrUnauthorized) {
			return err // 鉴权失败：重试只会放大攻击面，直接上报人工处理
		}
		last = err
		if attempt == r.MaxAttempts {
			break
		}
		delay := backoff
		if r.Jitter != nil {
			// 抖动 = [0, backoff/2) 随机增量：避免整群采集端同时重连的惊群。
			if half := backoff / 2; half > 0 {
				delay += time.Duration(r.Jitter() % int64(half))
			}
		}
		if r.Sleep != nil {
			if err := r.Sleep(ctx, delay); err != nil {
				return err
			}
		} else if err := sleepCtx(ctx, delay); err != nil {
			return err
		}
		backoff *= 2
		if r.MaxBackoff > 0 && backoff > r.MaxBackoff {
			backoff = r.MaxBackoff
		}
	}
	return fmt.Errorf("重连 %d 次仍失败（最后错误）: %w", r.MaxAttempts, last)
}

// sleepCtx 可取消的 sleep。
func sleepCtx(ctx context.Context, d time.Duration) error {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-t.C:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

// defaultJitter 非密码学随机就够：只要求不齐步走。
func defaultJitter() int64 { return rand.Int63() }
