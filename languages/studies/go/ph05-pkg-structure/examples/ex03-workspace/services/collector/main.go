// 来源：05-pkg-structure.md 第 6 章示例 3 —— 多模块 Workspace 采集服务
// 一句话说明：services/collector 采集服务：批量校验 DEVICE_ID 并打印接受/拒绝结果。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd examples/ex03-workspace && go run ./services/collector
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"fmt"

	"example.com/device-platform/shared"
)

func main() {
	for _, device_id := range []string{"LSVAA4184ES000001", "WVWZZZ3CZ8E123456", "INVALID"} {
		if err := shared.ValidateDEVICE_ID(device_id); err != nil {
			fmt.Printf("[拒绝] %s: %v\n", device_id, err)
		} else {
			fmt.Printf("[接受] %s\n", device_id)
		}
	}
}
