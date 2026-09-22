// project/config.go —— 配置加载器（解析与校验实现）
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run .
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"bufio"
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// ErrInvalidConfig 是哨兵错误，表示配置格式非法，供调用方用 errors.Is 判定。
var ErrInvalidConfig = errors.New("invalid config")

// ConfigError 是自定义错误类型，携带出错的行号与键，供调用方用 errors.As 提取。
type ConfigError struct {
	Line    int
	Key     string
	Message string
}

func (e *ConfigError) Error() string {
	return fmt.Sprintf("config error at line %d (key %q): %s", e.Line, e.Key, e.Message)
}

// Unwrap 把 ConfigError 挂到哨兵错误 ErrInvalidConfig 上，
// 使 errors.Is(err, ErrInvalidConfig) 与 errors.As(err, &ConfigError) 同时成立。
func (e *ConfigError) Unwrap() error { return ErrInvalidConfig }

// Config 是解析结果。
type Config struct {
	Timeout int // 秒
	MaxConn int
}

// LoadConfig 从文件加载配置：读取、解析、校验三步，每步错误都带路径上下文。
func LoadConfig(path string) (Config, error) {
	f, err := os.Open(path)
	if err != nil {
		return Config{}, fmt.Errorf("load config %s: %w", path, err)
	}
	defer f.Close() // 打开成功后立即注册关闭，保证所有退出路径都释放文件

	cfg, err := parse(f)
	if err != nil {
		return Config{}, fmt.Errorf("load config %s: %w", path, err)
	}
	if err := cfg.validate(); err != nil {
		return Config{}, fmt.Errorf("load config %s: %w", path, err)
	}
	return cfg, nil
}

// parse 解析 key=value 流；坏行返回 *ConfigError（含行号），经 Unwrap 链到 ErrInvalidConfig。
func parse(f *os.File) (Config, error) {
	var cfg Config
	sc := bufio.NewScanner(f)
	lineNo := 0
	for sc.Scan() {
		lineNo++
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue // 跳过空行与注释行
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			return Config{}, &ConfigError{Line: lineNo, Message: fmt.Sprintf("malformed line %q", line)}
		}
		key, value := strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1])
		var err error
		switch key {
		case "timeout":
			cfg.Timeout, err = strconv.Atoi(value)
		case "max_conn":
			cfg.MaxConn, err = strconv.Atoi(value)
		default:
			return Config{}, &ConfigError{Line: lineNo, Key: key, Message: "unknown key"}
		}
		if err != nil {
			return Config{}, &ConfigError{Line: lineNo, Key: key, Message: "value must be integer"}
		}
	}
	if err := sc.Err(); err != nil {
		return Config{}, fmt.Errorf("read config: %w", err)
	}
	return cfg, nil
}

// validate 校验必填项与取值范围；失败时挂到哨兵错误 ErrInvalidConfig 上。
func (c Config) validate() error {
	if c.Timeout <= 0 {
		return fmt.Errorf("%w: timeout must be positive (required)", ErrInvalidConfig)
	}
	if c.MaxConn <= 0 {
		return fmt.Errorf("%w: max_conn must be positive (required)", ErrInvalidConfig)
	}
	return nil
}
