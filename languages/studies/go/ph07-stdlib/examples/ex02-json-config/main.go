// 来源：07-stdlib.md 第 6 章示例 2 —— JSON 配置解析器（结构体 tag + os.ReadFile + json.Unmarshal）
// 一句话说明：嵌套结构体对应嵌套 JSON，错误逐层 %w 包装，解析后做业务校验。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go run . demo.json
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
)

// Config 配置结构：JSON tag 与配置文件字段一一对应
type Config struct {
	Server struct {
		Host string `json:"host"`
		Port int    `json:"port"`
	} `json:"server"`
	LogLevel string `json:"log_level"`
	Timeout  int    `json:"timeout"`
}

func loadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("读取配置 %s: %w", path, err)
	}
	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("解析配置 %s: %w", path, err)
	}
	if cfg.Server.Port <= 0 {
		return nil, fmt.Errorf("配置错误: server.port 必须为正数")
	}
	return &cfg, nil
}

func main() {
	if len(os.Args) < 2 {
		log.Fatal("用法: go run . <配置文件路径>")
	}
	cfg, err := loadConfig(os.Args[1])
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("服务地址: %s:%d, 日志级别: %s, 超时: %d 秒\n", cfg.Server.Host, cfg.Server.Port, cfg.LogLevel, cfg.Timeout)
}
