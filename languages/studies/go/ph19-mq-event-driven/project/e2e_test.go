// 来源：ph19-mq-event-driven project（根目录端到端验收）
// 一句话说明：e2e 把"设备遥测消费服务"完整跑一遍并对账：数据集里有什么输入、
// 服务就该输出什么（无重复副作用、毒消息进死信、抖动重试成功、积压归零）。
// 验收方式：go test ./... 全绿 = 消费链路符合设计。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...（含 -race）    验证状态：已验证（go1.25.6 本机实测全绿）
package project

import (
	"testing"

	"tenetlang/go/ph19-mq-event-driven/project/internal/broker"
	"tenetlang/go/ph19-mq-event-driven/project/internal/consumer"
	"tenetlang/go/ph19-mq-event-driven/project/internal/dataset"
	"tenetlang/go/ph19-mq-event-driven/project/internal/model"
	"tenetlang/go/ph19-mq-event-driven/project/internal/process"
	"tenetlang/go/ph19-mq-event-driven/project/internal/store"
)

// telemetryConsumer 组装消费服务（与 cmd 相同），返回可断言的部件。
func telemetryConsumer(t *broker.Topic) (*consumer.Consumer, *store.SnapshotStore, *store.DeadLog, consumer.Report) {
	snap := store.NewSnapshotStore()
	dedup := store.NewSeenWindow(10_000)
	dlog := store.NewDeadLog()
	proc := process.New(snap, dataset.FlakyDevice, 1) // 抖动设备前 1 次处理失败
	c := consumer.New(t, dedup, proc, dlog, consumer.Config{MaxAttempts: 3})
	return c, snap, dlog, c.RunOnce()
}

// scanExpected 独立于实现扫描 topic，给出输入的"应有结局"（对账基准）。
func scanExpected(t *broker.Topic) (unique, duplicates, poison, total int) {
	seen := map[string]bool{}
	for p := 0; p < t.NumPartitions(); p++ {
		for _, m := range t.Slice(p, 0) {
			total++
			e, err := model.Decode(m.Payload)
			if err != nil || e.SchemaVersion != model.SchemaV1 {
				poison++ // 坏载荷或未来 schema：毒消息
				continue
			}
			if seen[e.MsgID] {
				duplicates++
				continue
			}
			seen[e.MsgID] = true
		}
	}
	unique = len(seen)
	return unique, duplicates, poison, total
}

// TestEndToEndDeviceTelemetry 全链路验收。
func TestEndToEndDeviceTelemetry(t *testing.T) {
	topic := broker.NewTopic(4)
	published, err := dataset.Build(topic)
	if err != nil {
		t.Fatal(err)
	}
	expUnique, expDup, expPoison, expTotal := scanExpected(topic)
	if published != expTotal {
		t.Fatalf("dataset published=%d but scanned=%d", published, expTotal)
	}

	c, snap, dlog, rep := telemetryConsumer(topic)

	// 1. 基本数目：全部消息被读到；结果 = 输入账本。
	if rep.Consumed != expTotal {
		t.Fatalf("consumed=%d, want %d", rep.Consumed, expTotal)
	}
	if rep.Applied != expUnique {
		t.Fatalf("applied=%d, want unique=%d", rep.Applied, expUnique)
	}
	if rep.DuplicateSkipped != expDup {
		t.Fatalf("duplicateSkipped=%d, want %d", rep.DuplicateSkipped, expDup)
	}
	if rep.Poisoned+rep.Exhausted != expPoison {
		t.Fatalf("dead=%d (poisoned=%d exhausted=%d), want poison=%d",
			rep.Poisoned+rep.Exhausted, rep.Poisoned, rep.Exhausted, expPoison)
	}

	// 2. 重试确实发生过（抖动设备），且最终成功生效一次。
	if rep.Retried < 1 {
		t.Fatalf("retried=%d, want >=1（抖动设备必须走上重试路径）", rep.Retried)
	}
	if v, ok := snap.State(dataset.FlakyDevice); !ok || v.Samples != 1 {
		t.Fatalf("flaky device snapshot=%+v ok=%v, want samples=1", v, ok)
	}

	// 3. 幂等落地：5 辆正常设备各 samples=6、overspeed=1（重复投递没造成重复计数）。
	for _, want := range []string{"car-001", "car-002", "car-003", "car-004", "car-005"} {
		v, ok := snap.State(want)
		if !ok {
			t.Fatalf("device %s missing", want)
		}
		if v.Samples != 6 {
			t.Fatalf("%s samples=%d, want 6", want, v.Samples)
		}
		if v.Overspeed != 1 {
			t.Fatalf("%s overspeed=%d, want 1", want, v.Overspeed)
		}
	}

	// 4. 死信台账分类正确：decode 1 条（坏载荷）+ schema 1 条（未来版本）。
	byReason := map[string]int{}
	for _, d := range dlog.Entries() {
		byReason[d.Reason]++
	}
	if byReason["decode"] != 1 || byReason["schema"] != 1 {
		t.Fatalf("dead reasons=%v, want decode=1 schema=1", byReason)
	}

	// 5. 积压与提交：终态 lag=0；过程中见过积压（MaxLag>0）。
	for p := 0; p < topic.NumPartitions(); p++ {
		if lag := topic.HighWater(p) - c.Committed(p); lag != 0 {
			t.Fatalf("partition %d final lag=%d, want 0", p, lag)
		}
	}
	if c.MaxLag() <= 0 {
		t.Fatalf("MaxLag=%d, want >0（过程中应出现过积压水位）", c.MaxLag())
	}

	// 6. 快照设备数：5 正常 + 1 抖动 = 6（毒消息的 car-999 不应落库）。
	if got := len(snap.Devices()); got != 6 {
		t.Fatalf("snapshot devices=%d, want 6", got)
	}
}
