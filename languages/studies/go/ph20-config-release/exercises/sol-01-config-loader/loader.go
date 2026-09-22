// 来源：ph20-config-release exercises/sol-01-config-loader/loader.go
// 一句话说明：练习 1 参考实现——一个多环境配置加载模块：默认值 → profile 文件
// （config.<env>.json，env=dev/test/prod）→ 环境变量 → 命令行 flag 分层覆盖；
// 返回每字段来源表（可溯源），对必填项 fail-fast（启动即报错）。零第三方依赖。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -profile dev      验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
)

// 来源层名（每字段最终来自哪一层，发布排障"这个值哪来的"用）。
const (
	SrcDefault = "default"
	SrcFile    = "file"
	SrcEnv     = "env"
	SrcFlag    = "flag"
)

// envPrefix 是环境变量统一前缀，避免与宿主机的无关变量撞名。
const envPrefix = "PH20SOL1_"

// Config 是目标配置的静态结构。字段 tag 同时是 JSON 键与文档注释——
// "配置长什么样"固化在类型里，加载/校验/使用共用一份定义。
type Config struct {
	Port   int    `json:"port"`   // 监听端口
	Name   string `json:"name"`   // 服务名
	Debug  bool   `json:"debug"`  // 调试开关
	Region string `json:"region"` // 部署地域（可选）
	DBDSN  string `json:"dbDsn"`  // 必填：数据库连接串（走 secret 通道，不进仓库）
}

// Defaults 返回默认值层。环境特定值（DBDSN）不设默认——交给必填校验把关。
func Defaults() Config {
	return Config{Port: 8080, Name: "unnamed", Debug: false}
}

// RequiredError 表示必填配置缺失。实现 Is(target) 使其能被 errors.Is 精确命中
// （带 Key 区分），调用方（CI/发布脚本）能区分"配置不全"与其它解析错误。
type RequiredError struct {
	Key string // 缺失的配置项名（如 DB_DSN）
}

func (e *RequiredError) Error() string {
	return fmt.Sprintf("必填配置缺失: %s", e.Key)
}

func (e *RequiredError) Is(target error) bool {
	t, ok := target.(*RequiredError)
	return ok && t.Key == e.Key
}

var _ error = (*RequiredError)(nil)

// ErrProfileNotFound 表示所选 profile 的配置文件不存在（非致命：跳过并回退）。
var ErrProfileNotFound = errors.New("profile config file not found")

// LoadOptions 注入加载环境，便于测试不碰真实进程环境与磁盘。
type LoadOptions struct {
	Profile string                      // dev/test/prod
	Dir     string                      // 配置文件目录
	Getenv  func(string) (string, bool) // 环境读取（nil = os.LookupEnv）
	Args    []string                    // flag 参数；nil 表示不启用 flag 层
}

// Load 按 默认 → profile 文件 → env → flag 顺序加载配置。
// 返回配置、字段来源表（Config 字段名 → 层名）与错误。
func Load(opts LoadOptions) (Config, map[string]string, error) {
	cfg := Defaults()
	src := map[string]string{
		"Port": SrcDefault, "Name": SrcDefault, "Debug": SrcDefault,
		"Region": SrcDefault, "DBDSN": SrcDefault,
	}

	// 1. profile 文件层：config.<profile>.json。文件不存在 = 警告跳过
	//    （本地开发允许没有 prod 文件），存在则 JSON 覆盖对应默认字段。
	if opts.Dir != "" {
		path := filepath.Join(opts.Dir, "config."+opts.Profile+".json")
		if err := applyFile(&cfg, path, src); err != nil {
			if !errors.Is(err, ErrProfileNotFound) {
				return cfg, src, fmt.Errorf("load profile file: %w", err)
			}
		}
	}

	// 2. env 层：PH20SOL1_PORT / PH20SOL1_NAME / ... 覆盖。
	getenv := opts.Getenv
	if getenv == nil {
		getenv = os.LookupEnv
	}
	envMap := []struct{ field, key string }{
		{"Port", envPrefix + "PORT"},
		{"Name", envPrefix + "NAME"},
		{"Debug", envPrefix + "DEBUG"},
		{"Region", envPrefix + "REGION"},
		{"DBDSN", envPrefix + "DB_DSN"},
	}
	for _, e := range envMap {
		if v, ok := getenv(e.key); ok {
			if err := applyString(&cfg, e.field, v); err != nil {
				return cfg, src, fmt.Errorf("env %s: %w", e.key, err)
			}
			src[e.field] = SrcEnv
		}
	}

	// 3. flag 层：仅当调用方显式传 Args 时启用（nil = 库调用不解析命令行）。
	//    以当前值为默认注册，parse 后与 parse 前对比，变了的字段算 flag 覆盖。
	if opts.Args != nil {
		orig := cfg
		fs := flag.NewFlagSet("config", flag.ContinueOnError)
		fs.IntVar(&cfg.Port, "port", orig.Port, "override port")
		fs.StringVar(&cfg.Name, "name", orig.Name, "override name")
		fs.BoolVar(&cfg.Debug, "debug", orig.Debug, "override debug")
		fs.StringVar(&cfg.Region, "region", orig.Region, "override region")
		fs.StringVar(&cfg.DBDSN, "db-dsn", orig.DBDSN, "override db dsn (secret)")
		if err := fs.Parse(opts.Args); err != nil {
			return cfg, src, fmt.Errorf("parse flags: %w", err)
		}
		markFlag := func(field string, changed bool) {
			if changed {
				src[field] = SrcFlag
			}
		}
		markFlag("Port", cfg.Port != orig.Port)
		markFlag("Name", cfg.Name != orig.Name)
		markFlag("Debug", cfg.Debug != orig.Debug)
		markFlag("Region", cfg.Region != orig.Region)
		markFlag("DBDSN", cfg.DBDSN != orig.DBDSN)
	}

	// 4. 必填校验：fail-fast。DBDSN 缺失立即报错——服务不带空 DSN 启动，
	//    把"运行时连不上库"提前成"启动即失败"。
	if cfg.DBDSN == "" {
		return cfg, src, &RequiredError{Key: "DB_DSN"}
	}
	return cfg, src, nil
}

// applyFile 读 JSON 文件并覆盖 cfg 中"文件实际写了"的字段。
// 文件不存在返回 ErrProfileNotFound（调用方决定是否致命）。
func applyFile(cfg *Config, path string, src map[string]string) error {
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return ErrProfileNotFound
	}
	if err != nil {
		return fmt.Errorf("read %s: %w", path, err)
	}
	// 先用 map 探明"写了哪些键"，避免把未写字段的零值当文件来源误标。
	var present map[string]json.RawMessage
	if err := json.Unmarshal(data, &present); err != nil {
		return fmt.Errorf("parse %s: %w", path, err)
	}
	if err := json.Unmarshal(data, cfg); err != nil {
		return fmt.Errorf("parse %s: %w", path, err)
	}
	jsonField := map[string]string{
		"port": "Port", "name": "Name", "debug": "Debug",
		"region": "Region", "dbDsn": "DBDSN",
	}
	for jKey, field := range jsonField {
		if _, ok := present[jKey]; ok {
			src[field] = SrcFile
		}
	}
	return nil
}

// applyString 用环境变量字符串设置字段：按目标类型解析，带上下文错误。
func applyString(cfg *Config, field, v string) error {
	switch field {
	case "Port":
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 || n > 65535 {
			return fmt.Errorf("invalid port %q: want 1-65535", v)
		}
		cfg.Port = n
	case "Name":
		cfg.Name = v
	case "Debug":
		b, err := strconv.ParseBool(v)
		if err != nil {
			return fmt.Errorf("invalid debug %q: want bool", v)
		}
		cfg.Debug = b
	case "Region":
		cfg.Region = v
	case "DBDSN":
		cfg.DBDSN = v
	}
	return nil
}
