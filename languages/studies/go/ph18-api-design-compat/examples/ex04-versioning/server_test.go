// 来源：ph18-api-design-compat examples/ex04-versioning/server_test.go
// 一句话说明：版本共存的契约测试。断言三条版本纪律：
// ① v1 响应绝不包含 v2 新字段（老版本契约不扩大）；② v2 响应是 v1 的超集（字段只增不删）；
// ③ v1 响应带 Deprecation 头（弃用要显式通告，不能悄悄下线）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...（本文件为主）；静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

func newTestServer(t *testing.T) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	s := NewServer()
	s.store.Seed()
	s.Register(mux)
	ts := httptest.NewServer(mux)
	t.Cleanup(ts.Close)
	return ts
}

func getBody(t *testing.T, url string) (map[string]any, http.Header) {
	t.Helper()
	resp, err := http.Get(url)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d body=%s", resp.StatusCode, raw)
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatal(err)
	}
	return m, resp.Header
}

// TestV1ResponseHasNoV2Fields：v1 是老契约，v2 的新字段一个都不能漏进 v1。
// "v1 响应突然多了字段"与"少了字段"一样都是破坏性变更——客户端可能把
// 未知字段当错误处理，也可能依赖字段集合做校验（主文档 3.3/3.6）。
func TestV1ResponseHasNoV2Fields(t *testing.T) {
	ts := newTestServer(t)
	body, _ := getBody(t, ts.URL+"/v1/devices/car-001")
	for _, leaked := range []string{"model", "lastSeen"} {
		if _, ok := body[leaked]; ok {
			t.Fatalf("v1 response leaked v2 field %q: %v", leaked, body)
		}
	}
	for _, core := range []string{"id", "name", "online"} {
		if _, ok := body[core]; !ok {
			t.Fatalf("v1 response missing core field %q: %v", core, body)
		}
	}
}

// TestV2ResponseIsSupersetOfV1：v2 必须包含 v1 的全部字段（超集原则）。
func TestV2ResponseIsSupersetOfV1(t *testing.T) {
	ts := newTestServer(t)
	v1, _ := getBody(t, ts.URL+"/v1/devices/car-001")
	v2, _ := getBody(t, ts.URL+"/v2/devices/car-001")
	for k := range v1 {
		if _, ok := v2[k]; !ok {
			t.Fatalf("v2 response missing v1 field %q: %v", k, v2)
		}
		if v1[k] != v2[k] {
			t.Fatalf("field %q drifted between versions: v1=%v v2=%v", k, v1[k], v2[k])
		}
	}
	if v2["model"] != "M300" {
		t.Fatalf("v2 model = %v, want M300", v2["model"])
	}
}

// TestV1SendsDeprecationHeader：v1 命中时带 Deprecation: true 与 Sunset 期限。
func TestV1SendsDeprecationHeader(t *testing.T) {
	ts := newTestServer(t)
	_, h := getBody(t, ts.URL+"/v1/devices/car-001")
	if h.Get("Deprecation") != "true" {
		t.Fatalf("Deprecation = %q, want true", h.Get("Deprecation"))
	}
	if h.Get("Sunset") == "" {
		t.Fatal("Sunset header missing on deprecated v1")
	}
}

// TestV2HasNoDeprecationHeader：v2 是当前版本，不带弃用通告。
func TestV2HasNoDeprecationHeader(t *testing.T) {
	ts := newTestServer(t)
	_, h := getBody(t, ts.URL+"/v2/devices/car-001")
	if h.Get("Deprecation") != "" {
		t.Fatalf("v2 unexpectedly deprecated: %q", h.Get("Deprecation"))
	}
}
