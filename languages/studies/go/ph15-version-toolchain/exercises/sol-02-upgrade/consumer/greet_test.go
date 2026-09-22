package main

import (
	"strings"
	"testing"

	"example.com/greet"
)

// TestGreetContract 消费者对 greet 库的契约断言：以 "Hello, " 开头。
// 把 go.mod 的 require/replace 切到 v1.1.0（../greet-v1.1.0）后本测试会失败——
// 这正是"依赖升级需要测试验证"的落点（演练见 main.go 文件头验证块）。
func TestGreetContract(t *testing.T) {
	got := greet.Greet("service-a")
	if !strings.HasPrefix(got, "Hello, ") {
		t.Fatalf("greet.Greet() = %q, want prefix %q", got, "Hello, ")
	}
}
