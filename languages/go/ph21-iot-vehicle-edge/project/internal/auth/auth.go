// 来源：ph21-iot-vehicle-edge project/internal/auth/auth.go
// 一句话说明：网关级接入鉴权——HMAC 动态 token（时间槽），平台按 (当前槽, 上一槽)
// 校验，crypto/subtle 常量时间比较；每网关一密钥。签名/校验与 ex02 同构（主文档 3.2）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"errors"
	"fmt"
	"strconv"
	"time"
)

// ErrUnauthorized 鉴权失败（调用方对它是"上报，不重试"，主文档 3.3 纪律）。
var ErrUnauthorized = errors.New("auth: unauthorized gateway")

// SignToken 按时间槽签发动态 token。
func SignToken(secret, gatewayID string, slotDur time.Duration, now time.Time) string {
	slot := now.Unix() / int64(slotDur.Seconds())
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write([]byte(gatewayID + "|" + strconv.FormatInt(slot, 10)))
	return hex.EncodeToString(mac.Sum(nil))
}

// VerifyToken 校验 token（当前槽或上一槽）。
func VerifyToken(secret, gatewayID, token string, slotDur time.Duration, now time.Time) error {
	cur := now.Unix() / int64(slotDur.Seconds())
	for _, slot := range []int64{cur, cur - 1} {
		mac := hmac.New(sha256.New, []byte(secret))
		_, _ = mac.Write([]byte(gatewayID + "|" + strconv.FormatInt(slot, 10)))
		want := hex.EncodeToString(mac.Sum(nil))
		if subtle.ConstantTimeCompare([]byte(want), []byte(token)) == 1 {
			return nil
		}
	}
	return fmt.Errorf("%w: gateway=%s", ErrUnauthorized, gatewayID)
}

// Registry 每网关密钥表（离线 allowlist；生产落 DB/KMS 同语义）。
type Registry struct {
	secrets map[string]string
	slotDur time.Duration
}

// NewRegistry 从 map 建密钥表。
func NewRegistry(secrets map[string]string) *Registry {
	return &Registry{secrets: secrets, slotDur: 10 * time.Minute}
}

// Verify 校验 X-Gateway-ID 与 X-Token 是否匹配。
func (r *Registry) Verify(gatewayID, token string, now time.Time) error {
	secret, ok := r.secrets[gatewayID]
	if !ok {
		return fmt.Errorf("%w: 未知网关 %s", ErrUnauthorized, gatewayID)
	}
	return VerifyToken(secret, gatewayID, token, r.slotDur, now)
}
