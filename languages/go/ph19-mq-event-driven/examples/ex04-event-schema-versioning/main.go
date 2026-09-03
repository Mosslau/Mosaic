// 来源：ph19-mq-event-driven examples/ex04-event-schema-versioning/main.go
// 一句话说明：把"同一 topic 上 schema 演进"演给人看：老消费者读 v2 新事件不炸、
// 新消费者读 v1 老事件靠默认值、未知未来版本被明确拒绝、字段改名导致无声丢数据
// （主文档 3.8；兑现 ph18 3.3/3.4 埋下的"事件里的 schema 版本管理"预告）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
)

func main() {
	// 1. 同一 topic "fleet.telemetry" 里，先有 v1 事件，后来 producer 升级到 v2。
	v1msg, _ := BuildEnvelope("e-001", "telemetry", SchemaV1, TelemetryV1{
		VehicleID: "car-001", TS: 100, Speed: 50,
	})
	v2msg, _ := BuildEnvelope("e-002", "telemetry", SchemaV2, TelemetryV2{
		TelemetryV1: TelemetryV1{VehicleID: "car-001", TS: 101, Speed: 55},
		Lat:         31.23,
		Lng:         121.47,
	})

	// 2. 老消费者（只认得 v1 结构）读两代事件：都成功——v2 多出的 lat/lng 被忽略。
	fmt.Println("== 老消费者（v1 视角）==")
	for _, m := range []Envelope{v1msg, v2msg} {
		v, err := ParseTelemetryV1(m.Data)
		fmt.Printf("   %s schemaVersion=%d → 解析成功 %+v（err=%v）\n", m.MsgID, m.SchemaVersion, v, err)
	}
	fmt.Println("   ↑ v2 事件对老消费者无损：producer 先升级，老 consumer 不被打破")

	// 3. 新消费者读 v1 老事件：lat/lng 落零值——按业务语义决定兜底或标记不完整。
	v, _ := ParseTelemetryV2(v1msg.Data)
	fmt.Println("== 新消费者（v2 视角）读 v1 老事件 ==")
	fmt.Printf("   %+v → lat=%.1f lng=%.1f（零值=该事件确实没有坐标，不是丢了）\n", v, v.Lat, v.Lng)

	// 4. 未知未来版本（v9）：明确拒绝，不猜语义。
	v9, _ := BuildEnvelope("e-003", "telemetry", 9, map[string]any{"something": "new"})
	err := CheckSupported(v9, map[int]bool{SchemaV1: true, SchemaV2: true})
	fmt.Println("== 未来版本策略 ==")
	fmt.Printf("   v9 事件 → CheckSupported 报错：%v\n", err)
	fmt.Println("   真实工程：转存 raw 等配套消费者上线，禁止用旧 schema 硬解析")

	// 5. 字段改名是静默破坏：producer 把 lat 改成 latitude，按旧契约的消费者
	//    解析"成功"但丢了坐标——语法通过、语义丢失，比解析报错更难排查。
	renamed, _ := BuildEnvelope("e-004", "telemetry", SchemaV2,
		map[string]any{"vehicleId": "car-001", "ts": 102, "speed": 60, "latitude": 31.5})
	v5, perr := ParseTelemetryV2(renamed.Data)
	fmt.Println("== 字段改名（违禁示范）==")
	fmt.Printf("   v2'（latitude 顶替 lat）解析：err=%v，lat=%.1f —— 语法成功、语义丢失\n", perr, v5.Lat)
}
