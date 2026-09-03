// 来源：ph18-api-design-compat examples/ex03-pagination-filter/server_test.go
// 一句话说明：分页/过滤/排序的稳定性测试。重点验证"翻页不重不漏"与"排序稳定"——
// 这两条是列表接口最容易在演进中悄悄破坏的契约（主文档 3.5 的验收点）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...（本文件为主）；静态检查：go vet ./...
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

// getPage 请求一页并解码 Page。
func getPage(t *testing.T, base string, params url.Values) Page {
	t.Helper()
	u := base + "/v1/devices"
	if len(params) > 0 {
		u += "?" + params.Encode()
	}
	resp, err := http.Get(u)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		t.Fatalf("status = %d, body=%s", resp.StatusCode, body)
	}
	var p Page
	if err := json.NewDecoder(resp.Body).Decode(&p); err != nil {
		t.Fatal(err)
	}
	return p
}

// TestPaginationNoDuplicatesNoGaps：用 limit=20 把 103 条全部翻完，
// 断言并集恰好等于全集（不重不漏）——这是 offset 分页最核心的稳定性承诺。
func TestPaginationNoDuplicatesNoGaps(t *testing.T) {
	ts := newTestServer(t)
	seen := map[string]bool{}
	total := -1
	for off := 0; ; off += 20 {
		p := getPage(t, ts.URL, url.Values{"offset": {strconv.Itoa(off)}})
		if total == -1 {
			total = p.Total
		}
		if p.Total != total {
			t.Fatalf("total changed across pages: %d then %d", total, p.Total)
		}
		for _, d := range p.Items {
			if seen[d.ID] {
				t.Fatalf("duplicate id %s across pages", d.ID)
			}
			seen[d.ID] = true
		}
		if len(p.Items) < 20 {
			break // 最后一页
		}
	}
	if total != 103 || len(seen) != 103 {
		t.Fatalf("want 103 unique items, got total=%d unique=%d", total, len(seen))
	}
}

// TestFilterBeforePagination：过滤先于分页——total 是"过滤后的总数"。
func TestFilterBeforePagination(t *testing.T) {
	ts := newTestServer(t)
	p := getPage(t, ts.URL, url.Values{"status": {"offline"}})
	// 103 条里 i%3==1 的离线，即 34 条
	if p.Total != 34 {
		t.Fatalf("offline total = %d, want 34", p.Total)
	}
	if len(p.Items) > p.Total {
		t.Fatalf("page items %d exceed filtered total %d", len(p.Items), p.Total)
	}
	for _, d := range p.Items {
		if d.Status != "offline" {
			t.Fatalf("item %s status = %q, want offline", d.ID, d.Status)
		}
	}
}

// TestQMatchesNameSubstring：模糊过滤作用于 name。
func TestQMatchesNameSubstring(t *testing.T) {
	ts := newTestServer(t)
	p := getPage(t, ts.URL, url.Values{"q": {"车队A-10"}})
	// name 含子串 "车队A-10" 的共有 4 条：10 号车与 100/101/102 号车
	if p.Total != 4 {
		t.Fatalf("q total = %d, want 4", p.Total)
	}
}

// TestSortStableWithIDTiebreak：按 status 排序时同 status 内部按 id 升序——
// 排序契约里"同值有确定次序"才能让翻页稳定。
func TestSortStableWithIDTiebreak(t *testing.T) {
	ts := newTestServer(t)
	p := getPage(t, ts.URL, url.Values{"status": {"maintenance"}, "sort": {"status"}})
	if p.Total == 0 {
		t.Fatal("expected maintenance devices")
	}
	for i := 1; i < len(p.Items); i++ {
		if p.Items[i].ID < p.Items[i-1].ID {
			t.Fatalf("same-status page not ordered by id: %s before %s", p.Items[i].ID, p.Items[i-1].ID)
		}
	}
}

// TestUnknownSortFallsBackToID：非白名单排序字段回退默认（id），不报错——
// 排序能力不是无限承诺，白名单外字段回退默认比 400 更稳（契约不扩大）。
func TestUnknownSortFallsBackToID(t *testing.T) {
	ts := newTestServer(t)
	p := getPage(t, ts.URL, url.Values{"sort": {"hack"}})
	if len(p.Items) == 0 {
		t.Fatal("expected items")
	}
	if p.Items[0].ID != "dev-000" {
		t.Fatalf("first item = %s, want dev-000 (default id order)", p.Items[0].ID)
	}
}

// TestLimitCappedAndDefaulted：limit 缺省 = 20，超过 100 被截断到 100。
func TestLimitCappedAndDefaulted(t *testing.T) {
	ts := newTestServer(t)
	def := getPage(t, ts.URL, url.Values{})
	if len(def.Items) != 20 {
		t.Fatalf("default page items = %d, want 20", len(def.Items))
	}
	huge := getPage(t, ts.URL, url.Values{"limit": {"999"}})
	if len(huge.Items) != 100 || huge.Limit != 100 {
		t.Fatalf("capped limit page items/limit = %d/%d, want 100/100", len(huge.Items), huge.Limit)
	}
}
