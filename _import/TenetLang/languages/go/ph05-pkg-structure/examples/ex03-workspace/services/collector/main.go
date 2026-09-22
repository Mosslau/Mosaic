// 来源：05-pkg-structure.md 第 6 章示例 3 —— 多模块 Workspace 采集服务
// 一句话说明：services/collector 采集服务：批量校验 VIN 并打印接受/拒绝结果。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd examples/ex03-workspace && go run ./services/collector
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"fmt"

	"example.com/vehicle-platform/shared"
)

func main() {
	for _, vin := range []string{"LSVAA4184ES000001", "WVWZZZ3CZ8E123456", "INVALID"} {
		if err := shared.ValidateVIN(vin); err != nil {
			fmt.Printf("[拒绝] %s: %v\n", vin, err)
		} else {
			fmt.Printf("[接受] %s\n", vin)
		}
	}
}
