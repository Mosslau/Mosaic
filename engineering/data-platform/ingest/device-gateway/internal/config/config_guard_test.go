package config

import (
	"strings"
	"testing"
)

// setEnv 设置环境变量并在测试结束后恢复。
func setEnv(t *testing.T, kv map[string]string) {
	t.Helper()
	for k, v := range kv {
		t.Setenv(k, v)
	}
}

// TestLoad_RejectsSubUnitRates 速率 <1 必须 fail-fast。
// 背景(2026-09-18 审计实测): RATE_PER_DEVICE=0.5 这类"每 2 秒一条"的自然写法
// 会让令牌桶容量 int(0.5)=0 → x/time/rate 恒拒绝 → 所有设备永久 429, 且日志只显示"限流"。
func TestLoad_RejectsSubUnitRates(t *testing.T) {
	for _, tc := range []struct {
		name string
		env  map[string]string
		want string
	}{
		{"单设备速率小于 1", map[string]string{"RATE_PER_DEVICE": "0.5"}, "RATE_PER_DEVICE"},
		{"全局速率小于 1", map[string]string{"RATE_GLOBAL": "0.5"}, "RATE_GLOBAL"},
		{"单设备速率非法值回落默认(不报错)", map[string]string{"RATE_PER_DEVICE": "abc"}, ""},
	} {
		t.Run(tc.name, func(t *testing.T) {
			setEnv(t, tc.env)
			cfg, err := Load()
			if tc.want == "" {
				if err != nil {
					t.Fatalf("非法值应回落默认而非报错, 实际 %v", err)
				}
				if cfg.RatePerDevice < 1 {
					t.Fatalf("默认单设备速率必须 >= 1, 实际 %v", cfg.RatePerDevice)
				}
				return
			}
			if err == nil {
				t.Fatalf("期望报错包含 %q, 实际无错误", tc.want)
			}
			if !strings.Contains(err.Error(), tc.want) {
				t.Errorf("错误信息应包含 %q, 实际 %q", tc.want, err.Error())
			}
		})
	}
}

// TestLoad_ObservabilityDefaults 可观测端点默认值: metrics 专用端口 + pprof 仅回环。
func TestLoad_ObservabilityDefaults(t *testing.T) {
	cfg, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	if cfg.MetricsPort != 18081 {
		t.Errorf("GATEWAY_METRICS_PORT 默认应为 18081, 实际 %d", cfg.MetricsPort)
	}
	if cfg.PprofBind != "127.0.0.1" {
		t.Errorf("GATEWAY_PPROF_BIND 默认应为 127.0.0.1(pprof 不得暴露到局域网), 实际 %q", cfg.PprofBind)
	}
	if cfg.PprofPort != 18082 {
		t.Errorf("GATEWAY_PPROF_PORT 默认应为 18082, 实际 %d", cfg.PprofPort)
	}
}

// TestLoad_ProductionRequiresTokens 生产模式(非 dev)必须显式配置 token 白名单。
// 注意: DEVICE_TOKENS 设成空串会走 envList 的"未设置→回落默认"语义, 因此
// 用逗号/空格这种"设了但解析后为空"的值来制造空白名单。
func TestLoad_ProductionRequiresTokens(t *testing.T) {
	setEnv(t, map[string]string{"GATEWAY_DEV_MODE": "false", "DEVICE_TOKENS": ","})
	if _, err := Load(); err == nil {
		t.Fatal("生产模式且白名单为空必须报错")
	}
	// dev 模式则允许空白名单(靠 dev- 前缀放行)
	setEnv(t, map[string]string{"GATEWAY_DEV_MODE": "true", "DEVICE_TOKENS": ","})
	if _, err := Load(); err != nil {
		t.Fatalf("dev 模式应允许空白名单, 实际 %v", err)
	}
}
