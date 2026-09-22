// 来源：ph11-microservice-rpc 练习 3 参考实现 —— 设备管理服务（流式上报 + 限流）
// 一句话说明：roadmap「设备管理服务」练习——服务端令牌桶限流的上报接口（超限拒绝）+
// 基于 JSON-RPC 通知的服务端流推送（设备状态订阅）；客户端分别演示两种交互方式。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .
//
// 验证状态：已验证（go1.25.6）
// 覆盖率：go test -cover 实测 **73.8%**（go1.25.6，6 个用例全过，含限流拒绝/补桶恢复/流推送）
package main

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net"
	"strings"
	"sync/atomic"
	"time"
)

// ---- 令牌桶限流（简化版：refill 间隔把桶补满；生产用 golang.org/x/time/rate 的增量令牌桶）----

type tokenBucket struct {
	capacity int64
	tokens   atomic.Int64
}

// newTokenBucket 每 refill 间隔把令牌补满 capacity 个
func newTokenBucket(capacity int64, refill time.Duration) *tokenBucket {
	b := &tokenBucket{capacity: capacity}
	b.tokens.Store(capacity)
	go func() {
		ticker := time.NewTicker(refill)
		defer ticker.Stop() // 避免 time.Tick 的 ticker 无法停止（goroutine 泄漏）
		for range ticker.C {
			b.tokens.Store(b.capacity)
		}
	}()
	return b
}

// allow 原子扣一个令牌；无令牌返回 false
func (b *tokenBucket) allow() bool {
	for {
		t := b.tokens.Load()
		if t <= 0 {
			return false
		}
		if b.tokens.CompareAndSwap(t, t-1) {
			return true
		}
	}
}

// ---- wire 报文（JSON-RPC 2.0 简化版，同示例 5）----

type request struct {
	Method string          `json:"method"`
	Params json.RawMessage `json:"params"`
	ID     *uint64         `json:"id"`
}

type response struct {
	ID     uint64 `json:"id"`
	Result any    `json:"result"`
	Error  any    `json:"error"`
}

type notification struct {
	Method string `json:"method"`
	Params any    `json:"params"`
}

type DeviceStatus struct {
	DeviceID string  `json:"device_id"`
	Speed    float64 `json:"speed"`
	Ts       int64   `json:"ts"`
}

// ---- 设备管理服务（手写 JSON-RPC 服务端，同示例 5）----

type deviceServer struct {
	bucket *tokenBucket
}

// handleConn 处理一条连接：ReportStatus 走限流 + 响应；Subscribe 先 ack 再推送 5 条通知
func (d *deviceServer) handleConn(conn net.Conn) {
	defer conn.Close()
	dec := json.NewDecoder(conn)
	enc := json.NewEncoder(conn)
	for {
		var req request
		if err := dec.Decode(&req); err != nil {
			return
		}
		switch req.Method {
		case "DeviceService.ReportStatus":
			var params [1]DeviceStatus // JSON-RPC params 是数组
			if err := json.Unmarshal(req.Params, &params); err != nil {
				return
			}
			st := params[0]
			if req.ID == nil {
				continue
			}
			if !d.bucket.allow() { // 限流：超限拒绝（对应 gRPC 的 ResourceExhausted/HTTP 429）
				_ = enc.Encode(response{ID: *req.ID, Result: nil, Error: "rate limited"})
				continue
			}
			_ = enc.Encode(response{ID: *req.ID, Result: map[string]any{"ok": true, "device_id": st.DeviceID}, Error: nil})
		case "DeviceService.Subscribe":
			var params [1]DeviceStatus
			if err := json.Unmarshal(req.Params, &params); err != nil {
				return
			}
			deviceID := params[0].DeviceID
			if req.ID != nil {
				_ = enc.Encode(response{ID: *req.ID, Result: map[string]bool{"ok": true}, Error: nil})
			}
			// 服务端流：推 5 条通知（无 id）后关闭连接（EOF = 流结束）
			for i := 1; i <= 5; i++ {
				msg := notification{
					Method: "device.push",
					Params: DeviceStatus{DeviceID: deviceID, Speed: float64(50 + i*6), Ts: time.Now().Unix()},
				}
				if err := enc.Encode(msg); err != nil {
					return
				}
				time.Sleep(100 * time.Millisecond)
			}
			return
		default:
			if req.ID == nil {
				continue
			}
			_ = enc.Encode(response{ID: *req.ID, Result: nil, Error: "unknown method: " + req.Method})
		}
	}
}

func startServer(rate int64, refill time.Duration) (addr string, stop func(), err error) {
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", nil, err
	}
	d := &deviceServer{bucket: newTokenBucket(rate, refill)}
	go func() {
		for {
			conn, err := lis.Accept()
			if err != nil {
				return
			}
			go d.handleConn(conn)
		}
	}()
	return lis.Addr().String(), func() { lis.Close() }, nil
}

// ---- 客户端 ----

// reportStatus 上报一次设备状态；超限返回包含 "rate limited" 的错误
func reportStatus(addr string, st DeviceStatus) (string, error) {
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		return "", err
	}
	defer conn.Close()
	req := map[string]any{"method": "DeviceService.ReportStatus", "params": []any{st}, "id": uint64(time.Now().UnixNano())}
	if err := json.NewEncoder(conn).Encode(req); err != nil {
		return "", err
	}
	resp, err := bufio.NewReader(conn).ReadString('\n')
	if err != nil {
		return "", err
	}
	if strings.Contains(resp, `"error"`) && !strings.Contains(resp, `"error":null`) {
		var e struct {
			Error string `json:"error"`
		}
		_ = json.Unmarshal([]byte(resp), &e)
		return "", errors.New(e.Error)
	}
	return resp, nil
}

// subscribe 订阅设备状态流：收 want 条通知（同示例 5）
func subscribe(addr, deviceID string, want int) ([]DeviceStatus, error) {
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		return nil, err
	}
	defer conn.Close()
	req := map[string]any{"method": "DeviceService.Subscribe", "params": []any{DeviceStatus{DeviceID: deviceID}}, "id": 1}
	if err := json.NewEncoder(conn).Encode(req); err != nil {
		return nil, err
	}
	var pushes []DeviceStatus
	scanner := bufio.NewScanner(conn)
	for scanner.Scan() {
		line := scanner.Bytes()
		if strings.Contains(string(line), `"method"`) && !strings.Contains(string(line), `"id"`) {
			var n struct {
				Params DeviceStatus `json:"params"`
			}
			if err := json.Unmarshal(line, &n); err != nil {
				return nil, err
			}
			pushes = append(pushes, n.Params)
			if len(pushes) >= want {
				break
			}
		}
	}
	return pushes, scanner.Err()
}

func main() {
	addr, stop, err := startServer(3, time.Second) // 限流 3 次/秒
	if err != nil {
		log.Fatal(err)
	}
	defer stop()

	// ① 限流：第 1~3 次成功，第 4 次被拒（rate limited）
	fmt.Println("① 上报限流（3 次/秒）:")
	for i := 1; i <= 4; i++ {
		_, err := reportStatus(addr, DeviceStatus{DeviceID: "car-001", Speed: float64(60 + i)})
		if err != nil {
			fmt.Printf("   第 %d 次上报 -> 拒绝: %v\n", i, err)
		} else {
			fmt.Printf("   第 %d 次上报 -> ok\n", i)
		}
	}

	// ② 服务端流：订阅设备状态
	fmt.Println("② 订阅设备状态流:")
	pushes, err := subscribe(addr, "car-002", 5)
	if err != nil {
		log.Fatal(err)
	}
	for i, p := range pushes {
		fmt.Printf("   #%d device=%s speed=%.0f\n", i+1, p.DeviceID, p.Speed)
	}
}
