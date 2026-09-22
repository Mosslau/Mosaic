// 来源：ph20-config-release project/e2e_test.go
// 一句话说明：端到端验收——把多环境配置、版本自报、灰度裁决、发布预检四件事
// 串起来离体验证：跨环境配置不同、来源表正确、必填报错、灰度确定性、
// 好候选全绿 / 坏候选被拦。零第三方、无网络、无真配置中心。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...（另跑 go test -race ./...）
// 验证状态：已验证（go1.25.6 本机实测 vet/build/test 及 -race 全绿，gofmt 合规）
package project

import (
	"errors"
	"strings"
	"testing"

	"tenetlang/go/ph20-config-release/project/internal/config"
	"tenetlang/go/ph20-config-release/project/internal/feature"
	"tenetlang/go/ph20-config-release/project/internal/release"
	"tenetlang/go/ph20-config-release/project/internal/version"
)

// 复用仓库内 configs 样例目录做多环境切换测试（目录是模块自身资源）。
const configsDir = "./configs"

func TestMultiEnvConfigsDiffer(t *testing.T) {
	dev, devSrc, err := config.Load(config.Options{Profile: "dev", Dir: configsDir})
	if err != nil {
		t.Fatalf("load dev: %v", err)
	}
	prod, prodSrc, err := config.Load(config.Options{Profile: "prod", Dir: configsDir})
	if err != nil {
		t.Fatalf("load prod: %v", err)
	}
	if dev.Name == prod.Name || dev.Port == prod.Port {
		t.Errorf("dev/prod 配置应不同：dev=%+v prod=%+v", dev, prod)
	}
	if dev.Debug != true || prod.Debug != false {
		t.Errorf("dev.Debug=%v prod.Debug=%v, want true/false", dev.Debug, prod.Debug)
	}
	if prod.Region != "cn-north-1" {
		t.Errorf("prod.Region = %q, want cn-north-1", prod.Region)
	}
	// 来源可追溯：这些值来自 profile 文件。
	for _, k := range []string{"name", "port", "dbDsn", "logLevel"} {
		if devSrc[k] != config.SrcFile || prodSrc[k] != config.SrcFile {
			t.Errorf("%s 来源 dev=%s prod=%s, want file/file", k, devSrc[k], prodSrc[k])
		}
	}
}

func TestEnvOverridesFileAndSourceTraced(t *testing.T) {
	env := func(k string) (string, bool) {
		m := map[string]string{config.EnvPrefix + "PORT": "7070"}
		v, ok := m[k]
		return v, ok
	}
	cfg, src, err := config.Load(config.Options{Profile: "dev", Dir: configsDir, Getenv: env})
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Port != 7070 {
		t.Errorf("Port = %d, want 7070（env 覆盖文件）", cfg.Port)
	}
	if src["port"] != config.SrcEnv {
		t.Errorf("port 来源 = %s, want env", src["port"])
	}
}

func TestFlagBeatsEnvAndFile(t *testing.T) {
	cfg, src, err := config.Load(config.Options{
		Profile: "dev",
		Dir:     configsDir,
		Args:    []string{"-port", "6060", "-log-level", "warn"},
	})
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Port != 6060 || cfg.LogLevel != "warn" {
		t.Errorf("cfg = port=%d logLevel=%s, want 6060/warn", cfg.Port, cfg.LogLevel)
	}
	if src["port"] != config.SrcFlag || src["logLevel"] != config.SrcFlag {
		t.Errorf("来源: port=%s logLevel=%s, want flag/flag", src["port"], src["logLevel"])
	}
}

func TestRequiredDBDSNErrorIsMatchable(t *testing.T) {
	// 缺 DBDSN 时 errors.As 能精确命中哨兵（CI 可据此分类失败）。
	_, _, err := config.Load(config.Options{Profile: "empty", Dir: t.TempDir()})
	var req *config.RequiredError
	if !errors.As(err, &req) {
		t.Fatalf("期望 *config.RequiredError, got %v", err)
	}
	if req.Key != "DB_DSN" {
		t.Errorf("Key = %q, want DB_DSN", req.Key)
	}
}

func TestFeatureDecisionDeterministicAndPriority(t *testing.T) {
	internal := func(u string) bool { return strings.HasPrefix(u, "user-000") }
	f := feature.Feature{Name: "realtime-map", Allow: internal, Percent: 50}
	if err := f.Validate(); err != nil {
		t.Fatalf("Validate: %v", err)
	}
	// 同一 user 跨调用一致。
	for _, u := range []string{"user-0000", "user-0042", "user-0099"} {
		if feature.Evaluate(f, u) != feature.Evaluate(f, u) {
			t.Fatalf("user %s 裁决不稳定", u)
		}
	}
	if !feature.Evaluate(f, "user-0000") {
		t.Error("白名单 user-0000 应可见")
	}
	// HardOff 越过一切。
	f.HardOff = true
	if feature.Evaluate(f, "user-0000") {
		t.Error("HardOff 后白名单也不可见")
	}
}

func TestReleasePreflightGoodPassesBadFails(t *testing.T) {
	suite := release.StandardChecks()
	status := func(c release.Candidate) map[string]release.Status {
		m := map[string]release.Status{}
		for _, r := range suite.Run(c) {
			m[r.ID] = r.Status
		}
		return m
	}

	good := release.Candidate{
		Version:      "v2.1.0",
		ConfigText:   `{"dbDsn": "postgres://app@db/fleet"}`,
		Flags:        []release.FlagState{{Name: "old-dark", MustBeOff: true, IsOff: true}},
		Migrations:   []release.Migration{{ID: 1, Breaking: false, Note: "expand"}},
		RollbackPlan: "rollout undo --to v1.9.0",
	}
	for id, want := range map[string]release.Status{
		"version-injected": release.StatusPass, "no-plaintext-secret": release.StatusPass,
		"removed-flags-off": release.StatusPass, "migration-ids-monotonic": release.StatusPass,
		"breaking-migration-expanded": release.StatusPass, "rollback-plan-present": release.StatusPass,
	} {
		if got := status(good)[id]; got != want {
			t.Errorf("good check %s = %v, want %v", id, got, want)
		}
	}

	bad := release.Candidate{
		Version:    "dev",
		ConfigText: `{"dsn": "postgres://app:SuperSecret@db/fleet"}`,
		Flags:      []release.FlagState{{Name: "old-dark", MustBeOff: true, IsOff: false}},
		Migrations: []release.Migration{
			{ID: 2, Breaking: true, Note: "drop column"}, // 编号跳号 + 无 expand
		},
	}
	st := status(bad)
	for _, id := range []string{
		"version-injected", "no-plaintext-secret", "removed-flags-off",
		"migration-ids-monotonic", "breaking-migration-expanded", "rollback-plan-present",
	} {
		if st[id] != release.StatusFail {
			t.Errorf("bad check %s = %v, want FAIL", id, st[id])
		}
	}
}

func TestVersionInfoShape(t *testing.T) {
	// 版本自报的基本形状（值断言见 examples/ex04 单测；这里防字段悄悄退化）。
	info := version.Gather()
	if info.GoVersion == "" || info.OSArch == "" {
		t.Error("GoVersion/OSArch 不应为空")
	}
	if !strings.HasPrefix(info.Summary(), "version=") {
		t.Errorf("Summary 格式异常: %s", info.Summary())
	}
}
