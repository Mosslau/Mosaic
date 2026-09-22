// 来源：09-web-backend.md 第 6 章示例 6 —— 优雅关闭与超时
// 一句话说明：http.Server 显式超时（ReadHeader/Read/Write/Idle）+ 信号监听
// （SIGINT/SIGTERM）+ srv.Shutdown(ctx) 优雅关闭：先停止接收新连接、等存量请求处理完再退出。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行（冒烟验证步骤）：
//
//	# 1. 启动（前台）：
//	go run .                    # 或：go build -o /tmp/shutdown-example . && /tmp/shutdown-example
//	# 2. 另开终端：
//	curl -s http://127.0.0.1:18081/healthz      # → ok
//	# 3. 对服务进程发退出信号（Ctrl-C 或 kill -TERM <pid>），观察日志：
//	#    收到退出信号，开始优雅关闭… → 所有连接已处理完毕，服务退出（退出码 0）
//
// 冒烟测试（脚本化，验证后进程自动退出、不留残留）：
//
//	go build -o /tmp/shutdown-example .
//	/tmp/shutdown-example & echo $! > /tmp/shutdown-example.pid
//	sleep 0.5; curl -s http://127.0.0.1:18081/healthz
//	kill -TERM $(cat /tmp/shutdown-example.pid); wait $(cat /tmp/shutdown-example.pid); echo "exit=$?"
//	rm -f /tmp/shutdown-example /tmp/shutdown-example.pid
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
)

func main() {
	addr := "127.0.0.1:18081"
	srv := buildServer(addr)

	// ListenAndServe 在独立 goroutine 跑，主 goroutine 等信号
	go func() {
		log.Printf("服务监听 http://%s", addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("服务异常退出: %v", err)
		}
	}()

	// 监听退出信号（Ctrl-C 发 SIGINT；kill -TERM 发 SIGTERM；容器/编排平台常用 SIGTERM）
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)
	<-quit
	log.Println("收到退出信号，开始优雅关闭…")

	// 给存量请求最多 10 秒处理时间；超时未完成则强制退出
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Fatalf("优雅关闭超时，强制退出: %v", err)
	}
	log.Println("所有连接已处理完毕，服务退出")
}

// buildServer 显式超时配置——生产服务必设，防慢客户端拖死连接（ph07 已提，这里给完整版）
func buildServer(addr string) *http.Server {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("ok"))
	})
	return &http.Server{
		Addr:              addr,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,  // 读请求头超时（必设，防 Slowloris）
		ReadTimeout:       10 * time.Second, // 读完整请求体超时
		WriteTimeout:      10 * time.Second, // 写响应超时
		IdleTimeout:       60 * time.Second, // keep-alive 空闲连接超时
	}
}
