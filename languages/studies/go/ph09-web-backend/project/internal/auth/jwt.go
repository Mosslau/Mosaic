// 来源：ph09-web-backend 阶段项目 —— 设备数据上报 API（internal/auth 包）
// 一句话说明：标准库手写 HS256 JWT 签发/验签（RFC 7519 最小实现），供设备认证使用。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go test -v ./internal/auth
//
// 验证状态：已验证（go1.25.6）
package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"strings"
	"time"
)

// Sign 签发 HS256 JWT：header.payload.signature 三段 base64url（RawURLEncoding 无填充）。
// claims 会被追加 exp；不改调用方 map。
func Sign(claims map[string]any, secret []byte, ttl time.Duration) (string, error) {
	withExp := make(map[string]any, len(claims)+1)
	for k, v := range claims {
		withExp[k] = v
	}
	withExp["exp"] = time.Now().Add(ttl).Unix()

	header, err := json.Marshal(map[string]string{"alg": "HS256", "typ": "JWT"})
	if err != nil {
		return "", err
	}
	payload, err := json.Marshal(withExp)
	if err != nil {
		return "", err
	}
	enc := base64.RawURLEncoding
	signing := enc.EncodeToString(header) + "." + enc.EncodeToString(payload)

	mac := hmac.New(sha256.New, secret)
	mac.Write([]byte(signing))
	return signing + "." + enc.EncodeToString(mac.Sum(nil)), nil
}

// Verify 验签 + 过期校验：hmac.Equal 常数时间比较防时序攻击；能验签 = 未被篡改 = 可信。
func Verify(token string, secret []byte) (map[string]any, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil, errors.New("token 格式错误：应为三段")
	}
	enc := base64.RawURLEncoding
	signing := parts[0] + "." + parts[1]

	mac := hmac.New(sha256.New, secret)
	mac.Write([]byte(signing))
	if !hmac.Equal([]byte(parts[2]), []byte(enc.EncodeToString(mac.Sum(nil)))) {
		return nil, errors.New("签名不匹配：token 被篡改或密钥不对")
	}
	payload, err := enc.DecodeString(parts[1])
	if err != nil {
		return nil, errors.New("payload 解码失败")
	}
	var claims map[string]any
	if err := json.Unmarshal(payload, &claims); err != nil {
		return nil, errors.New("payload 不是合法 JSON")
	}
	exp, ok := claims["exp"].(float64)
	if !ok || time.Now().Unix() > int64(exp) {
		return nil, errors.New("token 已过期")
	}
	return claims, nil
}
