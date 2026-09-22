package main

import (
	"fmt"
	"math/rand"
	"sync"
	"sync/atomic"
	"testing"
)

// ---- 正确性：两种实现的 Get/Set 语义一致，-race 下无数据竞争 ----

func TestSingleCacheConcurrent(t *testing.T) {
	c := NewSingleCache()
	var wg sync.WaitGroup
	for g := 0; g < 8; g++ {
		wg.Add(1)
		go func(g int) {
			defer wg.Done()
			for i := 0; i < 500; i++ {
				c.Set(fmt.Sprintf("key-%d", (g*500+i)%100), i)
			}
		}(g)
	}
	wg.Wait()
	// 每把 key 都被写过 8 次（8 goroutine 各一次）；最后一次写者的值不确定，
	// 但 key 必须存在且是 int（不 panic、不丢数据）
	for k := 0; k < 100; k++ {
		if _, ok := c.Get(fmt.Sprintf("key-%d", k)); !ok {
			t.Fatalf("key-%d 丢失", k)
		}
	}
}

func TestShardedCacheConcurrent(t *testing.T) {
	c := NewShardedCache()
	var wg sync.WaitGroup
	for g := 0; g < 8; g++ {
		wg.Add(1)
		go func(g int) {
			defer wg.Done()
			for i := 0; i < 500; i++ {
				c.Set(fmt.Sprintf("key-%d", (g*500+i)%100), i)
			}
		}(g)
	}
	wg.Wait()
	for k := 0; k < 100; k++ {
		if _, ok := c.Get(fmt.Sprintf("key-%d", k)); !ok {
			t.Fatalf("key-%d 丢失", k)
		}
	}
}

// ---- 散列均匀性：100 个 key 应大致摊满 16 片（分片失效时竞争不会摊薄）----

func TestShardDistribution(t *testing.T) {
	c := NewShardedCache()
	seen := map[*shard]bool{}
	for k := 0; k < 1000; k++ {
		seen[c.shard(fmt.Sprintf("device-%04d", k))] = true
	}
	if len(seen) < 14 { // 1000 个 key 应覆盖 ≥14/16 片
		t.Fatalf("散列不均匀：只用了 %d/16 片", len(seen))
	}
}

// ---- 基准：固定 -cpu=8 放大竞争差异；key 预生成 + 洗牌 + 每 worker 错位起点 ----
// 要点：
//  1. key 池预生成（热路径不含 Sprintf 分配，否则分配成本会淹没锁竞争差异）；
//  2. 洗牌：真实负载里并发请求命中不同 key，不能用「所有 worker 同步轮询同一序列」——
//     那样竞争会集中在同一个分片上，分片优势被掩盖（实测锁定步设计分片反而更慢）；
//  3. 每 worker 用原子计数器错开起点（off），配合互质步长 37 走遍全池，模拟并发乱序访问

var hotKeys = func() []string {
	ks := make([]string, 4096)
	for i := range ks {
		ks[i] = fmt.Sprintf("device-%04d", i)
	}
	// 固定种子洗牌：每次基准可复现
	rand.New(rand.NewSource(42)).Shuffle(len(ks), func(i, j int) { ks[i], ks[j] = ks[j], ks[i] })
	return ks
}()

var keyOffset atomic.Uint64 // 每 worker 的起点错位（RunParallel 闭包每 worker 执行一次）

func BenchmarkSingleCacheSet(b *testing.B) {
	c := NewSingleCache()
	b.RunParallel(func(pb *testing.PB) {
		off := keyOffset.Add(1) * 257
		for i := uint64(0); pb.Next(); i++ {
			c.Set(hotKeys[(i*37+off)%uint64(len(hotKeys))], 1)
		}
	})
}

func BenchmarkShardedCacheSet(b *testing.B) {
	c := NewShardedCache()
	b.RunParallel(func(pb *testing.PB) {
		off := keyOffset.Add(1) * 257
		for i := uint64(0); pb.Next(); i++ {
			c.Set(hotKeys[(i*37+off)%uint64(len(hotKeys))], 1)
		}
	})
}
