// 来源：ph07-stdlib 阶段项目 —— HTTP health check 工具命令行入口
// 一句话说明：flag 收 URL 列表/间隔/超时，周期性并发探测并输出表格报告。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go run ./cmd/healthcheck -urls "https://example.com,https://example.org" -interval 5s -timeout 2s
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"context"
	"flag"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"tenetlang/go/ph07-stdlib/project/internal/checker"
)

func main() {
	urlsFlag := flag.String("urls", "", "逗号分隔的 URL 列表（必填）")
	interval := flag.Duration("interval", 5*time.Second, "探测间隔")
	timeout := flag.Duration("timeout", 2*time.Second, "单个请求超时")
	once := flag.Bool("once", false, "只探测一轮后退出（用于脚本与自测）")
	flag.Parse()

	urls := splitURLs(*urlsFlag)
	if len(urls) == 0 {
		fmt.Fprintln(os.Stderr, "错误: -urls 不能为空（逗号分隔的 URL 列表）")
		flag.PrintDefaults()
		os.Exit(1)
	}

	// Ctrl+C 优雅退出：signal.NotifyContext 把信号转成 context 取消
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	client := &http.Client{Timeout: *timeout * 2} // 客户端兜底超时，宽松于请求级超时

	fmt.Printf("探测 %d 个 URL，间隔 %s，单请求超时 %s（Ctrl+C 退出）\n", len(urls), *interval, *timeout)
	runRound(client, urls, *timeout)
	for !*once {
		select {
		case <-ctx.Done():
			fmt.Println("\n收到退出信号，停止探测")
			return
		case <-time.After(*interval):
			runRound(client, urls, *timeout)
		}
	}
}

// splitURLs 解析逗号分隔的 URL 列表，去空格、去空项
func splitURLs(s string) []string {
	var urls []string
	for _, u := range strings.Split(s, ",") {
		if u = strings.TrimSpace(u); u != "" {
			urls = append(urls, u)
		}
	}
	return urls
}

// runRound 执行一轮探测并打印表格
func runRound(client *http.Client, urls []string, timeout time.Duration) {
	report := checker.CheckAll(context.Background(), client, urls, timeout)
	fmt.Printf("\n[%s] 合计 %d | 健康 %d | 失败 %d | 失败率 %.0f%%\n",
		report.At.Format("15:04:05"), report.Total, report.Healthy, report.Failed, report.FailureRate()*100)
	fmt.Printf("%-45s %-8s %-10s %s\n", "URL", "状态码", "延迟", "错误")
	for _, r := range report.Results {
		fmt.Printf("%-45s %-8d %-10s %s\n", truncate(r.URL, 45), r.StatusCode, r.Latency.Round(time.Millisecond), r.Err)
	}
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n-3] + "..."
}
