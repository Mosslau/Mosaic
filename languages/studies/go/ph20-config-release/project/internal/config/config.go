// Package config 实现多环境分层配置加载：默认值 → profile 文件
// （config.<env>.json）→ 环境变量 → 命令行 flag，返回每字段来源表，
// 并对必填项 fail-fast。零第三方依赖，全部输入可注入以便离线测试。
package config

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// 来源层名（SourceMap 的值）。
const (
	SrcDefault = "default"
	SrcFile    = "file"
	SrcEnv     = "env"
	SrcFlag    = "flag"
)

// EnvPrefix 是环境变量前缀（与 service 名一致，避免宿主无关变量撞名）。
const EnvPrefix = "PH20PROJ_"

// Config 是服务配置。json tag 即配置文件键；字段注释写来源键与默认值。
type Config struct {
	Port     int    `json:"port"`     // 监听端口（默认 8080）
	Name     string `json:"name"`     // 服务名（默认 release-server）
	Debug    bool   `json:"debug"`    // 调试模式（默认 false）
	Region   string `json:"region"`   // 部署地域（可选）
	LogLevel string `json:"logLevel"` // 日志级别 info/debug/warn/error（可热更，见主文档 3.7）
	DBDSN    string `json:"dbDsn"`    // 必填：数据库连接串（secret，不进仓库）
}

// Defaults 返回默认值层。环境特定值（DBDSN/Region）不设默认。
func Defaults() Config {
	return Config{Port: 8080, Name: "release-server", Debug: false, LogLevel: "info"}
}

// SourceMap 记录每字段最终来自哪一层（字段用小写 JSON 键）。发布排障用。
type SourceMap map[string]string

// RequiredError 是必填项缺失的哨兵错误（errors.Is/As 可精确命中，带 Key）。
type RequiredError struct{ Key string }

func (e *RequiredError) Error() string { return fmt.Sprintf("必填配置缺失: %s", e.Key) }
func (e *RequiredError) Is(target error) bool {
	t, ok := target.(*RequiredError)
	return ok && t.Key == e.Key
}

// ErrProfileNotFound 表示所选 profile 的配置文件不存在（非致命，跳过）。
var ErrProfileNotFound = errors.New("profile config file not found")

// Options 注入加载环境（测试/离线使用），Dir 为空则跳过文件层。
type Options struct {
	Profile string                      // dev/test/prod
	Dir     string                      // 配置文件目录
	Getenv  func(string) (string, bool) // env 读取（nil = os.LookupEnv）
	Args    []string                    // flag 参数（nil = 不启用 flag 层）
}

// Load 按 默认 → profile 文件 → env → flag 顺序分层加载。
func Load(o Options) (Config, SourceMap, error) {
	cfg := Defaults()
	src := SourceMap{}
	for k := range fieldKeys {
		src[k] = SrcDefault
	}

	// 1. profile 文件层。
	if o.Dir != "" {
		path := filepath.Join(o.Dir, "config."+o.Profile+".json")
		if err := applyFile(&cfg, path, src); err != nil {
			if !errors.Is(err, ErrProfileNotFound) {
				return cfg, src, err
			}
		}
	}

	// 2. env 层：PH20PROJ_<FIELD>。
	getenv := o.Getenv
	if getenv == nil {
		getenv = os.LookupEnv
	}
	for _, e := range envFields {
		if v, ok := getenv(EnvPrefix + e.envName); ok {
			if err := applyString(&cfg, e.field, v); err != nil {
				return cfg, src, fmt.Errorf("env %s%s: %w", EnvPrefix, e.envName, err)
			}
			src[e.field] = SrcEnv
		}
	}

	// 3. flag 层（仅显式给 Args 时启用）：以当前值为默认，parse 前后对比判来源。
	if o.Args != nil {
		orig := cfg
		fs := flag.NewFlagSet("release-server", flag.ContinueOnError)
		fs.IntVar(&cfg.Port, "port", orig.Port, "override port")
		fs.StringVar(&cfg.Name, "name", orig.Name, "override service name")
		fs.BoolVar(&cfg.Debug, "debug", orig.Debug, "override debug")
		fs.StringVar(&cfg.Region, "region", orig.Region, "override region")
		fs.StringVar(&cfg.LogLevel, "log-level", orig.LogLevel, "override log level")
		fs.StringVar(&cfg.DBDSN, "db-dsn", orig.DBDSN, "override db dsn (secret)")
		if err := fs.Parse(o.Args); err != nil {
			return cfg, src, fmt.Errorf("parse flags: %w", err)
		}
		mark := func(field string, changed bool) {
			if changed {
				src[field] = SrcFlag
			}
		}
		mark("port", cfg.Port != orig.Port)
		mark("name", cfg.Name != orig.Name)
		mark("debug", cfg.Debug != orig.Debug)
		mark("region", cfg.Region != orig.Region)
		mark("logLevel", cfg.LogLevel != orig.LogLevel)
		mark("dbDsn", cfg.DBDSN != orig.DBDSN)
	}

	// 4. 必填校验（fail-fast）：不带 DBDSN 启动 = 运行时才暴露的定时炸弹。
	if cfg.DBDSN == "" {
		return cfg, src, &RequiredError{Key: "DB_DSN"}
	}
	return cfg, src, nil
}

// fieldKeys 与 envFields 表：字段名（JSON 小写）↔ Config 字段 ↔ env 变量名。
var fieldKeys = map[string]string{
	"port": "Port", "name": "Name", "debug": "Debug",
	"region": "Region", "logLevel": "LogLevel", "dbDsn": "DBDSN",
}

var envFields = []struct{ field, envName string }{
	{"port", "PORT"}, {"name", "NAME"}, {"debug", "DEBUG"},
	{"region", "REGION"}, {"logLevel", "LOG_LEVEL"}, {"dbDsn", "DB_DSN"},
}

// applyFile 读 JSON 文件，只把"文件实际写了"的字段计为 file 层来源。
func applyFile(cfg *Config, path string, src SourceMap) error {
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return ErrProfileNotFound
	}
	if err != nil {
		return fmt.Errorf("read %s: %w", path, err)
	}
	var present map[string]json.RawMessage
	if err := json.Unmarshal(data, &present); err != nil {
		return fmt.Errorf("parse %s: %w", path, err)
	}
	if err := json.Unmarshal(data, cfg); err != nil {
		return fmt.Errorf("parse %s: %w", path, err)
	}
	for k := range present {
		if _, ok := fieldKeys[k]; ok {
			src[k] = SrcFile
		}
	}
	return nil
}

// applyString 用 env/flag 字符串设置字段（按类型解析，带上下文错误）。
func applyString(cfg *Config, field, v string) error {
	switch field {
	case "port":
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 || n > 65535 {
			return fmt.Errorf("invalid port %q: want 1-65535", v)
		}
		cfg.Port = n
	case "name":
		cfg.Name = v
	case "debug":
		b, err := strconv.ParseBool(v)
		if err != nil {
			return fmt.Errorf("invalid debug %q: want bool", v)
		}
		cfg.Debug = b
	case "region":
		cfg.Region = v
	case "logLevel":
		lv := strings.ToLower(v)
		switch lv {
		case "info", "debug", "warn", "error":
			cfg.LogLevel = lv
		default:
			return fmt.Errorf("invalid logLevel %q: want info/debug/warn/error", v)
		}
	case "dbDsn":
		cfg.DBDSN = v
	default:
		return fmt.Errorf("unknown config field %q", field)
	}
	return nil
}
