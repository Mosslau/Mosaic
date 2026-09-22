// 来源：ph21-data-ingest-gateway project/internal/config/config.go
// 一句话说明：env 加载最小形态（ph20 分层纪律的应用层取子集）——必填项 fail-fast、
// 端口范围校验、每采集器密钥表（"id=secret,id2=secret2"）。零第三方。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

// Config 运行配置（env 注入）。
type Config struct {
	Addr            string
	Secrets         map[string]string // 每采集器一密（接入鉴权）
	CollectorID     string
	CollectorSecret string
	CloudURL        string
	FlushSize       int
	SpoolCap        int
}

// Load 从 getenv 加载；未提供的可选项用默认值。
func Load(getenv func(string) string) (*Config, error) {
	cfg := &Config{
		Addr:      ":8080",
		Secrets:   map[string]string{"relay-001": "dev-secret-1"},
		FlushSize: 3,
		SpoolCap:  64,
	}
	if v := getenv("PLATFORM_ADDR"); v != "" {
		cfg.Addr = v
	}
	if v := getenv("GATEWAY_SECRETS"); v != "" { // "id=secret,id2=secret2"
		m, err := parseSecrets(v)
		if err != nil {
			return nil, err
		}
		cfg.Secrets = m
	}
	if v := getenv("GATEWAY_ID"); v != "" {
		cfg.CollectorID = v
	}
	if v := getenv("GATEWAY_SECRET"); v != "" {
		cfg.CollectorSecret = v
	}
	if v := getenv("CLOUD_URL"); v != "" {
		cfg.CloudURL = v
	}
	if v := getenv("FLUSH_SIZE"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 {
			return nil, fmt.Errorf("FLUSH_SIZE 非法: %q", v)
		}
		cfg.FlushSize = n
	}
	if v := getenv("SPOOL_CAP"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 {
			return nil, fmt.Errorf("SPOOL_CAP 非法: %q", v)
		}
		cfg.SpoolCap = n
	}
	return cfg, nil
}

// LoadFromEnv 从进程环境加载。
func LoadFromEnv() (*Config, error) { return Load(os.Getenv) }

func parseSecrets(s string) (map[string]string, error) {
	out := map[string]string{}
	for _, kv := range strings.Split(s, ",") {
		id, secret, ok := strings.Cut(kv, "=")
		if !ok || id == "" || secret == "" {
			return nil, fmt.Errorf("GATEWAY_SECRETS 格式应为 id=secret,..., got %q", s)
		}
		out[id] = secret
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("GATEWAY_SECRETS 不能为空")
	}
	return out, nil
}
