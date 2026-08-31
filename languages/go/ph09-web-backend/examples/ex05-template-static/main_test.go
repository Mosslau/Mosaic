// 来源：09-web-backend.md 第 6 章示例 5 —— 模板渲染 + 静态文件
// 一句话说明：模板转义（XSS 防御）验证 + 表单 POST 校验 + 静态文件服务 + 303 重定向。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
)

func do(t *testing.T, h http.Handler, method, path string, form url.Values) *httptest.ResponseRecorder {
	t.Helper()
	var req *http.Request
	if form != nil {
		req = httptest.NewRequest(method, path, strings.NewReader(form.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	} else {
		req = httptest.NewRequest(method, path, nil)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

// TestTemplateEscapesXSS 模板自动转义：设备名含 <script> 时输出被转义，不会原样进 HTML
func TestTemplateEscapesXSS(t *testing.T) {
	s := newStore()
	s.mu.Lock()
	s.items["evil"] = Device{ID: "<script>alert(1)</script>", Status: "online", Speed: 1}
	s.mu.Unlock()

	rec := do(t, newMux(s), "GET", "/devices", nil)
	if rec.Code != http.StatusOK {
		t.Fatalf("状态码 = %d, 期望 200", rec.Code)
	}
	body := rec.Body.String()
	if strings.Contains(body, "<script>alert(1)</script>") {
		t.Error("模板未转义 <script>，存在 XSS 风险")
	}
	// html/template 会把 < 转成 &lt;、> 转成 &gt;
	if !strings.Contains(body, "&lt;script&gt;") {
		t.Errorf("期望转义后的 &lt;script&gt;, 实际响应: %s", body)
	}
	// 正常设备应渲染出来
	if !strings.Contains(body, "car-001") {
		t.Error("列表应包含种子设备 car-001")
	}
}

// TestFormCreateThenRedirect 表单 POST：成功 303 重定向回列表页
func TestFormCreateThenRedirect(t *testing.T) {
	h := newMux(newStore())
	rec := do(t, h, "POST", "/devices", url.Values{
		"device_id": {"car-009"},
		"status":    {"online"},
		"speed":     {"88.5"},
	})
	if rec.Code != http.StatusSeeOther {
		t.Errorf("状态码 = %d, 期望 303", rec.Code)
	}
	if loc := rec.Header().Get("Location"); loc != "/devices" {
		t.Errorf("Location = %q, 期望 /devices", loc)
	}
}

// TestFormValidation 表单校验：非法 speed / 空 id / 非法 status 均 400
func TestFormValidation(t *testing.T) {
	h := newMux(newStore())
	cases := []url.Values{
		{"device_id": {"car-x"}, "status": {"online"}, "speed": {"-5"}},  // 速度为负
		{"device_id": {"car-x"}, "status": {"online"}, "speed": {"abc"}}, // 速度非数字
		{"device_id": {""}, "status": {"online"}, "speed": {"1"}},        // 空 id
		{"device_id": {"car-x"}, "status": {"broken"}, "speed": {"1"}},   // 非法状态
	}
	for _, form := range cases {
		rec := do(t, h, "POST", "/devices", form)
		if rec.Code != http.StatusBadRequest {
			t.Errorf("表单 %v 状态码 = %d, 期望 400", form, rec.Code)
		}
	}
}

// TestStaticFile 静态文件：/static/style.css 返回文件内容且 Content-Type 正确
func TestStaticFile(t *testing.T) {
	rec := do(t, newMux(newStore()), "GET", "/static/style.css", nil)
	if rec.Code != http.StatusOK {
		t.Fatalf("状态码 = %d, 期望 200", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); !strings.HasPrefix(ct, "text/css") {
		t.Errorf("Content-Type = %q, 期望 text/css 开头", ct)
	}
	if !strings.Contains(rec.Body.String(), "font-family") {
		t.Error("CSS 内容未返回")
	}
}

// TestStaticMissing 静态文件不存在：404
func TestStaticMissing(t *testing.T) {
	rec := do(t, newMux(newStore()), "GET", "/static/nope.css", nil)
	if rec.Code != http.StatusNotFound {
		t.Errorf("状态码 = %d, 期望 404", rec.Code)
	}
}
