// 来源：06-concurrency.md 第 6 章示例 1 —— goroutine + WaitGroup 并发求和
// 一句话说明：把 1..1000000 切成 4 段，每段一个 goroutine 求和，WaitGroup 等待后汇总。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd examples/ex01-waitgroup-sum && go run .
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"fmt"
	"sync"
)

// sumChunk 对切片求和，结果写入 result 指向的槽位。
// 每个 goroutine 写不同的槽位，无共享写冲突，因此无需加锁。
func sumChunk(nums []int, wg *sync.WaitGroup, result *int) {
	defer wg.Done()
	total := 0
	for _, n := range nums {
		total += n
	}
	*result = total
}

func main() {
	nums := make([]int, 1000000)
	for i := range nums {
		nums[i] = i + 1
	}

	const parts = 4
	chunkSize := len(nums) / parts
	results := make([]int, parts)

	var wg sync.WaitGroup
	for i := 0; i < parts; i++ {
		start := i * chunkSize
		end := start + chunkSize
		if i == parts-1 {
			end = len(nums) // 最后一段收尾，避免整除截断丢数据
		}
		wg.Add(1) // Add 必须在 go 语句之前
		go sumChunk(nums[start:end], &wg, &results[i])
	}
	wg.Wait()

	total := 0
	for _, r := range results {
		total += r
	}
	fmt.Printf("1+2+...+1000000 = %d\n", total) // 500000500000
}
