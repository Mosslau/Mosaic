// 来源：ph10-database 阶段项目 —— 车辆轨迹存储服务（cmd/api 入口）
// 一句话说明：组装 Store（SQLite）+ Cache（Redis，故障降级内存缓存）+ HTTP 路由，
// http.Server 显式超时 + SIGINT/SIGTERM 优雅关闭（ph09 ex06 模式延续）。
// 验证环境：go1.25.6（darwin/arm64），依赖：modernc.org/sqlite v1.57.0、
// github.com/redis/go-redis/v9 v9.22.0；Redis 127.0.0.1:16379（可选，故障降级内存缓存）
// 运行：
//
//	go build ./...
//	go run ./cmd/api -addr 127.0.0.1:18080
//	# 冒烟：curl -s http://127.0.0.1:18080/healthz
//	#   curl -s -X POST http://127.0.0.1:18080/api/devices/car-001/points \
//	#     -d '{"points":[{"lat":31.1,"lng":121.2,"speed":60,"ts":"2025-01-01T00:00:00Z"}]}'
//	#   curl -s http://127.0.0.1:18080/api/devices/car-001/latest
//	#   curl -s "http://127.0.0.1:18080/api/devices/car-001/trajectory?from=2025-01-01T00:00:00Z&to=2025-01-01T01:00:00Z"
//
// 验证状态：已验证（go1.25.6；冒烟见 project/README.md 实测记录）
package main

import (
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"tenetlang/go/ph10-database/project/internal/api"
	"tenetlang/go/ph10-database/project/internal/cache"
	"tenetlang/go/ph10-database/project/internal/store"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:18080", "监听地址")
	dbPath := flag.String("db", "/tmp/vehicle-trajectory.db", "SQLite 数据库文件路径")
	redisAddr := flag.String("redis", "127.0.0.1:16379", "Redis 地址（不可达时自动降级内存缓存）")
	flag.Parse()

	// 1. 存储层：SQLite（busy_timeout + WAL，见 store 包）
	s, err := store.Open(*dbPath)
	if err != nil {
		log.Fatalf("打开数据库失败: %v", err)
	}
	defer s.Close()

	// 2. 缓存层：优先 Redis，探测失败降级内存缓存（缓存不致命，呼应 3.9）
	var c cache.Cache
	if rc := cache.NewRedis(*redisAddr); pingRedis(*redisAddr) {
		c = rc
		log.Printf("缓存: Redis %s", *redisAddr)
	} else {
		c = cache.NewMemory()
		log.Printf("缓存: Redis 不可达，降级内存缓存")
	}

	// 3. HTTP 层：显式超时（ph09 ex06 模式）
	srv := &http.Server{
		Addr:              *addr,
		Handler:           api.NewHandler(api.NewService(s, c)),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	// 4. 优雅关闭：等信号 → 停止接收新连接 → 给存量请求 10 秒
	go func() {
		log.Printf("车辆轨迹存储服务监听 %s（健康检查 GET /healthz）", *addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("服务异常退出: %v", err)
		}
	}()
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)
	<-quit
	log.Println("收到退出信号，开始优雅关闭…")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Fatalf("优雅关闭超时，强制退出: %v", err)
	}
	log.Println("所有连接已处理完毕，服务退出")
}

// pingRedis 探活（2 秒超时）
func pingRedis(addr string) bool {
	rc := cache.NewRedis(addr)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	// 通过类型断言拿到底层 client 做 Ping（cache 接口不暴露探活）
	type pinger interface {
		Ping(ctx context.Context) error
	}
	if p, ok := rc.(pinger); ok {
		return p.Ping(ctx) == nil
	}
	return false
}
