// 来源：06-concurrency.md 第 6 章示例 4 —— worker pool 任务队列（带 context 取消）
// 一句话说明：固定 3 个 worker 从任务 channel 取任务，context 100ms 超时后派发停止、worker 优雅退出。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd examples/ex04-worker-pool && go run .
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// worker 同时监听取消信号与任务 channel：任一条件满足即退出，杜绝 goroutine 泄漏。
func worker(ctx context.Context, id int, jobs <-chan int, wg *sync.WaitGroup) {
	defer wg.Done()
	for {
		select {
		case <-ctx.Done(): // 取消信号优先退出
			fmt.Printf("worker %d 退出（原因: %v）\n", id, ctx.Err())
			return
		case j, ok := <-jobs:
			if !ok { // jobs 关闭且取空
				fmt.Printf("worker %d 处理完所有任务，退出\n", id)
				return
			}
			time.Sleep(20 * time.Millisecond) // 模拟任务耗时
			fmt.Printf("worker %d 完成任务 %d\n", id, j)
		}
	}
}

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	const workers = 3
	jobs := make(chan int, 100)
	var wg sync.WaitGroup
	for i := 1; i <= workers; i++ {
		wg.Add(1)
		go worker(ctx, i, jobs, &wg)
	}

	go func() { // 任务派发（发送方）：ctx 取消时停止派发
		for j := 1; j <= 100; j++ {
			select {
			case jobs <- j:
			case <-ctx.Done():
				fmt.Println("ctx 已取消，停止派发任务")
				return
			}
		}
		close(jobs)
	}()

	wg.Wait() // 所有 worker 退出（正常耗尽或 ctx 取消）
	fmt.Println("worker pool 全部退出")
}
