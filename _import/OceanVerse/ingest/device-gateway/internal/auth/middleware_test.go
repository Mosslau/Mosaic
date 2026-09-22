package auth

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// okHandler 下游占位 handler, 被调用即 200
var okHandler = http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
})

// identityHandler 把解析到的身份写回响应头, 便于断言"认证之外还解析出了哪辆车"。
var identityHandler = http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
	id, ok := FromContext(r.Context())
	if !ok {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	w.Header().Set("X-Identity-VIN", id.VIN)
	w.WriteHeader(http.StatusOK)
})

func TestAuth_WhiteList(t *testing.T) {
	mw := New(map[string]string{"token-a": "OV00000001", "token-b": "OV00000002"}, false)
	h := mw.Wrap(okHandler)

	cases := []struct {
		name   string
		token  string
		expect int
	}{
		{"白名单 token-a", "token-a", http.StatusOK},
		{"白名单 token-b", "token-b", http.StatusOK},
		{"不在白名单", "token-x", http.StatusUnauthorized},
		{"空 token", "", http.StatusUnauthorized},
		{"dev- 前缀但非 dev 模式", "dev-OV00000009", http.StatusUnauthorized},
	}
	for _, c := range cases {
		r := httptest.NewRequest(http.MethodPost, "/api/v1/vehicle/report", nil)
		r.Header.Set(TokenHeader, c.token)
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		if w.Code != c.expect {
			t.Errorf("%s: 期望 %d, 实际 %d", c.name, c.expect, w.Code)
		}
	}
}

// TestAuth_ResolvesBoundVIN 绑定 token 必须解析出**绑定的 VIN**(身份),
// 这是 report handler 能校验"载荷 VIN == 设备身份"的前提。
func TestAuth_ResolvesBoundVIN(t *testing.T) {
	mw := New(map[string]string{"token-a": "OV00000001"}, false)
	h := mw.Wrap(identityHandler)

	r := httptest.NewRequest(http.MethodPost, "/", nil)
	r.Header.Set(TokenHeader, "token-a")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)

	if got := w.Header().Get("X-Identity-VIN"); got != "OV00000001" {
		t.Errorf("身份 VIN 应为 OV00000001, 实际 %q", got)
	}
}

func TestAuth_DevMode(t *testing.T) {
	mw := New(nil, true) // dev 模式, 空白名单
	h := mw.Wrap(identityHandler)

	// dev-{VIN} 放行, 且身份 VIN 取自 token 后缀
	r := httptest.NewRequest(http.MethodPost, "/", nil)
	r.Header.Set(TokenHeader, "dev-OV00000001")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != http.StatusOK {
		t.Fatalf("dev 模式应放行 dev-{VIN}, 实际 %d", w.Code)
	}
	if got := w.Header().Get("X-Identity-VIN"); got != "OV00000001" {
		t.Errorf("dev 模式身份 VIN 应取自 token 后缀 OV00000001, 实际 %q", got)
	}

	// 非 dev- 前缀且不在白名单 → 拒绝
	r = httptest.NewRequest(http.MethodPost, "/", nil)
	r.Header.Set(TokenHeader, "prod-token")
	w = httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != http.StatusUnauthorized {
		t.Errorf("dev 模式下非 dev- 前缀应拒绝, 实际 %d", w.Code)
	}

	// "dev-" 后为空 → 推断不出 VIN, 必须拒绝(旧实现会说它"是 dev- 前缀"就放行)
	r = httptest.NewRequest(http.MethodPost, "/", nil)
	r.Header.Set(TokenHeader, "dev-")
	w = httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != http.StatusUnauthorized {
		t.Errorf("dev- 后缀为空应拒绝, 实际 %d", w.Code)
	}
}
