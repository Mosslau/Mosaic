// exercises/sol-04-vehicle-cache.go —— 练习 4 参考实现：map + struct 管理车辆数据
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run sol-04-vehicle-cache.go
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
	fleet := make(map[string]Vehicle)

	// 增
	fleet["LSVAA4184ES000001"] = Vehicle{
		VIN:     "LSVAA4184ES000001",
		Model:   "Model S",
		Motor:   Motor{Speed: 80, Enabled: true},
		Battery: Battery{Level: 72, Temp: 35.2},
	}
	fleet["LSVAA4184ES000002"] = Vehicle{
		VIN:     "LSVAA4184ES000002",
		Model:   "Model 3",
		Motor:   Motor{Speed: 0, Enabled: false},
		Battery: Battery{Level: 55, Temp: 28.1},
	}
	fleet["LSVAA4184ES000003"] = Vehicle{
		VIN:     "LSVAA4184ES000003",
		Model:   "Model X",
		Motor:   Motor{Speed: 120, Enabled: true},
		Battery: Battery{Level: 90, Temp: 31.0},
	}

	// 查（直接访问提升字段）
	if v, ok := fleet["LSVAA4184ES000002"]; ok {
		fmt.Printf("查询 %s: %s Speed=%d Battery=%d%%\n", v.VIN, v.Model, v.Speed, v.Level)
	}

	// 改（回写提升字段）
	if v, ok := fleet["LSVAA4184ES000002"]; ok {
		v.Motor.Enabled = true
		v.Battery.Level = 80
		fleet["LSVAA4184ES000002"] = v
	}

	// 删
	delete(fleet, "LSVAA4184ES000003")

	// 统计：平均电量、运行中（Enabled）车辆数
	avg, running := fleetStats(fleet)
	fmt.Printf("\n车队规模=%d 平均电量=%.1f%% 运行中=%d\n", len(fleet), avg, running)

	// 按 VIN 排序列出
	vins := make([]string, 0, len(fleet))
	for vin := range fleet {
		vins = append(vins, vin)
	}
	sort.Strings(vins)

	fmt.Println("\n=== 车辆列表 ===")
	for _, vin := range vins {
		v := fleet[vin]
		fmt.Printf("%s | %-8s | Speed=%3d | Battery=%2d%%\n", v.VIN, v.Model, v.Speed, v.Level)
	}
}

// fleetStats 返回平均电量与运行中车辆数
func fleetStats(fleet map[string]Vehicle) (avgLevel float64, running int) {
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
