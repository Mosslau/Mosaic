// 来源：ph16-pgo-advanced-perf 练习 1 参考实现（compressBlock 的单测）
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行：go test -v ./...
// 验证状态：已验证（go1.25.6，2026-09-03）
package main

import "testing"

func TestCompressBlock(t *testing.T) {
	a := make([]byte, 4096)
	b := make([]byte, 4096)
	b[0] = 1
	if compressBlock(a) != compressBlock(a) {
		t.Fatal("compressBlock 不确定")
	}
	if compressBlock(a) == compressBlock(b) {
		t.Fatal("不同输入得到相同结果")
	}
	if compressBlock(nil) == 0 {
		t.Fatal("空块不应坍缩到 0 常量")
	}
}
