// 来源：ph13-perf-optimization 练习 4 参考实现 —— 优化锁竞争
// 一句话说明：同一个 string→int 缓存用两种同步策略实现——全局互斥锁 vs 16 分片锁
// （按 key 散列），并发基准量化差异；实测在 8 P 高竞争下分片锁约为全局锁的 1/1.7 耗时。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go test -race ./...
//	go test -run='^$' -bench=. -benchmem -benchtime=1s -cpu=8   # 固定 8 P 放大竞争差异
//
// 验证状态：已验证（go1.25.6，含 -race）
// benchmark 实测（go1.25.6，Apple M4 Pro，-benchtime=1s，-cpu=8，RunParallel，三次均值）：
//
//	BenchmarkSingleCacheSet-8   ~7.4M   161.3 ns/op   0 B/op   0 allocs/op
//	BenchmarkShardedCacheSet-8  ~12.8M    94.4 ns/op   0 B/op   0 allocs/op
//
// 结论：分片锁约为全局锁的 1/1.7 耗时（快约 1.7 倍）——竞争从「8 个 goroutine 抢 1 把锁」
// 摊薄为「每片平均 0.5 个 goroutine」，锁等待时间随竞争概率下降；
// 数字随机器波动，以本机重跑为准；基准设计要点（key 洗牌 + 每 worker 错位起点）见 main_test.go
package main

import (
	"hash/fnv"
	"sync"
)

const shards = 16

// ---- 全局互斥锁版：所有 goroutine 抢同一把锁 ----

// SingleCache 单锁缓存：map 读写都过同一把 mu
type SingleCache struct {
	mu sync.Mutex
	m  map[string]int
}

func NewSingleCache() *SingleCache {
	return &SingleCache{m: make(map[string]int)}
}

func (c *SingleCache) Get(key string) (int, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	v, ok := c.m[key]
	return v, ok
}

func (c *SingleCache) Set(key string, v int) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.m[key] = v
}

// ---- 分片锁版：按 key 散列到 16 片，每片一把锁 ----

type shard struct {
	mu sync.Mutex
	m  map[string]int
}

// ShardedCache 分片缓存：竞争概率降为 1/16
type ShardedCache struct {
	s [shards]shard
}

func NewShardedCache() *ShardedCache {
	c := &ShardedCache{}
	for i := range c.s {
		c.s[i].m = make(map[string]int)
	}
	return c
}

// shard 用 FNV-1a 把 key 散列到分片下标（散列均匀才能摊薄竞争）
func (c *ShardedCache) shard(key string) *shard {
	h := fnv.New32a()
	_, _ = h.Write([]byte(key))
	return &c.s[h.Sum32()%shards]
}

func (c *ShardedCache) Get(key string) (int, bool) {
	sh := c.shard(key)
	sh.mu.Lock()
	defer sh.mu.Unlock()
	v, ok := sh.m[key]
	return v, ok
}

func (c *ShardedCache) Set(key string, v int) {
	sh := c.shard(key)
	sh.mu.Lock()
	defer sh.mu.Unlock()
	sh.m[key] = v
}
