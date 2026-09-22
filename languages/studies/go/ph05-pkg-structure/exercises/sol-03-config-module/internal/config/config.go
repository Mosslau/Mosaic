// 来源：exercises/README.md 练习 3 —— 写配置加载模块参考实现
// 一句话说明：internal/config 包：JSON 文件 + 环境变量覆盖 + 集中校验（fail fast）。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd sol-03-config-module && go run ./cmd/server -config config.example.json
//	APP_PORT=9090 go run ./cmd/server -config config.example.json
//
// 验证状态：已验证（Go 1.22.2）
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
)

// Config 服务配置——加载后不再修改（不可变约定）
type Config struct {
	Port     int    `json:"port"`
	DataDir  string `json:"data_dir"`
	LogLevel string `json:"log_level"`
}

// Load 读取 JSON 配置文件，用环境变量覆盖部分字段，最后集中校验。
// 顺序：文件 → env 覆盖 → 校验；错误统一 %w 包装保留错误链。
func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read config %s: %w", path, err)
	}
	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("parse config %s: %w", path, err)
	}

	// 环境变量覆盖（12-factor 惯例）：容器/CI 里不改文件也能覆盖配置
	if v := os.Getenv("APP_PORT"); v != "" {
		port, err := strconv.Atoi(v)
		if err != nil {
			return nil, fmt.Errorf("env APP_PORT=%q: %w", v, err)
		}
		cfg.Port = port
	}
	if v := os.Getenv("APP_DATA_DIR"); v != "" {
		cfg.DataDir = v
	}
	if v := os.Getenv("APP_LOG_LEVEL"); v != "" {
		cfg.LogLevel = v
	}

	// 集中校验：宁可启动失败，不要运行到一半才暴露配置错误
	if cfg.Port <= 0 || cfg.Port > 65535 {
		return nil, fmt.Errorf("invalid port: %d", cfg.Port)
	}
	if cfg.DataDir == "" {
		return nil, fmt.Errorf("data_dir 不能为空")
	}
	return &cfg, nil
}
