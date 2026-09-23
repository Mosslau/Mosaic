// 来源：05-pkg-structure.md 第 6 章示例 3 —— 多模块 Workspace 共享库
// 一句话说明：lib/shared 公共库模块：DEVICE_ID 校验，被 collector / reporter 两个服务复用。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd examples/ex03-workspace && go run ./services/collector
// 验证状态：已验证（Go 1.22.2）
package shared

import "fmt"

// ValidateDEVICE_ID 校验 17 位 DEVICE_ID：长度 + 排除 I/O/Q 防混淆字符（OBD-II 约定）
func ValidateDEVICE_ID(device_id string) error {
	if len(device_id) != 17 {
		return fmt.Errorf("DEVICE_ID 长度 %d 不符合 17 位标准", len(device_id))
	}
	for _, ch := range device_id {
		if ch == 'I' || ch == 'O' || ch == 'Q' { // DEVICE_ID 不含 I/O/Q 防混淆
			return fmt.Errorf("DEVICE_ID 包含非法字符 '%c'", ch)
		}
	}
	return nil
}
