// 来源：06-concurrency.md 第 7 章「动手练习」练习 2 —— 并发爬虫
// 一句话说明：worker pool 并发抓取 URL 列表（假 fetcher 模拟网络延迟），每条带超时，fan-in 汇总成功与失败。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd exercises/sol-02-concurrent-crawler && go run .
//
// 验证状态：已验证（Go 1.22.2，含 go run -race 无竞争）
package main

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// page 是一次抓取的结果：url 标识来源，title 是抓到的标题，err 是失败原因（nil 表示成功）。
type page struct {
	url   string
	title string
	err   error
}

// job 是一条抓取任务：url 目标地址，delay 模拟的响应延迟（用于制造超时场景）。
type job struct {
	url   string
	delay time.Duration
}

// fetch 模拟一次网络抓取：等待 delay 后返回标题；超时由调用方通过 ctx 控制。
// 真实抓取用 net/http（属 ph07 标准库阶段），这里用假实现保证可离线运行。
func fetch(ctx context.Context, url string, delay time.Duration) (string, error) {
	select {
	case <-time.After(delay):
		return "来自 " + url + " 的标题", nil
	case <-ctx.Done():
		return "", ctx.Err()
	}
}

// crawler 从 jobs 取抓取任务，结果写入 pages。jobs 关闭且取空后退出。
func crawler(ctx context.Context, id int, jobs <-chan job, pages chan<- page, wg *sync.WaitGroup) {
	defer wg.Done()
	for j := range jobs {
		fetchCtx, cancel := context.WithTimeout(ctx, 600*time.Millisecond)
		title, err := fetch(fetchCtx, j.url, j.delay)
		cancel()
		pages <- page{url: j.url, title: title, err: err}
	}
}

func main() {
	// 8 个 URL，其中两个耗时 1200ms，将触发 600ms 请求级超时
	jobsDef := []job{
		{"https://example.com/a", 300 * time.Millisecond},
		{"https://example.com/b", 300 * time.Millisecond},
		{"https://example.com/c", 1200 * time.Millisecond},
		{"https://example.com/d", 300 * time.Millisecond},
		{"https://example.com/e", 300 * time.Millisecond},
		{"https://example.com/f", 1200 * time.Millisecond},
		{"https://example.com/g", 300 * time.Millisecond},
		{"https://example.com/h", 300 * time.Millisecond},
	}

	const workers = 4
	jobs := make(chan job, len(jobsDef))
	pages := make(chan page, len(jobsDef))

	var wg sync.WaitGroup
	for i := 1; i <= workers; i++ {
		wg.Add(1)
		go crawler(context.Background(), i, jobs, pages, &wg)
	}

	for _, j := range jobsDef { // 发送方：把任务派发给 worker 后关闭
		jobs <- j
	}
	close(jobs)

	wg.Wait()
	close(pages)

	ok, failed := 0, 0
	for p := range pages {
		if p.err != nil {
			fmt.Printf("[失败] %s: %v\n", p.url, p.err)
			failed++
			continue
		}
		fmt.Printf("[成功] %s → %s\n", p.url, p.title)
		ok++
	}
	fmt.Printf("汇总：成功 %d 个，失败 %d 个\n", ok, failed)
}
