package check

import (
	"strings"
	"testing"

	"tenetlang/go/ph15-version-toolchain/project/internal/gomodfile"
)

func mkReq(goLine, tc string) *gomodfile.Requirement {
	return &gomodfile.Requirement{Module: "example.com/x", Go: goLine, Toolchain: tc}
}

func TestRun(t *testing.T) {
	cases := []struct {
		name    string
		req     *gomodfile.Requirement
		current string
		want    string
		wantMsg string
	}{
		{"go 行满足", mkReq("1.25.0", ""), "go1.25.6", "ok", "≥"},
		{"go+toolchain 全满足", mkReq("1.25.0", "go1.25.6"), "go1.25.6", "ok", "≥"},
		{"go 行硬门槛失败", mkReq("1.99.0", ""), "go1.25.6", "fail", "硬门槛"},
		{"toolchain 更高告警", mkReq("1.25.0", "go1.26.0"), "go1.25.6", "warn", "auto 模式"},
		{"未声明 go 行", mkReq("", ""), "go1.25.6", "ok", "未声明"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			r := Run(tc.req, "/tmp/x/go.mod", tc.current, "")
			if string(r.Status) != tc.want {
				t.Fatalf("status = %q, want %q（message: %s）", r.Status, tc.want, r.Message)
			}
			if !strings.Contains(r.Message, tc.wantMsg) && !strings.Contains(r.Details, tc.wantMsg) {
				t.Fatalf("message/details 应含 %q: %q / %q", tc.wantMsg, r.Message, r.Details)
			}
		})
	}
}

func TestRunWantPolicy(t *testing.T) {
	// 当前 1.25.6 ≥ go 行 1.25.0，但 -want 1.26.0 把结论升级为 fail
	r := Run(mkReq("1.25.0", ""), "go.mod", "go1.25.6", "go1.26.0")
	if r.Status != StatusFail {
		t.Fatalf("策略门槛应 fail, got %q (%s)", r.Status, r.Message)
	}
	if !strings.Contains(r.Message, "策略要求") {
		t.Fatalf("message 应说明策略要求: %q", r.Message)
	}
	// -want 低于当前 → 不影响 ok
	r2 := Run(mkReq("1.25.0", ""), "go.mod", "go1.25.6", "go1.24.0")
	if r2.Status != StatusOK {
		t.Fatalf("低于当前的 -want 不应改变结论, got %q", r2.Status)
	}
}
