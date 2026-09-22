package main

import (
	"bufio"
	"encoding/json"
	"net"
	"strings"
	"testing"
	"time"
)

// rawCall 发一条裸 JSON-RPC 请求（params 为 nil 时发空数组），返回响应行
func rawCall(addr, method string, params any) (string, error) {
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		return "", err
	}
	defer conn.Close()
	p := params
	if p == nil {
		p = []any{}
	}
	req := map[string]any{"method": method, "params": p, "id": 1}
	if err := json.NewEncoder(conn).Encode(req); err != nil {
		return "", err
	}
	return bufio.NewReader(conn).ReadString('\n')
}

// TestRateLimitAllowance 限流内允许：rate=3，前 3 次成功
func TestRateLimitAllowance(t *testing.T) {
	addr, stop, err := startServer(3, time.Hour) // refill 极长：桶不会中途补满
	if err != nil {
		t.Fatal(err)
	}
	defer stop()
	for i := 1; i <= 3; i++ {
		if _, err := reportStatus(addr, DeviceStatus{DeviceID: "car-001", Speed: 60}); err != nil {
			t.Fatalf("第 %d 次应在限流内: %v", i, err)
		}
	}
}

// TestRateLimitRejects 第 4 次被拒绝
func TestRateLimitRejects(t *testing.T) {
	addr, stop, err := startServer(3, time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	defer stop()
	for i := 1; i <= 3; i++ {
		if _, err := reportStatus(addr, DeviceStatus{DeviceID: "car-001", Speed: 60}); err != nil {
			t.Fatal(err)
		}
	}
	_, err = reportStatus(addr, DeviceStatus{DeviceID: "car-001", Speed: 60})
	if err == nil || !strings.Contains(err.Error(), "rate limited") {
		t.Fatalf("第 4 次应被限流拒绝, got %v", err)
	}
}

// TestRateLimitRefill 补桶后恢复：refill 100ms，等 200ms 后可再次上报
func TestRateLimitRefill(t *testing.T) {
	addr, stop, err := startServer(2, 100*time.Millisecond)
	if err != nil {
		t.Fatal(err)
	}
	defer stop()
	if _, err := reportStatus(addr, DeviceStatus{DeviceID: "d", Speed: 1}); err != nil {
		t.Fatal(err)
	}
	if _, err := reportStatus(addr, DeviceStatus{DeviceID: "d", Speed: 1}); err != nil {
		t.Fatal(err)
	}
	if _, err := reportStatus(addr, DeviceStatus{DeviceID: "d", Speed: 1}); err == nil {
		t.Fatal("第 3 次应被限流")
	}
	time.Sleep(250 * time.Millisecond) // 桶已补满
	if _, err := reportStatus(addr, DeviceStatus{DeviceID: "d", Speed: 1}); err != nil {
		t.Fatalf("补桶后应恢复: %v", err)
	}
}

// TestSubscribeStream 订阅流：收 5 条设备状态推送
func TestSubscribeStream(t *testing.T) {
	addr, stop, err := startServer(10, time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	defer stop()
	pushes, err := subscribe(addr, "car-007", 5)
	if err != nil {
		t.Fatalf("subscribe: %v", err)
	}
	if len(pushes) != 5 {
		t.Fatalf("应收 5 条, got %d", len(pushes))
	}
	for i, p := range pushes {
		if p.DeviceID != "car-007" {
			t.Fatalf("推送 #%d device=%q, want car-007", i+1, p.DeviceID)
		}
		if p.Speed <= 0 {
			t.Fatalf("推送 #%d speed 异常: %v", i+1, p.Speed)
		}
	}
}

// TestReportThenSubscribe 上报与订阅在同一服务上共存
func TestReportThenSubscribe(t *testing.T) {
	addr, stop, err := startServer(5, time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	defer stop()
	if _, err := reportStatus(addr, DeviceStatus{DeviceID: "bus-01", Speed: 30}); err != nil {
		t.Fatal(err)
	}
	pushes, err := subscribe(addr, "bus-01", 5)
	if err != nil {
		t.Fatal(err)
	}
	if len(pushes) != 5 {
		t.Fatalf("订阅应正常, got %d 条", len(pushes))
	}
}

// TestUnknownMethod 未知方法返回错误
func TestUnknownMethod(t *testing.T) {
	addr, stop, err := startServer(5, time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	defer stop()
	resp, err := rawCall(addr, "DeviceService.Nope", nil)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(resp, "unknown method") {
		t.Fatalf("未知方法应报错: %s", resp)
	}
}
