package gbt32960

import (
	"encoding/hex"
	"errors"
	"testing"
	"time"
)

// golden 58B 示例帧(与 simframe 黄金样本/映射文档示例一致): 0x08 + 0x09
const goldenFrameHex = "232302fe" +
	"4f56323032363030303100000000000000" +
	"01" + "0021" +
	"1a09110c1e00" +
	"080101025a26dd00040001040ccc0cd00cc10cc7" +
	"0901010002474b" +
	"65"

// goldenFullFrameHex 142B 全信息体帧(由 device-simulator 的 simframe 生成后固化):
// 0x01 整车 + 0x05 位置 + 0x06 极值 + 0x07 报警 + 0x08 电压 + 0x09 温度 + 0x80 charging + 0x81 work
// —— 覆盖 vehicle_status 与 fault 两条主力解码路径(此前无用例)
const goldenFullFrameHex = "232302fe4f5632303236303030310000000000000001" +
	"00751a09110c1e00" +
	"010103ff01450001e2404effffffffffff" + // 0x01: 状态01/充电03/运行ff, 车速 0145=32.5, 里程 0001e240=12345.6, SOC 4e=78, 其余无效
	"050006ca96200157eee0" + // 0x05: 定位有效, lng 06ca9620=113.94, lat 0157eee0=22.54
	"06ffffffffffffffffffff4bffff44" + // 0x06: 电压极值无效, temp_max 4b=35℃, temp_min 44=28℃
	"07010000000001000e1001000000" + // 0x07: 等级01, 标志0, 1 个故障码 000e1001
	"080101025a26dd00020001020ccc0cd0" + // 0x08: 60.2V / -5.1A / 单体 [3.276, 3.280]
	"0901010002474b" + // 0x09: 探针 [31, 35]
	"8001000f002d00960050000004000000005803" + // 0x80: 45min / 1.5kW / 0.8kWh / 桩1024 / 站88 / 仓3
	"81010009010304b0007d03203c" + // 0x81: riding / sport / 1200rpm / 12.5N·m / 800W / 60%
	"33"

func mustHex(t *testing.T, s string) []byte {
	t.Helper()
	b, err := hex.DecodeString(s)
	if err != nil {
		t.Fatalf("测试样本 hex 非法: %v", err)
	}
	return b
}

// TestParseFrame_Golden 包头轻解析: 帧同步/VIN 去填充/命令字/BCC(§2)
func TestParseFrame_Golden(t *testing.T) {
	f, err := ParseFrame(mustHex(t, goldenFrameHex))
	if err != nil {
		t.Fatalf("黄金样本应解析成功: %v", err)
	}
	if f.Cmd != 0x02 || f.Ack != 0xFE {
		t.Errorf("命令单元应为 02 fe, 实际 %02x %02x", f.Cmd, f.Ack)
	}
	if f.VIN != "OV20260001" {
		t.Errorf("VIN 应去填充为 OV20260001, 实际 %q", f.VIN)
	}
	if len(f.Data) != 33 {
		t.Errorf("数据单元应 33B, 实际 %d", len(f.Data))
	}
}

// TestDecode_Golden 黄金样本解码: 0x08+0x09 → 一条 battery_status(§8-④)
func TestDecode_Golden(t *testing.T) {
	f, err := ParseFrame(mustHex(t, goldenFrameHex))
	if err != nil {
		t.Fatal(err)
	}
	reports, dlq, err := DecodeV1(f)
	if err != nil || len(dlq) != 0 {
		t.Fatalf("应无错误无 DLQ: err=%v dlq=%v", err, dlq)
	}
	if len(reports) != 1 {
		t.Fatalf("应合并为 1 条 battery_status, 实际 %d 条", len(reports))
	}
	r := reports[0]
	if r.Type != "battery_status" || r.VIN != "OV20260001" || r.SchemaVersion != "v1" {
		t.Errorf("信封字段不符: %+v", r)
	}
	if r.Ts != 1789619400 { // 2026-09-17 12:30:00 GMT+8
		t.Errorf("ts 应为 1789619400, 实际 %d", r.Ts)
	}
	if *r.Data.Voltage != 60.2 || *r.Data.Current != -5.1 {
		t.Errorf("电压/电流解码错误: %v %v", *r.Data.Voltage, *r.Data.Current)
	}
	wantCells := []float64{3.276, 3.280, 3.265, 3.271}
	if len(r.Data.CellVoltages) != 4 {
		t.Fatalf("应有 4 节单体, 实际 %d", len(r.Data.CellVoltages))
	}
	for i, v := range wantCells {
		if r.Data.CellVoltages[i] != v {
			t.Errorf("单体[%d] 应为 %v, 实际 %v", i, v, r.Data.CellVoltages[i])
		}
	}
	if len(r.Data.ProbeTemps) != 2 || r.Data.ProbeTemps[0] != 31 || r.Data.ProbeTemps[1] != 35 {
		t.Errorf("探针温度应为 [31 35], 实际 %v", r.Data.ProbeTemps)
	}
}

// TestParseFrame_BCC 校验失败 → 帧级错误(整帧 DLQ)
func TestParseFrame_BCC(t *testing.T) {
	raw := mustHex(t, goldenFrameHex)
	raw[len(raw)-1] ^= 0xFF // 破坏 BCC
	if _, err := ParseFrame(raw); err == nil {
		t.Error("BCC 错误应检出")
	}
}

// TestParseFrame_Sync 起始符错误 → 帧同步失败
func TestParseFrame_Sync(t *testing.T) {
	raw := mustHex(t, goldenFrameHex)
	raw[0] = 0x00
	if _, err := ParseFrame(raw); err == nil {
		t.Error("起始符错误应检出")
	}
}

// TestDecode_CustomUnits 0x80/0x81 解码(§5.2): 枚举翻译 + 有符号值 + 无效值丢弃
func TestDecode_CustomUnits(t *testing.T) {
	// 数据单元: 时间 + 0x80(15B) + 0x81(9B)
	du := mustHex(t,
		"1a09110c1e00"+ // 时间
			"8001"+"000f"+ // 0x80 统一头 v1, 15B
			"002d"+"0096"+"0050"+"00000400"+"00000058"+"03"+ // 45min, 1.5kW, 0.8kWh, 桩1024, 站88, 仓3
			"8101"+"0009"+ // 0x81 统一头 v1, 9B
			"01"+"03"+"04b0"+"ffdd"+"fe48"+"3c") // 行驶/运动/1200rpm/-3.5N·m/-440W/60%
	f := &Frame{Cmd: 0x02, VIN: "OV20260001", Data: du}
	reports, dlq, err := DecodeV1(f)
	if err != nil || len(dlq) != 0 {
		t.Fatalf("应无错误无 DLQ: err=%v dlq=%v", err, dlq)
	}
	if len(reports) != 2 {
		t.Fatalf("应输出 charging + work 两条, 实际 %d", len(reports))
	}
	var charging, work = reports[0], reports[1]
	if reports[0].Type == "work" {
		charging, work = reports[1], reports[0]
	}
	if charging.Type != "charging" {
		t.Fatalf("应有 charging 类型, 实际 %s", charging.Type)
	}
	if *charging.Data.RemainChargeMin != 45 || *charging.Data.PileID != 1024 ||
		*charging.Data.StationID != 88 || *charging.Data.SlotNo != 3 {
		t.Errorf("charging 字段解码错误: %+v", charging.Data)
	}
	if *charging.Data.ChargePower != 1.5 || *charging.Data.ChargeKWh != 0.8 {
		t.Errorf("charging 功率/电量解码错误: %v %v", *charging.Data.ChargePower, *charging.Data.ChargeKWh)
	}
	if work.Type != "work" {
		t.Fatalf("应有 work 类型, 实际 %s", work.Type)
	}
	if *work.Data.RideState != "riding" || *work.Data.RideMode != "sport" {
		t.Errorf("枚举翻译错误: %v %v", *work.Data.RideState, *work.Data.RideMode)
	}
	if *work.Data.MotorRPM != 1200 || *work.Data.MotorTorque != -3.5 || *work.Data.MotorPower != -440 || *work.Data.Throttle != 60 {
		t.Errorf("work 数值解码错误: %+v", work.Data)
	}
}

// TestDecode_UnknownCustomVersion 未知自定义单元版本 → 单元级 DLQ(版本纪律: 不猜), 帧其余部分不受影响
func TestDecode_UnknownCustomVersion(t *testing.T) {
	du := mustHex(t,
		"1a09110c1e00"+
			"8002"+"000f"+"002d00960050000004000000005803") // 0x80 但版本 v2
	f := &Frame{Cmd: 0x02, VIN: "OV20260001", Data: du}
	reports, dlq, err := DecodeV1(f)
	if err != nil {
		t.Fatalf("单元级失败不应升级为帧级错误: %v", err)
	}
	if len(reports) != 0 {
		t.Errorf("未知版本单元不应产出, 实际 %d 条", len(reports))
	}
	if len(dlq) != 1 || dlq[0].UnitType != 0x80 {
		t.Fatalf("应有 1 条 0x80 单元 DLQ, 实际 %+v", dlq)
	}
}

// TestDecode_FullFrame_AllBodies 全信息体帧: 一条帧拆出 5 类 L2 消息, 覆盖
// 0x01 整车 / 0x05 位置 / 0x06 极值 / 0x07 报警 四条此前无用例的解码路径(§8-④ 拆分规则)。
func TestDecode_FullFrame_AllBodies(t *testing.T) {
	f, err := ParseFrame(mustHex(t, goldenFullFrameHex))
	if err != nil {
		t.Fatalf("全信息体帧应解析成功: %v", err)
	}
	reports, dlq, err := DecodeV1(f)
	if err != nil || len(dlq) != 0 {
		t.Fatalf("应无错误无 DLQ: err=%v dlq=%v", err, dlq)
	}
	byType := map[string]int{}
	for _, r := range reports {
		byType[string(r.Type)]++
	}
	// 拆分规则: 0x01+0x05+0x06 合并一条 vehicle_status; 0x07 独立 fault;
	// 0x08+0x09 合并 battery_status; 0x80/0x81 各一条 → 共 5 条
	want := map[string]int{"vehicle_status": 1, "battery_status": 1, "fault": 1, "charging": 1, "work": 1}
	if len(reports) != 5 {
		t.Fatalf("应输出 5 条, 实际 %d 条: %v", len(reports), byType)
	}
	for k, v := range want {
		if byType[k] != v {
			t.Errorf("type=%s 应 %d 条, 实际 %d", k, v, byType[k])
		}
	}
	if len(dlq) != 0 {
		t.Errorf("不应有单元级 DLQ: %v", dlq)
	}

	for _, r := range reports {
		switch r.Type {
		case "vehicle_status":
			// 0x01 整车
			if got := *r.Data.Speed; got != 32.5 {
				t.Errorf("speed 应 32.5, 实际 %v", got)
			}
			if got := *r.Data.Odometer; got != 12345.6 {
				t.Errorf("odometer 应 12345.6, 实际 %v", got)
			}
			if got := *r.Data.SOC; got != 78 {
				t.Errorf("soc 应 78, 实际 %v", got)
			}
			// 0x05 位置
			if got := *r.Data.Lng; got != 113.94 {
				t.Errorf("lng 应 113.94, 实际 %v", got)
			}
			if got := *r.Data.Lat; got != 22.54 {
				t.Errorf("lat 应 22.54, 实际 %v", got)
			}
			// 0x06 极值
			if got := *r.Data.TempMax; got != 35 {
				t.Errorf("temp_max 应 35, 实际 %v", got)
			}
			if got := *r.Data.TempMin; got != 28 {
				t.Errorf("temp_min 应 28, 实际 %v", got)
			}
		case "fault":
			// 0x07 报警: 4B 十六进制码 → hex 大写无前缀(§8-⑤)
			if len(r.Data.FaultCodes) != 1 || r.Data.FaultCodes[0] != "E1001" {
				t.Errorf("fault_codes 应 [E1001], 实际 %v", r.Data.FaultCodes)
			}
		case "battery_status":
			if got := *r.Data.Voltage; got != 60.2 {
				t.Errorf("voltage 应 60.2, 实际 %v", got)
			}
			if len(r.Data.CellVoltages) != 2 || r.Data.CellVoltages[0] != 3.276 {
				t.Errorf("cell_voltages 应 [3.276 3.28], 实际 %v", r.Data.CellVoltages)
			}
		case "charging":
			if got := *r.Data.RemainChargeMin; got != 45 {
				t.Errorf("remain_charge_min 应 45, 实际 %v", got)
			}
			if got := *r.Data.PileID; got != 1024 {
				t.Errorf("pile_id 应 1024, 实际 %v", got)
			}
			if got := *r.Data.SlotNo; got != 3 {
				t.Errorf("slot_no 应 3, 实际 %v", got)
			}
		case "work":
			if got := *r.Data.RideState; got != "riding" {
				t.Errorf("ride_state 应 riding, 实际 %v", got)
			}
			if got := *r.Data.MotorTorque; got != 12.5 {
				t.Errorf("motor_torque 应 12.5, 实际 %v", got)
			}
			if got := *r.Data.MotorPower; got != 800 {
				t.Errorf("motor_power 应 800, 实际 %v", got)
			}
		}
	}
}

// TestDecode_InvalidValuesDropped 无效值(0xFF/0xFFFF)按 §5 约定丢弃, 不进 L2 也不进 DLQ
func TestDecode_InvalidValuesDropped(t *testing.T) {
	du := mustHex(t,
		"1a09110c1e00"+
			"01"+"ffffffffffffffffffffffffffffffff"+ // 0x01 整车: 全无效值(1B 类型 + 16B 国标体)
			"06ffffffffffffffffffffffffffff") // 0x06 极值: 全无效值
	f := &Frame{Cmd: 0x02, VIN: "OV20260001", Data: du}
	reports, dlq, err := DecodeV1(f)
	if err != nil || len(dlq) != 0 {
		t.Fatalf("无效值不应报错/进 DLQ: err=%v dlq=%v", err, dlq)
	}
	if len(reports) != 1 || reports[0].Type != "vehicle_status" {
		t.Fatalf("应仍产出 1 条 vehicle_status(字段缺省), 实际 %+v", reports)
	}
	d := reports[0].Data
	if d.Speed != nil || d.Odometer != nil || d.SOC != nil || d.TempMax != nil || d.TempMin != nil {
		t.Errorf("无效值字段应全部丢弃, 实际 speed=%v odo=%v soc=%v tmax=%v tmin=%v",
			d.Speed, d.Odometer, d.SOC, d.TempMax, d.TempMin)
	}
}

// TestParseTime_RejectsNormalizingValues 时间字段越界必须被拒绝, 而不是被 time.Date 归一化。
//
// 背景(2026-09-20 修复): 修复前直接把 6 个字节喂给 time.Date, 而 time.Date 会**归一化**
// 越界字段 —— MM=13 变成次年 1 月、dd=0 变成上月最后一天、HH=99 变成几天后。
// 后果: 字节明显非法的帧解出一个"看着合法"的时间戳, 并且能通过契约的 ts 容差校验
// (只要落在近 7 天内), 坏帧被当成好数据写进 Kafka。
func TestParseTime_RejectsNormalizingValues(t *testing.T) {
	base := []byte{0x1a, 0x09, 0x11, 0x0c, 0x1e, 0x00} // 2026-09-17 12:30:00
	if _, err := parseTime(base); err != nil {
		t.Fatalf("基准时间应合法: %v", err)
	}

	bad := map[string][]byte{
		"月份 0":  {0x1a, 0x00, 0x11, 0x0c, 0x1e, 0x00},
		"月份 13": {0x1a, 0x0d, 0x11, 0x0c, 0x1e, 0x00},
		"日为 0":  {0x1a, 0x09, 0x00, 0x0c, 0x1e, 0x00},
		"日超当月":  {0x1a, 0x02, 0x1e, 0x0c, 0x1e, 0x00}, // 2 月 30 日
		"小时 99": {0x1a, 0x09, 0x11, 0x63, 0x1e, 0x00},
		"分钟 99": {0x1a, 0x09, 0x11, 0x0c, 0x63, 0x00},
		"秒 99":  {0x1a, 0x09, 0x11, 0x0c, 0x1e, 0x63},
	}
	for name, du := range bad {
		if ts, err := parseTime(du); err == nil {
			t.Errorf("%s 应被拒绝, 却解出 ts=%d", name, ts)
		} else if !errors.Is(err, ErrBadTime) {
			t.Errorf("%s 应返回 ErrBadTime, 实际 %v", name, err)
		}
	}
}

// TestParseTime_TooShort 数据单元不足 6B 时报 ErrNoTime(与 ErrBadTime 区分: 一个是不完整, 一个是越界)。
func TestParseTime_TooShort(t *testing.T) {
	if _, err := parseTime([]byte{0x1a, 0x09}); !errors.Is(err, ErrNoTime) {
		t.Fatalf("应返回 ErrNoTime, 实际 %v", err)
	}
}

// TestParseTime_RoundTrip 合法时间必须解成正确的 Unix 秒(防止"校验改坏了正常路径")。
func TestParseTime_RoundTrip(t *testing.T) {
	// 2026-09-17 12:30:00 GMT+8 = 2026-09-17T04:30:00Z
	ts, err := parseTime([]byte{0x1a, 0x09, 0x11, 0x0c, 0x1e, 0x00})
	if err != nil {
		t.Fatalf("合法时间不应报错: %v", err)
	}
	want := time.Date(2026, 9, 17, 12, 30, 0, 0, time.FixedZone("GMT+8", 8*3600)).Unix()
	if ts != want {
		t.Errorf("ts 应为 %d, 实际 %d", want, ts)
	}
}
