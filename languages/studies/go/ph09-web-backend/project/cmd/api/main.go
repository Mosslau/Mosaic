// 来源：ph09-web-backend 阶段项目 —— 设备数据上报 API
// 一句话说明：可运行入口。预置设备数据（含设备密钥）→ 组装路由 → http.Server 显式超时
// + 信号优雅关闭。对应 Roadmap「设备数据上报 API」推荐项目。
// 验证环境：go1.25.6（darwin/arm64），仅标准库，go 1.22+（ServeMux 方法路由）
// 运行：
//
//	go run ./cmd/api              # 监听 127.0.0.1:18080
//	curl -s http://127.0.0.1:18080/healthz
//	# 认证拿 token（预置设备 car-001 密钥 sec-car-001）：
//	curl -s -X POST http://127.0.0.1:18080/api/devices/auth \
//	  -d '{"device_id":"car-001","secret":"sec-car-001"}'
//	# 带上返回的 token 上报：
//	curl -s -X POST http://127.0.0.1:18080/api/devices/car-001/report \
//	  -H "Authorization: Bearer <token>" -d '{"speed":88.5,"lat":31.2,"lng":121.5}'
//	# 只读查询无需鉴权：
//	curl -s http://127.0.0.1:18080/api/devices
//	# 退出：Ctrl-C（SIGINT）或 kill -TERM <pid>，观察优雅关闭日志
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"tenetlang/go/ph09-web-backend/project/internal/api"
	"tenetlang/go/ph09-web-backend/project/internal/device"
)

// jwtSecret 生产放环境变量并定期轮换（演示用固定值）
var jwtSecret = []byte("project-jwt-secret-change-me")

func main() {
	store := seedStore()
	addr := "127.0.0.1:18080"
	handler := api.NewHandler(store, jwtSecret, 10, time.Minute) // 每设备每分钟最多 10 次上报

	srv := &http.Server{
		Addr:              addr,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	go func() {
		log.Printf("设备数据上报 API 监听 http://%s", addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("服务异常退出: %v", err)
		}
	}()

	// 优雅关闭：等信号 → 停止接收新连接 → 给存量请求最多 10 秒
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

// seedStore 预置演示数据：三台设备 + 设备密钥（生产应走注册流程 + 数据库，见 ph10）
func seedStore() device.Store {
	return device.NewMemoryStore(
		device.Device{ID: "car-001", Status: "online", Speed: 60.5, Lat: 31.2304, Lng: 121.4737, Secret: "sec-car-001"},
		device.Device{ID: "car-002", Status: "offline", Speed: 0, Secret: "sec-car-002"},
		device.Device{ID: "car-003", Status: "online", Speed: 88.0, Lat: 30.2741, Lng: 120.1551, Secret: "sec-car-003"},
	)
}
