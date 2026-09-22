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
	global    *rate.Limiter // 全局令牌桶(三条通道共用)
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

// 全局限流的容量关系(2026-09-20 显式化, 修复前只有 factor=2 一个魔数):
//
//	全局桶 = rate.NewLimiter(RATE_GLOBAL, RATE_GLOBAL_BURST)
//
// 三条通道(HTTP 直连 / MQTT-JSON webhook / 二进制 webhook)**共用同一个全局桶**
// (GlobalWrap 与 Wrap 都走 l.global)。因此:
//
//	RATE_GLOBAL 必须 >= 三条通道的**合计**峰值 qps, 否则大促/整队上线时会被自己的全局限流 429 掉。
//
// 两条容量纠错(修复前后对比):
//   - 修复前 burst 硬编码 = 2×rate, 而 RATE_GLOBAL 默认 5000 → 突发上限 10000;
//     一万设备按 1s 周期上报恰好是 10000 qps, **正好把全局桶打穿**, 整队恢复上报时丢请求。
//   - 修复前 RATE_PER_DEVICE 的桶 burst = 速率本身(10) → 单设备可瞬时发 10 条;
//     1000 台设备同时惊群就是 10000 条瞬时请求, 又会打穿全局桶。
//     现在单设备 burst 收窄为 max(1, ceil(rate/2)), 把"惊群尖峰"交给全局桶兜,
//     单设备桶只负责掐"一台车持续发疯"。
//
// 放大倍率提醒: MQTT 通道一次设备上报 = **一条** HTTP webhook 请求; 二进制通道同样一条。
// 但若将来做"下行/补发/多 topic 扇出", 一次设备动作可能放大成 N 条 webhook 请求,
// 那时 RATE_GLOBAL 必须按 N 倍配置 —— 这个 N 没有地方能自动推导, 只能显式写在配置里。
const (
	// defaultGlobalBurstFactor 未显式配置 RATE_GLOBAL_BURST 时的突发系数。
	// 取 3: 覆盖"整队上线 + EMQX 缓冲补投"这类叠加尖峰(约 2 倍稳态), 留一档余量。
	defaultGlobalBurstFactor = 3
	// perDeviceBurstDivisor 单设备桶的突发 = ceil(速率 / 该值), 下限 1。
	perDeviceBurstDivisor = 2
)

// New 创建限流器。
//   - perDevice: 单设备条/秒;
//   - global: 全局限条/秒(三条通道合计);
//   - globalBurst <=0 时按 defaultGlobalBurstFactor × global 计算。
func New(perDevice, global float64, globalBurst int) *Limiter {
	if globalBurst <= 0 {
		globalBurst = burstFor(global, defaultGlobalBurstFactor)
	}
	l := &Limiter{
		global:    rate.NewLimiter(rate.Limit(global), globalBurst),
		perDevice: perDevice,
		devices:   make(map[string]*deviceEntry),
		stop:      make(chan struct{}),
	}
	go l.janitor()
	return l
}

// GlobalBurst 返回实际生效的全局突发容量(供启动日志与自检脚本核对容量关系)。
func (l *Limiter) GlobalBurst() int { return l.global.Burst() }

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
// 突发容量 = max(1, ceil(速率/2)): 单设备桶只负责掐"一台车持续发疯",
// **不**负责吸收整队上线的尖峰(那由全局桶兜) —— 容量公式见文件头注释。
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
		e = &deviceEntry{limiter: rate.NewLimiter(rate.Limit(l.perDevice), burstFor(l.perDevice, 1.0/perDeviceBurstDivisor))}
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
