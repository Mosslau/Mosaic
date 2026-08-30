// 来源：06-concurrency.md 第 6 章示例 5 —— Mutex 保护共享计数器（正确版本）
// 一句话说明：同一计数器用 sync.Mutex 保护，-race 下无警告、输出恒为 100000。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd examples/ex05-race-counter && go run -race ./good
//
// 验证状态：已验证（Go 1.22.2，无 DATA RACE）
package main

import (
	"fmt"
	"sync"
)

type Counter struct {
	mu    sync.Mutex
	value int
}

func (c *Counter) Inc() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.value++
}

func (c *Counter) Value() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.value
}

func main() {
	var wg sync.WaitGroup
	c := &Counter{}
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 1000; j++ {
				c.Inc()
			}
		}()
	}
	wg.Wait()
	fmt.Println("加锁计数:", c.Value(), "（期望 100000）")
}
