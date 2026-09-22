// 来源：ph08-testing 练习 3 参考实现 —— 给并发代码跑 race（修复版）
// 一句话说明：Mutex 保护计数器，建立 happens-before 关系消除数据竞争。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -race -v ./...   # 必须带 -race：复现并验证修复
//
// 验证状态：已验证（go1.25.6，-race 下干净通过）
package main

import (
	"fmt"
	"sync"
)

// Counter 修复版：所有读写都持锁，建立 happens-before 关系
type Counter struct {
	mu sync.Mutex
	n  int
}

func (c *Counter) Inc() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.n++
}

func (c *Counter) Value() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.n
}

func main() {
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
	fmt.Println("计数:", c.Value())
}
