// 来源：06-concurrency.md 第 7 章「动手练习」练习 1 —— worker pool
// 一句话说明：固定 4 个 worker 并发处理 20 个求平方任务，结果经 channel 汇总，发送方 close、worker range 消费。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd exercises/sol-01-worker-pool && go run .
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"fmt"
	"sync"
)

// result 是单个任务的输出：task 为原任务号，square 为计算结果，worker 记录处理者。
type result struct {
	task   int
	square int
	worker int
}

// worker 从 jobs 读取任务，结果写入 results。jobs 关闭且取空后 range 自动结束。
func worker(id int, jobs <-chan int, results chan<- result, wg *sync.WaitGroup) {
	defer wg.Done()
	for j := range jobs {
		results <- result{task: j, square: j * j, worker: id}
	}
}

func main() {
	const (
		total   = 20
		workers = 4
	)
	jobs := make(chan int, total)
	results := make(chan result, total)

	var wg sync.WaitGroup
	for i := 1; i <= workers; i++ {
		wg.Add(1)
		go worker(i, jobs, results, &wg)
	}

	// 发送方（main）负责关闭 jobs
	for j := 1; j <= total; j++ {
		jobs <- j
	}
	close(jobs)

	// 所有 worker 退出后再关闭 results，main 才能用 range 收尾
	wg.Wait()
	close(results)

	sum := 0
	for r := range results {
		fmt.Printf("任务 %2d → 平方 %4d（worker %d）\n", r.task, r.square, r.worker)
		sum += r.square
	}
	fmt.Printf("平方和 = %d（期望 %d）\n", sum, total*(total+1)*(2*total+1)/6)
}
