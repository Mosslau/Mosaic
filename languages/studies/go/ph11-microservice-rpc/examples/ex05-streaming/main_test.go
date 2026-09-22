package main

import (
	"bufio"
	"encoding/json"
	"net"
	"strings"
	"testing"
	"time"
)

func startTestServer(t *testing.T) (addr string, stop func()) {
	t.Helper()
	addr, stop, err := startStreamServer()
	if err != nil {
		t.Fatalf("startStreamServer: %v", err)
	}
	return addr, stop
}

// TestServerStreaming 订阅 → ack → 5 条推送 → EOF（服务端关闭连接 = 流结束）
func TestServerStreaming(t *testing.T) {
	addr, stop := startTestServer(t)
	defer stop()
	acks, pushes, err := subscribe(addr, "car-001", 5)
	if err != nil {
		t.Fatalf("subscribe: %v", err)
	}
	if len(acks) != 1 {
		t.Fatalf("应收到 1 条 ack, got %d: %v", len(acks), acks)
	}
	if !strings.Contains(acks[0], `"id":1`) {
		t.Fatalf("ack 应回显 id=1: %s", acks[0])
	}
	if len(pushes) != 5 {
		t.Fatalf("应收到 5 条推送, got %d", len(pushes))
	}
	for i, p := range pushes {
		if p.DeviceID != "car-001" {
			t.Fatalf("推送 #%d device_id=%q, want car-001", i+1, p.DeviceID)
		}
		if i > 0 && p.Speed <= pushes[i-1].Speed {
			t.Fatalf("推送速度应递增（模拟实时遥测）: %v -> %v", pushes[i-1].Speed, p.Speed)
		}
	}
}

// TestNotificationNoID 推送报文必须是无 id 的通知（否则客户端会当响应处理）
func TestNotificationNoID(t *testing.T) {
	addr, stop := startTestServer(t)
	defer stop()
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	_ = json.NewEncoder(conn).Encode(map[string]any{
		"method": "DeviceService.Subscribe",
		"params": []any{SubscribeParams{DeviceID: "car-002"}},
		"id":     3,
	})
	scanner := bufio.NewScanner(conn)
	var notifications, responses int
	for scanner.Scan() {
		line := scanner.Text()
		if strings.Contains(line, `"method"`) && !strings.Contains(line, `"id"`) {
			notifications++
		} else if strings.Contains(line, `"id"`) {
			responses++
		}
		if notifications == 5 {
			break
		}
	}
	if notifications != 5 {
		t.Fatalf("应收到 5 条通知, got %d", notifications)
	}
	if responses != 1 {
		t.Fatalf("应恰好 1 条带 id 的响应（ack）, got %d", responses)
	}
}

// TestRequestResponseOnSameConn 同一连接先请求/响应（GetStatus）、再订阅，验证连接可复用
func TestRequestResponseOnSameConn(t *testing.T) {
	addr, stop := startTestServer(t)
	defer stop()
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	enc := json.NewEncoder(conn)

	// ① GetStatus（id=9）→ 收到 id=9 的响应
	if err := enc.Encode(map[string]any{"method": "DeviceService.GetStatus", "params": []any{}, "id": 9}); err != nil {
		t.Fatal(err)
	}
	reader := bufio.NewReader(conn)
	line, err := reader.ReadString('\n')
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(line, `"id":9`) || !strings.Contains(line, "running") {
		t.Fatalf("GetStatus 响应异常: %s", line)
	}

	// ② 同一连接上再发订阅 → 收到 ack + 推送
	if err := enc.Encode(map[string]any{"method": "DeviceService.Subscribe", "params": []any{SubscribeParams{DeviceID: "bus-01"}}, "id": 4}); err != nil {
		t.Fatal(err)
	}
	var gotPush bool
	for i := 0; i < 6; i++ {
		line, err := reader.ReadString('\n')
		if err != nil {
			break // EOF = 服务端关闭
		}
		if strings.Contains(line, `"device_id":"bus-01"`) {
			gotPush = true
		}
	}
	if !gotPush {
		t.Fatal("同一连接复用后应能收到订阅推送")
	}
}

// TestSubscribePartial 客户端主动收 2 条就断开（流的生命周期由业务决定）
func TestSubscribePartial(t *testing.T) {
	addr, stop := startTestServer(t)
	defer stop()
	_, pushes, err := subscribe(addr, "car-003", 2)
	if err != nil {
		t.Fatalf("subscribe: %v", err)
	}
	if len(pushes) != 2 {
		t.Fatalf("应只收 2 条, got %d", len(pushes))
	}
}

// TestStreamingTimeout 服务端 150ms 一条、共 5 条 ≈ 750ms，不应超过 3s（防死锁回归）
func TestStreamingTimeout(t *testing.T) {
	addr, stop := startTestServer(t)
	defer stop()
	done := make(chan struct{})
	go func() {
		_, _, _ = subscribe(addr, "car-004", 5)
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(3 * time.Second):
		t.Fatal("订阅流超过 3s 未完成，疑似阻塞")
	}
}
