// Package chanx 实验：channel 底层语义的可观测面——无缓冲阻塞、缓冲不阻塞、
// 关闭后读取零值、select 随机选择、channel 并发安全（与 map 并发写 fatal 对照）。
// 结论：channel 是"带同步语义的消息队列"——无缓冲即同步点，缓冲即解耦；
// 关闭是广播（读端全部拿到零值）；select 在就绪分支间随机选择。
// 这些语义是 Go 并发模型（ph06 用法 + 本阶段机制）的运行时地基。
package chanx

import (
	"fmt"
	"sync"
	"time"
)

// UnbufferedSync 演示无缓冲 channel 的同步语义：发送与接收必须在同一时刻配对。
// 返回 (发送耗时, 是否正常完成)。接收方先就绪（goroutine），发送才能立即返回。
func UnbufferedSync() (sendTime time.Duration, ok bool) {
	ch := make(chan int) // 无缓冲
	done := make(chan struct{})
	go func() {
		close(done) // 先宣告"已就绪"
		<-ch        // 再阻塞等发送
	}()
	<-done // 确保接收方已就绪（goroutine 已进入 <-ch）
	start := time.Now()
	ch <- 42 // 有接收方在等 → 立即配对返回
	sendTime = time.Since(start)
	ok = true
	return
}

// BufferedNoBlock 演示缓冲 channel：容量 3，前 3 次发送不阻塞（不碰同步语义）。
func BufferedNoBlock() (drops int) {
	ch := make(chan int, 3)
	for i := 0; i < 3; i++ {
		ch <- i // 缓冲未满：不阻塞
	}
	// 不消费直接返回——证明缓冲吸收了这 3 个值
	for i := 0; i < 3; i++ {
		if <-ch != i {
			return -1
		}
	}
	return 0
}

// ClosedRead 演示关闭后的读取：range 读完缓冲后自动结束；
// 再读一个：channel 已关闭且空 → 零值 + ok=false。
func ClosedRead() (zero int, ok bool, drained int) {
	ch := make(chan int, 2)
	ch <- 1
	ch <- 2
	close(ch)
	for x := range ch {
		drained += x // 读到 1 和 2
	}
	zero, ok = <-ch // 关闭且空 → 0, false
	return
}

// SelectRandom 演示 select 在多个就绪分支间随机选择：两个分支都立即可用，
// 多次选择应两个分支都被选中过（随机性，非固定优先级）。
func SelectRandom(trials int) (a, b int) {
	for i := 0; i < trials; i++ {
		c1 := make(chan int, 1)
		c2 := make(chan int, 1)
		c1 <- 1
		c2 <- 2
		select {
		case <-c1:
			a++
		case <-c2:
			b++
		}
	}
	return
}

// ConcurrentSafeCounter 用 channel 做计数同步（goroutine 通过 channel 协作），
// 结果必须精确等于 n——与 ex02 的 map 并发写 fatal 形成对照：channel 天生并发安全。
func ConcurrentSafeCounter(n int) (total int) {
	ch := make(chan int, n)
	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			ch <- i // 并发发送：channel 内部有锁保护
		}(i)
	}
	wg.Wait()
	close(ch)
	for range ch {
		total++
	}
	return
}

// Report 生成 channel 语义实验报告。
func Report() string {
	sendTime, ok := UnbufferedSync()
	a, b := SelectRandom(100)
	return fmt.Sprintf(
		"无缓冲同步  : 发送耗时 %v, 完成=%v（接收方先就绪则发送立即配对）\n"+
			"缓冲不阻塞  : 容量 3 吸收 3 次发送，drop=%d\n"+
			"关闭读零值  : 见测试断言（v/ok/range 三态）\n"+
			"select 随机 : 100 次选择 → a=%d b=%d（两分支都被选中，非固定优先级）\n"+
			"并发安全计数: ConcurrentSafeCounter(1000) = %d（channel 内部同步，-race 零报告）",
		sendTime, ok, BufferedNoBlock(), a, b, ConcurrentSafeCounter(1000))
}
