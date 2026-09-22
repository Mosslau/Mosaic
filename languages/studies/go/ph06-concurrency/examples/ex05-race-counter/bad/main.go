// 来源：06-concurrency.md 第 6 章示例 5 —— 无锁版本（数据竞争演示）
// 一句话说明：100 个 goroutine 各累加 1000 次，无锁并发读写同一变量——数据竞争演示。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行（必须加 -race，否则可能输错值但不报错）：
//
//	cd examples/ex05-race-counter && go run -race ./bad
//
// 验证状态：已验证（Go 1.22.2，必现 WARNING: DATA RACE）
package main

import (
	"fmt"
	"sync"
)

type BadCounter struct{ value int }

func (c *BadCounter) Inc() { c.value++ } // 多 goroutine 并发读写 → 数据竞争

func main() {
	var wg sync.WaitGroup
	c := &BadCounter{}
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
	fmt.Println("无锁计数:", c.value, "（期望 100000，实际每次运行可能不同）")
}
