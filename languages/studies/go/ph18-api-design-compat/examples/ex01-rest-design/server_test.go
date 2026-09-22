// 来源：ph18-api-design-compat examples/ex01-rest-design/server_test.go
// 一句话说明：REST 方法语义的行为契约测试。每条用例都在钉一条 3.1 的纪律：
// 创建 201+Location、PUT 缺字段落零值、PATCH 只动给出的字段、DELETE 幂等 204。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...（本文件为主，另含 go vet ./...）
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func newTestServer(t *testing.T) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	s := &Server{store: NewStore()}
	s.Register(mux)
	ts := httptest.NewServer(mux)
	t.Cleanup(ts.Close)
	return ts
}

func doJSON(t *testing.T, method, url, body string) (*http.Response, map[string]any) {
	t.Helper()
	var rd io.Reader
	if body != "" {
		rd = strings.NewReader(body)
	}
	req, err := http.NewRequest(method, url, rd)
	if err != nil {
		t.Fatal(err)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	out := map[string]any{}
	if len(data) > 0 {
		_ = json.Unmarshal(data, &out)
	}
	return resp, out
}

func createOne(t *testing.T, base string) string {
	t.Helper()
	resp, body := doJSON(t, http.MethodPost, base+"/v1/devices", `{"name":"ecu-a"}`)
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create status = %d, want 201, body=%v", resp.StatusCode, body)
	}
	id, _ := body["id"].(string)
	if id == "" {
		t.Fatal("created device has no id")
	}
	if loc := resp.Header.Get("Location"); !strings.HasSuffix(loc, "/v1/devices/"+id) {
		t.Fatalf("Location = %q, want suffix /v1/devices/%s", loc, id)
	}
	return id
}

// TestCreateGet：创建 201 + Location，随后可 GET 到，ID 由服务端分配。
func TestCreateGet(t *testing.T) {
	ts := newTestServer(t)
	id := createOne(t, ts.URL)

	resp, body := doJSON(t, http.MethodGet, ts.URL+"/v1/devices/"+id, "")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("get status = %d, want 200", resp.StatusCode)
	}
	if body["name"] != "ecu-a" {
		t.Fatalf("name = %v, want ecu-a", body["name"])
	}
	if body["online"] != false {
		t.Fatalf("online = %v, want false", body["online"])
	}
}

// TestReplaceIsFullReplacement：PUT 缺字段落零值——没传 online 就变成 false。
func TestReplaceIsFullReplacement(t *testing.T) {
	ts := newTestServer(t)
	id := createOne(t, ts.URL)

	// 先 PATCH 上线，制造一个 online=true 的当前状态
	if resp, _ := doJSON(t, http.MethodPatch, ts.URL+"/v1/devices/"+id, `{"online":true}`); resp.StatusCode != http.StatusOK {
		t.Fatalf("patch status = %d, want 200", resp.StatusCode)
	}
	// PUT 只带 name：online 必须被重置为 false（全量替换，与 PATCH 相反）
	resp, body := doJSON(t, http.MethodPut, ts.URL+"/v1/devices/"+id, `{"name":"ecu-b"}`)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("put status = %d, want 200", resp.StatusCode)
	}
	if body["name"] != "ecu-b" || body["online"] != false {
		t.Fatalf("after PUT body=%v, want name=ecu-b online=false", body)
	}
}

// TestPatchOnlyTouchesGivenFields：PATCH 只更新给出的字段，其余保留。
func TestPatchOnlyTouchesGivenFields(t *testing.T) {
	ts := newTestServer(t)
	id := createOne(t, ts.URL)

	if resp, _ := doJSON(t, http.MethodPatch, ts.URL+"/v1/devices/"+id, `{"online":true}`); resp.StatusCode != http.StatusOK {
		t.Fatalf("patch online status = %d, want 200", resp.StatusCode)
	}
	resp, body := doJSON(t, http.MethodPatch, ts.URL+"/v1/devices/"+id, `{"name":"ecu-c"}`)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("patch name status = %d, want 200", resp.StatusCode)
	}
	// online 未被这次 PATCH 触碰，仍是 true
	if body["name"] != "ecu-c" || body["online"] != true {
		t.Fatalf("after PATCH name only body=%v, want name=ecu-c online=true", body)
	}
}

// TestDeleteIsIdempotent：DELETE 一次 204，第二次（资源已不存在）仍 204。
func TestDeleteIsIdempotent(t *testing.T) {
	ts := newTestServer(t)
	id := createOne(t, ts.URL)

	for i := 0; i < 2; i++ {
		req, _ := http.NewRequest(http.MethodDelete, ts.URL+"/v1/devices/"+id, nil)
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		resp.Body.Close()
		if resp.StatusCode != http.StatusNoContent {
			t.Fatalf("delete round %d status = %d, want 204", i+1, resp.StatusCode)
		}
	}
}

// TestInvalidBodyIs400：坏 JSON 与空 name 都回 400 + 统一 {code,message} 结构。
func TestInvalidBodyIs400(t *testing.T) {
	ts := newTestServer(t)

	resp, body := doJSON(t, http.MethodPost, ts.URL+"/v1/devices", `{not json`)
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("bad json status = %d, want 400", resp.StatusCode)
	}
	if body["code"] != "BAD_REQUEST" {
		t.Fatalf("code = %v, want BAD_REQUEST", body["code"])
	}

	resp, body = doJSON(t, http.MethodPost, ts.URL+"/v1/devices", `{"name":"   "}`)
	if resp.StatusCode != http.StatusBadRequest || body["code"] != "BAD_REQUEST" {
		t.Fatalf("blank name status/code = %d/%v, want 400/BAD_REQUEST", resp.StatusCode, body["code"])
	}
}

// TestUnknownIDIs404：GET 不存在的设备 → 404 + DEVICE_NOT_FOUND。
func TestUnknownIDIs404(t *testing.T) {
	ts := newTestServer(t)
	resp, body := doJSON(t, http.MethodGet, ts.URL+"/v1/devices/nope", "")
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", resp.StatusCode)
	}
	if body["code"] != "DEVICE_NOT_FOUND" {
		t.Fatalf("code = %v, want DEVICE_NOT_FOUND", body["code"])
	}
}

// TestPostIsNotIdempotent：POST 同一个 body 两次得到两个不同资源——这正是幂等接口
// 设计（PUT/DELETE）与非幂等接口（POST）的差别，也是 roadmap 必会概念 3 的起点。
func TestPostIsNotIdempotent(t *testing.T) {
	ts := newTestServer(t)
	body := `{"name":"dupe"}`
	r1, b1 := doJSON(t, http.MethodPost, ts.URL+"/v1/devices", body)
	r2, b2 := doJSON(t, http.MethodPost, ts.URL+"/v1/devices", body)
	if r1.StatusCode != http.StatusCreated || r2.StatusCode != http.StatusCreated {
		t.Fatalf("create statuses = %d,%d", r1.StatusCode, r2.StatusCode)
	}
	if b1["id"] == b2["id"] {
		t.Fatalf("two POST with same body got same id %v — POST 应为非幂等", b1["id"])
	}
}
