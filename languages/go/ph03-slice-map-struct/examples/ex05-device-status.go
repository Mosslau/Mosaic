// examples/ex05-device-status.go —— 设备状态管理（Map + Struct，按 ID 排序遍历）
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run ex05-device-status.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"fmt"
	"sort"
)

type Device struct {
	ID     string
	Type   string
	Status string // "online" / "offline"
	CPU    float64
	Mem    float64
}

func main() {
	devices := make(map[string]Device)

	// 添加设备
	devices["gw-001"] = Device{ID: "gw-001", Type: "gateway", Status: "online", CPU: 45.2, Mem: 72.1}
	devices["cam-002"] = Device{ID: "cam-002", Type: "camera", Status: "offline", CPU: 0, Mem: 0}
	devices["db-003"] = Device{ID: "db-003", Type: "database", Status: "online", CPU: 68.5, Mem: 85.3}

	// 查询单个设备
	if d, ok := devices["gw-001"]; ok {
		fmt.Printf("查询 gw-001: Status=%s CPU=%.1f%% Mem=%.1f%%\n", d.Status, d.CPU, d.Mem)
	}

	// 更新设备状态（struct 是值类型，需回写）
	if d, ok := devices["cam-002"]; ok {
		d.Status = "online"
		d.CPU = 23.7
		d.Mem = 45.0
		devices["cam-002"] = d
	}

	// 下线设备
	if d, ok := devices["db-003"]; ok {
		d.Status = "offline"
		devices["db-003"] = d
	}

	// 遍历设备（按 ID 排序输出以保持稳定）
	ids := make([]string, 0, len(devices))
	for id := range devices {
		ids = append(ids, id)
	}
	sort.Strings(ids)

	fmt.Println("\n=== 设备状态表 ===")
	for _, id := range ids {
		d := devices[id]
		fmt.Printf("%s | %-8s | %-7s | CPU:%5.1f%% | Mem:%5.1f%%\n",
			d.ID, d.Type, d.Status, d.CPU, d.Mem)
	}

	// 统计在线设备数
	online := 0
	for _, d := range devices {
		if d.Status == "online" {
			online++
		}
	}
	fmt.Printf("\n在线设备: %d/%d\n", online, len(devices))
}
