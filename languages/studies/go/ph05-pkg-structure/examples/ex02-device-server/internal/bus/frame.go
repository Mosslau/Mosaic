// 来源：05-pkg-structure.md 第 6 章示例 2 —— 设备数据服务标准布局
// 一句话说明：internal/bus 包：BUS 2.0A 标准帧定义与运行速度/转速解析。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd examples/ex02-device-server && go run ./cmd/device-server
// 验证状态：已验证（Go 1.22.2）
package bus

// Frame BUS 2.0A 标准帧：11 位 ID + 8 字节数据
type Frame struct {
	ID   uint32
	Data [8]byte
}

// 常用 BUS 帧 ID——OBD-II 协议约定
const (
	SpeedID   uint32 = 0x18F
	EngineRPM uint32 = 0x7E8
)

// ParseSpeed 解析运行速度：字节 2-3 大端，单位 km/h，精度 0.01
func ParseSpeed(f Frame) float64 {
	if f.ID != SpeedID || len(f.Data) < 4 {
		return 0
	}
	return float64(uint16(f.Data[2])<<8|uint16(f.Data[3])) * 0.01
}

// ParseRPM 解析转速：字节 3-4 大端，单位 rpm，精度 0.25
func ParseRPM(f Frame) float64 {
	if f.ID != EngineRPM || len(f.Data) < 4 || f.Data[0] < 3 {
		return 0
	}
	return (float64(f.Data[3])*256 + float64(f.Data[4])) / 4.0
}
