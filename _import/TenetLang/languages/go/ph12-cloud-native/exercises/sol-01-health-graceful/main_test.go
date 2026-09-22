package main

import (
	"context"
	"io"
	"log/slog"
	"net"
	"net/http"
	"os"
	"strings"
	"syscall"
	"testing"
	"time"
)

// startTest 起真实 server（随机端口），返回 baseURL、stop、server（控制 ready）
func startTest(t *testing.T) (string, func(), *server) {
	t.Helper()
	srv := newServer()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	httpSrv := &http.Server{Handler: srv.newHandler()}
	go func() { _ = httpSrv.Serve(ln) }()
	return "http://" + ln.Addr().String(), func() { _ = httpSrv.Close() }, srv
}

func get(t *testing.T, url string) (int, string) {
	t.Helper()
	resp, err := http.Get(url)
	if err != nil {
		t.Fatalf("GET %s: %v", url, err)
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, string(b)
}

func TestHealthzAlwaysOK(t *testing.T) {
	base, stop, _ := startTest(t)
	defer stop()
	code, body := get(t, base+"/healthz")
	if code != http.StatusOK || !strings.Contains(body, "ok") {
		t.Fatalf("healthz = %d %s", code, body)
	}
}

func TestReadyzBeforeReady(t *testing.T) {
	base, stop, _ := startTest(t)
	defer stop()
	code, body := get(t, base+"/readyz")
	if code != http.StatusServiceUnavailable || !strings.Contains(body, "not_ready") {
		t.Fatalf("readyz(未就绪) = %d %s, want 503", code, body)
	}
	// 业务接口口径一致
	code, _ = get(t, base+"/api/ping")
	if code != http.StatusServiceUnavailable {
		t.Fatalf("ping(未就绪) = %d, want 503", code)
	}
}

func TestReadyzAfterReady(t *testing.T) {
	base, stop, srv := startTest(t)
	defer stop()
	srv.MarkReady()
	code, body := get(t, base+"/readyz")
	if code != http.StatusOK || !strings.Contains(body, "ready") {
		t.Fatalf("readyz(就绪) = %d %s", code, body)
	}
	code, body = get(t, base+"/api/ping")
	if code != http.StatusOK || !strings.Contains(body, "pong") {
		t.Fatalf("ping(就绪) = %d %s", code, body)
	}
}

// 优雅退出：Shutdown 等待在途请求完成，不硬断
func TestShutdownWaitsForInflight(t *testing.T) {
	srv := newServer()
	srv.MarkReady()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	httpSrv := &http.Server{
		Handler: http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			time.Sleep(200 * time.Millisecond) // 慢 handler
			_, _ = w.Write([]byte("done"))
		}),
	}
	go func() { _ = httpSrv.Serve(ln) }()

	started := make(chan struct{})
	go func() {
		close(started)
		resp, err := http.Get("http://" + ln.Addr().String() + "/slow")
		if err != nil {
			t.Errorf("inflight GET: %v", err)
			return
		}
		defer resp.Body.Close()
		b, _ := io.ReadAll(resp.Body)
		if string(b) != "done" {
			t.Errorf("body = %q, want done", b)
		}
	}()
	<-started
	time.Sleep(50 * time.Millisecond)

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
		t.Fatal("Shutdown 卡住")
	}
}

// run 的信号路径：收到信号 → 优雅退出返回 nil
func TestRunExitsOnSignal(t *testing.T) {
	logger := slog.New(slog.NewJSONHandler(io.Discard, nil))
	sigCh := make(chan os.Signal, 1)
	go func() {
		time.Sleep(300 * time.Millisecond)
		sigCh <- syscall.SIGTERM // 注入信号，模拟 kill -TERM
	}()
	if err := run(logger, "127.0.0.1:0", sigCh); err != nil {
		t.Fatalf("run: %v", err)
	}
}

func TestUnknownPath(t *testing.T) {
	base, stop, _ := startTest(t)
	defer stop()
	code, _ := get(t, base+"/nope")
	if code != http.StatusNotFound {
		t.Fatalf("unknown = %d, want 404", code)
	}
}
