// Package config 从环境变量加载网关配置。期①坚持最小化: 只用环境变量, 不引配置文件库。
package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

// Config 网关全部配置
type Config struct {
	Port          int      // HTTP 监听端口
	KafkaBrokers  []string // Kafka broker 列表
	KafkaTopic    string   // 车端数据 topic
	DeviceTokens  []string // 合法设备 token 白名单
	WebhookToken  string   // EMQX webhook 来源鉴权密钥
	DevMode       bool     // 开发模式: 接受所有 "dev-" 前缀 token (仅本地压测用!)
	RatePerDevice float64  // 单设备限流(条/秒)
	RateGlobal    float64  // 全局限流(条/秒)
	ReadTimeout   time.Duration
	WriteTimeout  time.Duration
	ShutdownGrace time.Duration
}

// Load 从环境变量加载配置, 带合理默认值。
func Load() (*Config, error) {
	cfg := &Config{
		Port:          envInt("GATEWAY_PORT", 8080),
		KafkaBrokers:  envList("KAFKA_BROKERS", []string{"localhost:19092"}),
		KafkaTopic:    envStr("KAFKA_TOPIC", "vehicle-report-raw"),
		DeviceTokens:  envList("DEVICE_TOKENS", []string{"demo-token-001"}),
		WebhookToken:  envStr("GATEWAY_WEBHOOK_TOKEN", "dev-webhook-secret"),
		DevMode:       envBool("GATEWAY_DEV_MODE", false),
		RatePerDevice: envFloat("RATE_PER_DEVICE", 10),
		RateGlobal:    envFloat("RATE_GLOBAL", 5000),
		ReadTimeout:   envDur("GATEWAY_READ_TIMEOUT", 5*time.Second),
		WriteTimeout:  envDur("GATEWAY_WRITE_TIMEOUT", 5*time.Second),
		ShutdownGrace: envDur("GATEWAY_SHUTDOWN_GRACE", 10*time.Second),
	}
	if len(cfg.KafkaBrokers) == 0 {
		return nil, fmt.Errorf("KAFKA_BROKERS 不能为空")
	}
	if cfg.KafkaTopic == "" {
		return nil, fmt.Errorf("KAFKA_TOPIC 不能为空")
	}
	if !cfg.DevMode && len(cfg.DeviceTokens) == 0 {
		return nil, fmt.Errorf("生产模式下 DEVICE_TOKENS 不能为空 (或显式开启 GATEWAY_DEV_MODE)")
	}
	return cfg, nil
}

// ---- env 辅助函数 -------------------------------------------------------
// 统一语义: 环境变量"未设置或非法"时一律回退默认值, 保证配置在任何环境都可用;
// 真正的必填校验集中在 Load() 末尾(fail-fast), 辅助函数本身不报错。

func envStr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func envList(key string, def []string) []string {
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	parts := strings.Split(v, ",")
	out := parts[:0]
	for _, p := range parts {
		if s := strings.TrimSpace(p); s != "" {
			out = append(out, s)
		}
	}
	return out
}

func envInt(key string, def int) int {
	if v, err := strconv.Atoi(os.Getenv(key)); err == nil && v > 0 {
		return v
	}
	return def
}

func envFloat(key string, def float64) float64 {
	if v, err := strconv.ParseFloat(os.Getenv(key), 64); err == nil && v > 0 {
		return v
	}
	return def
}

func envBool(key string, def bool) bool {
	if v, err := strconv.ParseBool(os.Getenv(key)); err == nil {
		return v
	}
	return def
}

func envDur(key string, def time.Duration) time.Duration {
	if v, err := time.ParseDuration(os.Getenv(key)); err == nil && v > 0 {
		return v
	}
	return def
}
