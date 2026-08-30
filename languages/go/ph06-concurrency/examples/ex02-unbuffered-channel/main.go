// 来源：06-concurrency.md 第 6 章示例 2 —— 无缓冲 channel 的同步通信（worker 协作）
// 一句话说明：worker goroutine 完成采集后通过无缓冲 channel 向 main 交接"完成信号"，演示配对同步。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd examples/ex02-unbuffered-channel && go run .
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"fmt"
	"time"
)

func main() {
	done := make(chan string) // 无缓冲：完成信号必须被接收，发送才不阻塞
	go func() {               // 数据采集 worker
		for i := 1; i <= 3; i++ {
			time.Sleep(50 * time.Millisecond)
			fmt.Printf("  采集第 %d 组数据\n", i)
		}
		done <- "采集完成" // 同步交接点：main 未接收前，这里一直阻塞
		fmt.Println("worker：信号已交接，继续清理")
	}()
	msg := <-done // 同步点：阻塞等待 worker 的信号
	fmt.Println("main 收到:", msg)
}
