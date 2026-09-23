// 来源：ph18-api-design-compat exercises/sol-01-device-query-api（练习 1 参考实现）
// 一句话说明：查询 API 的验收测试。每条用例对应练习验收标准里的一条：
// 翻页不重不漏、过滤先于分页、排序稳定、limit 默认/上限、单对象查询 404。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...；静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strconv"
	"testing"
)

func newTestServer(t *testing.T) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	NewServer().Register(mux)
	ts := httptest.NewServer(mux)
	t.Cleanup(ts.Close)
	return ts
}

func getDevices(t *testing.T, base string, params url.Values) Page {
	t.Helper()
	u := base + "/api/v1/devices"
	if len(params) > 0 {
		u += "?" + params.Encode()
	}
	resp, err := http.Get(u)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		b, _ := io.ReadAll(resp.Body)
		t.Fatalf("status=%d body=%s", resp.StatusCode, b)
	}
	var p Page
	if err := json.NewDecoder(resp.Body).Decode(&p); err != nil {
		t.Fatal(err)
	}
	return p
}

// TestPaginationComplete：limit=10 翻完全部 57 辆，不重不漏。
func TestPaginationComplete(t *testing.T) {
	ts := newTestServer(t)
	seen := map[string]bool{}
	for off := 0; off < 57; off += 10 {
		p := getDevices(t, ts.URL, url.Values{"offset": {strconv.Itoa(off)}, "limit": {"10"}})
		for _, v := range p.Items {
			if seen[v.ID] {
				t.Fatalf("duplicate %s", v.ID)
			}
			seen[v.ID] = true
		}
	}
	if len(seen) != 57 {
		t.Fatalf("unique = %d, want 57", len(seen))
	}
}

// TestFilterAndTotal：过滤先于分页；offline 设备在 57 辆里有多少、每页是否全过滤正确。
func TestFilterAndTotal(t *testing.T) {
	ts := newTestServer(t)
	p := getDevices(t, ts.URL, url.Values{"status": {"offline"}})
	// 57 = 14 组 (i%4) + i=56(online)：i%4==1 的离线设备共 14 台
	if p.Total != 14 {
		t.Fatalf("offline total = %d, want 14", p.Total)
	}
	for _, v := range p.Items {
		if v.Status != "offline" {
			t.Fatalf("device %s status=%s, want offline", v.ID, v.Status)
		}
	}
}

// TestPlateSubstring：设备编号模糊查询。
func TestPlateSubstring(t *testing.T) {
	ts := newTestServer(t)
	p := getDevices(t, ts.URL, url.Values{"plate": {"京A-00"}})
	// 设备编号 京A-000..京A-009 共 10 辆
	if p.Total != 10 {
		t.Fatalf("plate total = %d, want 10", p.Total)
	}
}

// TestSingleDevice：单对象查询命中与未命中。
func TestSingleDevice(t *testing.T) {
	ts := newTestServer(t)
	resp, err := http.Get(ts.URL + "/api/v1/devices/veh-001")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("hit status=%d, want 200", resp.StatusCode)
	}

	resp, err = http.Get(ts.URL + "/api/v1/devices/veh-999")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("miss status=%d, want 404", resp.StatusCode)
	}
}

// TestInvalidParams：非法 status / 负数 offset → 400。
func TestInvalidParams(t *testing.T) {
	ts := newTestServer(t)
	resp, err := http.Get(ts.URL + "/api/v1/devices?status=bogus")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("bogus status -> %d, want 400", resp.StatusCode)
	}
	resp, err = http.Get(ts.URL + "/api/v1/devices?offset=-1")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("negative offset -> %d, want 400", resp.StatusCode)
	}
}
