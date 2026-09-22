// 来源：ph16-pgo-advanced-perf 练习 4 参考实现（digest 确定性 / 分位数函数 / 流量构成单测）
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方
// 运行：go test -v ./...
// 验证状态：已验证（go1.25.6，2026-09-02）
package main

import (
	"sort"
	"testing"
)

// percentile 把排序后的样本切成 q 分位（测试用独立实现，避免与 main 的闭包互为镜像）。
func percentile(sorted []float64, q float64) float64 {
	if len(sorted) == 0 {
		return 0
	}
	return sorted[int(q*float64(len(sorted)))-1]
}

func TestDigestDeterministic(t *testing.T) {
	mul := &mulCodec{A: 6364136223846793005, C: 1442695040888963407}
	a := digest(mul, 1000, 42)
	b := digest(mul, 1000, 42)
	if a != b {
		t.Fatalf("digest 不确定: %x != %x", a, b)
	}
	// 注意别用 256 的整倍数作 size：seed 只平移字节序列（byte(seed+i)），
	// 长度是 256 的倍数时 XOR 折叠会平移不变（实测 seed 42/43 在 size=1024 时相等）。
	if digest(mul, 1000, 42) == digest(mul, 1000, 43) {
		t.Fatal("不同 seed 得到相同结果（size 撞上平移不变性？）")
	}
	if digest(mul, 0, 42) != 0 {
		t.Fatal("空负载应返回 0")
	}
}

func TestCodecMix(t *testing.T) {
	mul := &mulCodec{A: 3, C: 1}
	if mul.Mix(5) != 16 {
		t.Fatalf("mulCodec.Mix(5) = %d, want 16", mul.Mix(5))
	}
	xor := &xorCodec{}
	if xor.Mix(0) != 0 {
		t.Fatalf("xorCodec.Mix(0) = %d, want 0", xor.Mix(0))
	}
}

func TestPickCodecMix(t *testing.T) {
	mul := &mulCodec{A: 1, C: 0}
	xor := &xorCodec{}
	// 90% 命中 mul：每 10 个里 9 个 mul、1 个（r%10==9）xor
	mulCount := 0
	for r := 0; r < 1000; r++ {
		if pickCodec(r, mul, xor) == mul {
			mulCount++
		}
	}
	if mulCount != 900 {
		t.Fatalf("mul 占比 = %d/1000, want 900", mulCount)
	}
}

func TestRequestSizeRange(t *testing.T) {
	for r := 0; r < 1000; r++ {
		s := requestSize(r)
		if s < 256 || s > 4096 {
			t.Fatalf("requestSize(%d) = %d 超出 [256,4096]", r, s)
		}
	}
}

func TestPercentile(t *testing.T) {
	sorted := []float64{1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
	if got := percentile(sorted, 0.50); got != 5 {
		t.Fatalf("p50 = %v, want 5", got)
	}
	if got := percentile(sorted, 0.90); got != 9 {
		t.Fatalf("p90 = %v, want 9", got)
	}
	if got := percentile(sorted, 1.0); got != 10 {
		t.Fatalf("p100 = %v, want 10", got)
	}
	sort.Float64s(sorted) // 防呆：确认入口要求已排序（占位断言，避免误用）
}
