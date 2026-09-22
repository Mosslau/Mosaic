// 来源：ph20-config-release exercises/sol-01-config-loader/loader_test.go
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func fakeGetenv(env map[string]string) func(string) (string, bool) {
	return func(k string) (string, bool) {
		v, ok := env[k]
		return v, ok
	}
}

func writeProfile(t *testing.T, dir, profile, content string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(dir, "config."+profile+".json"), []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestRequiredDBDSNMissingFailsFast(t *testing.T) {
	// 无文件、无 env、无 flag 提供 DBDSN → fail-fast，且错误能被 errors.Is 命中。
	_, _, err := Load(LoadOptions{Profile: "dev", Getenv: fakeGetenv(nil)})
	var req *RequiredError
	if !errors.As(err, &req) {
		t.Fatalf("期望 *RequiredError，got %v", err)
	}
	if req.Key != "DB_DSN" {
		t.Errorf("Key = %q, want DB_DSN", req.Key)
	}
}

func TestProfileFileLoadedAndSourceTraced(t *testing.T) {
	dir := t.TempDir()
	writeProfile(t, dir, "dev", `{"port": 9090, "dbDsn": "postgres://dev@localhost/fleet"}`)

	cfg, src, err := Load(LoadOptions{Profile: "dev", Dir: dir, Getenv: fakeGetenv(nil)})
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Port != 9090 || cfg.DBDSN == "" {
		t.Errorf("cfg = %+v, want port 9090 且有 dbDsn", cfg)
	}
	if src["Port"] != SrcFile || src["DBDSN"] != SrcFile {
		t.Errorf("来源表错误: Port=%s DBDSN=%s, want file/file", src["Port"], src["DBDSN"])
	}
	// 文件没写的字段保持 default 来源。
	if cfg.Name != "unnamed" || src["Name"] != SrcDefault {
		t.Errorf("Name = %q 来源 %s, want unnamed/default", cfg.Name, src["Name"])
	}
}

func TestEnvOverridesFile(t *testing.T) {
	dir := t.TempDir()
	writeProfile(t, dir, "prod", `{"port": 8443, "name": "fleet-api-prod", "dbDsn": "postgres://file@db/fleet"}`)
	env := fakeGetenv(map[string]string{
		envPrefix + "PORT":  "9443",
		envPrefix + "DEBUG": "true",
	})

	cfg, src, err := Load(LoadOptions{Profile: "prod", Dir: dir, Getenv: env})
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Port != 9443 || cfg.Debug != true {
		t.Errorf("cfg = %+v, want port 9443 debug true（env 覆盖）", cfg)
	}
	if src["Port"] != SrcEnv || src["Debug"] != SrcEnv {
		t.Errorf("来源表错误: Port=%s Debug=%s, want env/env", src["Port"], src["Debug"])
	}
	// env 没设的字段仍归文件层。
	if src["DBDSN"] != SrcFile || cfg.DBDSN != "postgres://file@db/fleet" {
		t.Errorf("DBDSN 来源 = %s, want file", src["DBDSN"])
	}
}

func TestFlagBeatsEnv(t *testing.T) {
	env := fakeGetenv(map[string]string{
		envPrefix + "PORT":   "8081",
		envPrefix + "DB_DSN": "postgres://env@db/fleet",
	})
	cfg, src, err := Load(LoadOptions{
		Profile: "dev",
		Getenv:  env,
		Args:    []string{"-port", "7070"},
	})
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Port != 7070 {
		t.Errorf("Port = %d, want 7070（flag 最高优先级）", cfg.Port)
	}
	if src["Port"] != SrcFlag {
		t.Errorf("Port 来源 = %s, want flag", src["Port"])
	}
}

func TestProfileFileMissingFallsBack(t *testing.T) {
	// profile 文件缺失（目录存在但没有该 env 的文件）→ 非致命，env 能顶上。
	dir := t.TempDir()
	env := fakeGetenv(map[string]string{envPrefix + "DB_DSN": "postgres://env@db/fleet"})
	cfg, _, err := Load(LoadOptions{Profile: "staging", Dir: dir, Getenv: env})
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Name != "unnamed" {
		t.Errorf("Name = %q, want unnamed（文件缺失回退默认）", cfg.Name)
	}
}

func TestProfilesSwitchConfig(t *testing.T) {
	dir := t.TempDir()
	writeProfile(t, dir, "dev", `{"port": 9090, "name": "dev-api", "dbDsn": "postgres://dev@db/fleet"}`)
	writeProfile(t, dir, "prod", `{"port": 8443, "name": "prod-api", "dbDsn": "postgres://prod@db/fleet"}`)

	dev, _, err := Load(LoadOptions{Profile: "dev", Dir: dir, Getenv: fakeGetenv(nil)})
	if err != nil {
		t.Fatalf("Load dev: %v", err)
	}
	prod, _, err := Load(LoadOptions{Profile: "prod", Dir: dir, Getenv: fakeGetenv(nil)})
	if err != nil {
		t.Fatalf("Load prod: %v", err)
	}
	if dev.Port == prod.Port || dev.Name == prod.Name {
		t.Errorf("dev/prod 配置应不同: dev=%+v prod=%+v", dev, prod)
	}
}
