// project/main.go —— 设备状态管理 CLI（命令入口与分发）
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run main.go device.go <命令>
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"fmt"
	"os"
	"strconv"
)

func main() {
	devices := seedDevices()

	if len(os.Args) < 2 {
		usage()
		return
	}

	switch os.Args[1] {
	case "list":
		fmt.Println("=== 设备列表 ===")
		printDevices(listDevices(devices))

	case "show":
		if len(os.Args) < 3 {
			fmt.Println("用法: go run . show <id>")
			return
		}
		if d, ok := findDevice(devices, os.Args[2]); ok {
			printDevices([]Device{d})
		} else {
			fmt.Printf("设备 %q 不存在\n", os.Args[2])
		}

	case "update":
		if len(os.Args) < 3 {
			fmt.Println("用法: go run . update <id> [-cpu <值>] [-mem <值>] [-status <值>]")
			return
		}
		id := os.Args[2]
		cpu, mem, status, err := parseUpdateArgs(os.Args[3:])
		if err != nil {
			fmt.Println("参数错误:", err)
			return
		}
		if err := updateDevice(devices, id, cpu, mem, status); err != nil {
			fmt.Println("更新失败:", err)
			return
		}
		if d, ok := findDevice(devices, id); ok {
			fmt.Printf("更新后 %s: Status=%s CPU=%.1f%% Mem=%.1f%%\n", d.ID, d.Status, d.CPU, d.Mem)
		}

	case "filter":
		if len(os.Args) < 3 {
			fmt.Println("用法: go run . filter <status>")
			return
		}
		result := filterDevices(devices, os.Args[2])
		fmt.Printf("=== 状态为 %q 的设备（%d 台）===\n", os.Args[2], len(result))
		printDevices(result)

	case "summary":
		online, offline, avgCPU, avgMem := summary(devices)
		fmt.Printf("总计=%d 在线=%d 离线=%d\n", online+offline, online, offline)
		fmt.Printf("平均 CPU=%.1f%% 平均 Mem=%.1f%%\n", avgCPU, avgMem)

	default:
		fmt.Printf("未知命令 %q\n\n", os.Args[1])
		usage()
	}
}

// parseUpdateArgs 解析 -key value 形式的更新参数；未提供的参数返回 -1 或空串表示不修改
func parseUpdateArgs(args []string) (cpu, mem float64, status string, err error) {
	cpu, mem = -1, -1
	for i := 0; i+1 < len(args); i += 2 {
		key, val := args[i], args[i+1]
		switch key {
		case "-cpu":
			if cpu, err = strconv.ParseFloat(val, 64); err != nil {
				return -1, -1, "", fmt.Errorf("cpu 值非法: %q", val)
			}
		case "-mem":
			if mem, err = strconv.ParseFloat(val, 64); err != nil {
				return -1, -1, "", fmt.Errorf("mem 值非法: %q", val)
			}
		case "-status":
			status = val
		default:
			return -1, -1, "", fmt.Errorf("未知参数 %q", key)
		}
	}
	return cpu, mem, status, nil
}

func usage() {
	fmt.Println(`设备状态管理 CLI

用法:
  go run main.go device.go list                列出全部设备
  go run main.go device.go show <id>           查询单个设备
  go run main.go device.go update <id> [-cpu <值>] [-mem <值>] [-status <值>]  更新设备
  go run main.go device.go filter <status>     按状态筛选
  go run main.go device.go summary             统计在线/离线与平均资源利用率`)
}
