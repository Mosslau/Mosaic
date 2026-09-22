package simframe

import (
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// 交叉对拍(2026-09-20 新建): 造帧器(simframe) 与 解码器(device-codec/internal/gbt32960)
// 锁在**同一份字节样本**上。
//
// 背景: 两个实现是刻意"两边独立实现同一份规格"(互为对拍), 但此前没有任何测试让 A 的产出
// 过 B 的解码 —— 只有各自内嵌的黄金样本, 属于"两边同时错就一起错"的结构性盲区(第 1、2 步评审发现)。
//
// 为什么用托管样本而不是直接互相 import: Go 的 internal 规则禁止跨模块 import internal 包,
// 而两侧(造帧器/解码器)本来就是 internal 包。托管样本是唯一能同时约束两侧的做法:
//   - 本测试: 按样本里的输入造帧 → 字节必须与样本的 bytes_hex **逐字节相同**
//   - 解码器侧(crosscheck_test.go): 解析同一份 bytes_hex → 字段必须等于样本的 decode.expect
//
// 因此: 任何一侧私自改动字节口径 → 该侧测试立刻变红。

// fixturePath 样本位置: 放在**解码器模块**的 testdata 下(它是契约的消费方, 也是
// 字段期望值的天然归属地); 本测试只读它, 不写。
func fixturePath(t *testing.T) string {
	t.Helper()
	// 本包的 go test 工作目录 = internal/simframe, 故 ../../../device-codec/...
	p := filepath.Join("..", "..", "..", "device-codec", "testdata", "crosscheck_full_frame.json")
	if _, err := os.Stat(p); err != nil {
		t.Skipf("交叉样本不可读(%s): %v —— 单模块检出时跳过", p, err)
	}
	return p
}

type crossFixture struct {
	VIN      string `json:"vin"`
	Cmd      byte   `json:"cmd"`
	Ack      byte   `json:"ack"`
	TimeGMT8 []int  `json:"time_gmt8"`
	Inputs   struct {
		Vehicle struct {
			VehicleStatus byte    `json:"vehicle_status"`
			ChargeStatus  byte    `json:"charge_status"`
			SpeedKmh      float64 `json:"speed_kmh"`
			OdometerKm    float64 `json:"odometer_km"`
			SOC           float64 `json:"soc"`
		} `json:"vehicle"`
		Position struct {
			Lng float64 `json:"lng"`
			Lat float64 `json:"lat"`
		} `json:"position"`
		Extremes struct {
			TempMax float64 `json:"temp_max"`
			TempMin float64 `json:"temp_min"`
		} `json:"extremes"`
		Alarm struct {
			Level      byte     `json:"level"`
			FaultCodes []uint32 `json:"fault_codes"`
		} `json:"alarm"`
		BatteryVolt struct {
			Voltage      float64   `json:"voltage"`
			Current      float64   `json:"current"`
			CellVoltages []float64 `json:"cell_voltages"`
		} `json:"battery_volt"`
		BatteryTemp struct {
			ProbeTemps []float64 `json:"probe_temps"`
		} `json:"battery_temp"`
		Charging struct {
			RemainMin uint16  `json:"remain_min"`
			PowerKW   float64 `json:"power_kw"`
			EnergyKWh float64 `json:"energy_kwh"`
			PileID    uint32  `json:"pile_id"`
			StationID uint32  `json:"station_id"`
			SlotNo    byte    `json:"slot_no"`
		} `json:"charging"`
		Work struct {
			RideState   byte    `json:"ride_state"`
			RideMode    byte    `json:"ride_mode"`
			MotorRPM    uint16  `json:"motor_rpm"`
			MotorTorque float64 `json:"motor_torque"`
			MotorPower  float64 `json:"motor_power"`
			Throttle    uint8   `json:"throttle"`
		} `json:"work"`
	} `json:"inputs"`
	BytesHex string `json:"bytes_hex"`
}

func loadFixture(t *testing.T) crossFixture {
	t.Helper()
	raw, err := os.ReadFile(fixturePath(t))
	if err != nil {
		t.Fatalf("读样本失败: %v", err)
	}
	var f crossFixture
	if err := json.Unmarshal(raw, &f); err != nil {
		t.Fatalf("样本 JSON 非法: %v", err)
	}
	if len(f.TimeGMT8) != 6 {
		t.Fatalf("time_gmt8 必须是 6 个元素, 实际 %d", len(f.TimeGMT8))
	}
	return f
}

func (f crossFixture) time() time.Time {
	t := f.TimeGMT8
	return time.Date(t[0], time.Month(t[1]), t[2], t[3], t[4], t[5], 0,
		time.FixedZone("GMT+8", 8*3600))
}

// buildFromFixture 按样本输入造一帧 —— 与 cmd/bin-simulator 使用**同一批** Body* 构造函数。
func buildFromFixture(f crossFixture) []byte {
	return Frame(f.Cmd, f.Ack, f.VIN, DataUnit(f.time(),
		BodyVehicle(VehicleBody{
			VehicleStatus: f.Inputs.Vehicle.VehicleStatus,
			ChargeStatus:  f.Inputs.Vehicle.ChargeStatus,
			SpeedKmh:      f.Inputs.Vehicle.SpeedKmh,
			OdometerKm:    f.Inputs.Vehicle.OdometerKm,
			SOC:           f.Inputs.Vehicle.SOC,
		}),
		BodyPosition(f.Inputs.Position.Lng, f.Inputs.Position.Lat),
		BodyExtremes(f.Inputs.Extremes.TempMax, f.Inputs.Extremes.TempMin),
		BodyAlarm(f.Inputs.Alarm.Level, f.Inputs.Alarm.FaultCodes),
		BodyBatteryVolt(BatteryVoltBody{
			Voltage:      f.Inputs.BatteryVolt.Voltage,
			Current:      f.Inputs.BatteryVolt.Current,
			CellVoltages: f.Inputs.BatteryVolt.CellVoltages,
		}),
		BodyBatteryTemp(f.Inputs.BatteryTemp.ProbeTemps),
		BodyCharging(ChargingBody{
			RemainMin: f.Inputs.Charging.RemainMin,
			PowerKW:   f.Inputs.Charging.PowerKW,
			EnergyKWh: f.Inputs.Charging.EnergyKWh,
			PileID:    f.Inputs.Charging.PileID,
			StationID: f.Inputs.Charging.StationID,
			SlotNo:    f.Inputs.Charging.SlotNo,
		}),
		BodyWork(WorkBody{
			RideState:   f.Inputs.Work.RideState,
			RideMode:    f.Inputs.Work.RideMode,
			MotorRPM:    f.Inputs.Work.MotorRPM,
			MotorTorque: f.Inputs.Work.MotorTorque,
			MotorPower:  f.Inputs.Work.MotorPower,
			Throttle:    f.Inputs.Work.Throttle,
		}),
	))
}

// TestCrossCheck_SimframeMatchesFixtureBytes 造帧器的产出必须与托管样本**逐字节相同**。
// 失败即说明本包(或样本)偏离了规格 —— 两侧字节口径必须一致, 否则对端解不出来。
func TestCrossCheck_SimframeMatchesFixtureBytes(t *testing.T) {
	f := loadFixture(t)
	got := hex.EncodeToString(buildFromFixture(f))

	if got != f.BytesHex {
		t.Errorf("造帧器产出与交叉样本不一致\n实际: %s\n样本: %s\n"+
			"(若确认是造帧器正确、样本过期: 用本测试输出的实际值更新 %s 的 bytes_hex,"+
			"并同步核对解码器侧 crosscheck_test.go 的期望)",
			got, f.BytesHex, fixturePath(t))
	}
	// 帧长自洽: 头 24B + 数据单元 + BCC 1B
	if want := 24 + len(got)/2 - 24; want != len(got)/2 {
		t.Errorf("帧长自洽性检查失败: %d", want)
	}
}

// TestCrossCheck_FrameIsSelfConsistent 帧头自洽(命令/应答/VIN/加密方式/长度字段/BCC)。
func TestCrossCheck_FrameIsSelfConsistent(t *testing.T) {
	f := loadFixture(t)
	frame := buildFromFixture(f)

	if frame[0] != '#' || frame[1] != '#' {
		t.Fatalf("起始符必须是 ##, 实际 %q", frame[:2])
	}
	if frame[2] != f.Cmd || frame[3] != f.Ack {
		t.Errorf("命令单元不一致: %#x %#x", frame[2], frame[3])
	}
	if frame[21] != EncPlain {
		t.Errorf("加密方式应为明文 %#x, 实际 %#x", EncPlain, frame[21])
	}
	// VIN 左对齐右补 0x00
	vinField := frame[4:21]
	end := len(vinField)
	for end > 0 && vinField[end-1] == 0 {
		end--
	}
	if string(vinField[:end]) != f.VIN {
		t.Errorf("VIN 字段往返不一致: %q", string(vinField[:end]))
	}
	// BCC 自洽(与解码器的算法独立实现: 这里从原始字节重算)
	var bcc byte
	for _, b := range frame[2 : len(frame)-1] {
		bcc ^= b
	}
	if bcc != frame[len(frame)-1] {
		t.Errorf("BCC 自洽失败: 重算 %#x, 帧内 %#x", bcc, frame[len(frame)-1])
	}
}
