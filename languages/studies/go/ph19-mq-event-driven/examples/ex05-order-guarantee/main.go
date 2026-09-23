// 来源：ph19-mq-event-driven examples/ex05-order-guarantee/main.go
// 一句话说明：正反两个分区键策略摆在一起对比——稳定 key 保住每个 key 的内部顺序，
// 轮询/易变 key 让同一台设备的消息散落各分区、顺序被打乱（主文档 3.4）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "fmt"

func main() {
	// —— 正面：稳定 key（deviceID 作为分区键）——
	fmt.Println("== 稳定分区键（key=deviceID）==")
	ok := NewBroker(3)
	produceDemo(ok, true)
	consumed := ConsumeSerially(ok)
	for _, key := range []string{"A", "B"} {
		seq := Values(PerKey(consumed, key))
		fmt.Printf("   key=%s 消费子序列 = %v —— 每个 key 内部保序\n", key, seq)
	}

	// —— 反面：轮询/易变分区键（同 key 散落多分区）——
	fmt.Println("== 轮询分区键（同 key 每来一条换一个分区）==")
	bad := NewBroker(3)
	produceDemo(bad, false)
	consumed = ConsumeSerially(bad)
	broken := false
	for _, key := range []string{"A", "B"} {
		seq := Values(PerKey(consumed, key))
		exp := []string{key + "-1", key + "-2", key + "-3"}
		if !ValuesEqual(seq, exp) {
			broken = true
		}
		fmt.Printf("   key=%s 消费子序列 = %v（期望 %v）\n", key, seq, exp)
	}
	if broken {
		fmt.Println("   ↑ 顺序被打乱：跨分区拼接后同一实体的先后关系已不可信")
	}
}

func produceDemo(b *Broker, stable bool) {
	// A、B 两台设备交替上报 3 次，每次按各自 key 写入（稳定 or 轮询）。
	for i := 1; i <= 3; i++ {
		if stable {
			b.ProduceStable("A", fmt.Sprintf("A-%d", i))
			b.ProduceStable("B", fmt.Sprintf("B-%d", i))
		} else {
			b.ProduceRoundRobin("A", fmt.Sprintf("A-%d", i))
			b.ProduceRoundRobin("B", fmt.Sprintf("B-%d", i))
		}
	}
}
