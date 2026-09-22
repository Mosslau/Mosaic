// 来源：ph13-perf-optimization 示例 5 —— 减少锁竞争 + mutex/block profile
// 一句话说明：同一个计数器用三种同步策略实现（全局互斥锁 / 16 分片锁 / atomic），
// 并发基准量化差异；再用 runtime.SetMutexProfileFraction + SetBlockProfileRate
// 采集 mutex 与 block profile，定位「等待发生在哪一行」。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go test -race ./...
//	go test -run='^$' -bench=. -benchtime=1s -cpu=8   # 固定 8 P 放大竞争差异
//	go run .                                               # 打印 mutex/block profile 文本摘要
//
// 验证状态：已验证（go1.25.6，profile 输出为实测）；benchmark 数字随机器波动
package main

import (
	"bytes"
	"fmt"
	"runtime"
	"runtime/pprof"
	"sync"
	"sync/atomic"
	"time"
)

// ---- 三种计数器实现 ----

// GlobalCounter 全局互斥锁：所有 goroutine 抢同一把锁
type GlobalCounter struct {
	mu sync.Mutex
	n  int64
}

func (c *GlobalCounter) Inc() {
	c.mu.Lock()
	c.n++
	c.mu.Unlock()
}

func (c *GlobalCounter) Load() int64 {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.n
}

const shards = 16

// ShardedCounter 分片锁：按 key 散列到 16 个分片，竞争概率降为 1/16
// 每个分片独占 64 字节缓存行（padding），避免 false sharing（分片了但缓
// 存行仍共享的话，核间缓存一致性流量照样拖慢——这是只看锁看不到的一层）
type ShardedCounter struct {
	s [shards]struct {
		mu sync.Mutex
		n  int64
		_  [48]byte // sync.Mutex(8) + int64(8) + 48 = 64，正好一个缓存行：分片间不共享缓存行
	}
}

func (c *ShardedCounter) Inc(key uint64) {
	sh := &c.s[key%shards]
	sh.mu.Lock()
	sh.n++
	sh.mu.Unlock()
}

func (c *ShardedCounter) Load() int64 {
	var sum int64
	for i := range c.s {
		c.s[i].mu.Lock()
		sum += c.s[i].n
		c.s[i].mu.Unlock()
	}
	return sum
}

// AtomicCounter 无锁：atomic.AddInt64 一条 CPU 指令，无 goroutine 挂起
type AtomicCounter struct {
	n atomic.Int64
}

func (c *AtomicCounter) Inc()        { c.n.Add(1) }
func (c *AtomicCounter) Load() int64 { return c.n.Load() }

// ---- mutex / block profile 演示 ----

// DemoMutexProfile 制造 8 goroutine 抢一把锁的竞争，然后 dump mutex profile 文本。
// SetMutexProfileFraction(1) 表示「每一次竞争事件都记录」（生产用更大的值降开销）。
func DemoMutexContention() string {
	runtime.SetMutexProfileFraction(1)
	defer runtime.SetMutexProfileFraction(0)

	var mu sync.Mutex
	var wg sync.WaitGroup
	for g := 0; g < 8; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < 2000; i++ {
				mu.Lock()
				mu.Unlock()
			}
		}()
	}
	wg.Wait()

	var buf bytes.Buffer
	// debug=1 输出可读文本：竞争次数 + 调用栈
	if err := pprof.Lookup("mutex").WriteTo(&buf, 1); err != nil {
		return err.Error()
	}
	return buf.String()
}

// DemoBlockProfile 制造 channel 阻塞，然后 dump block profile 文本。
// SetBlockProfileRate(1) 表示「每一次阻塞事件都记录」（单位 ns，1 = 全记录）。
func DemoBlockProfile() string {
	runtime.SetBlockProfileRate(1)
	defer runtime.SetBlockProfileRate(0)

	ch := make(chan struct{})
	go func() {
		time.Sleep(20 * time.Millisecond)
		close(ch)
	}()
	<-ch // 主 goroutine 在这里阻塞约 20ms

	var buf bytes.Buffer
	if err := pprof.Lookup("block").WriteTo(&buf, 1); err != nil {
		return err.Error()
	}
	return buf.String()
}

func main() {
	fmt.Println("=== mutex profile（8 goroutine 抢一把锁）===")
	fmt.Println(DemoMutexContention())
	fmt.Println("=== block profile（主 goroutine 等 channel 20ms）===")
	fmt.Println(DemoBlockProfile())
}
