// 来源：ph20-config-release examples/ex01-env-file-flag/config.go
// 一句话说明：同一份 Config 可以被环境变量 / 配置文件 / 命令行 flag 三个来源
// 提供——各自独立读取，值"显式给出"才覆盖默认（主文档 3.1/3.2）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strconv"
)

// envPrefix 演示用前缀：真实项目通常用服务名如 NINEBOT_SERVER_。
const envPrefix = "PH20EX01_"

// Config 演示用服务配置：同一组字段可以被 env/file/flag 三个来源提供。
// 字段注释写清楚"每个来源的键名"——Config 结构体本身即配置文档。
type Config struct {
	Port   int    `json:"port"`   // 键：PH20EX01_PORT / config.json 的 port / -port
	Name   string `json:"name"`   // 键：PH20EX01_NAME / config.json 的 name / -name
	Debug  bool   `json:"debug"`  // 键：PH20EX01_DEBUG / config.json 的 debug / -debug
	Region string `json:"region"` // 键：PH20EX01_REGION（可选，无默认值）
}

// DefaultConfig 返回默认值层。env/file/flag 各层都只覆盖"显式给出的键"，
// 所以默认值先落好，后续读取采用"读到了才改"的语义。
func DefaultConfig() Config {
	return Config{Port: 8080, Name: "unnamed", Debug: false}
}

// FromEnv 用环境变量覆盖 c。getenv 注入便于测试（不碰真实环境）；
// 返回的 bool 区分"已设置（哪怕是空串）"与"未设置"——这是 3.1 的关键陷阱。
func (c *Config) FromEnv(getenv func(string) (string, bool)) error {
	if v, ok := getenv(envPrefix + "PORT"); ok {
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 || n > 65535 {
			return fmt.Errorf("invalid %sPORT %q: want 1-65535", envPrefix, v)
		}
		c.Port = n
	}
	if v, ok := getenv(envPrefix + "NAME"); ok {
		c.Name = v // 空串也是"显式设置"：允许把名字清空
	}
	if v, ok := getenv(envPrefix + "DEBUG"); ok {
		b, err := strconv.ParseBool(v)
		if err != nil {
			return fmt.Errorf("invalid %sDEBUG %q: want bool", envPrefix, v)
		}
		c.Debug = b
	}
	if v, ok := getenv(envPrefix + "REGION"); ok {
		c.Region = v
	}
	return nil
}

// RegisterFlags 把 c 的现有值当 flag 默认值注册：parse 后 flag 显式给出即覆盖。
// 指针型绑定让 flag.Parse 直接改到 c 字段上，无需再写一遍覆盖逻辑。
func (c *Config) RegisterFlags(fs *flag.FlagSet) {
	fs.IntVar(&c.Port, "port", c.Port, "listen port (overrides env/file)")
	fs.StringVar(&c.Name, "name", c.Name, "service name (overrides env/file)")
	fs.BoolVar(&c.Debug, "debug", c.Debug, "debug mode (overrides env/file)")
	fs.StringVar(&c.Region, "region", c.Region, "region hint (overrides env/file)")
}

// FromFile 从 JSON 配置文件读入并覆盖 c。json.Unmarshal 语义与"覆盖层"吻合：
// 文件里有的键覆盖 struct 当前值，缺的键不动（不会把默认值清零）。
func (c *Config) FromFile(path string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("read config file %s: %w", path, err)
	}
	if err := json.Unmarshal(data, c); err != nil {
		return fmt.Errorf("parse config file %s: %w", path, err)
	}
	return nil
}

func (c Config) String() string {
	return fmt.Sprintf("port=%d name=%q debug=%v region=%q", c.Port, c.Name, c.Debug, c.Region)
}
