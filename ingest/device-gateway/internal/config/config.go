// Package config 从环境变量加载网关配置。第 1 阶段坚持最小化: 只用环境变量, 不引配置文件库。
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
	KafkaTopic    string   // 车端数据 topic(JSON 通道)
	KafkaBinTopic string   // 二进制原始帧 topic(§7: ov.raw.binary.v1)
	DeviceTokens  []string // 合法设备 token 白名单
	WebhookToken  string   // EMQX webhook 来源鉴权密钥
	DevMode       bool     // 开发模式: 接受所有 "dev-" 前缀 token (仅本地压测用!)
	RatePerDevice float64  // 单设备限流(条/秒)
	RateGlobal    float64  // 全局限流(条/秒)
	MetricsPort   int      // /metrics 端口(需被容器内 Prometheus 抓取, 监听全网卡)
	PprofBind     string   // /debug/pprof 绑定地址(仅回环)
	PprofPort     int      // /debug/pprof 端口
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
		KafkaBinTopic: envStr("KAFKA_BIN_TOPIC", "ov.raw.binary.v1"),
		DeviceTokens:  envList("DEVICE_TOKENS", []string{"demo-token-001"}),
		WebhookToken:  envStr("GATEWAY_WEBHOOK_TOKEN", "dev-webhook-secret"),
		DevMode:       envBool("GATEWAY_DEV_MODE", false),
		RatePerDevice: envFloat("RATE_PER_DEVICE", 10),
		RateGlobal:    envFloat("RATE_GLOBAL", 5000),
		MetricsPort:   envInt("GATEWAY_METRICS_PORT", 18081),
		// pprof 只绑回环: 能读出进程内存(含 webhook 密钥与设备 token)
		PprofBind:     envStr("GATEWAY_PPROF_BIND", "127.0.0.1"),
		PprofPort:     envInt("GATEWAY_PPROF_PORT", 18082),
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
	if cfg.KafkaBinTopic == "" {
		return nil, fmt.Errorf("KAFKA_BIN_TOPIC 不能为空")
	}
	if !cfg.DevMode && len(cfg.DeviceTokens) == 0 {
		return nil, fmt.Errorf("生产模式下 DEVICE_TOKENS 不能为空 (或显式开启 GATEWAY_DEV_MODE)")
	}
	// 限流速率必须 >= 1 条/秒: 令牌桶容量取 int(速率), <1 会被截断为 0,
	// 而 x/time/rate 在 burst=0 时**恒拒绝** → 全量 429(2026-09-18 审计实测复现)。
	if cfg.RatePerDevice < 1 {
		return nil, fmt.Errorf("RATE_PER_DEVICE 必须 >= 1 (条/秒), 实际 %v: 小于 1 会导致令牌桶容量为 0、所有请求被拒", cfg.RatePerDevice)
	}
	if cfg.RateGlobal < 1 {
		return nil, fmt.Errorf("RATE_GLOBAL 必须 >= 1 (条/秒), 实际 %v: 小于 1 会导致令牌桶容量为 0、所有请求被拒", cfg.RateGlobal)
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
