// 来源：09-web-backend.md 第 6 章示例 4 —— JWT 认证（手写 HS256）
// 一句话说明：用标准库（crypto/hmac + crypto/sha256 + encoding/base64 + encoding/json）
// 手写最小 JWT 签发/验签，讲透 header.payload.signature 结构与 HMAC 验签原理。
// 生产建议用 github.com/golang-jwt/jwt/v5（第三方，本示例不引入）；教学实现完整可运行。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go run .
//	curl -s -X POST http://127.0.0.1:18080/login -d '{"username":"admin","password":"123456"}'
//	# 用返回的 token 访问受保护接口：
//	curl -s http://127.0.0.1:18080/api/profile -H "Authorization: Bearer <token>"
//
// 测试：
//
//	go test -v ./...
//	go test -bench=. -benchmem -run=^$   # JWT 签发性能
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"strings"
	"time"
)

// signJWT 签发 HS256 JWT：header.payload.signature 三段 base64url（RawURLEncoding 无填充）。
// claims 会被追加 "exp" 字段（拷贝后再追加，不改调用方 map）。
func signJWT(claims map[string]any, secret []byte, ttl time.Duration) (string, error) {
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

// verifyJWT 验签 + 校验过期：用同一 secret 重算签名，hmac.Equal 常数时间比较防时序攻击。
// 能验签 = 未被篡改 = 可信——这是"无状态认证"的核心：服务端不存会话，只存密钥。
func verifyJWT(token string, secret []byte) (map[string]any, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil, errors.New("token 格式错误：应为 header.payload.signature 三段")
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
	// JSON 数字统一解码为 float64，exp 是 Unix 秒
	exp, ok := claims["exp"].(float64)
	if !ok || time.Now().Unix() > int64(exp) {
		return nil, errors.New("token 已过期")
	}
	return claims, nil
}
