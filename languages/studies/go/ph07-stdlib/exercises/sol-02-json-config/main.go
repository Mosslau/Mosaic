// 来源：exercises/README.md 练习 2 参考实现 —— JSON 配置解析器（tag + 校验 + %w 包装）
// 一句话说明：读取 JSON 配置 → 结构体解析 → 必填与取值范围校验，三类错误可区分。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go run . <配置文件路径>
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"slices"
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

// 三类错误用 sentinel error 区分，调用方可用 errors.Is 判定
var (
	ErrRead     = errors.New("读取配置失败")
	ErrParse    = errors.New("解析配置失败")
	ErrValidate = errors.New("配置校验失败")
)

var validLogLevels = []string{"debug", "info", "warn", "error"}

// validate 业务校验：解析成功 ≠ 配置合法
func (c *Config) validate() error {
	if c.Server.Host == "" {
		return fmt.Errorf("server.host 不能为空")
	}
	if c.Server.Port < 1 || c.Server.Port > 65535 {
		return fmt.Errorf("server.port 必须在 1~65535，当前为 %d", c.Server.Port)
	}
	if !slices.Contains(validLogLevels, c.LogLevel) {
		return fmt.Errorf("log_level 必须是 %v 之一，当前为 %q", validLogLevels, c.LogLevel)
	}
	if c.Timeout <= 0 {
		return fmt.Errorf("timeout 必须为正数，当前为 %d", c.Timeout)
	}
	return nil
}

func loadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("%w: %s: %w", ErrRead, path, err)
	}
	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("%w: %s: %w", ErrParse, path, err)
	}
	if err := cfg.validate(); err != nil {
		return nil, fmt.Errorf("%w: %w", ErrValidate, err)
	}
	return &cfg, nil
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "用法: go run . <配置文件路径>")
		os.Exit(1)
	}
	cfg, err := loadConfig(os.Args[1])
	if err != nil {
		switch {
		case errors.Is(err, ErrRead):
			fmt.Fprintln(os.Stderr, "[读取错误]", err)
		case errors.Is(err, ErrParse):
			fmt.Fprintln(os.Stderr, "[解析错误]", err)
		case errors.Is(err, ErrValidate):
			fmt.Fprintln(os.Stderr, "[校验错误]", err)
		}
		os.Exit(1)
	}
	fmt.Printf("服务地址: %s:%d, 日志级别: %s, 超时: %d 秒\n",
		cfg.Server.Host, cfg.Server.Port, cfg.LogLevel, cfg.Timeout)
}
