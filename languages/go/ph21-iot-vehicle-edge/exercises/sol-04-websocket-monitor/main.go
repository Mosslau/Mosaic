// 来源：ph21-iot-vehicle-edge exercises/sol-04-websocket-monitor/main.go
// 一句话说明：练习 4 演示——两个面板会话订阅 veh-001：状态 v1→v3 全部收到且顺序
// 一致；中途"断开"一个会话，新会话（模拟重连）入会即补到最新 v3；版本回退的
// v2 提交被拒。用法：go run .
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，输出见下方预期）
package main

import "fmt"

func main() {
	m := NewMonitor()
	p1 := newFakeSession("panel-1")
	p2 := newFakeSession("panel-2")
	m.Subscribe("veh-001", p1)
	m.Subscribe("veh-001", p2)

	// 状态流 v1..v3。
	for i := int64(1); i <= 3; i++ {
		_ = m.Apply(State{Vehicle: "veh-001", Version: i, Data: map[string]any{"speed_kmh": float64(40 + i*10)}})
	}
	for _, p := range []*fakeSession{p1, p2} {
		msg := ""
		for i := 0; i < 3; i++ {
			st, _ := p.Next()
			msg += fmt.Sprintf(" v%d:%.0f", st.Version, st.Data["speed_kmh"].(float64))
		}
		fmt.Printf("%s 收到:%s\n", p.Name(), msg)
	}

	// 断线重连：p1 断开，新面板 p3 入会 → 立即收到最新快照 v3。
	p1.Close()
	p3 := newFakeSession("panel-3(reconnected)")
	m.Subscribe("veh-001", p3)
	st, _ := p3.Next()
	fmt.Printf("%s 入会快照: v%d\n", p3.Name(), st.Version)

	// 版本回退被拒：v2 提交失败，p2 不会再收到。
	err := m.Apply(State{Vehicle: "veh-001", Version: 2, Data: map[string]any{"speed_kmh": 999}})
	fmt.Printf("版本回退提交: %v\n", err)
	fmt.Println("== sol-04 演示完成 ==")
}
