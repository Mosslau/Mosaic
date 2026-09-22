// 来源：ph20-config-release examples/ex04-version-injection/version_test.go
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"strings"
	"testing"
)

func TestGatherUsesInjectedVars(t *testing.T) {
	// 模拟 ldflags 注入：把包级变量改成真实发布时的值。
	oldV, oldC, oldD := version, commit, date
	version, commit, date = "v1.2.3", "9f1a2b3", "2026-09-03T00:00:00Z"
	defer func() { version, commit, date = oldV, oldC, oldD }()

	info := Gather()
	if info.Version != "v1.2.3" {
		t.Errorf("Version = %q, want v1.2.3", info.Version)
	}
	if info.Commit != "9f1a2b3" {
		t.Errorf("Commit = %q, want 9f1a2b3", info.Commit)
	}
	if info.Date != "2026-09-03T00:00:00Z" {
		t.Errorf("Date = %q, want 2026-09-03T00:00:00Z", info.Date)
	}
	if info.GoVersion == "" || !strings.HasPrefix(info.GoVersion, "go") {
		t.Errorf("GoVersion = %q, want go1.x.y", info.GoVersion)
	}
	if info.OSArch == "" {
		t.Error("OSArch 不应为空")
	}
	if info.ModulePath == "" {
		t.Error("ModulePath 不应为空（ReadBuildInfo 应能读到主模块）")
	}
}

func TestGatherDefaultsToDev(t *testing.T) {
	// 不注入时的默认：version=dev、commit=none——诚实暴露"没走发布流水线"。
	info := Gather()
	if info.Version != "dev" || info.Commit != "none" {
		t.Errorf("未注入时 Version/Commit = %q/%q, want dev/none", info.Version, info.Commit)
	}
}

func TestSummaryAndFullContainKeyFields(t *testing.T) {
	oldV, oldC, oldD := version, commit, date
	version, commit, date = "v2.0.0", "abc", "2026-01-01"
	defer func() { version, commit, date = oldV, oldC, oldD }()

	info := Gather()
	s := info.Summary()
	for _, want := range []string{"version=v2.0.0", "commit=abc", "go="} {
		if !strings.Contains(s, want) {
			t.Errorf("Summary() 缺少 %q，got: %s", want, s)
		}
	}
	f := info.Full()
	for _, want := range []string{"version:      v2.0.0", "commit:       abc", "go version:   "} {
		if !strings.Contains(f, want) {
			t.Errorf("Full() 缺少 %q", want)
		}
	}
}
