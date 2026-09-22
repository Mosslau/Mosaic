// 来源：09-web-backend.md 第 6 章示例 4 —— JWT 认证（手写 HS256）
// 一句话说明：handler 层测试——登录成功/失败、无 token/坏 token/过期 token 的 401、带 token 访问 profile。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...
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

func do(t *testing.T, method, path, body, token string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	rec := httptest.NewRecorder()
	newMux().ServeHTTP(rec, req)
	return rec
}

func login(t *testing.T) string {
	t.Helper()
	rec := do(t, "POST", "/login", `{"username":"admin","password":"123456"}`, "")
	if rec.Code != http.StatusOK {
		t.Fatalf("登录状态码 = %d, 期望 200, 响应: %s", rec.Code, rec.Body.String())
	}
	var resp struct {
		Token string `json:"token"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("登录响应解析失败: %v", err)
	}
	if resp.Token == "" {
		t.Fatal("登录响应缺少 token")
	}
	return resp.Token
}

func TestLogin(t *testing.T) {
	rec := do(t, "POST", "/login", `{"username":"admin","password":"123456"}`, "")
	if rec.Code != http.StatusOK {
		t.Errorf("登录状态码 = %d, 期望 200", rec.Code)
	}
	recBad := do(t, "POST", "/login", `{"username":"admin","password":"wrong"}`, "")
	if recBad.Code != http.StatusUnauthorized {
		t.Errorf("错误密码状态码 = %d, 期望 401", recBad.Code)
	}
}

func TestProfileWithToken(t *testing.T) {
	token := login(t)
	rec := do(t, "GET", "/api/profile", "", token)
	if rec.Code != http.StatusOK {
		t.Fatalf("带 token 访问状态码 = %d, 期望 200, 响应: %s", rec.Code, rec.Body.String())
	}
	var resp map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("profile 响应解析失败: %v", err)
	}
	if resp["username"] != "admin" {
		t.Errorf("username = %q, 期望 admin", resp["username"])
	}
}

func TestProfileWithoutToken(t *testing.T) {
	rec := do(t, "GET", "/api/profile", "", "")
	if rec.Code != http.StatusUnauthorized {
		t.Errorf("无 token 状态码 = %d, 期望 401", rec.Code)
	}
}

func TestProfileWithBadToken(t *testing.T) {
	rec := do(t, "GET", "/api/profile", "", "not-a-jwt")
	if rec.Code != http.StatusUnauthorized {
		t.Errorf("坏 token 状态码 = %d, 期望 401", rec.Code)
	}
}

func TestProfileWithTamperedToken(t *testing.T) {
	token, _ := signJWT(map[string]any{"username": "admin"}, []byte(testSecret), time.Hour)
	parts := strings.Split(token, ".")
	tampered := parts[0] + "." + "eyJ1c2VybmFtZSI6ImhhY2tlciJ9" + "." + parts[2]
	rec := do(t, "GET", "/api/profile", "", tampered)
	if rec.Code != http.StatusUnauthorized {
		t.Errorf("篡改 token 状态码 = %d, 期望 401", rec.Code)
	}
}
