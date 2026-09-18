// Package ratelimit 令牌桶限流: 全局闸门 + 单设备闸门, 双闸门都过才放行。
// 防两种风暴: ① 单设备故障疯狂重发 ② 大批设备同时上线(惊群)。
package ratelimit

import (
	"log/slog"
	"math"
	"net/http"
	"sync"
	"time"

	"golang.org/x/time/rate"

	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/metrics"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/model"
)

// Limiter 双层限流器
type Limiter struct {
	global    *rate.Limiter // 全局令牌桶
	perDevice float64       // 单设备速率(条/秒)

	mu        sync.Mutex
	devices   map[string]*deviceEntry // key: 设备 token 或 VIN
	stop      chan struct{}
	closeOnce sync.Once
}

type deviceEntry struct {
	limiter  *rate.Limiter
	lastSeen time.Time
}

// maxDeviceKeys dev 模式下设备桶 map 的容量上限。
// 生产环境 key 来自 token 白名单(有界); dev 模式放行任意 "dev-" 前缀, key 空间无界,
// 恶意/异常客户端可用海量假 token 撑爆内存。超限后不再为新 key 建桶(退化为只受全局限流)。
const maxDeviceKeys = 100000

// New 创建限流器。perDevice: 单设备条/秒; global: 全局条/秒(突发容量取速率的 2 倍)。
func New(perDevice, global float64) *Limiter {
	l := &Limiter{
		global:    rate.NewLimiter(rate.Limit(global), burstFor(global, 2)),
		perDevice: perDevice,
		devices:   make(map[string]*deviceEntry),
		stop:      make(chan struct{}),
	}
	go l.janitor()
	return l
}

// burstFor 计算令牌桶突发容量, 保证 >= 1。
// 用 int(速率) 直接截断会让 0<速率<1 得到 burst=0, 而 x/time/rate 在 burst=0 时恒拒绝
// → 全量 429。速率 >= 1 已由 config.Load() fail-fast 拦住, 这里做兜底防呆。
func burstFor(perSec float64, factor float64) int {
	b := int(math.Ceil(perSec * factor))
	if b < 1 {
		return 1
	}
	return b
}

// Wrap 限流中间件。设备标识取自鉴权通过的 token(车联网场景 token 与设备一一对应)。
func (l *Limiter) Wrap(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !l.global.Allow() {
			l.reject(w, r)
			return
		}
		key := r.Header.Get("X-Device-Token")
		if !l.deviceLimiter(key).Allow() {
			l.reject(w, r)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// Close 停止后台清理协程(优雅退出时调用)。幂等: 重复调用不会 panic(close 已关闭的 channel 会 panic)。
func (l *Limiter) Close() { l.closeOnce.Do(func() { close(l.stop) }) }

// GlobalWrap 只挂全局令牌桶(不建单设备桶)。
// 用途: EMQX webhook 两条通道(JSON / 二进制)。它们的单设备限流在 EMQX 协议层
// (listener rate_limit), 网关侧不应再按请求头建桶; 但**必须**有全局桶兜底 ——
// 此前这两条路由完全没挂限流, 任意速率可直达 Kafka(2026-09-18 审计整改)。
func (l *Limiter) GlobalWrap(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !l.global.Allow() {
			l.reject(w, r)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// reject 拒绝请求: 带 Retry-After 引导设备端退避重试, 并计入 metrics(拒绝率必须可观测)。
func (l *Limiter) reject(w http.ResponseWriter, r *http.Request) {
	metrics.RequestsTotal.WithLabelValues(r.URL.Path, "rate_limited").Inc()
	w.Header().Set("Retry-After", "1")
	model.WriteError(w, model.CodeRateLimited, "触发限流, 请降速重试")
}

// deviceLimiter 取/建单设备令牌桶(惰性创建, 首次出现的设备才占内存)。
// 突发容量 = 速率: 最多容忍 1 秒的瞬时突发——周期上报的设备不应有秒级以上的毛刺,
// 这个取值把"正常抖动放行、持续发疯掐死"区分开。
func (l *Limiter) deviceLimiter(key string) *rate.Limiter {
	l.mu.Lock()
	defer l.mu.Unlock()
	e, ok := l.devices[key]
	if !ok {
		// 容量上限: dev 模式 key 空间无界, 防止海量假 token 撑爆内存
		if len(l.devices) >= maxDeviceKeys {
			slog.Warn("设备限流桶已达容量上限, 新设备仅受全局限流", "limit", maxDeviceKeys)
			return l.global
		}
		// 突发容量 = 速率, 即允许最多 1 秒的瞬时突发
		e = &deviceEntry{limiter: rate.NewLimiter(rate.Limit(l.perDevice), burstFor(l.perDevice, 1))}
		l.devices[key] = e
	}
	e.lastSeen = time.Now()
	return e.limiter
}

// janitor 每分钟清理闲置超过 5 分钟的设备限流器, 防止 map 无限增长。
// 10 万设备同时在线时 map 约几十 MB, 可接受; 清理只是为了防泄漏。
func (l *Limiter) janitor() {
	tick := time.NewTicker(time.Minute)
	defer tick.Stop()
	for {
		select {
		case <-l.stop:
			return
		case <-tick.C:
			l.mu.Lock()
			for k, e := range l.devices {
				if time.Since(e.lastSeen) > 5*time.Minute {
					delete(l.devices, k)
				}
			}
			l.mu.Unlock()
		}
	}
}
