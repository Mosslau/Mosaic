// examples/ex04-struct-embed.go —— Struct 组合嵌入：车辆实体与字段提升
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run ex04-struct-embed.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import "fmt"

type Motor struct {
	Speed   int
	Enabled bool
}

type Battery struct {
	Level int     // 百分比 0-100
	Temp  float64 // 摄氏度
}

type Vehicle struct {
	VIN     string
	Model   string
	Motor   // 匿名字段嵌入
	Battery // 匿名字段嵌入
}

func main() {
	v := Vehicle{
		VIN:     "LSVAA4184ES000001",
		Model:   "Model S",
		Motor:   Motor{Speed: 80, Enabled: true},
		Battery: Battery{Level: 72, Temp: 35.2},
	}

	// 字段提升：直接访问嵌入类型的字段
	fmt.Printf("VIN=%s Model=%s\n", v.VIN, v.Model)
	fmt.Printf("Speed=%d Enabled=%v\n", v.Speed, v.Enabled)
	fmt.Printf("Battery=%d%% Temp=%.1fC\n", v.Level, v.Temp)

	// 也可以通过嵌入类型名访问
	v.Motor.Speed = 100
	v.Battery.Level = 85
	fmt.Printf("更新后: Speed=%d Battery=%d%%\n", v.Speed, v.Level)
}
