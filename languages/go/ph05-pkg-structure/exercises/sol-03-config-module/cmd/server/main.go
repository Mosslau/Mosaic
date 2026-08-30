// 来源：exercises/README.md 练习 3 —— 写配置加载模块参考实现
// 一句话说明：cmd/server 入口：加载配置并打印，log.Fatal 仅用于启动失败。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd sol-03-config-module && go run ./cmd/server -config config.example.json
//	APP_PORT=9090 go run ./cmd/server -config config.example.json
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"flag"
	"log"

	"tenetlang/go/ph05-pkg-structure/exercises/sol-03-config-module/internal/config"
)

func main() {
	path := flag.String("config", "", "JSON 配置文件路径")
	flag.Parse()
	if *path == "" {
		log.Fatalf("用法: server -config <配置文件>")
	}
	cfg, err := config.Load(*path)
	if err != nil {
		log.Fatalf("load config: %v", err) // 库代码不打日志，打印是 main 层职责
	}
	log.Printf("配置加载成功: port=%d data_dir=%q log_level=%q", cfg.Port, cfg.DataDir, cfg.LogLevel)
}
