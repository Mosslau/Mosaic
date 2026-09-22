// 来源：06-concurrency.md 第 6 章示例 3 —— select + time.After 超时控制
// 一句话说明：两个数据源并发抓取，select 多路等待；100ms 内无数据先降级，稍后仍能读到迟到的数据。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd examples/ex03-select-timeout && go run .
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"fmt"
	"time"
)

// fakeFetch 模拟远程数据源：等待 delay 后把结果写入 out。
func fakeFetch(name string, delay time.Duration, out chan<- string) {
	time.Sleep(delay)
	out <- name + " 的数据"
}

func main() {
	chA := make(chan string, 1) // 缓冲 1：无人接收时发送方也不永久阻塞
	chB := make(chan string, 1)
	go fakeFetch("数据源 A", 150*time.Millisecond, chA)
	go fakeFetch("数据源 B", 200*time.Millisecond, chB)

	select {
	case data := <-chA:
		fmt.Println("拿到:", data)
	case data := <-chB:
		fmt.Println("拿到:", data)
	case <-time.After(100 * time.Millisecond):
		fmt.Println("超时：100ms 内无数据，先做降级处理")
	}

	// 超时只是"放弃等待"——数据到达后仍可读取
	select {
	case data := <-chA:
		fmt.Println("稍后 A 返回:", data)
	case data := <-chB:
		fmt.Println("稍后 B 返回:", data)
	case <-time.After(500 * time.Millisecond):
		fmt.Println("两个数据源均未返回")
	}
}
