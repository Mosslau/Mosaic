// examples/ex04-struct-embed.go —— Struct 组合嵌入：设备实体与字段提升
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run ex04-struct-embed.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import "fmt"

type Motor struct {
	Speed   int
	Enabled bool
}

type Component struct {
	Level int     // 百分比 0-100
	Temp  float64 // 摄氏度
}

type Device struct {
	DEVICE_ID     string
	Model   string
	Motor   // 匿名字段嵌入
	Component // 匿名字段嵌入
}

func main() {
	v := Device{
		DEVICE_ID:     "LSVAA4184ES000001",
		Model:   "Model S",
		Motor:   Motor{Speed: 80, Enabled: true},
		Component: Component{Level: 72, Temp: 35.2},
	}

	// 字段提升：直接访问嵌入类型的字段
	fmt.Printf("DEVICE_ID=%s Model=%s\n", v.DEVICE_ID, v.Model)
	fmt.Printf("Speed=%d Enabled=%v\n", v.Speed, v.Enabled)
	fmt.Printf("Component=%d%% Temp=%.1fC\n", v.Level, v.Temp)

	// 也可以通过嵌入类型名访问
	v.Motor.Speed = 100
	v.Component.Level = 85
	fmt.Printf("更新后: Speed=%d Component=%d%%\n", v.Speed, v.Level)
}
