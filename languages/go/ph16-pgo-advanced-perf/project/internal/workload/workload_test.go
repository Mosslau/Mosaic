// 来源：ph16-pgo-advanced-perf 综合项目（internal/workload 的单元测试）
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行：go test ./internal/workload/...
// 验证状态：已验证（go1.25.6，2026-09-02）
package workload

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
)

// 起一个本地假 apiserver：返回固定 JSON，延迟 ~1ms，让压测有时间意义。
func newFakeServer(t *testing.T) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("/api/devices/", func(w http.ResponseWriter, r *http.Request) {
		// 模拟服务端一小段 CPU 工作（签名核心里 digest 的量级）
		var h uint64 = 1469598103934665603
		for i := 0; i < 2000; i++ {
			h = h*1099511628211 + uint64(i)
		}
		_ = h
		fmt.Fprintf(w, `{"id":%q,"digest":%x}`+"\n", r.URL.Path, h)
	})
	return httptest.NewServer(mux)
}

func TestRunBasic(t *testing.T) {
	srv := newFakeServer(t)
	defer srv.Close()

	s, err := Run(Config{URL: srv.URL, Total: 200, Workers: 4, Devices: 50})
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	if s.Total != 200 {
		t.Fatalf("Total = %d, want 200", s.Total)
	}
	if s.OK != 200 {
		t.Fatalf("OK = %d, want 200", s.OK)
	}
	if s.Throughput <= 0 {
		t.Fatal("Throughput 应为正")
	}
	// 延迟分位数单调性：p50 <= p95 <= p99
	if !(s.P50 <= s.P95 && s.P95 <= s.P99) {
		t.Fatalf("分位数不单调: p50=%.2f p95=%.2f p99=%.2f", s.P50, s.P95, s.P99)
	}
}

func TestRunBadConfig(t *testing.T) {
	if _, err := Run(Config{Total: 0, Workers: 1}); err == nil {
		t.Fatal("Total=0 应报错")
	}
	if _, err := Run(Config{Total: 10, Workers: 0}); err == nil {
		t.Fatal("Workers=0 应报错")
	}
}
