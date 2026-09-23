// 来源：05-pkg-structure.md 第 6 章示例 2 —— 设备数据服务标准布局
// 一句话说明：internal/config 包：集中构造并校验服务配置，返回不可变 Config。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd examples/ex02-device-server && go run ./cmd/device-server
// 验证状态：已验证（Go 1.22.2）
package config

import "fmt"

// Config 服务配置——加载后不再修改（不可变约定，多 goroutine 读无竞态）
type Config struct {
	Port     int
	Protocol string
}

// Load 构造默认配置并集中校验——文档片段为聚焦布局省略了 error，完整版返回 (Config, error)
func Load() (Config, error) {
	cfg := Config{Port: 8080, Protocol: "BUS"}
	if cfg.Port <= 0 || cfg.Port > 65535 {
		return Config{}, fmt.Errorf("invalid port: %d", cfg.Port)
	}
	return cfg, nil
}
