// 来源：ph13-perf-optimization 示例 6 —— goroutine 泄漏检测 + execution trace
// 一句话说明：调用方超时放弃后，发送方 goroutine 永远阻塞在无缓冲 channel 上（泄漏）；
// 用 runtime.NumGoroutine 计数与 goroutine profile 文本 dump 定位泄漏的函数与行号，
// 修复手段是缓冲 channel 或 context 取消；最后用 runtime/trace 采集执行轨迹文件。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go test -race ./...          # 泄漏演示与修复版均无数据竞争
//	go run .                     # 打印泄漏前后 goroutine 数 + trace 文件摘要
//	go tool trace /tmp/ex06-trace.out   # 打开 trace 查看器（交互式 UI，本环境未验证）
//
// 验证状态：已验证（go1.25.6）；go tool trace 的浏览器 UI 属交互式查看器，未在本环境验证
package main

import (
	"bytes"
	"fmt"
	"os"
	"runtime"
	"runtime/pprof"
	"runtime/trace"
	"time"
)

// leakySend 泄漏版：结果 channel 无缓冲，调用方超时返回后，这里的发送永远阻塞，
// goroutine 连同其栈一起常驻内存——泄漏 1 万次就是 1 万个 goroutine
func leakySend(work func() int, timeout time.Duration) (int, bool) {
	ch := make(chan int) // 无缓冲：发送方必须有接收方配对
	go func() {
		ch <- work() // 调用方放弃后，这行永远阻塞
	}()
	select {
	case v := <-ch:
		return v, true
	case <-time.After(timeout):
		return 0, false // 超时返回——goroutine 被抛弃，泄漏发生
	}
}

// fixedSend 修复版：缓冲 1 的 channel 让发送方无需等待接收方，超时放弃也不会泄漏；
// 更完整的取消传播用 context（ph06），这里只需理解「发送方不能依赖接收方在场」
func fixedSend(work func() int, timeout time.Duration) (int, bool) {
	ch := make(chan int, 1) // 缓冲 1：发送方写完就走
	go func() {
		ch <- work()
	}()
	select {
	case v := <-ch:
		return v, true
	case <-time.After(timeout):
		return 0, false
	}
}

// slowWork 模拟一个必然超时的慢任务
func slowWork() int {
	time.Sleep(50 * time.Millisecond)
	return 42
}

// goroutineProfile 返回 goroutine profile 的文本 dump（debug=1：按栈聚合的计数）
func goroutineProfile() string {
	var buf bytes.Buffer
	_ = pprof.Lookup("goroutine").WriteTo(&buf, 1) // 此处错误无关紧要：dump 失败也只是拿不到 profile 文本
	return buf.String()
}

// captureTrace 采集 work 执行期间的 execution trace 到文件
func captureTrace(path string, work func()) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	if err := trace.Start(f); err != nil {
		return err
	}
	work()
	trace.Stop()
	return nil
}

func main() {
	fmt.Println("goroutines before:", runtime.NumGoroutine())
	for i := 0; i < 20; i++ {
		leakySend(slowWork, time.Millisecond) // 全部超时 → 泄漏 20 个 goroutine
	}
	time.Sleep(100 * time.Millisecond) // 等泄漏的 goroutine 都阻塞到位
	fmt.Println("goroutines after 20 leaky calls:", runtime.NumGoroutine())

	fmt.Println("--- goroutine profile 摘录（能看到泄漏栈聚在 leakySend）---")
	fmt.Println(goroutineProfile())

	const tracePath = "/tmp/ex06-trace.out"
	_ = os.Remove(tracePath)
	err := captureTrace(tracePath, func() {
		for i := 0; i < 4; i++ {
			fixedSend(slowWork, time.Second) // 修复版：不泄漏
		}
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, "trace:", err)
		os.Exit(1)
	}
	info, _ := os.Stat(tracePath)
	fmt.Printf("trace 已写入 %s（%d 字节），用 go tool trace %s 打开\n", tracePath, info.Size(), tracePath)
}
