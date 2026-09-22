package config

import (
	"strings"
	"testing"
)

// clearEnv 清空所有相关环境变量, 保证用例间隔离
func clearEnv(t *testing.T) {
	t.Helper()
	for _, k := range []string{
		"GATEWAY_PORT", "KAFKA_BROKERS", "KAFKA_TOPIC", "DEVICE_TOKENS",
		"GATEWAY_WEBHOOK_TOKEN", "GATEWAY_DEV_MODE", "RATE_PER_DEVICE", "RATE_GLOBAL",
	} {
		t.Setenv(k, "")
	}
}

func TestLoad_Defaults(t *testing.T) {
	clearEnv(t)
	cfg, err := Load()
	if err != nil {
		t.Fatalf("默认配置应加载成功: %v", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("默认端口应 8080, 实际 %d", cfg.Port)
	}
	if cfg.KafkaTopic != "vehicle-report-raw" {
		t.Errorf("默认 topic 错误: %s", cfg.KafkaTopic)
	}
	if cfg.DevMode {
		t.Error("DevMode 默认必须为 false")
	}
}

func TestLoad_Override(t *testing.T) {
	clearEnv(t)
	t.Setenv("GATEWAY_PORT", "9090")
	t.Setenv("KAFKA_BROKERS", "k1:9092, k2:9092 ,k3:9092")
	t.Setenv("DEVICE_TOKENS", "t1=OV00000001,t2=OV00000002")

	cfg, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Port != 9090 {
		t.Errorf("端口覆盖失败: %d", cfg.Port)
	}
	if len(cfg.KafkaBrokers) != 3 {
		t.Errorf("brokers 应解析为 3 个(逗号分隔+去空格), 实际 %v", cfg.KafkaBrokers)
	}
	if len(cfg.DeviceTokens) != 2 {
		t.Errorf("tokens 应为 2 个, 实际 %v", cfg.DeviceTokens)
	}
	if got := cfg.DeviceBinding["t1"]; got != "OV00000001" {
		t.Errorf("t1 应绑定 OV00000001, 实际 %q", got)
	}
	if got := cfg.DeviceBinding["t2"]; got != "OV00000002" {
		t.Errorf("t2 应绑定 OV00000002, 实际 %q", got)
	}
}

// TestLoad_DefaultTokenIsBound 默认白名单也必须是绑定形态 ——
// 否则开箱即用的配置本身就带着"token 可上报任意 VIN"的洞。
func TestLoad_DefaultTokenIsBound(t *testing.T) {
	clearEnv(t)
	cfg, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	if len(cfg.DeviceBinding) == 0 {
		t.Fatal("默认 DEVICE_TOKENS 必须解析出绑定关系")
	}
	for token, vin := range cfg.DeviceBinding {
		if token == "" || vin == "" {
			t.Errorf("默认绑定不完整: %q → %q", token, vin)
		}
	}
}

func TestLoad_ProdRequiresTokens(t *testing.T) {
	clearEnv(t)
	// 显式给"空列表"(逗号分隔后全为空 → 白名单为空), 非 dev 模式应拒绝启动(fail-fast)
	t.Setenv("DEVICE_TOKENS", ",")
	if _, err := Load(); err == nil {
		t.Error("生产模式且无有效 DEVICE_TOKENS 应拒绝启动")
	}
	// dev 模式下空 token 可启动(压测场景)
	t.Setenv("GATEWAY_DEV_MODE", "true")
	if _, err := Load(); err != nil {
		t.Errorf("dev 模式空 token 应可启动: %v", err)
	}
}

// TestLoad_RejectsUnboundToken 未绑定 VIN 的 token 必须 fail-fast(两种模式都不放行)。
// 背景: 只有"认证"没有"身份"时, 设备可用合法 token 上报任意 VIN(冒充他人车辆)。
func TestLoad_RejectsUnboundToken(t *testing.T) {
	for _, mode := range []string{"false", "true"} {
		t.Run("DEV_MODE="+mode, func(t *testing.T) {
			clearEnv(t)
			t.Setenv("GATEWAY_DEV_MODE", mode)
			t.Setenv("DEVICE_TOKENS", "demo-token-001")
			_, err := Load()
			if err == nil {
				t.Fatal("未绑定 VIN 的 token 必须被拒绝")
			}
			if !strings.Contains(err.Error(), "token=VIN") {
				t.Errorf("错误信息应给出正确写法提示, 实际 %q", err.Error())
			}
		})
	}
}
