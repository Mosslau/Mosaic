// 来源：ph08-testing 主文档示例 4 —— mock 隔离外部依赖（接口 + 手写 stub）
// 一句话说明：遥测上报服务依赖 Reporter 接口，不依赖具体通道。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go run .
//	go test -v ./...
//
// 验证状态：已验证（go1.25.6）
package main

import "fmt"

// Reporter 外部上报通道（真实实现：MQTT/HTTP，见 ph09/ph11 阶段）
type Reporter interface {
	Report(deviceID string, payload map[string]any) error
}

// TelemetryService 遥测上报服务：依赖接口，不依赖具体实现
type TelemetryService struct{ reporter Reporter }

func NewTelemetryService(r Reporter) *TelemetryService {
	return &TelemetryService{reporter: r}
}

func (s *TelemetryService) Publish(deviceID string, payload map[string]any) error {
	if deviceID == "" {
		return fmt.Errorf("deviceID 不能为空")
	}
	if s.reporter == nil {
		return fmt.Errorf("reporter 未初始化")
	}
	return s.reporter.Report(deviceID, payload)
}

// logReporter 一个最简真实实现：打印到日志（仅用于 main 演示）
type logReporter struct{}

func (logReporter) Report(deviceID string, payload map[string]any) error {
	fmt.Printf("上报 %s: %v\n", deviceID, payload)
	return nil
}

func main() {
	svc := NewTelemetryService(logReporter{})
	if err := svc.Publish("car-001", map[string]any{"speed": 80}); err != nil {
		fmt.Println("上报失败:", err)
	}
}
