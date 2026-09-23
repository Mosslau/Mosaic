// exercises/sol-04-device-cache.go —— 练习 4 参考实现：map + struct 管理设备数据
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run sol-04-device-cache.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"fmt"
	"sort"
)

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
	fleet := make(map[string]Device)

	// 增
	fleet["LSVAA4184ES000001"] = Device{
		DEVICE_ID:     "LSVAA4184ES000001",
		Model:   "Model S",
		Motor:   Motor{Speed: 80, Enabled: true},
		Component: Component{Level: 72, Temp: 35.2},
	}
	fleet["LSVAA4184ES000002"] = Device{
		DEVICE_ID:     "LSVAA4184ES000002",
		Model:   "Model 3",
		Motor:   Motor{Speed: 0, Enabled: false},
		Component: Component{Level: 55, Temp: 28.1},
	}
	fleet["LSVAA4184ES000003"] = Device{
		DEVICE_ID:     "LSVAA4184ES000003",
		Model:   "Model X",
		Motor:   Motor{Speed: 120, Enabled: true},
		Component: Component{Level: 90, Temp: 31.0},
	}

	// 查（直接访问提升字段）
	if v, ok := fleet["LSVAA4184ES000002"]; ok {
		fmt.Printf("查询 %s: %s Speed=%d Component=%d%%\n", v.DEVICE_ID, v.Model, v.Speed, v.Level)
	}

	// 改（回写提升字段）
	if v, ok := fleet["LSVAA4184ES000002"]; ok {
		v.Motor.Enabled = true
		v.Component.Level = 80
		fleet["LSVAA4184ES000002"] = v
	}

	// 删
	delete(fleet, "LSVAA4184ES000003")

	// 统计：平均电量、运行中（Enabled）设备数
	avg, running := fleetStats(fleet)
	fmt.Printf("\n设备组规模=%d 平均电量=%.1f%% 运行中=%d\n", len(fleet), avg, running)

	// 按 DEVICE_ID 排序列出
	device_ids := make([]string, 0, len(fleet))
	for device_id := range fleet {
		device_ids = append(device_ids, device_id)
	}
	sort.Strings(device_ids)

	fmt.Println("\n=== 设备列表 ===")
	for _, device_id := range device_ids {
		v := fleet[device_id]
		fmt.Printf("%s | %-8s | Speed=%3d | Component=%2d%%\n", v.DEVICE_ID, v.Model, v.Speed, v.Level)
	}
}

// fleetStats 返回平均电量与运行中设备数
func fleetStats(fleet map[string]Device) (avgLevel float64, running int) {
	if len(fleet) == 0 {
		return 0, 0
	}
	total := 0
	for _, v := range fleet {
		total += v.Level
		if v.Enabled {
			running++
		}
	}
	return float64(total) / float64(len(fleet)), running
}
