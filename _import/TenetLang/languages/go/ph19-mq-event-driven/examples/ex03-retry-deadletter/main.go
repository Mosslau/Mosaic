// 来源：ph19-mq-event-driven examples/ex03-retry-deadletter/main.go
// 一句话说明：演示三类结局——(1) 下游抖动，重试 2 次后成功；(2) 永远失败的可重试
// 错误，耗尽 3 次进死信；(3) 毒消息，一次失败立即进死信、不浪费重试（主文档 3.6）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"errors"
	"fmt"
	"time"
)

func main() {
	// 指数退避：第 1 次重试等 50ms、第 2 次 100ms、第 3 次 200ms……
	backoff := func(n int) time.Duration {
		d := time.Duration(1<<(n-1)) * 50 * time.Millisecond
		fmt.Printf("   ⏳ 退避 %s 后重试…\n", d)
		return d
	}
	dlq := NewDLQ()
	p := NewPipeline(Config{MaxAttempts: 3, Backoff: backoff}, dlq)

	// 场景 1：下游前两次抖动、第三次成功（可重试错误）。
	attempts := 0
	out1 := p.Handle(Message{ID: "m1", Payload: "order-1 扣款"},
		func(Message) error {
			attempts++
			if attempts < 3 {
				return Retryable(errors.New("下游超时（可重试）"))
			}
			return nil
		})
	fmt.Printf("m1 → %s（尝试 %d 次后成功，抖动场景）\n\n", out1.Status, out1.Attempts)

	// 场景 2：永远失败的可重试错误 → 3 次耗尽进死信。
	out2 := p.Handle(Message{ID: "m2", Payload: "order-2 扣款"},
		func(Message) error {
			return Retryable(errors.New("三方通道永久不可达"))
		})
	fmt.Printf("m2 → %s（重试耗尽，进死信）\n\n", out2.Status)

	// 场景 3：毒消息 → 只试 1 次就进死信，不浪费剩余 2 次重试。
	calls := 0
	out3 := p.Handle(Message{ID: "m3", Payload: "not-json{{{"},
		func(Message) error {
			calls++
			return fmt.Errorf("%w: JSON 解析失败", ErrPoison)
		})
	fmt.Printf("m3 → %s（仅尝试 %d 次；calls=%d，毒消息不重试）\n\n", out3.Status, out3.Attempts, calls)

	fmt.Println("== 死信队列内容 ==")
	for _, e := range dlq.Entries() {
		fmt.Printf("   id=%s attempts=%d reason=%s\n", e.Message.ID, e.Attempts, e.Reason)
	}
	fmt.Println("m1 成功不计入死信；m2/m3 的死信原因分类不同——排查路径也不同。")
}
