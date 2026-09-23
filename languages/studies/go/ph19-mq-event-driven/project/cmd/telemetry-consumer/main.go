// 来源：ph19-mq-event-driven project/cmd/telemetry-consumer/main.go
// 一句话说明：组装点——fake broker + 数据集 → 消费者组跑一轮 → 打印报表。
// 承接 ph17/ph18 埋下的「消费链路」上下文：上游设备侧上报的遥测进入 topic
// （真实生产形态是 ph21 的 MQTT/网关采集写入，本示例用 dataset 模拟），
// 本服务是链路的"清洗/消费/存储"段：幂等消费、schema 版本校验、重试/死信、
// 积压归零。roadmap §19 推荐项目「设备遥测消费服务」落地。
// 真 Kafka 切换：把 internal/broker 换成 kafka-go 后 consumer/process/store 原样复用——
//
//	go get github.com/segmentio/kafka-go@latest
//	docker run -d -p 9092:9092 apache/kafka:3.7.0
//	Producer: kafka.Writer{Topic:"fleet.telemetry.v1"}（key=deviceID 保证同设备同分区）
//	Consumer: kafka.Reader{GroupID:"fleet-consumers", 分区数=4} + CommitOffsets
//	（未在本环境验证；本仓库无 broker/Docker，离线形态等价于内嵌的 Topic/Group）。
//
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run ./cmd/telemetry-consumer
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"sort"
	"time"

	"tenetlang/go/ph19-mq-event-driven/project/internal/broker"
	"tenetlang/go/ph19-mq-event-driven/project/internal/consumer"
	"tenetlang/go/ph19-mq-event-driven/project/internal/dataset"
	"tenetlang/go/ph19-mq-event-driven/project/internal/process"
	"tenetlang/go/ph19-mq-event-driven/project/internal/store"
)

func main() {
	partitions := flag.Int("partitions", 4, "topic 分区数")
	maxAttempts := flag.Int("max-attempts", 3, "每条消息最大尝试次数（含首次）")
	flag.Parse()

	topic := broker.NewTopic(*partitions)
	published, err := dataset.Build(topic)
	if err != nil {
		log.Fatal(err)
	}

	snap := store.NewSnapshotStore()
	dedup := store.NewSeenWindow(10_000)
	dlog := store.NewDeadLog()
	proc := process.New(snap, dataset.FlakyDevice, 1) // 抖动设备前 1 次处理失败
	consumer := consumer.New(topic, dedup, proc, dlog, consumer.Config{
		MaxAttempts: *maxAttempts,
		Backoff:     func(n int) time.Duration { return time.Duration(n) * 10 * time.Millisecond },
	})

	fmt.Printf("== 设备遥测消费服务：topic=%d 分区，数据集 %d 条 ==\n", *partitions, published)
	start := time.Now()
	rep := consumer.RunOnce()
	fmt.Printf("消费耗时 %v\n\n", time.Since(start))

	fmt.Println("== 消费报表 ==")
	fmt.Printf("   读取 %d 条：真实生效 %d，重复投递拦截 %d，内部重试 %d 次\n",
		rep.Consumed, rep.Applied, rep.DuplicateSkipped, rep.Retried)
	fmt.Printf("   死信 %d 条（毒消息 %d + 重试耗尽 %d），最大积压 %d 条\n",
		rep.Poisoned+rep.Exhausted, rep.Poisoned, rep.Exhausted, rep.MaxLag)

	fmt.Println("\n== 每设备快照（样例）==")
	ids := make([]string, 0, 6)
	states := snap.Devices()
	for id := range states {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	for _, id := range ids {
		if id != "car-001" && id != "car-003" && id != dataset.FlakyDevice {
			continue
		}
		v := states[id]
		fmt.Printf("   %s samples=%d overspeed=%d last_speed=%.0f\n",
			id, v.Samples, v.Overspeed, v.LastSpeed)
	}

	fmt.Println("\n== 死信台账 ==")
	for _, d := range dlog.Entries() {
		fmt.Printf("   msg=%s device=%s reason=%s attempts=%d\n",
			short(d.MsgID), short(d.DeviceID), d.Reason, d.Attempts)
	}

	// 终态积压必须归零（消费追平 = 无积压，主文档 3.7）。
	totalLag := 0
	for p := 0; p < topic.NumPartitions(); p++ {
		totalLag += topic.HighWater(p) - consumer.Committed(p)
	}
	fmt.Printf("\n终态积压：%d 条（应归零）\n", totalLag)
	if totalLag != 0 {
		os.Exit(1)
	}
}

func short(s string) string {
	if len(s) <= 12 {
		return s
	}
	return s[:12]
}
