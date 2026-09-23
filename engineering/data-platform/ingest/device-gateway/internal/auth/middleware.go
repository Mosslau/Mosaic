// Package auth 设备鉴权中间件: 校验 X-Device-Token, 并解析出**设备身份(绑定的 VIN)**。
//
// 两层语义(2026-09-18 补齐第二层):
//   - 认证: token 是否合法(第 1 阶段静态白名单; 第 2 阶段接车辆档案服务后改为查注册表)
//   - 身份: 这个 token 代表**哪辆车** —— 载荷 VIN 必须与之一致
//
// 只有认证、没有身份时, 任何持合法 token 的设备都能上报**任意 VIN**(冒充他人车辆写数据)。
// MQTT 通道靠 topic 绑定 VIN(topic = ov/{vin}/...), HTTP 通道没有 topic, 只能靠 token 绑定。
package auth

import (
	"context"
	"net/http"
	"strings"

	"github.com/Mosslau/Mosaic/ingest/device-gateway/internal/metrics"
	"github.com/Mosslau/Mosaic/ingest/device-gateway/internal/model"
)

const TokenHeader = "X-Device-Token"

// DevTokenPrefix dev 模式的后缀约定: token = "dev-" + VIN。
// 与 device-simulator 的 http-simulator 构造一致(token := "dev-" + vin),
// 使上万设备的压测无需预置白名单; 但**仍然做 VIN 校验** —— 旧实现放行任意 "dev-"
// 前缀, 等于给 VIN 校验留了一道后门(dev 模式在共享环境里被打开就重新裸奔)。
const DevTokenPrefix = "dev-"

// Identity 已认证的设备身份。
type Identity struct {
	VIN string // 该 token 绑定的 VIN(dev 模式由 token 后缀推断)
}

// ctxKey 身份在 context 中的键(不导出, 防止外部伪造)。
type ctxKey struct{}

// Middleware 设备鉴权中间件
type Middleware struct {
	bindings map[string]string // token → VIN 绑定表
	devMode  bool              // 开发模式: 额外接受 "dev-{VIN}" 形态
}

// New 构造中间件。bindings 为 token → VIN 绑定表(已由 config.Load 解析并校验)。
func New(bindings map[string]string, devMode bool) *Middleware {
	m := &Middleware{bindings: make(map[string]string, len(bindings)), devMode: devMode}
	for token, vin := range bindings {
		m.bindings[token] = vin
	}
	return m
}

// Wrap 包装 next: 鉴权失败直接 401, 不进入后续处理链; 成功则把身份注入 context。
func (m *Middleware) Wrap(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id, ok := m.identity(r.Header.Get(TokenHeader))
		if !ok {
			metrics.RequestsTotal.WithLabelValues(r.URL.Path, "unauthorized").Inc()
			model.WriteError(w, model.CodeUnauthorized, "设备令牌缺失或非法")
			return
		}
		next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), ctxKey{}, id)))
	})
}

// FromContext 取已认证身份。第二个返回值为 false 表示链路上没有身份 ——
// 只可能出现在直接调用 handler 的单测里(生产路径必经 Wrap), 此时不做 VIN 校验。
func FromContext(ctx context.Context) (Identity, bool) {
	id, ok := ctx.Value(ctxKey{}).(Identity)
	return id, ok
}

// identity 解析 token → 身份。
// 顺序: 先查绑定表, 再(仅 dev 模式)按 "dev-{VIN}" 推断。
func (m *Middleware) identity(token string) (Identity, bool) {
	if token == "" {
		return Identity{}, false
	}
	if vin, ok := m.bindings[token]; ok {
		return Identity{VIN: vin}, true
	}
	if m.devMode {
		if vin, ok := strings.CutPrefix(token, DevTokenPrefix); ok && vin != "" {
			return Identity{VIN: vin}, true
		}
	}
	return Identity{}, false
}
