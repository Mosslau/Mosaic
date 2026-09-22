// 来源：09-web-backend.md 第 6 章示例 4 —— JWT 认证（手写 HS256）
// 一句话说明：jwt.go 的单元测试——签发/验签往返、篡改检测、错误密钥、过期、格式错误，
// 附签发 benchmark（结果写入 examples/README.md）。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...
//	go test -bench=. -benchmem -run=^$
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"strings"
	"testing"
	"time"
)

const testSecret = "test-secret-key"

func TestSignVerifyRoundTrip(t *testing.T) {
	token, err := signJWT(map[string]any{"username": "admin"}, []byte(testSecret), time.Hour)
	if err != nil {
		t.Fatalf("签发失败: %v", err)
	}
	claims, err := verifyJWT(token, []byte(testSecret))
	if err != nil {
		t.Fatalf("验签失败: %v", err)
	}
	if claims["username"] != "admin" {
		t.Errorf("claims.username = %v, 期望 admin", claims["username"])
	}
	if _, ok := claims["exp"]; !ok {
		t.Error("claims 应包含自动追加的 exp 字段")
	}
	// 结构必须是三段
	if parts := strings.Split(token, "."); len(parts) != 3 {
		t.Errorf("token 段数 = %d, 期望 3", len(parts))
	}
}

func TestVerifyTamperedPayload(t *testing.T) {
	token, _ := signJWT(map[string]any{"username": "admin"}, []byte(testSecret), time.Hour)
	// 篡改 payload 中间段（把 admin 改成 hacker），签名不变 → 验签必须失败
	parts := strings.Split(token, ".")
	tampered := parts[0] + "." + "eyJ1c2VybmFtZSI6ImhhY2tlciJ9" + "." + parts[2]
	if _, err := verifyJWT(tampered, []byte(testSecret)); err == nil {
		t.Fatal("篡改后的 token 竟然验签通过")
	}
}

func TestVerifyWrongSecret(t *testing.T) {
	token, _ := signJWT(map[string]any{"username": "admin"}, []byte(testSecret), time.Hour)
	if _, err := verifyJWT(token, []byte("another-secret")); err == nil {
		t.Fatal("错误密钥验签竟然通过")
	}
}

func TestVerifyExpired(t *testing.T) {
	// ttl 为负 → 签发即过期
	token, err := signJWT(map[string]any{"username": "admin"}, []byte(testSecret), -time.Minute)
	if err != nil {
		t.Fatalf("签发失败: %v", err)
	}
	if _, err := verifyJWT(token, []byte(testSecret)); err == nil {
		t.Fatal("过期 token 竟然验签通过")
	}
}

func TestVerifyMalformed(t *testing.T) {
	if _, err := verifyJWT("只有一段", []byte(testSecret)); err == nil {
		t.Fatal("格式错误的 token 竟然验签通过")
	}
	if _, err := verifyJWT("a.b.c.d", []byte(testSecret)); err == nil {
		t.Fatal("四段 token 竟然验签通过")
	}
}

// benchSink 包级变量承接 benchmark 结果，防止编译器把无副作用的签发循环整体优化掉
// （ph08 示例 5 的包级 sink 做法，见 ph08-testing/examples/ex05-benchmark-cover）
var benchSink string

// BenchmarkSignJWT 签发性能：记录 ns/op 与 allocs/op（教学对照用，见 examples/README.md）
func BenchmarkSignJWT(b *testing.B) {
	for i := 0; i < b.N; i++ {
		token, err := signJWT(map[string]any{"username": "admin"}, []byte(testSecret), time.Hour)
		if err != nil {
			b.Fatal(err)
		}
		benchSink = token
	}
}
