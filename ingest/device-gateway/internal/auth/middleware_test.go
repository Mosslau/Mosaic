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

func TestAuth_WhiteList(t *testing.T) {
	mw := New([]string{"token-a", "token-b"}, false)
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
		{"dev- 前缀但非 dev 模式", "dev-anything", http.StatusUnauthorized},
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

func TestAuth_DevMode(t *testing.T) {
	mw := New(nil, true) // dev 模式, 空白名单
	h := mw.Wrap(okHandler)

	// dev- 前缀放行
	r := httptest.NewRequest(http.MethodPost, "/", nil)
	r.Header.Set(TokenHeader, "dev-OV00000001")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != http.StatusOK {
		t.Errorf("dev 模式应放行 dev- 前缀, 实际 %d", w.Code)
	}

	// 非 dev- 前缀仍拒绝
	r = httptest.NewRequest(http.MethodPost, "/", nil)
	r.Header.Set(TokenHeader, "prod-token")
	w = httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != http.StatusUnauthorized {
		t.Errorf("dev 模式下非 dev- 前缀应拒绝, 实际 %d", w.Code)
	}
}
