// 来源：ph09-web-backend 阶段项目 —— 车辆数据上报 API（internal/api 包）
// 一句话说明：每设备固定窗口限流器——单机实现（map + Mutex），分布式（Redis 令牌桶）见 ph10。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go test -v ./internal/api
//
// 验证状态：已验证（go1.25.6）
package api

import (
	"sync"
	"time"
)

// deviceLimiter 按设备 ID 的固定窗口限流器
type deviceLimiter struct {
	mu     sync.Mutex
	hits   map[string][]time.Time // key: device_id → 窗口内上报时间戳
	limit  int
	window time.Duration
}

func newDeviceLimiter(limit int, window time.Duration) *deviceLimiter {
	return &deviceLimiter{hits: make(map[string][]time.Time), limit: limit, window: window}
}

// allow 窗口内次数 < limit 则放行并记录
func (l *deviceLimiter) allow(key string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	cutoff := time.Now().Add(-l.window)
	kept := l.hits[key][:0]
	for _, t := range l.hits[key] {
		if t.After(cutoff) {
			kept = append(kept, t)
		}
	}
	l.hits[key] = kept
	if len(kept) >= l.limit {
		return false
	}
	l.hits[key] = append(l.hits[key], time.Now())
	return true
}
