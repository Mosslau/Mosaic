// 来源：09-web-backend.md 第 6 章示例 2 —— 中间件组合
// 一句话说明：日志（状态码捕获）+ panic 恢复 + CORS + 固定窗口限流四个横切关注点
// 组成一个服务，演示 func(http.Handler) http.Handler 洋葱模型。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go run .
//	curl -s http://127.0.0.1:18080/ping
//	curl -s -i -X OPTIONS http://127.0.0.1:18080/ping   # 看 CORS 头
//	curl -s http://127.0.0.1:18080/boom                 # 看恢复中间件返回 500
//	seq 1 40 | xargs -I{} curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:18080/ping  # 限流 429
//
// 测试：
//
//	go test -v ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"log"
	"net"
	"net/http"
	"runtime/debug"
	"sync"
	"time"
)

func main() {
	handler := chain(newMux(),
		withLogging,
		withRecovery,
		withCORS,
		withRateLimit(30, time.Minute), // 每 IP 每窗口最多 30 次
	)

	addr := "127.0.0.1:18080"
	log.Printf("中间件示例监听 http://%s", addr)
	if err := http.ListenAndServe(addr, handler); err != nil {
		log.Fatal(err)
	}
}

// newMux 业务路由（演示用：ping + 故意 panic 的 /boom）
func newMux() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /ping", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("pong"))
	})
	mux.HandleFunc("GET /boom", func(w http.ResponseWriter, r *http.Request) {
		panic("故意触发 panic 演示恢复中间件")
	})
	return mux
}

// chain 洋葱模型组装器：按顺序从外到内包裹，先挂的先执行
func chain(h http.Handler, middlewares ...func(http.Handler) http.Handler) http.Handler {
	for i := len(middlewares) - 1; i >= 0; i-- {
		h = middlewares[i](h)
	}
	return h
}

// --- 中间件 1：请求日志 ---

// statusRecorder 包装 ResponseWriter 捕获状态码（net/http 不直接暴露）
type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *statusRecorder) WriteHeader(code int) {
	r.status = code
	r.ResponseWriter.WriteHeader(code)
}

func withLogging(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(rec, r) // 放行：执行后续中间件与最终 handler
		log.Printf("%s %s → %d (%s)", r.Method, r.URL.Path, rec.status, time.Since(start))
	})
}

// --- 中间件 2：panic 恢复 ---

func withRecovery(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if err := recover(); err != nil {
				log.Printf("panic 已恢复: %v\n%s", err, debug.Stack())
				http.Error(w, "internal server error", http.StatusInternalServerError)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

// --- 中间件 3：CORS ---

func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// 生产注意：Allow-Origin 按域名白名单回显，* 不能与 Allow-Credentials 并用
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if r.Method == http.MethodOptions { // 预检请求直接放行，不进入业务
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// --- 中间件 4：固定窗口限流（每 IP 每窗口 N 次） ---

type ipLimiter struct {
	mu     sync.Mutex
	hits   map[string][]time.Time // key: 客户端 IP → 最近请求时间戳
	limit  int
	window time.Duration
}

func newIPLimiter(limit int, window time.Duration) *ipLimiter {
	return &ipLimiter{hits: make(map[string][]time.Time), limit: limit, window: window}
}

// allow 判断 key 是否放行：窗口内的请求数 < limit 才放行并记录
func (l *ipLimiter) allow(key string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	cutoff := time.Now().Add(-l.window)
	kept := l.hits[key][:0]
	for _, t := range l.hits[key] {
		if t.After(cutoff) {
			kept = append(kept, t)
		}
	}
	l.hits[key] = kept
	if len(kept) >= l.limit {
		return false // 超限 → 429
	}
	l.hits[key] = append(l.hits[key], time.Now())
	return true
}

func withRateLimit(limit int, window time.Duration) func(http.Handler) http.Handler {
	limiter := newIPLimiter(limit, window)
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ip, _, err := net.SplitHostPort(r.RemoteAddr) // RemoteAddr 是 "ip:port"
			if err != nil {
				ip = r.RemoteAddr
			}
			if !limiter.allow(ip) {
				http.Error(w, "request too frequent", http.StatusTooManyRequests)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}
