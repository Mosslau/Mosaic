// 来源：ph11-microservice-rpc 示例 5 —— 流式概念（JSON-RPC 通知流演示"服务端流"）
// 一句话说明：net/rpc 只支持"请求/响应"（一发一收），没有原生流式模式；本示例用
// JSON-RPC 2.0 的"通知（notification，无 id）"在一条持久 TCP 连接上模拟服务端流——
// 服务端持续推送设备状态消息，客户端循环读取直到 EOF，消息边界用换行分隔。
// 流式是传输层概念：gRPC 的四种模式（一元/服务端流/客户端流/双向流）见阶段笔记 3.1/4.3，
// 本示例演示其底层形态"同一连接上连续的多条消息"。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go run .            # 单进程演示：订阅设备状态流，收 5 条推送后 EOF
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"strings"
	"time"
)

// ---- wire 报文结构（JSON-RPC 2.0 简化版）----

// request 请求：有 id 期待响应；无 id 即通知（notification）
type request struct {
	Method string          `json:"method"`
	Params json.RawMessage `json:"params"`
	ID     *uint64         `json:"id"` // 指针：null/缺省 = 通知
}

// response 响应：回显 id
type response struct {
	ID     uint64 `json:"id"`
	Result any    `json:"result"`
	Error  any    `json:"error"`
}

// notification 服务端推送：无 id（通知语义，不需要回复）
type notification struct {
	Method string `json:"method"`
	Params any    `json:"params"`
}

type DeviceStatus struct {
	DeviceID string  `json:"device_id"`
	Speed    float64 `json:"speed"`
	Ts       int64   `json:"ts"`
}

type SubscribeParams struct{ DeviceID string }

// ---- 服务端：手写 JSON-RPC 2.0 + 服务端推送 ----

// handleConn 处理一条客户端连接：循环读请求；Subscribe 方法先回 ack，再推送 N 条通知后关闭连接
func handleConn(conn net.Conn) {
	defer conn.Close()
	dec := json.NewDecoder(conn)
	enc := json.NewEncoder(conn)
	for {
		var req request
		if err := dec.Decode(&req); err != nil {
			return // 客户端关闭 / 报文损坏 → 结束连接（对客户端来说就是 EOF = 流结束）
		}
		switch req.Method {
		case "DeviceService.Subscribe":
			// JSON-RPC 的 params 是数组（net/rpc/jsonrpc 也是"数组包单参数"），先解包再解析
			var params [1]SubscribeParams
			if err := json.Unmarshal(req.Params, &params); err != nil {
				return
			}
			p := params[0]
			if req.ID != nil {
				// 先回 ack（带 id 的普通响应），告诉客户端流已建立
				_ = enc.Encode(response{ID: *req.ID, Result: map[string]bool{"ok": true}, Error: nil})
			}
			// 服务端流：连续推送 5 条通知（无 id → 客户端不回复），推完关闭连接
			for i := 1; i <= 5; i++ {
				msg := notification{
					Method: "device.push",
					Params: DeviceStatus{
						DeviceID: p.DeviceID,
						Speed:    float64(60 + i*7),
						Ts:       time.Now().Unix(),
					},
				}
				if err := enc.Encode(msg); err != nil {
					return
				}
				time.Sleep(150 * time.Millisecond) // 模拟实时遥测节奏
			}
			return // 流结束：服务端关闭连接 → 客户端读到 EOF
		case "DeviceService.GetStatus": // 同一连接上的普通请求/响应（演示连接复用）
			if req.ID == nil {
				continue // 通知不需要响应
			}
			_ = enc.Encode(response{
				ID:     *req.ID,
				Result: map[string]string{"status": "running"},
				Error:  nil,
			})
		default:
			if req.ID == nil {
				continue
			}
			_ = enc.Encode(response{ID: *req.ID, Result: nil, Error: "unknown method: " + req.Method})
		}
	}
}

func startStreamServer() (addr string, stop func(), err error) {
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", nil, err
	}
	go func() {
		for {
			conn, err := lis.Accept()
			if err != nil {
				return
			}
			go handleConn(conn)
		}
	}()
	return lis.Addr().String(), func() { lis.Close() }, nil
}

// ---- 客户端：订阅 + 循环读流 ----

// subscribe 建立订阅：发 Subscribe 请求（带 id），收 ack，然后循环读通知直到 EOF
// 返回 ack 之后收到的全部通知消息
func subscribe(addr, deviceID string, want int) (acks []string, pushes []DeviceStatus, err error) {
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		return nil, nil, err
	}
	defer conn.Close()

	// ① 发订阅请求（带 id=1：期待 ack）
	req := map[string]any{"method": "DeviceService.Subscribe", "params": []any{SubscribeParams{DeviceID: deviceID}}, "id": 1}
	if err := json.NewEncoder(conn).Encode(req); err != nil {
		return nil, nil, err
	}

	// ② 循环读：有 id 的是 ack/响应，无 id 的是服务端推送；EOF = 流结束
	scanner := bufio.NewScanner(conn)
	for scanner.Scan() {
		line := scanner.Bytes()
		if strings.Contains(string(line), `"method"`) && !strings.Contains(string(line), `"id"`) {
			// 通知（无 id）：服务端推送的设备状态
			var n struct {
				Params DeviceStatus `json:"params"`
			}
			if err := json.Unmarshal(line, &n); err != nil {
				return nil, nil, err
			}
			pushes = append(pushes, n.Params)
			if len(pushes) >= want {
				break // 收够了就主动断开（流的生命周期由业务决定）
			}
			continue
		}
		acks = append(acks, string(line)) // 带 id 的响应：ack
	}
	if err := scanner.Err(); err != nil && err != io.EOF {
		return nil, nil, err
	}
	return acks, pushes, nil
}

func main() {
	addr, stop, err := startStreamServer()
	if err != nil {
		log.Fatal(err)
	}
	defer stop()

	acks, pushes, err := subscribe(addr, "car-001", 5)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("ack: %s\n", strings.Join(acks, " "))
	fmt.Printf("收到 %d 条服务端推送:\n", len(pushes))
	for i, p := range pushes {
		fmt.Printf("  #%d device=%s speed=%.0f ts=%d\n", i+1, p.DeviceID, p.Speed, p.Ts)
	}

	// 同一连接上的普通请求/响应（连接复用演示）
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()
	_ = json.NewEncoder(conn).Encode(map[string]any{"method": "DeviceService.GetStatus", "params": []any{}, "id": 9})
	resp, err := bufio.NewReader(conn).ReadString('\n')
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("GetStatus 响应: %s", resp)
}
