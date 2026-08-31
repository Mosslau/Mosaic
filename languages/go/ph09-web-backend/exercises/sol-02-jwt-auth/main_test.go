// 来源：ph09-web-backend 练习 2 参考实现 —— 登录注册 + JWT
// 一句话说明：注册/登录/鉴权全链路测试 + JWT 签发验签单元测试（篡改、过期、格式错误）。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...
//	go test -cover ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func do(t *testing.T, users *userStore, method, path, body, token string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	rec := httptest.NewRecorder()
	newMux(users).ServeHTTP(rec, req)
	return rec
}

// register 辅助：注册并返回 token
func register(t *testing.T, users *userStore, username, password string) string {
	t.Helper()
	rec := do(t, users, "POST", "/register", `{"username":"`+username+`","password":"`+password+`"}`, "")
	if rec.Code != http.StatusCreated {
		t.Fatalf("注册状态码 = %d, 期望 201, 响应: %s", rec.Code, rec.Body.String())
	}
	var resp struct {
		Token string `json:"token"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("注册响应解析失败: %v", err)
	}
	return resp.Token
}

func TestRegister(t *testing.T) {
	users := newUserStore()
	rec := do(t, users, "POST", "/register", `{"username":"alice","password":"pw1"}`, "")
	if rec.Code != http.StatusCreated {
		t.Errorf("注册状态码 = %d, 期望 201", rec.Code)
	}
	// 重复注册 → 409
	recDup := do(t, users, "POST", "/register", `{"username":"alice","password":"pw2"}`, "")
	if recDup.Code != http.StatusConflict {
		t.Errorf("重复注册状态码 = %d, 期望 409", recDup.Code)
	}
	// 缺字段 → 400
	recEmpty := do(t, users, "POST", "/register", `{"username":"","password":""}`, "")
	if recEmpty.Code != http.StatusBadRequest {
		t.Errorf("缺字段注册状态码 = %d, 期望 400", recEmpty.Code)
	}
}

func TestLogin(t *testing.T) {
	users := newUserStore()
	register(t, users, "alice", "pw1")
	rec := do(t, users, "POST", "/login", `{"username":"alice","password":"pw1"}`, "")
	if rec.Code != http.StatusOK {
		t.Errorf("正确密码登录状态码 = %d, 期望 200", rec.Code)
	}
	recBad := do(t, users, "POST", "/login", `{"username":"alice","password":"wrong"}`, "")
	if recBad.Code != http.StatusUnauthorized {
		t.Errorf("错误密码登录状态码 = %d, 期望 401", recBad.Code)
	}
}

func TestProfileWithToken(t *testing.T) {
	users := newUserStore()
	token := register(t, users, "alice", "pw1")
	rec := do(t, users, "GET", "/api/profile", "", token)
	if rec.Code != http.StatusOK {
		t.Fatalf("带 token 访问状态码 = %d, 期望 200, 响应: %s", rec.Code, rec.Body.String())
	}
	var resp map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("profile 响应解析失败: %v", err)
	}
	if resp["username"] != "alice" {
		t.Errorf("username = %q, 期望 alice", resp["username"])
	}
}

func TestProfileUnauthorized(t *testing.T) {
	users := newUserStore()
	if rec := do(t, users, "GET", "/api/profile", "", ""); rec.Code != http.StatusUnauthorized {
		t.Errorf("无 token 状态码 = %d, 期望 401", rec.Code)
	}
	if rec := do(t, users, "GET", "/api/profile", "", "not-a-jwt"); rec.Code != http.StatusUnauthorized {
		t.Errorf("坏 token 状态码 = %d, 期望 401", rec.Code)
	}
	// 篡改 payload（admin→hacker）后签名不变 → 401
	token, _ := signJWT(map[string]any{"username": "admin"}, time.Hour)
	parts := strings.Split(token, ".")
	tampered := parts[0] + "." + "eyJ1c2VybmFtZSI6ImhhY2tlciJ9" + "." + parts[2]
	if rec := do(t, users, "GET", "/api/profile", "", tampered); rec.Code != http.StatusUnauthorized {
		t.Errorf("篡改 token 状态码 = %d, 期望 401", rec.Code)
	}
	// 过期 token → 401（ttl 为负）
	expired, _ := signJWT(map[string]any{"username": "alice"}, -time.Minute)
	if rec := do(t, users, "GET", "/api/profile", "", expired); rec.Code != http.StatusUnauthorized {
		t.Errorf("过期 token 状态码 = %d, 期望 401", rec.Code)
	}
}

func TestJWTUnit(t *testing.T) {
	// 往返：签发 → 验签拿到 claims
	token, err := signJWT(map[string]any{"username": "alice"}, time.Hour)
	if err != nil {
		t.Fatalf("签发失败: %v", err)
	}
	claims, err := verifyJWT(token)
	if err != nil {
		t.Fatalf("验签失败: %v", err)
	}
	if claims["username"] != "alice" {
		t.Errorf("claims.username = %v, 期望 alice", claims["username"])
	}
	// 格式错误
	if _, err := verifyJWT("a.b"); err == nil {
		t.Error("两段 token 竟然验签通过")
	}
}
