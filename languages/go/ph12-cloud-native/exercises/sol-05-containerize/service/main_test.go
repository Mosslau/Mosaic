package main

import (
	"io"
	"net"
	"net/http"
	"strings"
	"testing"
)

func start(t *testing.T) (string, func(), *server) {
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

func TestHealthz(t *testing.T) {
	base, stop, _ := start(t)
	defer stop()
	code, body := get(t, base+"/healthz")
	if code != http.StatusOK || !strings.Contains(body, "ok") {
		t.Fatalf("healthz = %d %s", code, body)
	}
}

func TestReadyzTransition(t *testing.T) {
	base, stop, srv := start(t)
	defer stop()
	code, body := get(t, base+"/readyz")
	if code != http.StatusServiceUnavailable || !strings.Contains(body, "not_ready") {
		t.Fatalf("未就绪: %d %s", code, body)
	}
	code, _ = get(t, base+"/api/ping")
	if code != http.StatusServiceUnavailable {
		t.Fatalf("ping 未就绪: %d", code)
	}
	srv.MarkReady()
	code, body = get(t, base+"/readyz")
	if code != http.StatusOK || !strings.Contains(body, "ready") {
		t.Fatalf("就绪: %d %s", code, body)
	}
	code, _ = get(t, base+"/api/ping")
	if code != http.StatusOK {
		t.Fatalf("ping 就绪: %d", code)
	}
}
