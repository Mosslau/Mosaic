// 来源：04-method-interface.md 第 6 章示例 5 —— 类型断言与 type switch：多源数据分发
// 一句话说明：演示 ok 模式断言（失败不 panic）与 type switch 按具体类型分发数据。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：go run ex05-type-switch.go
// 验证状态：已验证（Go 1.22.2）
package main

import "fmt"

type BUSFrame struct {
	ID   uint32
	Data [8]byte
}

func (c BUSFrame) String() string {
	return fmt.Sprintf("BUSFrame{ID=0x%X}", c.ID)
}

func processData(data interface{}) {
	switch v := data.(type) {
	case BUSFrame:
		fmt.Printf("BUS 帧  : ID=0x%X Data=%v\n", v.ID, v.Data[:4])
	case float64:
		fmt.Printf("传感器值: %.2f\n", v)
	case string:
		fmt.Printf("日志消息: %s\n", v)
	case []string:
		fmt.Printf("信号列表: %v\n", v)
	default:
		fmt.Printf("未知类型: %T = %v\n", v, v)
	}
}

func main() {
	var val interface{} = BUSFrame{ID: 0x7E8, Data: [8]byte{0x41, 0x0D, 0x00, 0x00}}
	if frame, ok := val.(BUSFrame); ok {
		fmt.Println("断言成功:", frame.String())
	}
	if _, ok := val.(int); !ok {
		fmt.Println("val 不是 int 类型——断言失败不 panic")
	}
	fmt.Println("\n=== type switch 分发 ===")
	processData(BUSFrame{ID: 0x18F, Data: [8]byte{0x00, 0xFA, 0x20}})
	processData(36.5)
	processData("运行速度传感器离线")
	processData([]string{"turn_left", "brake"})
}
