// 来源：exercises/README.md 练习 1 —— Sensor 接口参考实现
// 一句话说明：定义单方法 Sensor 接口，值接收者与指针接收者两个实现统一采集。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：go run sol-01-sensor.go
// 验证状态：已验证（Go 1.22.2）
package main

import "fmt"

// Sensor 单方法小接口——由消费方 collect 定义，只有需要的 1 个方法
type Sensor interface {
	Read() float64
}

// Thermometer 温度传感器——值接收者：只读状态，不修改自身
type Thermometer struct {
	ID string
}

func (t Thermometer) Read() float64 {
	return 21.5 + float64(len(t.ID))*0.1
}

// PressureSensor 压力传感器——指针接收者：需要修改校准偏移
type PressureSensor struct {
	ID     string
	offset float64
}

func (p *PressureSensor) Read() float64 {
	return 1013.0 + p.offset
}

func (p *PressureSensor) Calibrate(offset float64) {
	p.offset = offset
}

// collect 对接口编程：Thermometer（值）和 *PressureSensor（指针）都满足 Sensor
// 说明：*T 的方法集包含值接收者方法，因此指针类型同样满足接口；
// 反之若 PressureSensor 只有指针接收者方法，则只有 *PressureSensor 满足接口。
func collect(sensors []Sensor, rounds int) {
	for r := 1; r <= rounds; r++ {
		fmt.Printf("第 %d 轮: ", r)
		for _, s := range sensors {
			fmt.Printf("%.2f  ", s.Read())
		}
		fmt.Println()
	}
}

func main() {
	temp := Thermometer{ID: "T01"}
	pres := &PressureSensor{ID: "P01"}
	pres.Calibrate(2.5)
	collect([]Sensor{temp, pres}, 3)
}
