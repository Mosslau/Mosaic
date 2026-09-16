// Package auth 设备鉴权中间件: 校验 X-Device-Token。
// 第 1 阶段用静态白名单; 第 2 阶段接车辆档案服务后改为查询设备注册表。
package auth

import (
	"net/http"
	"strings"

	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/metrics"
	"github.com/Mosslau/OceanVerse/ingest/device-gateway/internal/model"
)

const TokenHeader = "X-Device-Token"

// Middleware 设备鉴权中间件
type Middleware struct {
	tokens  map[string]struct{} // 白名单
	devMode bool                // 开发模式: 放行 "dev-" 前缀 token
}

func New(tokens []string, devMode bool) *Middleware {
	m := &Middleware{tokens: make(map[string]struct{}, len(tokens)), devMode: devMode}
	for _, t := range tokens {
		m.tokens[t] = struct{}{}
	}
	return m
}

// Wrap 包装 next: 鉴权失败直接 401, 不进入后续处理链
func (m *Middleware) Wrap(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		token := r.Header.Get(TokenHeader)
		if !m.valid(token) {
			metrics.RequestsTotal.WithLabelValues(r.URL.Path, "unauthorized").Inc()
			model.WriteError(w, model.CodeUnauthorized, "设备令牌缺失或非法")
			return
		}
		next.ServeHTTP(w, r)
	})
}

// valid 校验 token 是否合法。
// dev 模式放行 "dev-" 前缀: 压测模拟器要生成上万设备身份, 不可能预置白名单;
// 生产环境 GATEWAY_DEV_MODE=false, 仅白名单生效。
func (m *Middleware) valid(token string) bool {
	if token == "" {
		return false
	}
	if m.devMode && strings.HasPrefix(token, "dev-") {
		return true
	}
	_, ok := m.tokens[token]
	return ok
}
