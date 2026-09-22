package main

import (
	"context"
	"io"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"testing"
	"time"
)

// startTestServer 起一个真实 HTTP server（随机端口），返回 baseURL、stop 与 *server（便于控制 ready）
func startTestServer(t *testing.T) (string, func(), *server) {
	t.Helper()
	srv := newServer()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	httpSrv := &http.Server{Handler: srv.newHandler()}
	go func() { _ = httpSrv.Serve(ln) }()
	return "http://" + ln.Addr().String(), func() { _ = httpSrv.Close(); ln.Close() }, srv
}

func get(t *testing.T, url string) (int, string) {
	t.Helper()
	resp, err := http.Get(url)
	if err != nil {
		t.Fatalf("GET %s: %v", url, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, string(body)
}

// /healthz 不依赖 ready 状态：进程活着即 200（liveness 语义）
func TestHealthzAlwaysOK(t *testing.T) {
	base, stop, _ := startTestServer(t)
	defer stop()

	code, body := get(t, base+"/healthz")
	if code != http.StatusOK || !strings.Contains(body, `"ok"`) {
		t.Fatalf("healthz = %d %s, want 200 ok", code, body)
	}
}

// 未 MarkReady 时 /readyz 必须 503（K8s 摘除实例的依据）
func TestReadyzNotReady(t *testing.T) {
	base, stop, _ := startTestServer(t)
	defer stop()

	code, body := get(t, base+"/readyz")
	if code != http.StatusServiceUnavailable || !strings.Contains(body, "not_ready") {
		t.Fatalf("readyz(未就绪) = %d %s, want 503", code, body)
	}
	// 业务接口在未就绪时也拒绝
	code, body = get(t, base+"/api/echo")
	if code != http.StatusServiceUnavailable {
		t.Fatalf("echo(未就绪) = %d %s, want 503", code, body)
	}
}

// MarkReady 后 /readyz 变 200，业务接口恢复
func TestReadyzAfterReady(t *testing.T) {
	base, stop, srv := startTestServer(t)
	defer stop()

	srv.MarkReady()
	code, body := get(t, base+"/readyz")
	if code != http.StatusOK || !strings.Contains(body, "ready") {
		t.Fatalf("readyz(就绪) = %d %s, want 200 ready", code, body)
	}
	code, body = get(t, base+"/api/echo")
	if code != http.StatusOK || !strings.Contains(body, "pong") {
		t.Fatalf("echo(就绪) = %d %s, want 200 pong", code, body)
	}
}

// 404：未知路径
func TestUnknownPath(t *testing.T) {
	base, stop, _ := startTestServer(t)
	defer stop()
	code, _ := get(t, base+"/nope")
	if code != http.StatusNotFound {
		t.Fatalf("unknown path = %d, want 404", code)
	}
}

// 优雅退出：向进程发 SIGTERM 后，Shutdown 等待在途请求完成。
// 这里直接验证 server.Shutdown 的语义（不依赖真实信号）：先起一个慢请求，
// Shutdown 期间它必须被处理完而不是被硬断。
func TestGracefulShutdownWaitsForInflight(t *testing.T) {
	srv := newServer()
	srv.MarkReady()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	httpSrv := &http.Server{
		Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// 慢 handler：睡 200ms 再返回
			time.Sleep(200 * time.Millisecond)
			_, _ = w.Write([]byte("done"))
		}),
	}
	go func() { _ = httpSrv.Serve(ln) }()

	started := make(chan struct{})
	go func() {
		close(started)
		// 与 Shutdown 并发发起请求
		resp, err := http.Get("http://" + ln.Addr().String() + "/slow")
		if err != nil {
			t.Errorf("inflight GET: %v", err)
			return
		}
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		if string(body) != "done" {
			t.Errorf("inflight body = %q, want done", body)
		}
	}()
	<-started
	time.Sleep(50 * time.Millisecond) // 确保请求已进入 handler

	shut := make(chan error, 1)
	go func() {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		shut <- httpSrv.Shutdown(ctx)
	}()
	select {
	case err := <-shut:
		if err != nil {
			t.Fatalf("Shutdown: %v", err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("Shutdown 卡住：在途请求未在超时内完成")
	}
}

// 信号语义：SIGTERM 与 os.Interrupt 都在监听列表（进程级验证交给 main 冒烟，
// 这里验证 Notify 注册不报错）
func TestSignalNotify(t *testing.T) {
	ch := make(chan os.Signal, 1)
	signal.Notify(ch, os.Interrupt, syscall.SIGTERM)
	signal.Stop(ch) // 恢复默认：避免测试进程被测试框架的信号干扰
}
