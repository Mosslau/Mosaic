// 来源：ph10-database 练习 3 参考实现 —— Redis 缓存用户信息（旁路缓存）
// 一句话说明：读路径"先查缓存 → 未命中查 SQLite → 回填带 TTL"，写路径"删缓存"；
// errors.Is(err, redis.Nil) 区分"未命中"与"Redis 故障"（故障降级查库）、空值缓存防穿透、
// TTL 随机抖动防雪崩。Redis 地址 127.0.0.1:16379，测试不可达时自动跳过。
// 验证环境：go1.25.6（darwin/arm64），依赖：github.com/redis/go-redis/v9 v9.22.0、
// modernc.org/sqlite v1.57.0；Redis 127.0.0.1:16379（本机临时实例）
// 运行：
//
//	redis-server --port 16379 --save '' --appendonly no --daemonize yes   # 先起 Redis
//	go test -v ./...
//	go run .
//	redis-cli -p 16379 shutdown nosave                                    # 测完清理
//
// 验证状态：已验证（go1.25.6 + go-redis v9.22.0 + 本机 Redis 16379）
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
	_ "modernc.org/sqlite"
)

var redisAddr = "127.0.0.1:16379"

// User 用户信息
type User struct {
	ID       int64  `json:"id"`
	Username string `json:"username"`
}

// newUserDB 建 users 表并塞两条数据
func newUserDB() (*sql.DB, error) {
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		return nil, err
	}
	if _, err := db.Exec(`CREATE TABLE users (
		id INTEGER PRIMARY KEY, username TEXT NOT NULL, password TEXT NOT NULL)`); err != nil {
		db.Close()
		return nil, err
	}
	if _, err := db.Exec(`INSERT INTO users (username, password) VALUES ('alice','a'), ('bob','b')`); err != nil {
		db.Close()
		return nil, err
	}
	return db, nil
}

// GetUser 旁路缓存三件套
func GetUser(ctx context.Context, db *sql.DB, rdb *redis.Client, id int64) (*User, error) {
	key := fmt.Sprintf("user:%d", id)
	raw, err := rdb.Get(ctx, key).Result()
	if err == nil { // 缓存命中
		if raw == "" {
			return nil, sql.ErrNoRows // 空值缓存命中：判定"不存在"
		}
		var u User
		if json.Unmarshal([]byte(raw), &u) == nil {
			return &u, nil
		}
	} else if !errors.Is(err, redis.Nil) {
		// Redis 故障：降级查库（缓存不致命）——记日志后继续走下面的查库分支，
		// 与 examples/ex06-redis-cache 的降级策略一致；回填 Set 失败同样无害（错误被忽略）
		log.Printf("Redis 故障（%v），降级查库", err)
	}
	// 未命中：查库
	var u User
	if err := db.QueryRow("SELECT id, username FROM users WHERE id = ?", id).
		Scan(&u.ID, &u.Username); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			rdb.Set(ctx, key, "", 60*time.Second) // 空值缓存防穿透
		}
		return nil, err
	}
	// 回填：TTL 随机抖动防雪崩
	ttl := 10*time.Minute + time.Duration(id%30)*time.Second
	data, _ := json.Marshal(u)
	rdb.Set(ctx, key, data, ttl)
	return &u, nil
}

// Invalidate 写路径：删缓存
func Invalidate(ctx context.Context, rdb *redis.Client, id int64) error {
	return rdb.Del(ctx, fmt.Sprintf("user:%d", id)).Err()
}

func main() {
	ctx := context.Background()
	db, err := newUserDB()
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	rdb := redis.NewClient(&redis.Options{Addr: redisAddr})
	defer rdb.Close()
	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatal("Redis 不可达，请先启动: redis-server --port 16379 --save '' --appendonly no --daemonize yes")
	}
	u, _ := GetUser(ctx, db, rdb, 1) // 第一次：查库回填
	fmt.Println("用户:", u.Username)
	u2, _ := GetUser(ctx, db, rdb, 1) // 第二次：缓存命中
	fmt.Println("再次读取（缓存命中）:", u2.Username)
}
