// 来源：ph16-pgo-advanced-perf 示例 ex05-bench-baseline（测试 + 基准）
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行：go test -v ./...；go test -run='^$' -bench=. -benchmem -count=6
// 验证状态：已验证（go1.25.6，2026-09-03）
package main

import (
	"os"
	"testing"
)

func TestChecksumDeterministic(t *testing.T) {
	data := "device-0001 online latency=42ms"
	if checksum(data, 0) != checksum(data, 0) {
		t.Fatal("checksum 不确定")
	}
	if checksum(data, 0) == checksum(data+"x", 0) {
		t.Fatal("不同输入得到相同结果")
	}
}

var sinkU uint64

// BenchmarkChecksum 是回归脚本守护的基准。
// SLOW=1 环境变量模拟"某次提交把代码改慢了"（每字节多 2 轮混合）——
// 只影响演示，不影响正确性；真实场景里"慢"来自代码变更而非开关。
func BenchmarkChecksum(b *testing.B) {
	extra := 0
	if os.Getenv("SLOW") == "1" {
		extra = 2
	}
	data := "device-0001 online latency=42ms fw=v1.2 rssi=-67"
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		sinkU = checksum(data, extra)
	}
}
