package main

import (
	"strings"
	"sync"
	"testing"
)

// ---- 正确性：并发计数结果精确（-race 下无数据竞争）----

func TestGlobalCounterConcurrent(t *testing.T) {
	var c GlobalCounter
	var wg sync.WaitGroup
	for g := 0; g < 8; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < 1000; i++ {
				c.Inc()
			}
		}()
	}
	wg.Wait()
	if got := c.Load(); got != 8000 {
		t.Fatalf("GlobalCounter=%d, want 8000", got)
	}
}

func TestShardedCounterConcurrent(t *testing.T) {
	var c ShardedCounter
	var wg sync.WaitGroup
	for g := 0; g < 8; g++ {
		wg.Add(1)
		go func(g uint64) {
			defer wg.Done()
			for i := uint64(0); i < 1000; i++ {
				c.Inc(g*1000 + i)
			}
		}(uint64(g))
	}
	wg.Wait()
	if got := c.Load(); got != 8000 {
		t.Fatalf("ShardedCounter=%d, want 8000", got)
	}
}

func TestAtomicCounterConcurrent(t *testing.T) {
	var c AtomicCounter
	var wg sync.WaitGroup
	for g := 0; g < 8; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < 1000; i++ {
				c.Inc()
			}
		}()
	}
	wg.Wait()
	if got := c.Load(); got != 8000 {
		t.Fatalf("AtomicCounter=%d, want 8000", got)
	}
}

// ---- profile 采集：真实采集并断言输出里包含预期内容 ----

func TestDemoMutexContention(t *testing.T) {
	out := DemoMutexContention()
	if !strings.Contains(out, "mutex") {
		t.Fatalf("mutex profile 输出缺少头信息:\n%s", out)
	}
	if !strings.Contains(out, "DemoMutexContention") {
		t.Fatalf("mutex profile 应包含竞争发生的函数名:\n%s", out)
	}
}

func TestDemoBlockProfile(t *testing.T) {
	out := DemoBlockProfile()
	// debug=1 文本输出的头是 "--- contention:"（block profile 记录的就是阻塞争用事件）
	if !strings.Contains(out, "contention") {
		t.Fatalf("block profile 输出缺少头信息:\n%s", out)
	}
	if !strings.Contains(out, "DemoBlockProfile") || !strings.Contains(out, "chanrecv") {
		t.Fatalf("block profile 应包含阻塞发生的函数名与阻塞点:\n%s", out)
	}
}

// ---- 并发基准：固定 -cpu=8 放大竞争差异 ----

func BenchmarkGlobalCounter(b *testing.B) {
	var c GlobalCounter
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			c.Inc()
		}
	})
}

func BenchmarkShardedCounter(b *testing.B) {
	var c ShardedCounter
	var key uint64
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			key++
			c.Inc(key)
		}
	})
}

func BenchmarkAtomicCounter(b *testing.B) {
	var c AtomicCounter
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			c.Inc()
		}
	})
}
