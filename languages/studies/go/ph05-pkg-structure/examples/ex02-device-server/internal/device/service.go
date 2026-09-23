// 来源：05-pkg-structure.md 第 6 章示例 2 —— 设备数据服务标准布局
// 一句话说明：internal/device 包：业务服务，按帧 ID 分发解析，管理运行状态。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd examples/ex02-device-server && go run ./cmd/device-server
// 验证状态：已验证（Go 1.22.2）
package device

import (
	"errors"
	"fmt"
	"sync"

	"tenetlang/go/ph05-pkg-structure/examples/ex02-device-server/internal/bus"
)

// Service 设备数据服务——三个 internal 包在模块内互引无障碍
type Service struct {
	mu      sync.Mutex
	running bool
}

// NewService 创建运行中的服务
func NewService() *Service { return &Service{running: true} }

// Process 按帧 ID 分发到对应解析器
func (s *Service) Process(frame bus.Frame) string {
	switch frame.ID {
	case bus.SpeedID:
		return fmt.Sprintf("运行速度: %.1f km/h", bus.ParseSpeed(frame))
	case bus.EngineRPM:
		return fmt.Sprintf("转速: %.0f rpm", bus.ParseRPM(frame))
	default:
		return "未知帧类型"
	}
}

// Shutdown 幂等关闭：重复关闭返回错误而非静默忽略
func (s *Service) Shutdown() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if !s.running {
		return errors.New("服务已关闭")
	}
	s.running = false
	fmt.Println("设备数据服务已安全关闭")
	return nil
}
