// 来源：ph20-config-release examples/ex05-rollout-decision/main.go
// 一句话说明：用确定性健康曲线回放三个发布故事——一路健康冲到 100%、金丝雀
// 阶段就翻车立即回滚、放量到 30% 后回归触发回滚（主文档 3.4）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
)

func main() {
	// 故事 A：新版本一路健康。4 个档位各喂 3 轮 100% 健康 → 观察窗满即放量，
	// 最后在 full-100 档宣布 complete。
	fmt.Println("== 故事 A：一路健康，逐档放量到 100% ==")
	ra := NewRollout(DefaultPhases())
	healthy := make([]float64, 0, 12)
	for i := 0; i < 12; i++ {
		healthy = append(healthy, 1.0)
	}
	for _, line := range ra.Run(healthy) {
		fmt.Println("  ", line)
	}

	// 故事 B：金丝雀就翻车。第 1 轮健康、第 2~3 轮健康比例跌破阈值 → 回滚。
	fmt.Println("\n== 故事 B：金丝雀期持续不健康，立即回滚 ==")
	rb := NewRollout(DefaultPhases())
	for _, line := range rb.Run([]float64{1.0, 0.4, 0.2}) {
		fmt.Println("  ", line)
	}

	// 故事 C：放量到 30% 后才回归。canary 全好、rolling-30 观察 1 轮后连坏 → 回滚。
	fmt.Println("\n== 故事 C：滚到 30% 后回归异常，中途回滚 ==")
	rc := NewRollout(DefaultPhases())
	samples := []float64{
		1.0, 1.0, 1.0, // canary 观察窗满 → advance
		1.0,      // rolling-30 第 1 轮
		0.5, 0.3, // 连续两轮不健康 → rollback
	}
	for _, line := range rc.Run(samples) {
		fmt.Println("  ", line)
	}

	fmt.Println()
	fmt.Println("说明：健康采样来自探针聚合（服务 /healthz / 错误率预算），决策器只做")
	fmt.Println("     纯逻辑判断；实际放量/撤量由载体执行（K8s 副本数、网关权重，见 ph12）。")
}
