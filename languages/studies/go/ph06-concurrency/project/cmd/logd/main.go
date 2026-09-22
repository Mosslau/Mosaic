// 来源：06-concurrency.md 第 7 章「阶段项目」—— 并发日志处理器（演示入口）
// 一句话说明：3 个来源 goroutine 并发写日志，worker pool 消费、按级别过滤/聚合，超时刷新 + 优雅关闭，输出日志流与统计。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd project && go run ./cmd/logd
//
// 验证状态：已验证（Go 1.22.2，含 go run -race ./cmd/logd 无竞争）
package main

import (
	"context"
	"fmt"
	"os"
	"sync"
	"time"

	"tenetlang/go/ph06-concurrency/project/internal/logproc"
)

func main() {
	const (
		workers  = 4
		minLevel = logproc.LevelInfo // DEBUG 会被过滤
	)
	p := logproc.New(workers, minLevel, os.Stdout)

	// 超时刷新：每 50ms 把输出缓冲刷到 stdout，避免日志滞留
	flushCtx, flushCancel := context.WithCancel(context.Background())
	go p.FlushLoop(flushCtx, 50*time.Millisecond)

	// 三个来源（多源并发写入）：各自 goroutine 提交日志
	sources := []struct {
		name string
		msgs []logproc.Entry
	}{
		{"collector", []logproc.Entry{
			{Level: logproc.LevelInfo, Message: "采集批次 1 完成"},
			{Level: logproc.LevelDebug, Message: "采样点 17 电压 3.31V"},
			{Level: logproc.LevelWarn, Message: "采集间隔抖动 12ms"},
			{Level: logproc.LevelError, Message: "连接设备 D07 超时，重试"},
		}},
		{"api", []logproc.Entry{
			{Level: logproc.LevelInfo, Message: "GET /v1/devices 200"},
			{Level: logproc.LevelInfo, Message: "POST /v1/commands 202"},
			{Level: logproc.LevelError, Message: "请求参数校验失败"},
		}},
		{"scheduler", []logproc.Entry{
			{Level: logproc.LevelInfo, Message: "定时任务 tick 1"},
			{Level: logproc.LevelWarn, Message: "任务队列积压 200 条"},
			{Level: logproc.LevelDebug, Message: "缓存命中 98%"},
			{Level: logproc.LevelInfo, Message: "定时任务 tick 2"},
		}},
	}

	submitCtx, submitCancel := context.WithCancel(context.Background())
	var wg sync.WaitGroup
	for _, src := range sources {
		wg.Add(1)
		go func(name string, msgs []logproc.Entry) {
			defer wg.Done()
			for _, m := range msgs {
				m.Source = name
				m.Time = time.Now()
				if err := p.Submit(submitCtx, m); err != nil {
					fmt.Fprintf(os.Stderr, "[%s] 提交被拒绝: %v\n", name, err)
					return
				}
			}
		}(src.name, src.msgs)
	}
	wg.Wait()      // 所有来源结束提交
	submitCancel() // 禁止再提交（Shutdown 的前置约定）

	flushCancel() // 停掉超时刷新
	p.Shutdown()  // 优雅关闭：排空在途日志并刷出

	s := p.Stats()
	fmt.Println("\n=== 处理统计 ===")
	fmt.Printf("收到 %d 条，级别过滤丢弃 %d 条\n", s.Total, s.Filtered)
	for _, lv := range []logproc.Level{logproc.LevelInfo, logproc.LevelWarn, logproc.LevelError} {
		fmt.Printf("  %-5s %d 条\n", lv, s.ByLevel[lv])
	}
	for _, name := range []string{"collector", "api", "scheduler"} {
		fmt.Printf("  %-9s %d 条\n", name, s.BySource[name])
	}
}
