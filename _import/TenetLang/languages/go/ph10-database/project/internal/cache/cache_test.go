package cache

import (
	"context"
	"testing"
	"time"
)

func TestMemoryCacheSetGet(t *testing.T) {
	c := NewMemory()
	ctx := context.Background()
	e := Entry{DeviceID: "car-001", Lat: 31.2, Lng: 121.3, Speed: 70, TS: time.Now()}
	if err := c.Set(ctx, "car-001", e, time.Minute); err != nil {
		t.Fatal(err)
	}
	got, ok := c.Get(ctx, "car-001")
	if !ok {
		t.Fatal("写入后应命中")
	}
	if got.Speed != 70 {
		t.Errorf("speed = %v, want 70", got.Speed)
	}
}

func TestMemoryCacheMiss(t *testing.T) {
	c := NewMemory()
	if _, ok := c.Get(context.Background(), "ghost"); ok {
		t.Error("未写入应未命中")
	}
}

func TestMemoryCacheOverwrite(t *testing.T) {
	c := NewMemory()
	ctx := context.Background()
	c.Set(ctx, "car-001", Entry{DeviceID: "car-001", Speed: 10}, time.Minute)
	c.Set(ctx, "car-001", Entry{DeviceID: "car-001", Speed: 20}, time.Minute)
	got, _ := c.Get(ctx, "car-001")
	if got.Speed != 20 {
		t.Errorf("speed = %v, want 20（覆盖写）", got.Speed)
	}
}

// TestRedisCacheRoundTrip Redis 实现：不可达则跳过（本环境已实测可达）
func TestRedisCacheRoundTrip(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	c := NewRedis("127.0.0.1:16379")
	// 探活：不可达则跳过
	rc, ok := c.(*redisCache)
	if !ok {
		t.Fatal("type assertion failed")
	}
	if err := rc.client.Ping(ctx).Err(); err != nil {
		t.Skipf("Redis 不可达（%v），跳过 Redis 缓存用例", err)
	}
	rc.client.FlushDB(ctx)

	e := Entry{DeviceID: "car-001", Lat: 31.2, Lng: 121.3, Speed: 88.5, TS: time.Now()}
	if err := c.Set(ctx, "car-001", e, time.Minute); err != nil {
		t.Fatal(err)
	}
	got, ok := c.Get(ctx, "car-001")
	if !ok {
		t.Fatal("Redis 写入后应命中")
	}
	if got.Speed != 88.5 {
		t.Errorf("speed = %v, want 88.5", got.Speed)
	}
	if _, ok := c.Get(ctx, "ghost"); ok {
		t.Error("未写入应未命中")
	}
}
