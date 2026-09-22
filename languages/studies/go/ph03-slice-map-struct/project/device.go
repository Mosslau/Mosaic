// project/device.go —— 设备状态管理 CLI（Device 结构与设备管理函数）
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run main.go device.go <命令>
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"fmt"
	"sort"
)

// Device 表示一台设备的状态
type Device struct {
	ID     string
	Type   string
	Status string  // "online" / "offline"
	CPU    float64 // 百分比 0-100
	Mem    float64 // 百分比 0-100
}

// seedDevices 返回一批种子设备数据，作为 CLI 的初始数据源
func seedDevices() map[string]Device {
	return map[string]Device{
		"gw-001":   {ID: "gw-001", Type: "gateway", Status: "online", CPU: 45.2, Mem: 72.1},
		"cam-002":  {ID: "cam-002", Type: "camera", Status: "offline", CPU: 0, Mem: 0},
		"db-003":   {ID: "db-003", Type: "database", Status: "online", CPU: 68.5, Mem: 85.3},
		"edge-004": {ID: "edge-004", Type: "edge", Status: "online", CPU: 12.3, Mem: 30.5},
		"plc-005":  {ID: "plc-005", Type: "plc", Status: "offline", CPU: 0, Mem: 0},
	}
}

// findDevice 按 ID 查询，返回设备与是否存在（ok 模式）
func findDevice(devices map[string]Device, id string) (Device, bool) {
	d, ok := devices[id]
	return d, ok
}

// listDevices 返回按 ID 排序的全部设备
func listDevices(devices map[string]Device) []Device {
	result := make([]Device, 0, len(devices))
	for _, d := range devices {
		result = append(result, d)
	}
	sort.Slice(result, func(i, j int) bool { return result[i].ID < result[j].ID })
	return result
}

// filterDevices 返回指定状态的设备，按 ID 排序保证输出稳定
func filterDevices(devices map[string]Device, status string) []Device {
	result := make([]Device, 0)
	for _, d := range devices {
		if d.Status == status {
			result = append(result, d)
		}
	}
	sort.Slice(result, func(i, j int) bool { return result[i].ID < result[j].ID })
	return result
}

// updateDevice 更新设备指标与状态；cpu/mem 传 -1 表示不修改，status 传空串表示不修改
func updateDevice(devices map[string]Device, id string, cpu, mem float64, status string) error {
	d, ok := devices[id]
	if !ok {
		return fmt.Errorf("设备 %q 不存在", id)
	}
	if cpu >= 0 {
		d.CPU = cpu
	}
	if mem >= 0 {
		d.Mem = mem
	}
	if status != "" {
		d.Status = status
	}
	devices[id] = d // struct 是值类型，需回写
	return nil
}

// summary 统计在线/离线数量与所有设备的平均 CPU/Mem
func summary(devices map[string]Device) (online, offline int, avgCPU, avgMem float64) {
	if len(devices) == 0 {
		return 0, 0, 0, 0
	}
	var cpuTotal, memTotal float64
	for _, d := range devices {
		if d.Status == "online" {
			online++
		} else {
			offline++
		}
		cpuTotal += d.CPU
		memTotal += d.Mem
	}
	n := float64(len(devices))
	return online, offline, cpuTotal / n, memTotal / n
}

// printDevices 以表格形式打印设备列表
func printDevices(devices []Device) {
	for _, d := range devices {
		fmt.Printf("%s | %-8s | %-7s | CPU:%5.1f%% | Mem:%5.1f%%\n",
			d.ID, d.Type, d.Status, d.CPU, d.Mem)
	}
}
