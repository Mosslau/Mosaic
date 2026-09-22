// 来源：ph08-testing 主文档示例 4 —— mock 隔离外部依赖（接口 + 手写 stub）
// 一句话说明：手写 stub 记录调用参数做行为断言，可开关模拟故障。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"errors"
	"testing"
)

// stubReporter 手写 stub：记录每次上报的 deviceID，fail 开关模拟通道故障
type stubReporter struct {
	calls []string
	fail  bool
}

func (s *stubReporter) Report(deviceID string, payload map[string]any) error {
	if s.fail {
		return errors.New("上报通道不可用")
	}
	s.calls = append(s.calls, deviceID)
	return nil
}

func TestPublishSuccess(t *testing.T) {
	stub := &stubReporter{}
	svc := NewTelemetryService(stub)
	if err := svc.Publish("car-001", map[string]any{"speed": 80}); err != nil {
		t.Fatalf("上报失败: %v", err)
	}
	if len(stub.calls) != 1 || stub.calls[0] != "car-001" {
		t.Errorf("调用记录 = %v, 期望 [car-001]", stub.calls)
	}
}

func TestPublishChannelDown(t *testing.T) {
	stub := &stubReporter{fail: true}
	svc := NewTelemetryService(stub)
	if err := svc.Publish("car-001", map[string]any{}); err == nil {
		t.Error("通道故障时应当返回错误")
	}
}

func TestPublishEmptyID(t *testing.T) {
	svc := NewTelemetryService(&stubReporter{})
	if err := svc.Publish("", map[string]any{}); err == nil {
		t.Error("空 deviceID 应当返回错误")
	}
}
