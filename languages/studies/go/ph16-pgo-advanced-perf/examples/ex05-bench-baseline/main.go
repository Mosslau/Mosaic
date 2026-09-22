// 来源：ph16-pgo-advanced-perf 示例 ex05-bench-baseline（性能回归基线）
// 一句话说明：一个被基准覆盖的小函数 + 一个 benchstat 思路的回归脚本——
// benchregress.sh baseline 存基线（-count=6 取中位数），benchregress.sh check
// 重跑对比，中位数回归超过阈值（默认 10%）即 exit 1，可直接挂 CI。
// 验证环境：go1.25.6（darwin/arm64，Apple M4 Pro），依赖：零第三方 + bash/awk/sort
// 运行（cd ex05-bench-baseline）：
//
//	# 1. 正确性
//	go test -v ./...
//	# 2. 存基线（产物在 /tmp，不进仓库）
//	./benchregress.sh baseline
//	# 3. 无回归：check 通过（exit 0）
//	./benchregress.sh check
//	# 4. 人为制造回归：SLOW=1 让 checksum 每字节多混 2 轮，check 必须报警（exit 1）
//	SLOW=1 ./benchregress.sh check
//	# 5.（可选）装过 benchstat 的话，同一份数据可直接喂给它做统计显著性分析
//	benchstat /tmp/ph16/ex05-baseline.txt /tmp/ph16/ex05-current.txt
//
// 验证块（go1.25.6 实测，2026-09-03，数字随机器波动 ±10~20%）：
//
//	$ ./benchregress.sh baseline   → 基线写入 /tmp/ph16/ex05-baseline.txt（6 次采样，中位数 27.65 ns/op）
//	$ ./benchregress.sh check      → PASS  基线 27.6 → 本次 27.2 ns/op（-1.6%），exit 0
//	$ SLOW=1 ./benchregress.sh check → REGRESSION 27.6 → 103.5 ns/op（+274.5%），exit 1
//	$ benchstat baseline current   → +278.39% (p=0.002 n=6) —— benchstat 统计显著性实测可用
//
// 验证状态：已验证（go1.25.6，2026-09-03）
package main

import "fmt"

// checksum 是被基准守护的函数：FNV 风格逐字节混合，extra 控制额外混合轮数
// （extra 只用于教学演示"回归"——SLOW=1 时 benchmark 传 extra=2 模拟代码变慢）。
func checksum(data string, extra int) uint64 {
	h := uint64(1469598103934665603)
	for i := 0; i < len(data); i++ {
		h ^= uint64(data[i])
		h *= 1099511628211
		for k := 0; k < extra; k++ {
			h ^= h >> 13
			h *= 1099511628211
		}
	}
	return h
}

func main() {
	fmt.Printf("checksum=%x\n", checksum("device-0001 online latency=42ms", 0))
}
