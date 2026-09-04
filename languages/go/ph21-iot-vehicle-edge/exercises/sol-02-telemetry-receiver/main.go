// 来源：ph21-iot-vehicle-edge exercises/sol-02-telemetry-receiver/main.go
// 一句话说明：练习 2 演示——喂入 8 条报文：4 条有效（含需换算的速度）、1 条缺 vin、
// 1 条超量程、1 条重复、1 条乱序；打印三路计数与换算结果。
// 用法：go run .
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，输出见下方预期）
package main

import "fmt"

func main() {
	r := NewReceiver(100)
	feed := []string{
		`{"vin":"veh-001","seq":1,"speed":30.0}`,
		`{"vin":"veh-001","seq":2,"speed":50.0}`,
		`{"vin":"veh-001","seq":3,"speed":60.0}`,
		`{"vin":"veh-001","seq":4,"speed":100.0}`,
		`{"seq":5,"speed":10.0}`,                 // 缺 vin
		`{"vin":"veh-001","seq":6,"speed":999}`,  // 超量程
		`{"vin":"veh-001","seq":2,"speed":50.0}`, // 重复
		`{"vin":"veh-001","seq":1,"speed":30.0}`, // 乱序迟到
	}
	for _, raw := range feed {
		if got, err := r.Handle([]byte(raw)); err != nil {
			fmt.Println("[拒]", err)
		} else {
			fmt.Printf("[收] %s seq=%d speed=%.1fkm/h\n", got.Vin, got.Seq, got.SpeedKmh)
		}
	}
	fmt.Println("汇总:", r.Summary())
	fmt.Println("== sol-02 演示完成 ==")
}
