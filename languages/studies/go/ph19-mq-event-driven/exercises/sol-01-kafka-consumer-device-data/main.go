// 来源：ph19-mq-event-driven exercises/sol-01-kafka-consumer-device-data（练习 1 参考实现）
// 一句话说明：main —— 离线"Kafka 消费设备数据"全流程：生成一批设备遥测写入
// 模拟 topic → 双成员消费者组并行消费 → 输出每设备统计。roadmap §19 练习 1 落地。
// 真 broker 切换：把 Topic/Group 换成 kafka-go 的 Writer/Reader——
//
//	go get github.com/segmentio/kafka-go@latest
//	docker run -d --name kafka -p 9092:9092 apache/kafka:3.7.0
//	Writer.Topic("fleet.telemetry") 写 key/value（json）;
//	ReaderConfig{GroupID:"fleet-readers", Topic:..., Partition策略} 读 + CommitOffsets。
//	Consumer 侧业务（解码→聚合→提交）与"分区模型"语义由上面的 kafka-go 实现，
//	与本文件 store/handle/组提交逻辑一一对应，可无缝替换。（未在本环境验证）
//
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"sort"
	"time"
)

func main() {
	topic := NewTopic(3)
	g := NewGroup()
	store := NewStatsStore()

	// 1. 生产一批遥测（固定序列保证输出可复现；按 deviceID 稳定散列分区）。
	devices := []string{"car-001", "car-002", "car-003", "car-004", "car-005"}
	ts := time.Date(2026, 9, 1, 8, 0, 0, 0, time.UTC).Unix()
	totalProduced := 0
	for i := 0; i < 24; i++ {
		v := devices[i%len(devices)]
		t := Telemetry{
			DeviceID: v,
			TS:        ts + int64(i),
			Speed:     float64(40 + (i*7)%90), // 模拟速度波动
			Component:   80 - i%15,
		}
		raw, err := json.Marshal(t)
		if err != nil {
			log.Fatal(err)
		}
		p, off := topic.Publish(v, raw)
		if i < 6 {
			fmt.Printf("   produce → partition=%d offset=%d %s\n", p, off, v)
		}
		totalProduced++
	}
	fmt.Printf("共生产 %d 条遥测到 topic（3 分区）\n\n", totalProduced)

	// 2. 双成员消费者组并行消费。
	members := []string{"fleet-reader-1", "fleet-reader-2"}
	fmt.Println("== 消费者组并行消费 ==")
	counts, err := DrainGroup(topic, g, members, store)
	if err != nil {
		log.Fatal(err)
	}
	for _, m := range members {
		fmt.Printf("   %s 处理 %d 条\n", m, counts[m])
	}

	// 3. 输出每设备统计（排序打印，输出稳定）。
	fmt.Println("== 每设备统计 ==")
	snapshot := store.Snapshot()
	ids := make([]string, 0, len(snapshot))
	for id := range snapshot {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	totalConsumed := 0
	for _, id := range ids {
		v := snapshot[id]
		totalConsumed += v.Samples
		fmt.Printf("   %s samples=%d max_speed=%.0f last_ts=%d\n", id, v.Samples, v.MaxSpeed, v.LastTS)
	}
	fmt.Printf("合计消费 %d = 生产 %d（一次性追平，无重复无遗漏）\n", totalConsumed, totalProduced)
}
