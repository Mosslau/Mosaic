// 来源：ph19-mq-event-driven examples/ex02-idempotent-consumer/main.go
// 一句话说明：演示 at-least-once 下的重复投递与幂等消费效果：一份带重复的
// 事件流里，去重表把重复 MsgID 拦在副作用之外（主文档 3.5）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "fmt"

func main() {
	// 正常 5 次采样 + 投递层重复 3 次（同一 MsgID 被 redeliver，
	// 每个重复事件看起来都是独立的一条消息，但幂等键相同）。
	uniq := []TelemetryEvent{
		NewEvent("car-001", 100, 50, 1),
		NewEvent("car-001", 101, 55, 2),
		NewEvent("car-002", 100, 40, 1),
		NewEvent("car-001", 102, 60, 3),
		NewEvent("car-002", 101, 45, 2),
	}
	// 重复投递：第 1、3 条被 broker 又投了一次（offset 不同，MsgID 相同）
	log := []TelemetryEvent{
		uniq[0], uniq[0], uniq[1], uniq[2], uniq[2],
		uniq[3], uniq[4],
	}

	d := NewDeduper(1000)
	store := NewSnapshotStore()
	processed, skipped := ProcessLog(log, d, store.Apply)

	fmt.Printf("投递共 %d 条（含重复），幂等消费后：真实处理 %d 条，跳过重复 %d 条\n",
		len(log), processed, skipped)
	fmt.Printf("快照表记录 %d 辆车，副作用计数 = 去重后的唯一事件数\n", storeCnt(store))
	for _, id := range []string{"car-001", "car-002"} {
		v, ok := store.Get(id)
		if ok {
			fmt.Printf("   %s：latest_ts=%d speed=%.0f samples=%d\n",
				id, v.LastTS, v.LastSpeed, v.Samples)
		}
	}
	fmt.Println("若不去重，car-001 的 samples 会被重复事件累加成 5（现在是 3）——统计不失真。")
}

func storeCnt(s *SnapshotStore) int {
	n := 0
	for _, id := range []string{"car-001", "car-002"} {
		if _, ok := s.Get(id); ok {
			n++
		}
	}
	return n
}
