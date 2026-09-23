// 来源：ph19-mq-event-driven project/internal/dataset/dataset.go
// 一句话说明：确定性的测试/演示数据集——一台设备一条事件流的"离线录音回放"：
// 5 辆正常设备 ×6 条（含超速样本）、1 辆抖动设备（下游前 1 次处理失败）、3 条
// 重复投递（同一 MsgID 以新 offset 重放）、1 条坏载荷、1 条未来 schema 版本。
// 覆盖消费链路关心的全部输入形态（主文档 3.5/3.6/3.8）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package dataset

import (
	"fmt"

	"tenetlang/go/ph19-mq-event-driven/project/internal/broker"
	"tenetlang/go/ph19-mq-event-driven/project/internal/model"
)

// FlakyDevice 抖动设备：processor 会对其前 flakyFailures 次处理返回可重试错误。
const (
	FlakyDevice = "car-flaky"
)

// Build 把固定数据集写入 topic（分区数由 topic 决定）。
// 返回写入总条数。多次调用会重复写入同一数据集（幂等语义由消费端负责）。
func Build(t *broker.Topic) (int, error) {
	n := 0
	emit := func(e model.TelemetryEvent) error {
		raw, err := e.Encode()
		if err != nil {
			return fmt.Errorf("dataset encode %s: %w", e.MsgID, err)
		}
		t.Produce(e.DeviceID, raw)
		n++
		return nil
	}

	// 1. 5 辆正常设备，每辆 6 条：seq=5 时超速（128 km/h）制造 overspeed 样本。
	devices := []string{"car-001", "car-002", "car-003", "car-004", "car-005"}
	speeds := []float64{40, 50, 60, 70, 128, 90}
	seq1 := make([]model.TelemetryEvent, 0, len(devices))
	for vi, veh := range devices {
		for seq := 0; seq < len(speeds); seq++ {
			e := model.TelemetryEvent{
				MsgID:         fmt.Sprintf("%s-%03d", veh, seq+1),
				SchemaVersion: model.SchemaV1,
				DeviceID:     veh,
				TS:            int64(vi*100 + seq + 1),
				Speed:         speeds[seq],
				Component:       90 - seq,
			}
			if err := emit(e); err != nil {
				return n, err
			}
		}
		seq1 = append(seq1, model.TelemetryEvent{
			MsgID:         fmt.Sprintf("%s-%03d", veh, 1),
			SchemaVersion: model.SchemaV1,
			DeviceID:     veh,
			TS:            int64(vi*100 + 1),
			Speed:         speeds[0],
			Component:       90,
		})
	}

	// 2. 3 条重复投递：前 3 台设备的第 1 条以新 offset 重放（at-least-once）。
	for i := 0; i < 3; i++ {
		if err := emit(seq1[i]); err != nil {
			return n, err
		}
	}

	// 3. 抖动设备一条：处理层会先失败 1 次再成功（重试路径可见）。
	flaky := model.TelemetryEvent{
		MsgID:         "flaky-001",
		SchemaVersion: model.SchemaV1,
		DeviceID:     FlakyDevice,
		TS:            999,
		Speed:         55,
		Component:       88,
	}
	if err := emit(flaky); err != nil {
		return n, err
	}

	// 4. 坏载荷：直接写非法 JSON（毒消息 decode 分类）。
	t.ProduceRaw(0, []byte("not-json{{{"))
	n++

	// 5. 未来 schema 版本：能解码但版本不受支持（毒消息 schema 分类）。
	future := model.TelemetryEvent{
		MsgID:         "schema-9",
		SchemaVersion: 9,
		DeviceID:     "car-999",
		TS:            1000,
		Speed:         0,
		Component:       0,
	}
	if err := emit(future); err != nil {
		return n, err
	}
	return n, nil
}
