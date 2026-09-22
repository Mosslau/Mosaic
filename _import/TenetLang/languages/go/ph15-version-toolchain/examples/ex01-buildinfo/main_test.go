package main

import (
	"runtime/debug"
	"strings"
	"testing"
)

func TestReportShape(t *testing.T) {
	out := report()
	// runtime.Version() 形如 "go1.25.6"，是编译该二进制的工具链版本
	if !strings.HasPrefix(out, "runtime.Version(): go") {
		t.Fatalf("输出应以 runtime.Version(): go 开头, 实际: %q", out)
	}
	// 模块版本来自 debug.ReadBuildInfo()：在 git 仓库内构建且打了 tag 时
	// 才是 vX.Y.Z；未打 tag 时是 "(devel)"——断言不锁死具体值
	for _, want := range []string{"main module      :", "go version(build):"} {
		if !strings.Contains(out, want) {
			t.Fatalf("输出缺少 %q, 完整输出:\n%s", want, out)
		}
	}
}

func TestReadBuildInfoMainPath(t *testing.T) {
	bi, ok := debug.ReadBuildInfo()
	if !ok {
		t.Skip("build info 不可用")
	}
	want := "tenetlang/go/ph15-version-toolchain/examples/ex01-buildinfo"
	if bi.Main.Path != want {
		t.Fatalf("main module path = %q, want %q", bi.Main.Path, want)
	}
	if bi.GoVersion == "" {
		t.Fatal("GoVersion 为空：构建信息应含 go 工具链版本")
	}
}
