package main

import "testing"

// TestWorkspaceWiring 能编译通过本身就证明 workspace 生效：service-a 的 go.mod
// require sharedlib v0.0.0（无发布版本），只有 go.work 把该路径解析到本地目录，
// import 才可能成功。
func TestWorkspaceWiring(t *testing.T) {
	got := run()
	if got != "Hello from sharedlib, service-a!" {
		t.Fatalf("run() = %q, want %q", got, "Hello from sharedlib, service-a!")
	}
}
