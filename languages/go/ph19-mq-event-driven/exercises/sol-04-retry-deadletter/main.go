// 来源：ph19-mq-event-driven exercises/sol-04-retry-deadletter（练习 4 参考实现）
// 一句话说明：main —— 三类结局演示：抖动后成功（重投 2 次）、可重试错误耗尽进 DLQ、
// 毒消息一次失败即 DLQ（主文档 3.6）。roadmap §19 练习 4「处理重试和死信」落地。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"errors"
	"fmt"
)

func main() {
	// 1. 抖动作业：前两次失败（可重试），第三次成功。
	attempts1 := 0
	p1 := NewPipeline(3, func(j Job) error {
		attempts1++
		if attempts1 < 3 {
			return errors.New("下游超时（可重试）")
		}
		return nil
	})
	rep1 := p1.Run([]Job{{ID: "j1", Payload: "扣款"}})
	fmt.Printf("j1：成功，共尝试 %d 次（processed=%d retried=%d dead=%d）\n\n",
		attempts1, rep1.Processed, rep1.Retried, rep1.Dead)

	// 2. 永久可重试失败 → 尝试满 3 次进 DLQ。
	attempts2 := 0
	p2 := NewPipeline(3, func(j Job) error {
		attempts2++
		return errors.New("三方通道不可达")
	})
	rep2 := p2.Run([]Job{{ID: "j2", Payload: "扣款"}})
	fmt.Printf("j2：dead（dead=%d），共尝试 %d 次\n", rep2.Dead, attempts2)

	// 3. 毒消息 → 不重试，一次即 DLQ。
	attempts3 := 0
	p3 := NewPipeline(3, func(j Job) error {
		attempts3++
		return fmt.Errorf("%w: JSON 解析失败", ErrPoison)
	})
	rep3 := p3.Run([]Job{{ID: "j3", Payload: "not-json"}})
	fmt.Printf("j3：dead（毒消息，dead=%d），只尝试 %d 次\n\n", rep3.Dead, attempts3)

	fmt.Println("== DLQ 明细（含各自原因）==")
	for _, e := range append(append([]DLQEntry{}, p2.DLQ()...), p3.DLQ()...) {
		fmt.Printf("   id=%s attempts=%d poison=%v reason=%s\n",
			e.Job.ID, e.Job.Attempts+1, e.Poison, e.Reason)
	}
}
