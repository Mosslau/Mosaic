package main

import (
	"bytes"
	"sync"
	"testing"
)

var testData = bytes.Repeat([]byte("abcdefghij"), 409) // 4090 字节

func TestProcessEqual(t *testing.T) {
	a, b := ProcessNoPool(testData), ProcessPool(testData)
	if a != b {
		t.Fatalf("两种实现结果不一致: %d vs %d", a, b)
	}
}

// TestPoolReset 验证「不复位会串数据」这一坑：Put 回去的对象带着旧内容。
// 用独立的局部 Pool（而非全局 bufPool）保证确定性：同一 goroutine 内 Put 进私有槽位，
// 中间无 GC，下一次 Get 稳定取回同一个对象。
func TestPoolReset(t *testing.T) {
	p := &sync.Pool{New: func() any { return new(bytes.Buffer) }}
	buf := p.Get().(*bytes.Buffer)
	buf.WriteString("dirty")
	p.Put(buf) // 故意不 Reset 就归还

	got := p.Get().(*bytes.Buffer)
	if got.String() != "dirty" {
		t.Fatalf("池中对象内容 = %q, want %q（证明 Put 的对象会原样回来）", got.String(), "dirty")
	}
	got.Reset()
	if got.Len() != 0 {
		t.Fatal("Reset 后应为空")
	}
}

// TestProcessPoolConcurrent 并发使用 Pool：-race 下验证无数据竞争
func TestProcessPoolConcurrent(t *testing.T) {
	var wg sync.WaitGroup
	for g := 0; g < 8; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < 200; i++ {
				if ProcessPool(testData) != ProcessNoPool(testData) {
					t.Error("并发下结果不一致")
					return
				}
			}
		}()
	}
	wg.Wait()
}

// 并发基准：RunParallel 模拟多 P 同时处理请求，最能体现 Pool 的 per-P 本地缓存优势
func BenchmarkProcessNoPool(b *testing.B) {
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			sink = ProcessNoPool(testData)
		}
	})
}

func BenchmarkProcessPool(b *testing.B) {
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			sink = ProcessPool(testData)
		}
	})
}

// ---- 小响应体对照：分配成本低时 Pool 的 Get/Put 簿记反而可能超过省下的分配 ----
// 实测结论（go1.25.6，Apple M4 Pro）：约 50 字节的小负载下朴素版更快——
// 见 README「sync.Pool 什么时候值得用」一节的实测记录
var smallData = []byte("GET /healthz HTTP/1.1\r\nHost: localhost\r\n\r\n")

func BenchmarkProcessNoPoolSmall(b *testing.B) {
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			sink = ProcessNoPool(smallData)
		}
	})
}

func BenchmarkProcessPoolSmall(b *testing.B) {
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			sink = ProcessPool(smallData)
		}
	})
}

var sink int
