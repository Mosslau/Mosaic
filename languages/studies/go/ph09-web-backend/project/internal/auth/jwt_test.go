// 来源：ph09-web-backend 阶段项目 —— 设备数据上报 API（internal/auth 包）
// 一句话说明：JWT 签发/验签单元测试——往返、篡改、错误密钥、过期、格式错误。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./internal/auth
//	go test -cover ./internal/auth
//
// 验证状态：已验证（go1.25.6）
package auth

import (
	"strings"
	"testing"
	"time"
)

const testSecret = "auth-test-secret"

func TestSignVerifyRoundTrip(t *testing.T) {
	token, err := Sign(map[string]any{"device_id": "car-001"}, []byte(testSecret), time.Hour)
	if err != nil {
		t.Fatalf("签发失败: %v", err)
	}
	claims, err := Verify(token, []byte(testSecret))
	if err != nil {
		t.Fatalf("验签失败: %v", err)
	}
	if claims["device_id"] != "car-001" {
		t.Errorf("claims.device_id = %v, 期望 car-001", claims["device_id"])
	}
	if _, ok := claims["exp"]; !ok {
		t.Error("claims 应包含 exp")
	}
	if parts := strings.Split(token, "."); len(parts) != 3 {
		t.Errorf("token 段数 = %d, 期望 3", len(parts))
	}
}

func TestVerifyTampered(t *testing.T) {
	token, _ := Sign(map[string]any{"device_id": "car-001"}, []byte(testSecret), time.Hour)
	parts := strings.Split(token, ".")
	tampered := parts[0] + "." + "eyJkZXZpY2VfaWQiOiJjYXItMDAyIn0" + "." + parts[2] // device_id → car-002
	if _, err := Verify(tampered, []byte(testSecret)); err == nil {
		t.Fatal("篡改 payload 竟然验签通过")
	}
}

func TestVerifyWrongSecret(t *testing.T) {
	token, _ := Sign(map[string]any{"device_id": "car-001"}, []byte(testSecret), time.Hour)
	if _, err := Verify(token, []byte("wrong")); err == nil {
		t.Fatal("错误密钥竟然验签通过")
	}
}

func TestVerifyExpired(t *testing.T) {
	token, err := Sign(map[string]any{"device_id": "car-001"}, []byte(testSecret), -time.Minute)
	if err != nil {
		t.Fatalf("签发失败: %v", err)
	}
	if _, err := Verify(token, []byte(testSecret)); err == nil {
		t.Fatal("过期 token 竟然验签通过")
	}
}

func TestVerifyMalformed(t *testing.T) {
	if _, err := Verify("a.b", []byte(testSecret)); err == nil {
		t.Fatal("两段 token 竟然验签通过")
	}
	if _, err := Verify("", []byte(testSecret)); err == nil {
		t.Fatal("空 token 竟然验签通过")
	}
}
