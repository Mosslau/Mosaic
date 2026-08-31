package main

import (
	"context"
	"database/sql"
	"errors"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
	_ "modernc.org/sqlite"
)

// newTestRedis 尝试连接 Redis，不可达则跳过（本环境已实测可达）
func newTestRedis(t *testing.T) *redis.Client {
	t.Helper()
	rdb := redis.NewClient(&redis.Options{Addr: redisAddr})
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	if err := rdb.Ping(ctx).Err(); err != nil {
		t.Skipf("Redis 不可达（%v），跳过 Redis 用例；启动方式见文件头注释", err)
	}
	t.Cleanup(func() { rdb.Close() })
	return rdb
}

func TestGetUserMissThenHit(t *testing.T) {
	db, _ := newUserDB()
	defer db.Close()
	rdb := newTestRedis(t)
	ctx := context.Background()
	rdb.FlushDB(ctx)

	u1, err := GetUser(ctx, db, rdb, 1) // 首次：查库回填
	if err != nil {
		t.Fatalf("GetUser(1): %v", err)
	}
	if u1.Username != "alice" {
		t.Errorf("username = %q, want alice", u1.Username)
	}
	exists, _ := rdb.Exists(ctx, "user:1").Result()
	if exists != 1 {
		t.Error("回填后缓存应存在")
	}
	u2, err := GetUser(ctx, db, rdb, 1) // 二次：缓存命中
	if err != nil {
		t.Fatalf("GetUser(2): %v", err)
	}
	if u2.Username != "alice" {
		t.Errorf("缓存命中读取 username = %q", u2.Username)
	}
}

func TestGetUserMissingFillsEmptyCache(t *testing.T) {
	db, _ := newUserDB()
	defer db.Close()
	rdb := newTestRedis(t)
	ctx := context.Background()
	rdb.FlushDB(ctx)

	_, err := GetUser(ctx, db, rdb, 999)
	if !errors.Is(err, sql.ErrNoRows) {
		t.Fatalf("want sql.ErrNoRows, got %v", err)
	}
	raw, _ := rdb.Get(ctx, "user:999").Result()
	if raw != "" {
		t.Errorf("空值缓存内容 = %q, want 空串", raw)
	}
}

func TestGetUserCacheTTL(t *testing.T) {
	db, _ := newUserDB()
	defer db.Close()
	rdb := newTestRedis(t)
	ctx := context.Background()
	rdb.FlushDB(ctx)

	if _, err := GetUser(ctx, db, rdb, 1); err != nil {
		t.Fatal(err)
	}
	ttl, _ := rdb.TTL(ctx, "user:1").Result()
	if ttl <= 0 || ttl > 11*time.Minute {
		t.Errorf("TTL = %v, 应在 (0, 11min]（10min + 抖动 ≤30s）", ttl)
	}
}

func TestInvalidateDeletesKey(t *testing.T) {
	db, _ := newUserDB()
	defer db.Close()
	rdb := newTestRedis(t)
	ctx := context.Background()
	rdb.FlushDB(ctx)

	if _, err := GetUser(ctx, db, rdb, 2); err != nil {
		t.Fatal(err)
	}
	if err := Invalidate(ctx, rdb, 2); err != nil {
		t.Fatal(err)
	}
	n, _ := rdb.Exists(ctx, "user:2").Result()
	if n != 0 {
		t.Error("删缓存后 key 应不存在")
	}
}
