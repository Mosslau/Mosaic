// examples/ex03-config-errors-is.go —— 配置解析：哨兵错误 + %w 包装 + errors.Is 判定
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run ex03-config-errors-is.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"errors"
	"fmt"
	"strconv"
	"strings"
)

// ErrInvalidConfig 是哨兵错误（sentinel error），供调用方用 errors.Is 判定
var ErrInvalidConfig = errors.New("invalid config")

type Config struct {
	Timeout int
	MaxConn int
}

func parseConfig(input string) (Config, error) {
	var cfg Config
	for _, line := range strings.Split(strings.TrimSpace(input), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue // 跳过空行与注释行
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			return Config{}, fmt.Errorf("%w: malformed line %q", ErrInvalidConfig, line)
		}
		key, value := strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1])
		var err error
		switch key {
		case "timeout":
			cfg.Timeout, err = strconv.Atoi(value)
		case "max_conn":
			cfg.MaxConn, err = strconv.Atoi(value)
		default:
			return Config{}, fmt.Errorf("%w: unknown key %q", ErrInvalidConfig, key)
		}
		if err != nil {
			// 包装链：ErrInvalidConfig -> strconv 的原始错误，两类错误都可被判定
			return Config{}, fmt.Errorf("%w: %s must be integer: %w", ErrInvalidConfig, key, err)
		}
	}
	if cfg.Timeout <= 0 || cfg.MaxConn <= 0 {
		return Config{}, fmt.Errorf("%w: timeout and max_conn must be positive", ErrInvalidConfig)
	}
	return cfg, nil
}

func main() {
	input := `
# 服务配置
timeout=30
max_conn=100
`
	if cfg, err := parseConfig(input); err != nil {
		if errors.Is(err, ErrInvalidConfig) {
			fmt.Println("配置格式错误:", err)
		} else {
			fmt.Println("未知错误:", err)
		}
	} else {
		fmt.Printf("配置解析成功: timeout=%d, max_conn=%d\n", cfg.Timeout, cfg.MaxConn)
	}
}
