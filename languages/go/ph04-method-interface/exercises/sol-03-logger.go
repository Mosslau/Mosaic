// 来源：exercises/README.md 练习 3 —— Logger 接口参考实现
// 一句话说明：小接口 Logger + ConsoleLogger / NilLogger 两个实现，通过依赖注入切换。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：go run sol-03-logger.go
// 验证状态：已验证（Go 1.22.2）
package main

import "fmt"

// Logger 小接口：业务只依赖日志抽象，不依赖具体输出实现
type Logger interface {
	Log(level, msg string)
}

// ConsoleLogger 打印到标准输出
type ConsoleLogger struct{}

func (ConsoleLogger) Log(level, msg string) {
	fmt.Printf("[%s] %s\n", level, msg)
}

// NilLogger 空实现（no-op）：关闭日志或测试时静默
type NilLogger struct{}

func (NilLogger) Log(level, msg string) {}

// DeviceService 通过字段持有 Logger，初始化时注入——不感知具体实现
type DeviceService struct {
	logger Logger
}

func (d *DeviceService) Start(device string) {
	d.logger.Log("INFO", device+" 启动")
}

func (d *DeviceService) Fault(device string) {
	d.logger.Log("ERROR", device+" 故障")
}

func main() {
	fmt.Println("=== 注入 ConsoleLogger ===")
	svc := &DeviceService{logger: ConsoleLogger{}}
	svc.Start("CAN0")
	svc.Fault("CAN0")

	fmt.Println("=== 注入 NilLogger（应无输出）===")
	silent := &DeviceService{logger: NilLogger{}}
	silent.Start("CAN0")
	silent.Fault("CAN0")
	fmt.Println("（上方确实无任何日志）")
}
