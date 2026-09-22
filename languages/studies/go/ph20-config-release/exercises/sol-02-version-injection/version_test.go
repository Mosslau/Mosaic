// 来源：ph20-config-release exercises/sol-02-version-injection/version_test.go
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"
)

// setInjected 临时模拟 ldflags 注入。
func setInjected(t *testing.T, v, c, d string) {
	t.Helper()
	old := [3]string{version, commit, date}
	version, commit, date = v, c, d
	t.Cleanup(func() { version, commit, date = old[0], old[1], old[2] })
}

func TestJSONOutputHasStableFields(t *testing.T) {
	setInjected(t, "v1.4.0", "abc1234", "2026-09-03T00:00:00Z")
	var buf bytes.Buffer
	if code := run([]string{}, &buf); code != 0 {
		t.Fatalf("run 退出码 = %d, want 0", code)
	}
	var m map[string]any
	if err := json.Unmarshal(buf.Bytes(), &m); err != nil {
		t.Fatalf("输出不是合法 JSON: %v\n%s", err, buf.String())
	}
	if m["version"] != "v1.4.0" || m["commit"] != "abc1234" {
		t.Errorf("JSON 字段错误: %v", m)
	}
	if _, ok := m["goVersion"]; !ok {
		t.Error("JSON 缺少 goVersion（接口字段不允许悄悄删）")
	}
}

func TestVersionFlagPrintsSummaryAndExitsZero(t *testing.T) {
	setInjected(t, "v1.4.0", "abc1234", "2026-09-03")
	var buf bytes.Buffer
	if code := run([]string{"-version"}, &buf); code != 0 {
		t.Fatalf("-version 退出码 = %d, want 0", code)
	}
	out := buf.String()
	for _, want := range []string{"version=v1.4.0", "commit=abc1234"} {
		if !strings.Contains(out, want) {
			t.Errorf("-version 输出缺少 %q，got: %s", want, out)
		}
	}
}

func TestDefaultShowsDev(t *testing.T) {
	// 未注入时诚实显示 dev（不假装发过版）。
	var buf bytes.Buffer
	if code := run([]string{}, &buf); code != 0 {
		t.Fatalf("退出码 = %d, want 0", code)
	}
	if !strings.Contains(buf.String(), `"version": "dev"`) {
		t.Errorf("未注入 JSON 应含 version=dev，got:\n%s", buf.String())
	}
}

func TestUnknownFlagFails(t *testing.T) {
	var buf bytes.Buffer
	if code := run([]string{"-nope"}, &buf); code != 2 {
		t.Errorf("未知 flag 退出码 = %d, want 2", code)
	}
}
