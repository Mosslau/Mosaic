// 来源：05-pkg-structure.md 第 6 章示例 2 —— 车辆数据服务标准布局
// 一句话说明：internal/vehicle 包：业务服务，按帧 ID 分发解析，管理运行状态。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd examples/ex02-vehicle-server && go run ./cmd/vehicle-server
// 验证状态：已验证（Go 1.22.2）
package vehicle

import (
	"errors"
	"fmt"
	"sync"

	"tenetlang/go/ph05-pkg-structure/examples/ex02-vehicle-server/internal/canbus"
)

// Service 车辆数据服务——三个 internal 包在模块内互引无障碍
type Service struct {
	mu      sync.Mutex
	running bool
}

// NewService 创建运行中的服务
func NewService() *Service { return &Service{running: true} }

// Process 按帧 ID 分发到对应解析器
func (s *Service) Process(frame canbus.Frame) string {
	switch frame.ID {
	case canbus.SpeedID:
		return fmt.Sprintf("车速: %.1f km/h", canbus.ParseSpeed(frame))
	case canbus.EngineRPM:
		return fmt.Sprintf("转速: %.0f rpm", canbus.ParseRPM(frame))
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
	fmt.Println("车辆数据服务已安全关闭")
	return nil
}
