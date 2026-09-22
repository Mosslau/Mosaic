package gomodfile

import (
	"os"
	"path/filepath"
	"testing"
)

func TestParse(t *testing.T) {
	cases := []struct {
		name    string
		content string
		wantMod string
		wantGo  string
		wantTC  string
	}{
		{
			name:    "标准三行",
			content: "module example.com/app\n\ngo 1.25.0\n",
			wantMod: "example.com/app", wantGo: "1.25.0",
		},
		{
			name:    "带 toolchain 行与注释",
			content: "module example.com/app\n\ngo 1.25.0\n\ntoolchain go1.25.6\n// 注释行\n",
			wantMod: "example.com/app", wantGo: "1.25.0", wantTC: "go1.25.6",
		},
		{
			name:    "go 行高（工具链门槛演示）",
			content: "module example.com/old\n\ngo 1.21.0\n",
			wantMod: "example.com/old", wantGo: "1.21.0",
		},
		{
			name:    "无 go 行（远古模块）",
			content: "module example.com/legacy\n",
			wantMod: "example.com/legacy",
		},
		{
			name:    "go.mod 的 require 等行被忽略",
			content: "module example.com/app\n\ngo 1.25.0\n\nrequire example.com/dep v1.2.3\n",
			wantMod: "example.com/app", wantGo: "1.25.0",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			req, err := Parse([]byte(tc.content))
			if err != nil {
				t.Fatalf("Parse: %v", err)
			}
			if req.Module != tc.wantMod || req.Go != tc.wantGo || req.Toolchain != tc.wantTC {
				t.Fatalf("Parse = %+v, want module=%q go=%q toolchain=%q",
					req, tc.wantMod, tc.wantGo, tc.wantTC)
			}
		})
	}
}

func TestParseInvalid(t *testing.T) {
	// 二进制垃圾也应安全返回（scanner 不 panic）
	req, err := Parse([]byte("\x00\x01\x02module example.com/x\n"))
	if err != nil {
		t.Fatalf("Parse 不应因脏数据报错: %v", err)
	}
	if req == nil {
		t.Fatal("Parse 返回 nil")
	}
}

func TestFindUp(t *testing.T) {
	// 临时目录树：a/b/c 里只有 a/go.mod，从 c 向上应找到 a/go.mod
	base := t.TempDir()
	if err := os.MkdirAll(filepath.Join(base, "a", "b", "c"), 0o755); err != nil {
		t.Fatal(err)
	}
	modPath := filepath.Join(base, "a", "go.mod")
	if err := os.WriteFile(modPath, []byte("module example.com/x\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	got, err := FindUp(filepath.Join(base, "a", "b", "c"))
	if err != nil {
		t.Fatalf("FindUp: %v", err)
	}
	if got != modPath {
		t.Fatalf("FindUp = %q, want %q", got, modPath)
	}
	// 无 go.mod 的祖先链应报错
	if _, err := FindUp(t.TempDir()); err == nil {
		t.Fatal("FindUp 应报错（无 go.mod）")
	}
}
