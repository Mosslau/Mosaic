// 来源：ph20-config-release examples/ex01-env-file-flag/config_test.go
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"os"
	"strings"
	"testing"
)

// fakeLookup 返回可注入的 getenv：ok=true 表示"设置了"，哪怕值是空串。
func fakeLookup(env map[string]string) func(string) (string, bool) {
	return func(key string) (string, bool) {
		v, ok := env[key]
		return v, ok
	}
}

func TestFromEnvOverridesSetKeysKeepsOthers(t *testing.T) {
	cfg := DefaultConfig()
	err := cfg.FromEnv(fakeLookup(map[string]string{
		envPrefix + "PORT": "7070",
		envPrefix + "NAME": "gateway",
	}))
	if err != nil {
		t.Fatalf("FromEnv: %v", err)
	}
	if cfg.Port != 7070 {
		t.Errorf("Port = %d, want 7070", cfg.Port)
	}
	if cfg.Name != "gateway" {
		t.Errorf("Name = %q, want gateway", cfg.Name)
	}
	if cfg.Debug { // 未设置：应保持默认 false
		t.Errorf("Debug = true, want false（未设置的键不该被改动）")
	}
}

func TestFromEnvEmptyStringCountsAsSet(t *testing.T) {
	// 空串也被判定为"已设置"：允许把文件层/默认值显式清空。
	cfg := DefaultConfig()
	cfg.Name = "to-be-cleared"
	err := cfg.FromEnv(fakeLookup(map[string]string{envPrefix + "NAME": ""}))
	if err != nil {
		t.Fatalf("FromEnv: %v", err)
	}
	if cfg.Name != "" {
		t.Errorf("Name = %q, want 空串（设置成空 = 覆盖）", cfg.Name)
	}
}

func TestFromEnvValidatesPort(t *testing.T) {
	cfg := DefaultConfig()
	err := cfg.FromEnv(fakeLookup(map[string]string{envPrefix + "PORT": "not-a-number"}))
	if err == nil {
		t.Fatal("期望非法 PORT 报错，却得到 nil")
	}
	if !strings.Contains(err.Error(), "invalid "+envPrefix+"PORT") {
		t.Errorf("错误信息应带字段名与预期，got: %v", err)
	}
}

func TestFromEnvUnsetKeyDoesNotTouch(t *testing.T) {
	// 未设置（ok=false）与设置了空值不同：完全不覆盖，字段保持默认。
	cfg := DefaultConfig()
	err := cfg.FromEnv(fakeLookup(map[string]string{
		envPrefix + "PORT":   "6060",
		envPrefix + "REGION": "", // 设置了空 region → 覆盖成空
	}))
	if err != nil {
		t.Fatalf("FromEnv: %v", err)
	}
	if cfg.Region != "" {
		t.Errorf("Region = %q, want 空串（显式设置）", cfg.Region)
	}
	if cfg.Name != "unnamed" { // 未设置 Name：保持默认
		t.Errorf("Name = %q, want unnamed", cfg.Name)
	}
}

func TestFromFileMissingKeyKeepsDefault(t *testing.T) {
	// JSON 文件里没写的键不清默认；写了的键覆盖。
	path := writeSampleConfig([]byte(`{"port": 8081}`))
	defer os.Remove(path) // 测试内忽略清理错误即可
	cfg := DefaultConfig()
	if err := cfg.FromFile(path); err != nil {
		t.Fatalf("FromFile: %v", err)
	}
	if cfg.Port != 8081 {
		t.Errorf("Port = %d, want 8081", cfg.Port)
	}
	if cfg.Name != "unnamed" {
		t.Errorf("Name = %q, want unnamed（缺键不清默认）", cfg.Name)
	}
}
