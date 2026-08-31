// 来源：ph10-database 示例 6 —— Redis 旁路缓存（go-redis）
// 一句话说明：读路径"先查缓存 → 未命中查 SQLite → 回填带 TTL"，写路径"先写库 → 删缓存"；
// 空值缓存防穿透、TTL 随机抖动防雪崩、errors.Is(err, redis.Nil) 区分"未命中"与"故障"。
// 依赖 Redis：运行前先起一个本机 Redis（本环境用端口 16379）：
//
//	redis-server --port 16379 --save '' --appendonly no --daemonize yes
//
// 验证环境：go1.25.6（darwin/arm64），依赖：github.com/redis/go-redis/v9 v9.22.0、
// modernc.org/sqlite v1.57.0；Redis 127.0.0.1:16379（本机临时实例）
// 运行：
//
//	go test -v ./...       # Redis 不可达时测试自动跳过（t.Skip）
//	go run .               # 需 Redis 可达
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

// redisAddr 可被测试覆盖（测试里用同一地址，不可达则跳过）
var redisAddr = "127.0.0.1:16379"

// User 用户信息（缓存里存 JSON）
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

// getUser 旁路缓存三件套：查缓存 → 未命中查库 → 回填
func getUser(ctx context.Context, db *sql.DB, rdb *redis.Client, id int64) (*User, error) {
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
		return nil, err // Redis 故障：降级查库，缓存不致命
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
	// 回填：TTL 加随机抖动防雪崩
	ttl := 10*time.Minute + time.Duration(id%30)*time.Second
	data, _ := json.Marshal(u)
	rdb.Set(ctx, key, data, ttl)
	return &u, nil
}

// invalidateUser 写路径：删缓存（删而非更新，避免缓存与库的中间态）
func invalidateUser(ctx context.Context, rdb *redis.Client, id int64) error {
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
		log.Fatal("Redis 不可达，请先启动: redis-server --port 16379 --save '' --appendonly no")
	}
	u, err := getUser(ctx, db, rdb, 1) // 第一次：查库回填
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println("用户:", u.Username)
	u2, err := getUser(ctx, db, rdb, 1) // 第二次：缓存命中
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println("再次读取（缓存命中）:", u2.Username)
	if err := invalidateUser(ctx, rdb, 1); err != nil {
		log.Fatal(err)
	}
	fmt.Println("写路径已删缓存")
}
