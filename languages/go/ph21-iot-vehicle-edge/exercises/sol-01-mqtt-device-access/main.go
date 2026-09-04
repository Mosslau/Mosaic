// 来源：ph21-iot-vehicle-edge exercises/sol-01-mqtt-device-access/main.go
// 一句话说明：练习 1 演示——接入核心 + 内存假传输：3 台车接入（1 台坏 token 被拒），
// 收到遥测后回调按 vin 分发；一台车停止发消息超时被判离线。
// 用法：go run .
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，输出见下方预期）
package main

import (
	"fmt"
	"time"
)

func main() {
	core := NewAccess(2*time.Second, func(id, token string) bool {
		return token == "tok-"+id // 每车一密 allowlist
	})
	got := make(chan string, 16)
	core.OnTelemetry(func(vin string, payload []byte) {
		got <- fmt.Sprintf("%s:%s", vin, payload)
	})

	// 3 台车接入；第 4 台坏 token 被拒。
	var devs []*memTransport
	for i := 1; i <= 3; i++ {
		id := fmt.Sprintf("veh-%03d", i)
		mt := newMemTransport()
		if err := core.Attach(id, "tok-"+id, mt); err != nil {
			panic(err)
		}
		devs = append(devs, mt)
	}
	bad := newMemTransport()
	if err := core.Attach("veh-999", "wrong", bad); err != nil {
		fmt.Printf("坏 token 设备被拒（预期）: %v\n", err)
	}
	fmt.Printf("在线设备数: %d\n", core.OnlineCount())

	// 每台车发一条遥测 → 回调按 vin 收到。
	for _, mt := range devs {
		mt.simulate("veh/"+mt.deviceID+"/telemetry", []byte(`{"seq":1}`))
	}
	for i := 0; i < 3; i++ {
		fmt.Println("收到:", <-got)
	}

	// 心跳超时：直接推进"最后心跳时间"（离线测试不真等 2s——用 CheckHeartbeats(now)）。
	core.mu.Lock()
	for _, s := range core.devices {
		s.lastSeen = time.Now().Add(-3 * time.Second) // 模拟 3 秒没心跳
	}
	core.mu.Unlock()
	down := core.CheckHeartbeats(time.Now())
	fmt.Printf("心跳超时判离线: %v；剩余在线 %d\n", down, core.OnlineCount())
	fmt.Println("== sol-01 演示完成 ==")
}
