// 来源：05-pkg-structure.md 第 6 章示例 2 —— 设备数据服务标准布局
// 一句话说明：cmd/device-server 程序入口：装配 config/bus/device 三个包。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd examples/ex02-device-server && go run ./cmd/device-server
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"fmt"
	"log"

	"tenetlang/go/ph05-pkg-structure/examples/ex02-device-server/internal/bus"
	"tenetlang/go/ph05-pkg-structure/examples/ex02-device-server/internal/config"
	"tenetlang/go/ph05-pkg-structure/examples/ex02-device-server/internal/device"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("load config: %v", err) // log.Fatal 仅用于 main 启动失败
	}
	fmt.Printf("设备数据服务启动 [端口:%d 协议:%s]\n", cfg.Port, cfg.Protocol)

	svc := device.NewService()
	frames := []bus.Frame{
		{ID: 0x18F, Data: [8]byte{0x00, 0xFA, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00}},
		{ID: 0x7E8, Data: [8]byte{0x04, 0x41, 0x0C, 0x1A, 0xF4, 0x00, 0x00, 0x00}},
	}
	for _, f := range frames {
		fmt.Printf("  [0x%X] → %s\n", f.ID, svc.Process(f))
	}
	if err := svc.Shutdown(); err != nil {
		log.Fatal(err)
	}
}
