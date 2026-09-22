// 来源：06-concurrency.md 第 7 章「动手练习」练习 3 —— 任务超时控制
// 一句话说明：对耗时不同的任务统一套 1s 超时，超时未完成则放弃并降级处理。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd exercises/sol-03-task-timeout && go run .
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"context"
	"fmt"
	"time"
)

const timeout = 1 * time.Second

// runTask 在独立 goroutine 里执行任务，通过 select 同时等待「完成」与「超时」：
// 超时到达时任务还在跑，立即放弃等待并返回降级信号。
// 注意：runTask 不会强行杀死 goroutine——任务函数应检查 ctx.Done() 以便尽早退出。
func runTask(ctx context.Context, name string, work time.Duration) (string, error) {
	done := make(chan string, 1) // 缓冲 1：即使调用方已放弃，任务完成后发送也不阻塞
	go func() {
		select {
		case <-time.After(work): // 模拟耗时工作
			done <- name + " 完成"
		case <-ctx.Done(): // 收到取消信号立即返回，不发送结果
		}
	}()

	select {
	case result := <-done:
		return result, nil
	case <-ctx.Done():
		return "", ctx.Err() // context deadline exceeded → 调用方降级
	}
}

func main() {
	type task struct {
		name string
		work time.Duration
	}
	tasks := []task{
		{"任务A（短耗时）", 300 * time.Millisecond},
		{"任务B（中等耗时）", 900 * time.Millisecond},
		{"任务C（长耗时）", 1800 * time.Millisecond},
	}

	for _, t := range tasks {
		// 每个任务独立 1s 超时，互不干扰
		taskCtx, cancel := context.WithTimeout(context.Background(), timeout)
		result, err := runTask(taskCtx, t.name, t.work)
		cancel()

		if err != nil {
			fmt.Printf("%s：超时（%v），降级处理：返回缓存结果\n", t.name, err)
			continue
		}
		fmt.Printf("%s：%s\n", t.name, result)
	}
}
