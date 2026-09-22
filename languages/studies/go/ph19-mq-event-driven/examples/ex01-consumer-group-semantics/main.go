// 来源：ph19-mq-event-driven examples/ex01-consumer-group-semantics/main.go
// 一句话说明：跑一个完整场景，把"分区 → 消费者组 → 提交 → 重平衡"演给人看：
// 3 个分区写入一批车辆遥测 → 2 成员组各分到分区 → 第 3 个成员加入触发重平衡
// → 再写入的增量由新分配下的成员续读（主文档 3.1/3.3）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "fmt"

func main() {
	// 1. topic 建 3 个分区，写入第一批 9 条车辆遥测（按车 key 散列落分区）。
	broker := NewBroker(3)
	type sample struct{ key, value string }
	batch1 := []sample{
		{"car-001", "speed=10"}, {"car-002", "speed=20"}, {"car-003", "speed=30"},
		{"car-001", "speed=12"}, {"car-002", "speed=22"}, {"car-003", "speed=32"},
		{"car-001", "speed=14"}, {"car-002", "speed=24"}, {"car-003", "speed=34"},
	}
	fmt.Println("== 1. 写入 9 条遥测（key 散列到 3 个分区）==")
	for _, s := range batch1 {
		p, off := broker.Produce(s.key, s.value)
		fmt.Printf("   partition=%d offset=%d  %s %s\n", p, off, s.key, s.value)
	}

	// 2. 组内两个成员 m1/m2：m1 领奇数分配、m2 领偶数分配（轮询取模）。
	g := NewGroup("fleet-readers", broker)
	members := []string{"m1", "m2"}
	printAssign(g, members)

	// 3. 两成员各自消费自己分到的分区，处理一条提交一条。
	fmt.Println("== 2. m1/m2 消费各自分区并逐条提交 ==")
	for _, m := range members {
		parts := Assign(broker.NumPartitions(), members)[m]
		total := 0
		for _, p := range parts {
			n, _ := g.Consume(p, func(r Record) error {
				fmt.Printf("   [%s] partition=%d offset=%d %s %s\n", m, p, r.Offset, r.Key, r.Value)
				return nil
			})
			total += n
		}
		fmt.Printf("   [%s] 共处理 %d 条\n", m, total)
	}

	// 4. 第三个成员加入 → 重平衡：每个分区仍恰好归一个成员，成员间重新切分。
	fmt.Println("== 3. m3 加入，重平衡 ==")
	members = append(members, "m3")
	printAssign(g, members)

	// 5. 又写入 3 条增量：旧消息的 offset 已由组提交，新成员只从提交点续读。
	fmt.Println("== 4. 写入增量后由重平衡后的成员续读 ==")
	batch2 := []sample{{"car-001", "speed=50"}, {"car-002", "speed=60"}, {"car-003", "speed=70"}}
	for _, s := range batch2 {
		broker.Produce(s.key, s.value)
	}
	for _, m := range members {
		parts := Assign(broker.NumPartitions(), members)[m]
		total := 0
		for _, p := range parts {
			n, _ := g.Consume(p, func(r Record) error {
				fmt.Printf("   [%s] partition=%d offset=%d %s %s\n", m, p, r.Offset, r.Key, r.Value)
				return nil
			})
			total += n
		}
		fmt.Printf("   [%s] 本次续读 %d 条（旧消息不重复消费 = offset 提交生效）\n", m, total)
	}
}

func printAssign(g *Group, members []string) {
	fmt.Println("== 当前分配（每分区恰好一个成员）==")
	for _, m := range members {
		parts := Assign(g.PartitionCount(), members)[m]
		fmt.Printf("   %s ──▶ 分区 %v\n", m, parts)
	}
}
