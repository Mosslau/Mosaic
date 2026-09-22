// exercises/sol-03-config-parse.go —— 练习 3 参考实现：配置解析错误处理
// 验证环境：Go 1.22.2（darwin/arm64），无外部依赖
// 运行：go run sol-03-config-parse.go
// 已验证：Go 1.22.2，gofmt 无差异、go vet 通过
package main

import (
	"errors"
	"fmt"
	"strings"
)

// ErrInvalidConfig 是哨兵错误，调用方用 errors.Is 判定
var ErrInvalidConfig = errors.New("invalid config")

// parseConfig 解析 key=value 格式，坏行错误带行号与原始内容。
func parseConfig(input string) (map[string]string, error) {
	cfg := make(map[string]string)
	for i, raw := range strings.Split(input, "\n") {
		line := strings.TrimSpace(raw)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			return nil, fmt.Errorf("%w: line %d: malformed line %q", ErrInvalidConfig, i+1, raw)
		}
		key, value := strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1])
		if key == "" {
			return nil, fmt.Errorf("%w: line %d: empty key", ErrInvalidConfig, i+1)
		}
		cfg[key] = value
	}
	return cfg, nil
}

func main() {
	good := "# 服务配置\ntimeout=30\nmax_conn=100\n"
	if cfg, err := parseConfig(good); err != nil {
		fmt.Println("解析失败:", err)
	} else {
		fmt.Println("解析成功:", cfg)
	}

	bad := "timeout=30\nnot-a-kv-line\nmax_conn=100\n"
	if _, err := parseConfig(bad); errors.Is(err, ErrInvalidConfig) {
		fmt.Println("配置格式错误:", err)
	} else if err != nil {
		fmt.Println("未知错误:", err)
	}
}
