// 来源：project/ —— 标准 Go 项目模板 internal 业务层
// 一句话说明：internal/config 配置加载：默认值 → JSON 文件 → 环境变量覆盖 → 集中校验（fail fast）。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd project && go run ./cmd/device-cli config
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
	DataFile string `json:"data_file"`
	LogLevel string `json:"log_level"`
}

// Default 返回内置默认配置——模板开箱即用，不强制依赖外部配置文件
func Default() Config {
	return Config{
		Port:     8080,
		DataDir:  "./data",
		DataFile: "./data/devices.json",
		LogLevel: "info",
	}
}

// Load 加载配置：默认值 → 文件覆盖 → 环境变量覆盖 → 集中校验。
// path 为空时使用默认配置；错误统一 %w 包装保留错误链。
func Load(path string) (*Config, error) {
	cfg := Default()
	if path != "" {
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("read config %s: %w", path, err)
		}
		if err := json.Unmarshal(data, &cfg); err != nil {
			return nil, fmt.Errorf("parse config %s: %w", path, err)
		}
	}

	// 环境变量覆盖（12-factor 惯例）：不改文件即可覆盖配置
	if v := os.Getenv("DEVICE_CLI_PORT"); v != "" {
		port, err := strconv.Atoi(v)
		if err != nil {
			return nil, fmt.Errorf("env DEVICE_CLI_PORT=%q: %w", v, err)
		}
		cfg.Port = port
	}
	if v := os.Getenv("DEVICE_CLI_DATA_FILE"); v != "" {
		cfg.DataFile = v
	}

	// 集中校验：宁可启动失败，不要运行到一半才暴露配置错误
	if cfg.Port <= 0 || cfg.Port > 65535 {
		return nil, fmt.Errorf("invalid port: %d", cfg.Port)
	}
	if cfg.DataFile == "" {
		return nil, fmt.Errorf("data_file 不能为空")
	}
	return &cfg, nil
}
