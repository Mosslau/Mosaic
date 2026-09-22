// 来源：ph07-stdlib 阶段项目自测 —— checker 包单元测试
// 一句话说明：httptest 模拟快/慢/失败三种端点，验证并发探测、超时与统计口径。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go test -v ./internal/checker
//
// 验证状态：已验证（Go 1.22.2）
package checker

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestCheckAll(t *testing.T) {
	fast := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer fast.Close()

	slow := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(500 * time.Millisecond) // 故意慢于超时阈值
		w.WriteHeader(http.StatusOK)
	}))
	defer slow.Close()

	broken := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer broken.Close()

	urls := []string{fast.URL, slow.URL, broken.URL, "http://127.0.0.1:1/unreachable"}
	report := CheckAll(context.Background(), http.DefaultClient, urls, 100*time.Millisecond)

	if report.Total != 4 {
		t.Fatalf("Total = %d, 期望 4", report.Total)
	}
	if report.Healthy != 1 {
		t.Errorf("Healthy = %d, 期望 1（只有 fast）", report.Healthy)
	}
	if report.Failed != 3 {
		t.Errorf("Failed = %d, 期望 3（slow 超时 / broken 500 / unreachable）", report.Failed)
	}
	if rate := report.FailureRate(); rate != 0.75 {
		t.Errorf("FailureRate = %v, 期望 0.75", rate)
	}

	// 结果按 URL 排序，输出稳定
	for i := 1; i < len(report.Results); i++ {
		if report.Results[i-1].URL > report.Results[i].URL {
			t.Errorf("结果未按 URL 排序: %q > %q", report.Results[i-1].URL, report.Results[i].URL)
		}
	}
}

func TestCheckRespectsTimeout(t *testing.T) {
	slow := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(2 * time.Second)
	}))
	defer slow.Close()

	start := time.Now()
	report := CheckAll(context.Background(), http.DefaultClient, []string{slow.URL}, 100*time.Millisecond)
	elapsed := time.Since(start)

	if elapsed > 1*time.Second {
		t.Errorf("超时控制失效：耗时 %v 远超 100ms 超时", elapsed)
	}
	if report.Results[0].Err == "" {
		t.Error("慢端点应产生超时错误, 实际成功")
	}
}

func TestResultOK(t *testing.T) {
	cases := []struct {
		name string
		r    Result
		want bool
	}{
		{"200 健康", Result{StatusCode: 200}, true},
		{"301 重定向健康", Result{StatusCode: 301}, true},
		{"500 不健康", Result{StatusCode: 500}, false},
		{"网络错误不健康", Result{Err: "timeout"}, false},
		{"0 状态码不健康", Result{}, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := tc.r.OK(); got != tc.want {
				t.Errorf("OK() = %v, 期望 %v", got, tc.want)
			}
		})
	}
}
