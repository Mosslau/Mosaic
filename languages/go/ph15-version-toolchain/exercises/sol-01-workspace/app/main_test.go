package main

import "testing"

// TestAppUsesLib 编译依赖 workspace 提供 lib（require v0.0.0 无发布版本），
// 能编译 = workspace 生效；本测试再断言内容。
func TestAppUsesLib(t *testing.T) {
	got := run("t")
	want := "Hello, t! (lib v0.0.0-workspace)"
	if got != want {
		t.Fatalf("run() = %q, want %q", got, want)
	}
}
