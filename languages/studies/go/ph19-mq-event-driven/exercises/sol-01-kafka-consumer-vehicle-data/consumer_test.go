// 来源：ph19-mq-event-driven exercises/sol-01-kafka-consumer-vehicle-data（练习 1 参考实现）
// 一句话说明：练习 1 验收的可执行版本——组消费无重无漏、分配无重叠、解码失败
// 浮出、提交后新成员续读不重放（承接 examples/ex01 的语义测试）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"fmt"
	"testing"
)

// publishTelemetry 造一条遥测并发布。
func publishTelemetry(topic *Topic, vehicle string, ts int64, speed float64) {
	raw, _ := json.Marshal(Telemetry{VehicleID: vehicle, TS: ts, Speed: speed})
	topic.Publish(vehicle, raw)
}

// TestDrainGroupConsumesAllOnce 双成员组消费一轮：每车 samples == 该车生产条数，
// 总条数 == 生产条数（无重复、无遗漏）。
func TestDrainGroupConsumesAllOnce(t *testing.T) {
	topic := NewTopic(3)
	g := NewGroup()
	store := NewStatsStore()
	produced := map[string]int{}
	for i := 0; i < 18; i++ {
		veh := fmt.Sprintf("car-%03d", i%6)
		publishTelemetry(topic, veh, int64(i), float64(i))
		produced[veh]++
	}
	counts, err := DrainGroup(topic, g, []string{"w1", "w2"}, store)
	if err != nil {
		t.Fatal(err)
	}
	total := counts["w1"] + counts["w2"]
	if total != 18 {
		t.Fatalf("consumed total=%d, want 18", total)
	}
	for veh, want := range produced {
		if got := store.Snapshot()[veh].Samples; got != want {
			t.Fatalf("vehicle %s samples=%d, want %d", veh, got, want)
		}
	}
}

// TestAssignmentNoOverlapNoGap 分配不变量：分区 6、成员 3，每个分区恰好一个成员。
func TestAssignmentNoOverlapNoGap(t *testing.T) {
	got := AssignPartitions(6, []string{"a", "b", "c"})
	seen := map[int]int{}
	for _, parts := range got {
		for _, p := range parts {
			seen[p]++
		}
	}
	for p := 0; p < 6; p++ {
		if seen[p] != 1 {
			t.Fatalf("partition %d assigned %d times", p, seen[p])
		}
	}
}

// TestDecodeFailureSurfaces 坏载荷（非 JSON）应让 DrainGroup 返回错误而不是静默吞掉。
func TestDecodeFailureSurfaces(t *testing.T) {
	topic := NewTopic(1)
	topic.Publish("car-001", []byte("not-json{{{"))
	_, err := DrainGroup(topic, NewGroup(), []string{"w1"}, NewStatsStore())
	if err == nil {
		t.Fatal("decode failure must surface as error")
	}
}

// TestResumeFromCommitted 提交后换成员续读：新成员只读增量，不重放已提交消息。
func TestResumeFromCommitted(t *testing.T) {
	topic := NewTopic(1)
	g := NewGroup()
	store := NewStatsStore()
	publishTelemetry(topic, "car-001", 1, 10)
	publishTelemetry(topic, "car-001", 2, 20)
	// w1 先消费完当前 2 条（提交到 offset 2）
	if _, err := DrainGroup(topic, g, []string{"w1"}, store); err != nil {
		t.Fatal(err)
	}
	// 上游又追加 3 条；w2 接管同一分区
	for i := 3; i <= 5; i++ {
		publishTelemetry(topic, "car-001", int64(i), float64(i*10))
	}
	counts, err := DrainGroup(topic, g, []string{"w2"}, store)
	if err != nil {
		t.Fatal(err)
	}
	if counts["w2"] != 3 {
		t.Fatalf("w2 consumed %d, want 3（只应读新增的 3 条）", counts["w2"])
	}
	if v := store.Snapshot()["car-001"]; v.Samples != 5 {
		t.Fatalf("car-001 samples=%d, want 5", v.Samples)
	}
}
