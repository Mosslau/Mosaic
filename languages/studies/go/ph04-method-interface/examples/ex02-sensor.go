// 来源：04-method-interface.md 第 6 章示例 2 —— Sensor 接口：CAN / UART 数据采集
// 一句话说明：演示小接口 + 隐式实现——CANSensor（值接收者）与 UARTSensor（指针接收者）都满足 Sensor 接口。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：go run ex02-sensor.go
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"fmt"
	"math/rand"
)

type Sensor interface {
	Read() float64
	Name() string
}

// CAN 总线传感器——值接收者
type CANSensor struct {
	Channel string
}

func (c CANSensor) Read() float64 {
	return 25.0 + rand.Float64()*10.0
}

func (c CANSensor) Name() string {
	return "CAN-" + c.Channel
}

// UART 传感器——指针接收者（需修改校准偏移）
type UARTSensor struct {
	Port   string
	offset float64
}

func (u *UARTSensor) Read() float64 {
	return 3.3 + rand.Float64()*1.7 + u.offset
}

func (u *UARTSensor) Name() string {
	return "UART-" + u.Port
}

func (u *UARTSensor) Calibrate(offset float64) {
	u.offset = offset
}

// collect 对接口编程：无论值类型还是指针类型，只要满足 Sensor 就能统一采集
func collect(sensors []Sensor) {
	for _, s := range sensors {
		fmt.Printf("[%s] 读数: %.2f\n", s.Name(), s.Read())
	}
}

func main() {
	can := CANSensor{Channel: "CAN0"}
	uart := &UARTSensor{Port: "/dev/ttyUSB0", offset: 0.5}
	fmt.Println("=== 第 1 轮采集 ===")
	collect([]Sensor{can, uart}) // can 值类型、uart 指针，都满足 Sensor
	uart.Calibrate(1.0)
	fmt.Println("\n=== 校准后采集 ===")
	collect([]Sensor{can, uart})
}
