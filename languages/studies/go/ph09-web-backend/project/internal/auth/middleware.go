// 来源：ph09-web-backend 阶段项目 —— 设备数据上报 API（internal/auth 包）
// 一句话说明：鉴权中间件——解析 Authorization: Bearer <JWT>，验签后把 device_id 写入 context；
// 同时校验 token 归属的设备与路径参数一致（设备只能上报自己的数据）。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go test -v ./internal/auth
//
// 验证状态：已验证（go1.25.6）
package auth

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
)

// ctxKey 私有 context 键类型（避免与其他包冲突）
type ctxKey struct{}

// ClaimsDeviceID 从 context 取 device_id claim（中间件写入）
func ClaimsDeviceID(ctx context.Context) string {
	v, _ := ctx.Value(ctxKey{}).(string)
	return v
}

// Middleware 返回鉴权中间件：验签通过才放行，并把 device_id 写入请求 context
func Middleware(secret []byte) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			token, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
			if !ok {
				writeError(w, http.StatusUnauthorized, "UNAUTHORIZED", "缺少 Bearer token")
				return
			}
			claims, err := Verify(token, secret)
			if err != nil {
				writeError(w, http.StatusUnauthorized, "UNAUTHORIZED", "token 无效或已过期")
				return
			}
			deviceID, _ := claims["device_id"].(string)
			ctx := context.WithValue(r.Context(), ctxKey{}, deviceID)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// writeError 统一错误结构（与 api 包一致，避免依赖环所以本包自带一份）
func writeError(w http.ResponseWriter, status int, code, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"code": code, "message": msg})
}
