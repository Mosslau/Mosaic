// 来源：ph19-mq-event-driven project/internal/process/process.go
// 一句话说明：业务处理层（消费链路里"解码 → 校验 schema → 模拟下游 → 落快照"）。
// 错误即分类信号：解码失败/未知 schema 版本是毒消息（不重试），其余视为可重试
// 的瞬时故障。分类用哨兵 + errors.Is，杜绝字符串匹配（golang-patterns）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package process

import (
	"errors"
	"fmt"

	"tenetlang/go/ph19-mq-event-driven/project/internal/model"
	"tenetlang/go/ph19-mq-event-driven/project/internal/store"
)

// 毒消息分类哨兵：ErrDecode（载荷无法解析）/ ErrSchema（未知未来 schema 版本）
// 都包装自 ErrPoison——consumer 用 errors.Is 分别映射死信原因（主文档 3.6）。
var (
	ErrPoison = errors.New("poison message: retrying will not help")
	ErrDecode = fmt.Errorf("%w: decode failure", ErrPoison)
	ErrSchema = fmt.Errorf("%w: unsupported schema version", ErrPoison)
)

// Processor 处理一条原始消息：解码 + schema 校验 + 落快照。
// flaky 非 nil 时模拟"下游短暂抖动"：对该车辆的前 n 次处理返回可重试错误，
// 让消费端的重试路径在数据集里可见（离线可复现，不靠随机）。
type Processor struct {
	snap *store.SnapshotStore
	// flake 记录"哪个车辆的前 N 次处理会抖动"。
	flake  string
	remain int
}

// New 构造 processor：snap 是副作用落库目标。
// flakyVehicle/flakyTimes 为 0 时禁用抖动模拟。
func New(snap *store.SnapshotStore, flakyVehicle string, flakyTimes int) *Processor {
	return &Processor{snap: snap, flake: flakyVehicle, remain: flakyTimes}
}

// Process 处理一条消息。返回 nil 表示成功；返回的 error 由 consumer 分类：
// errors.Is(ErrPoison/ErrDecode/ErrSchema) → 死信；其他 → 可重试。
func (p *Processor) Process(m model.Message) error {
	// 1. 解码：坏载荷 = 毒消息（decode 分类）。
	e, err := model.Decode(m.Payload)
	if err != nil {
		return fmt.Errorf("%w: %v", ErrDecode, err)
	}
	// 2. schema 版本校验：未知未来版本 = 毒消息（schema 分类）——不猜语义。
	if e.SchemaVersion != model.SchemaV1 {
		return fmt.Errorf("%w: got v%d, want v%d", ErrSchema, e.SchemaVersion, model.SchemaV1)
	}
	// 3. 模拟下游抖动（真实工程这里是 DB/分析服务超时等瞬时故障）。
	if p.flake != "" && p.remain > 0 && e.VehicleID == p.flake {
		p.remain--
		return fmt.Errorf("模拟下游抖动：%s 的这次处理超时", e.VehicleID)
	}
	// 3. 落快照（副作用；已通过幂等检查的键才会走到这里）。
	p.snap.Apply(e)
	return nil
}
