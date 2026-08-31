// 来源：ph08-testing 练习 3 参考实现 —— 给并发代码跑 race（修复版）
// 一句话说明：100 个 goroutine 并发 Inc，-race 下验证无数据竞争且结果精确为 100。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -race -v ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"sync"
	"testing"
)

func TestCounterConcurrent(t *testing.T) {
	var c Counter
	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			c.Inc()
		}()
	}
	wg.Wait()
	if got := c.Value(); got != 100 {
		t.Errorf("Value() = %d, 期望 100", got)
	}
}

// 备选修复方案对照：atomic 无需锁，适合单一数值场景
// （本文件仅测 Mutex 版；atomic 版思路：atomic.Int64 的 Add/Load 自带同步语义）
