// 来源：ph13-perf-optimization 练习 3 参考实现 —— 查 goroutine 泄漏
// 一句话说明：fan-out 模式里调用方只收一半结果就返回，无缓冲 channel 的发送方
// goroutine 全部卡死在发送上（泄漏）；用 runtime.NumGoroutine 计数 + goroutine
// profile 文本 dump 定位泄漏点；修复手段是「缓冲 = 发送方数量」让发送方写完即走。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go test -race ./...
//	go run .                   # 打印泄漏前后 goroutine 数与 profile 摘录
//
// 验证状态：已验证（go1.25.6，含 -race）；goroutine 数字随调度波动，趋势稳定
package main

import (
	"bytes"
	"fmt"
	"runtime"
	"runtime/pprof"
	"time"
)

// leakyFanOut 泄漏版：n 个发送 goroutine 共用无缓冲 channel，调用方只消费一半就返回，
// 剩下 n/2 个发送方永远阻塞在 ch <- work()——goroutine 连同其栈常驻内存
func leakyFanOut(n int, work func() int) int {
	ch := make(chan int) // 无缓冲：每个发送方都必须等到有接收方在场
	for i := 0; i < n; i++ {
		go func() {
			ch <- work() // 调用方放弃后，这行永远阻塞（泄漏点）
		}()
	}
	total := 0
	for i := 0; i < n/2; i++ { // 只消费一半结果就返回
		total += <-ch
	}
	return total
}

// fixedFanOut 修复版：缓冲容量 = 发送方数量 n，每个发送方写完立即返回，
// 调用方只消费一半也不影响剩余发送方退出——发送方不依赖接收方在场
func fixedFanOut(n int, work func() int) int {
	ch := make(chan int, n) // 缓冲 n：所有发送方都能把结果放进去
	for i := 0; i < n; i++ {
		go func() {
			ch <- work()
		}()
	}
	total := 0
	for i := 0; i < n/2; i++ {
		total += <-ch
	}
	return total
}

// slowWork 模拟一个耗时任务（真实场景里是 RPC、DB 查询）
func slowWork() int {
	time.Sleep(10 * time.Millisecond)
	return 42
}

// goroutineProfile 返回 goroutine profile 的文本 dump（debug=1：按调用栈聚合计数）——
// 泄漏的 goroutine 会聚在 leakyFanOut 的 ch <- work() 那一行
func goroutineProfile() string {
	var buf bytes.Buffer
	_ = pprof.Lookup("goroutine").WriteTo(&buf, 1) // 此处错误无关紧要：dump 失败也只是拿不到 profile 文本
	return buf.String()
}

func main() {
	fmt.Println("goroutines before:", runtime.NumGoroutine())
	total := leakyFanOut(40, slowWork)
	fmt.Println("leakyFanOut total:", total)
	time.Sleep(200 * time.Millisecond) // 等泄漏的发送方全部阻塞到位
	fmt.Println("goroutines after leakyFanOut:", runtime.NumGoroutine())

	prof := goroutineProfile()
	fmt.Println("--- goroutine profile 摘录（泄漏栈聚在 leakyFanOut）---")
	fmt.Println(prof)

	_ = fixedFanOut(40, slowWork)
	time.Sleep(200 * time.Millisecond)
	fmt.Println("goroutines after fixedFanOut:", runtime.NumGoroutine())
}
