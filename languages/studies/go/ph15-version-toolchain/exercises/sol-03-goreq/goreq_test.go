package main

import (
	"os"
	"strings"
	"testing"
)

func TestParseGoMod(t *testing.T) {
	cases := []struct {
		name, file string
		wantMod    string
		wantGo     string
		wantTC     string
	}{
		{"基本三行", "testdata/basic.mod", "example.com/basic", "1.25.0", ""},
		{"注释与空行", "testdata/commented.mod", "example.com/commented", "1.24.0", ""},
		{"含 toolchain 行", "testdata/toolchain-ok.mod", "example.com/withtoolchain", "1.25.0", "go1.25.6"},
		{"go 行高于当前", "testdata/gohigh.mod", "example.com/gohigh", "1.99.0", ""},
		{"无 go 行", "testdata/nogo.mod", "example.com/nogo", "", ""},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			data, err := os.ReadFile(tc.file)
			if err != nil {
				t.Fatal(err)
			}
			req, err := parseGoMod(data)
			if err != nil {
				t.Fatalf("parseGoMod: %v", err)
			}
			if req.Module != tc.wantMod || req.Go != tc.wantGo || req.Toolchain != tc.wantTC {
				t.Fatalf("parseGoMod(%s) = %+v, want module=%q go=%q toolchain=%q",
					tc.file, req, tc.wantMod, tc.wantGo, tc.wantTC)
			}
		})
	}
}

func TestCompareVersions(t *testing.T) {
	cases := []struct {
		a, b string
		want int
	}{
		{"go1.25.6", "1.25.0", 1}, // 前缀不同照样按数字比
		{"1.25.0", "go1.25.0", 0},
		{"1.25", "1.25.0", 0}, // 缺段补 0
		{"1.25.6", "1.25.60", -1},
		{"1.26", "1.25.99", 1},
		{"1.21", "1.22", -1},
	}
	for _, tc := range cases {
		if got := compareVersions(tc.a, tc.b); got != tc.want {
			t.Fatalf("compareVersions(%q, %q) = %d, want %d", tc.a, tc.b, got, tc.want)
		}
	}
}

func TestRequiredVersionPriority(t *testing.T) {
	// toolchain 行与 go 行各自独立参与判定（Check 内部），这里只验证两行都被解析
	req := &Requirement{Go: "1.25.0", Toolchain: "go1.25.6"}
	if req.Toolchain != "go1.25.6" || req.Go != "1.25.0" {
		t.Fatalf("解析结果不符: %+v", req)
	}
}

func TestCheck(t *testing.T) {
	cases := []struct {
		name    string
		req     Requirement
		current string
		want    string
		wantSub string
	}{
		{"go 行满足", Requirement{Go: "1.24.0"}, "1.25.6", "ok", "OK"},
		{"go 行+toolchain 全满足", Requirement{Go: "1.25.0", Toolchain: "go1.25.6"}, "1.25.6", "ok", "OK"},
		{"go 行高于当前(硬门槛)", Requirement{Go: "1.99.0"}, "1.25.6", "fail", "FAIL"},
		{"toolchain 行高于当前(告警)", Requirement{Go: "1.25.0", Toolchain: "go1.26.0"}, "1.25.6", "warn", "WARN"},
		{"未声明 go 行", Requirement{}, "1.25.6", "ok", "未声明"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			status, lines := Check(&tc.req, tc.current)
			if status != tc.want {
				t.Fatalf("Check status = %q, want %q（输出: %v）", status, tc.want, lines)
			}
			if !strings.Contains(strings.Join(lines, "\n"), tc.wantSub) {
				t.Fatalf("Check 输出应含 %q, got %v", tc.wantSub, lines)
			}
		})
	}
}
