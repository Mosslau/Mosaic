// 来源：ph21-data-ingest-gateway project/internal/auth/auth_test.go
// 一句话说明：鉴权包测试——正确 token 通过/错密钥与未知采集器拒绝、窗口外过期拒绝。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package auth

import (
	"errors"
	"testing"
	"time"
)

func TestVerifyAcceptsValidToken(t *testing.T) {
	now := time.Now()
	tok := SignToken("s3cr3t", "relay-001", 10*time.Minute, now)
	if err := VerifyToken("s3cr3t", "relay-001", tok, 10*time.Minute, now.Add(time.Minute)); err != nil {
		t.Errorf("有效 token 应通过: %v", err)
	}
}

func TestVerifyRejectsWrongKeyAndCollector(t *testing.T) {
	now := time.Now()
	tok := SignToken("s3cr3t", "relay-001", 10*time.Minute, now)
	if err := VerifyToken("bad", "relay-001", tok, 10*time.Minute, now); !errors.Is(err, ErrUnauthorized) {
		t.Errorf("错密钥应拒绝, got %v", err)
	}
	if err := VerifyToken("s3cr3t", "relay-002", tok, 10*time.Minute, now); !errors.Is(err, ErrUnauthorized) {
		t.Errorf("错采集器应拒绝, got %v", err)
	}
}

func TestVerifyExpiredAfterWindow(t *testing.T) {
	now := time.Now()
	tok := SignToken("s3cr3t", "relay-001", time.Minute, now)
	future := now.Add(3 * time.Minute)
	if err := VerifyToken("s3cr3t", "relay-001", tok, time.Minute, future); !errors.Is(err, ErrUnauthorized) {
		t.Errorf("过期 token 应拒绝, got %v", err)
	}
}

func TestRegistryUnknownCollector(t *testing.T) {
	r := NewRegistry(map[string]string{"relay-001": "s1"})
	tok := SignToken("s1", "relay-001", time.Minute, time.Now())
	if err := r.Verify("relay-999", tok, time.Now()); !errors.Is(err, ErrUnauthorized) {
		t.Errorf("未知采集器应拒绝, got %v", err)
	}
}
