package simframe

import (
	"bytes"
	"encoding/hex"
	"testing"
	"time"
)

// TestFrame_Structure 帧结构五要素: 起始符/命令单元/VIN 填充/长度/BCC(§2)
func TestFrame_Structure(t *testing.T) {
	du := DataUnit(time.Date(2026, 9, 17, 12, 30, 0, 0, time.UTC)) // UTC 20:30? 见 TimeField 测试
	f := Frame(CmdRealtime, AckNone, "OV20260001", du)

	if !bytes.Equal(f[:2], []byte("##")) {
		t.Fatalf("起始符应为 ##, 实际 %x", f[:2])
	}
	if f[2] != CmdRealtime || f[3] != AckNone {
		t.Errorf("命令单元应为 02 fe, 实际 %02x %02x", f[2], f[3])
	}
	vin := f[4:21]
	if !bytes.Equal(vin[:10], []byte("OV20260001")) || !bytes.Equal(vin[10:], make([]byte, 7)) {
		t.Errorf("VIN 应左对齐右补 0x00, 实际 %x", vin)
	}
	if f[21] != EncPlain {
		t.Errorf("加密方式应为 0x01, 实际 %02x", f[21])
	}
	dlen := int(f[22])<<8 | int(f[23])
	if dlen != len(du) {
		t.Errorf("数据单元长度应为 %d, 实际 %d", len(du), dlen)
	}
	var bcc byte
	for _, b := range f[2 : len(f)-1] {
		bcc ^= b
	}
	if bcc != f[len(f)-1] {
		t.Errorf("BCC 校验错误: 期望 %02x, 实际 %02x", bcc, f[len(f)-1])
	}
}

// TestTimeField GMT+8 明文(§8-③): UTC 04:30 → 帧内 12:30
func TestTimeField(t *testing.T) {
	ts := time.Date(2026, 9, 17, 4, 30, 0, 0, time.UTC)
	got := TimeField(ts)
	want := []byte{26, 9, 17, 12, 30, 0}
	if !bytes.Equal(got, want) {
		t.Errorf("时间字段应为 %x, 实际 %x", want, got)
	}
}

// TestGolden_BatteryVolt 与映射文档 §5.1 示例帧对拍(黄金样本)
func TestGolden_BatteryVolt(t *testing.T) {
	got := BodyBatteryVolt(BatteryVoltBody{
		Voltage: 60.2, Current: -5.1,
		CellVoltages: []float64{3.276, 3.280, 3.265, 3.271},
	})
	want, _ := hex.DecodeString("080101025a26dd00040001040ccc0cd00cc10cc7")
	if !bytes.Equal(got, want) {
		t.Errorf("0x08 黄金样本不匹配:\n got %x\nwant %x", got, want)
	}
}

// TestGolden_BatteryTemp 0x09 黄金样本
func TestGolden_BatteryTemp(t *testing.T) {
	got := BodyBatteryTemp([]float64{31, 35})
	want, _ := hex.DecodeString("0901010002" + "474b")
	if !bytes.Equal(got, want) {
		t.Errorf("0x09 黄金样本不匹配:\n got %x\nwant %x", got, want)
	}
}

// TestGolden_FullFrame 整帧对拍: 与文档/解码器共享的 58B 示例帧逐字节一致
func TestGolden_FullFrame(t *testing.T) {
	ts := time.Date(2026, 9, 17, 4, 30, 0, 0, time.UTC) // = GMT+8 12:30:00
	du := DataUnit(ts,
		BodyBatteryVolt(BatteryVoltBody{
			Voltage: 60.2, Current: -5.1,
			CellVoltages: []float64{3.276, 3.280, 3.265, 3.271},
		}),
		BodyBatteryTemp([]float64{31, 35}),
	)
	got := Frame(CmdRealtime, AckNone, "OV20260001", du)
	want, _ := hex.DecodeString("232302fe" +
		"4f56323032363030303100000000000000" + // VIN
		"01" + "0021" +
		"1a09110c1e00" +
		"080101025a26dd00040001040ccc0cd00cc10cc7" +
		"0901010002474b" +
		"65")
	if !bytes.Equal(got, want) {
		t.Errorf("整帧黄金样本不匹配:\n got %x\nwant %x", got, want)
	}
}

// TestCustomUnits 自定义单元统一头 + 定长 payload(§5.2)
func TestCustomUnits(t *testing.T) {
	c := BodyCharging(ChargingBody{RemainMin: 45, PowerKW: 1.5, EnergyKWh: 0.8, PileID: 1024, StationID: 88, SlotNo: 3})
	if len(c) != 4+15 {
		t.Errorf("0x80 应 19B, 实际 %d", len(c))
	}
	if c[0] != TypeCharging || c[1] != ProtoV1 {
		t.Errorf("0x80 统一头应为 [80 01], 实际 [%02x %02x]", c[0], c[1])
	}
	if int(c[2])<<8|int(c[3]) != 15 {
		t.Errorf("0x80 payload 长度应为 15, 实际 %d", int(c[2])<<8|int(c[3]))
	}

	w := BodyWork(WorkBody{RideState: RideRiding, RideMode: ModeSport, MotorRPM: 1200, MotorTorque: -3.5, MotorPower: -440, Throttle: 60})
	if len(w) != 4+9 {
		t.Errorf("0x81 应 13B, 实际 %d", len(w))
	}
	// 负值有符号编码: -3.5 N·m → -35 → 0xffdd; -440 W → 0xfe48
	// w = [81 01 00 09 | state mode | rpm×2 | torque×2 | power×2 | throttle]
	if w[8] != 0xff || w[9] != 0xdd {
		t.Errorf("转矩 -3.5 应编码 ff dd, 实际 %02x %02x", w[8], w[9])
	}
	if w[10] != 0xfe || w[11] != 0x48 {
		t.Errorf("功率 -440 应编码 fe 48, 实际 %02x %02x", w[10], w[11])
	}
}

// TestInvalidFields 无效值约定: 0x06 未承载的电压极值填 0xFF/0xFFFF(§5)
func TestInvalidFields(t *testing.T) {
	e := BodyExtremes(35, 28)
	if len(e) != 15 {
		t.Fatalf("0x06 应 15B, 实际 %d", len(e))
	}
	if !bytes.Equal(e[1:9], []byte{0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff}) {
		t.Errorf("电压极值应全填无效值, 实际 %x", e[1:9])
	}
	if e[11] != 75 || e[14] != 68 { // 35+40 / 28+40
		t.Errorf("温度极值应为 4b 44 位置值, 实际 %02x %02x", e[11], e[14])
	}
}
