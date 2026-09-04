// 来源：ph21-iot-vehicle-edge examples/ex03-websocket-shadow/main.go
// 一句话说明：演示主程序——起影子中枢；模拟"面板订阅 + 车端上报 + 云侧下发 desired"
// 三方实时链路：设备上线收到 connected(含 desired)、上报 reported 后面板收到带版本
// 的 snapshot 推送、云侧 SetDesired 后设备收到 desired 且面板同步新快照。
// 用法：go run . -addr 127.0.0.1:18880
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（127.0.0.1 真 TCP 帧级收发实测，输出见下方预期）
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"time"
)

// recvLoop 打印收到的文本帧（面板/设备共用；心跳帧由 readMessage 分发层应答）。
func recvLoop(c *Conn, who string, done chan<- string) {
	for {
		opcode, payload, err := c.ReadMessage()
		if err != nil {
			done <- who + ": 连接结束"
			return
		}
		switch opcode {
		case opText, opBinary:
			done <- who + ": " + string(payload)
		case opPing:
			_ = c.WriteMessage(opPong, nil)
		case opPong:
			// 心跳确认
		case opClose:
			done <- who + ": 连接结束"
			return
		}
	}
}

func main() {
	addr := flag.String("addr", "127.0.0.1:18880", "hub 监听地址")
	flag.Parse()

	// 每车 token（连接态鉴权，主文档 3.2）；ping 间隔 500ms 演示心跳。
	hub, err := NewHub(*addr, func(vehicle, role, token string) bool {
		return token == "tok-"+vehicle
	}, 500*time.Millisecond)
	if err != nil {
		panic(err)
	}
	hub.Start()
	defer hub.Stop()
	fmt.Printf("影子中枢已监听 %s\n", hub.Addr())

	ch := make(chan string, 16)

	// 1) 面板订阅 veh-001。
	panel, err := Dial(hub.Addr().String(), "/ws/shadow/veh-001/panel?token=tok-veh-001")
	if err != nil {
		panic(err)
	}
	defer panel.Close()
	go recvLoop(panel, "[面板]", ch)

	// 2) 设备上线（收到 connected + desired 初始态）。
	dev, err := Dial(hub.Addr().String(), "/ws/shadow/veh-001/device?token=tok-veh-001")
	if err != nil {
		panic(err)
	}
	defer dev.Close()
	go recvLoop(dev, "[设备]", ch)

	time.Sleep(150 * time.Millisecond)
	// 3) 设备上报两帧 reported。
	for i := 0; i < 2; i++ {
		msg, _ := json.Marshal(map[string]any{"op": "report", "reported": map[string]any{"speed": 50 + i*15}})
		_ = dev.WriteMessage(opText, msg)
		time.Sleep(100 * time.Millisecond)
	}
	// 4) 云侧下指令：设限速 80（带 baseVersion，值取当前影子版本）。
	_, _, v := hub.shadowOf("veh-001")
	if _, err := hub.SetDesired("veh-001", map[string]any{"speed_limit": 80}, v); err != nil {
		panic(err)
	}

	// 5) 收三方消息直到超时，按序打印。
	timeout := time.After(800 * time.Millisecond)
	for i := 0; i < 6; i++ {
		select {
		case m := <-ch:
			fmt.Println(m)
		case <-timeout:
			fmt.Println("（等待超时，提前结束打印）")
			return
		}
	}
	fmt.Println("== ex03 演示完成：设备影子 / 推送 / desired 下发全通 ==")
}

// shadowOf 读取某车影子版本（演示辅助）。
func (h *Hub) shadowOf(vehicle string) (map[string]any, map[string]any, int64) {
	h.mu.Lock()
	defer h.mu.Unlock()
	s := h.shadows[vehicle]
	if s == nil {
		return nil, nil, 0
	}
	return s.Snapshot()
}
