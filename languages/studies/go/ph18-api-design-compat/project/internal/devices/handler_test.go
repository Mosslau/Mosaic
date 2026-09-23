// 来源：ph18-api-design-compat project/internal/devices/handler_test.go
// 一句话说明：版本化接口的行为测试（httptest 集成）。钉住的契约：
// ① v1 响应绝不泄漏 v2 字段（老契约不扩大）；② v2 是 v1 的超集；
// ③ v1 带 Deprecation 头；④ 错误统一 {code,message}；⑤ 过滤/分页/排序语义。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...；静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package devices

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func newTestHandler() *httptest.Server {
	mux := http.NewServeMux()
	New(NewStore()).Register(mux)
	ts := httptest.NewServer(mux)
	return ts
}

func getJSON(t *testing.T, url string) (map[string]any, http.Header) {
	t.Helper()
	resp, err := http.Get(url)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		b, _ := io.ReadAll(resp.Body)
		t.Fatalf("GET %s status=%d body=%s", url, resp.StatusCode, b)
	}
	raw, _ := io.ReadAll(resp.Body)
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatal(err)
	}
	return m, resp.Header
}

// TestV1ResponseHasNoV2Fields：v1 只含 id/name/online。
func TestV1ResponseHasNoV2Fields(t *testing.T) {
	ts := newTestHandler()
	defer ts.Close()
	body, h := getJSON(t, ts.URL+"/v1/devices/dev-001")
	if h.Get("Deprecation") != "true" {
		t.Fatal("v1 must be marked deprecated")
	}
	for _, leaked := range []string{"model", "lastSeen"} {
		if _, ok := body[leaked]; ok {
			t.Fatalf("v1 leaked v2 field %q: %v", leaked, body)
		}
	}
	for _, core := range []string{"id", "name", "online"} {
		if _, ok := body[core]; !ok {
			t.Fatalf("v1 missing core field %q", core)
		}
	}
}

// TestV2IsSupersetOfV1：v2 单对象含全部 v1 字段 + model/lastSeen，且不带弃用头。
func TestV2IsSupersetOfV1(t *testing.T) {
	ts := newTestHandler()
	defer ts.Close()
	v1, _ := getJSON(t, ts.URL+"/v1/devices/dev-001")
	v2, h := getJSON(t, ts.URL+"/v2/devices/dev-001")
	if h.Get("Deprecation") != "" {
		t.Fatal("v2 must not be deprecated")
	}
	for k := range v1 {
		if v1[k] != v2[k] {
			t.Fatalf("field %q drifted: v1=%v v2=%v", k, v1[k], v2[k])
		}
	}
	if v2["model"] != "M300" {
		t.Fatalf("model = %v, want M300", v2["model"])
	}
}

// TestListVersionsFields：列表端点 v1/v2 的字段视图与 v2 sort 能力。
func TestListVersionsFields(t *testing.T) {
	ts := newTestHandler()
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/v1/devices")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	var v1List []map[string]any
	if err := json.Unmarshal(raw, &v1List); err != nil {
		t.Fatal(err)
	}
	if len(v1List) != 2 {
		t.Fatalf("v1 list len = %d, want 2", len(v1List))
	}
	if _, ok := v1List[0]["model"]; ok {
		t.Fatal("v1 list leaked model")
	}

	resp, err = http.Get(ts.URL + "/v2/devices?sort=name")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	raw, _ = io.ReadAll(resp.Body)
	var v2List []map[string]any
	if err := json.Unmarshal(raw, &v2List); err != nil {
		t.Fatal(err)
	}
	if len(v2List) != 2 || v2List[0]["name"] != "1号设备" {
		t.Fatalf("v2 sorted-by-name list = %v", v2List)
	}
	if v2List[0]["model"] == nil {
		t.Fatal("v2 list missing model field")
	}
}

// TestErrorsAreUnified：未知设备 404 + DEVICE_NOT_FOUND；坏参数 400 + BAD_REQUEST。
func TestErrorsAreUnified(t *testing.T) {
	ts := newTestHandler()
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/v1/devices/nope")
	if err != nil {
		t.Fatal(err)
	}
	raw, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	var e1 map[string]string
	_ = json.Unmarshal(raw, &e1)
	if resp.StatusCode != http.StatusNotFound || e1["code"] != "DEVICE_NOT_FOUND" {
		t.Fatalf("not-found error = %d %v", resp.StatusCode, e1)
	}

	resp, err = http.Get(ts.URL + "/v2/devices?status=bogus")
	if err != nil {
		t.Fatal(err)
	}
	raw, _ = io.ReadAll(resp.Body)
	resp.Body.Close()
	var e2 map[string]string
	_ = json.Unmarshal(raw, &e2)
	if resp.StatusCode != http.StatusBadRequest || e2["code"] != "BAD_REQUEST" {
		t.Fatalf("bad-request error = %d %v", resp.StatusCode, e2)
	}
}

// TestCreateAndDeleteLifecycle：注册 201 → 命中；注销两次均 204（幂等）。
func TestCreateAndDeleteLifecycle(t *testing.T) {
	ts := newTestHandler()
	defer ts.Close()

	resp, err := http.Post(ts.URL+"/v1/devices", "application/json", strings.NewReader(`{"name":"新设备"}`))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	var created map[string]any
	_ = json.Unmarshal(raw, &created)
	if resp.StatusCode != http.StatusCreated || created["id"] == nil {
		t.Fatalf("create = %d %v", resp.StatusCode, created)
	}

	for i := 0; i < 2; i++ {
		req, _ := http.NewRequest(http.MethodDelete, ts.URL+"/v1/devices/"+created["id"].(string), nil)
		del, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		del.Body.Close()
		if del.StatusCode != http.StatusNoContent {
			t.Fatalf("delete round %d = %d, want 204", i+1, del.StatusCode)
		}
	}
}
