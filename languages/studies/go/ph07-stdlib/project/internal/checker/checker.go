// 来源：ph07-stdlib 阶段项目 —— HTTP health check 工具核心
// 一句话说明：并发探测多个 URL，context 超时控制，统计状态码/延迟/失败率。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go test -v ./internal/checker
//
// 验证状态：已验证（Go 1.22.2）
package checker

import (
	"context"
	"fmt"
	"net/http"
	"sort"
	"sync"
	"time"
)

// Result 单个 URL 的一次探测结果
type Result struct {
	URL        string        `json:"url"`
	StatusCode int           `json:"status_code"` // 0 表示请求未建立（网络错误/超时）
	Latency    time.Duration `json:"latency"`
	Err        string        `json:"error,omitempty"`
}

// OK 判定：2xx/3xx 视为健康
func (r Result) OK() bool {
	return r.Err == "" && r.StatusCode >= 200 && r.StatusCode < 400
}

// Report 一次全量探测的汇总报告
type Report struct {
	At      time.Time `json:"at"`
	Results []Result  `json:"results"`
	Total   int       `json:"total"`
	Healthy int       `json:"healthy"`
	Failed  int       `json:"failed"`
}

// FailureRate 失败率（0~1）；Total 为 0 时返回 0
func (r Report) FailureRate() float64 {
	if r.Total == 0 {
		return 0
	}
	return float64(r.Failed) / float64(r.Total)
}

// Check 探测单个 URL：请求级 context 超时 + 计时
func Check(ctx context.Context, client *http.Client, url string) Result {
	start := time.Now()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return Result{URL: url, Err: fmt.Sprintf("构造请求: %v", err)}
	}
	resp, err := client.Do(req)
	if err != nil {
		return Result{URL: url, Latency: time.Since(start), Err: err.Error()}
	}
	defer resp.Body.Close()
	// 健康检查只关心状态码与延迟，不读 body；直接 Close 释放连接
	return Result{URL: url, StatusCode: resp.StatusCode, Latency: time.Since(start)}
}

// CheckAll 并发探测全部 URL，每个请求带独立超时；结果按 URL 排序保证输出稳定
func CheckAll(ctx context.Context, client *http.Client, urls []string, timeout time.Duration) Report {
	results := make([]Result, len(urls))
	var wg sync.WaitGroup
	for i, url := range urls {
		wg.Add(1)
		go func(i int, url string) {
			defer wg.Done()
			reqCtx, cancel := context.WithTimeout(ctx, timeout) // 每个请求独立超时
			defer cancel()
			results[i] = Check(reqCtx, client, url) // 各写各的槽位，无共享写冲突
		}(i, url)
	}
	wg.Wait()

	report := Report{At: time.Now(), Results: results, Total: len(results)}
	for _, r := range results {
		if r.OK() {
			report.Healthy++
		} else {
			report.Failed++
		}
	}
	sort.Slice(report.Results, func(i, j int) bool {
		return report.Results[i].URL < report.Results[j].URL
	})
	return report
}
