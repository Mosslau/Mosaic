// 来源：ph10-database 阶段项目 —— 车辆轨迹存储服务（internal/cache 包）
// 一句话说明：最新位置旁路缓存——Cache 接口 + Redis 实现 + 内存实现（测试/降级用）。
// api 层只依赖 Cache 接口；Redis 不可用时降级到内存缓存（呼应 3.9「缓存不致命」），
// 本项目测试用内存实现，Redis 实现另有独立测试（不可达则跳过）。
// 验证环境：go1.25.6（darwin/arm64），依赖：github.com/redis/go-redis/v9 v9.22.0
// 运行：
//
//	go test -v ./internal/cache
//
// 验证状态：已验证（go1.25.6 + go-redis v9.22.0 + 本机 Redis 16379）
package cache

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

// Entry 缓存条目（对应 store.Point 的可序列化视图）
type Entry struct {
	DeviceID string    `json:"device_id"`
	Lat      float64   `json:"lat"`
	Lng      float64   `json:"lng"`
	Speed    float64   `json:"speed"`
	TS       time.Time `json:"ts"`
}

// Cache 最新位置缓存接口：api 层只依赖它
type Cache interface {
	// Get 命中返回 (entry, true)；未命中返回 (Entry{}, false)
	Get(ctx context.Context, deviceID string) (Entry, bool)
	// Set 写入并带 TTL
	Set(ctx context.Context, deviceID string, e Entry, ttl time.Duration) error
}

// redisCache Redis 实现（旁路缓存：短 TTL）
type redisCache struct {
	client *redis.Client
}

// NewRedis 构造 Redis 缓存（redisAddr 形如 "127.0.0.1:16379"）
func NewRedis(redisAddr string) Cache {
	return &redisCache{client: redis.NewClient(&redis.Options{Addr: redisAddr})}
}

// Ping 探活（供入口探测 Redis 是否可用）
func (c *redisCache) Ping(ctx context.Context) error {
	return c.client.Ping(ctx).Err()
}

func (c *redisCache) key(deviceID string) string { return "latest:" + deviceID }

func (c *redisCache) Get(ctx context.Context, deviceID string) (Entry, bool) {
	raw, err := c.client.Get(ctx, c.key(deviceID)).Bytes()
	if errors.Is(err, redis.Nil) {
		return Entry{}, false
	}
	if err != nil {
		return Entry{}, false // Redis 故障：当作未命中，降级查库
	}
	var e Entry
	if json.Unmarshal(raw, &e) != nil {
		return Entry{}, false
	}
	return e, true
}

func (c *redisCache) Set(ctx context.Context, deviceID string, e Entry, ttl time.Duration) error {
	raw, err := json.Marshal(e)
	if err != nil {
		return fmt.Errorf("marshal cache entry: %w", err)
	}
	return c.client.Set(ctx, c.key(deviceID), raw, ttl).Err()
}

// memoryCache 内存实现：测试与降级用（RWMutex 保护，读多写少）
type memoryCache struct {
	mu sync.RWMutex
	m  map[string]Entry
}

// NewMemory 构造内存缓存（测试注入 / Redis 故障降级）
func NewMemory() Cache {
	return &memoryCache{m: make(map[string]Entry)}
}

func (c *memoryCache) Get(ctx context.Context, deviceID string) (Entry, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	e, ok := c.m[deviceID]
	return e, ok
}

func (c *memoryCache) Set(ctx context.Context, deviceID string, e Entry, ttl time.Duration) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.m[deviceID] = e
	return nil
}
