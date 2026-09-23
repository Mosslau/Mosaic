package gbt32960

import (
	"encoding/hex"
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/Mosslau/Mosaic/ingest/device-contracts/vehicle"
)

// 交叉对拍(2026-09-20 新建): **造帧器(simframe)的产出字节** → **解码器(本包)的解码结果**。
//
// 为什么需要这一层: simframe 与 gbt32960 是刻意"两边独立实现同一份规格"(互为对拍),
// 但此前没有任何测试真的让 A 的产出过 B 的解码 —— 只有各自内嵌的黄金样本,
// 属于"两边同时错就一起错"的结构性盲区(第 1、2 步评审发现)。
//
// 分工:
//   - 造帧器侧(device-simulator/internal/simframe/crosscheck_test.go): 按样本输入造帧, 断言字节 == bytes_hex
//   - 本文件: 解析同一份 bytes_hex, 断言字段 == decode.expect
//
// 因此任何一侧私自改字节口径 → 该侧立刻变红。样本: testdata/crosscheck_full_frame.json。

type crossFixture struct {
	VIN      string `json:"vin"`
	TimeGMT8 []int  `json:"time_gmt8"`
	BytesHex string `json:"bytes_hex"`
	Decode   struct {
		ReportCount int `json:"report_count"`
		Expect      struct {
			VehicleStatus struct {
				Speed    float64 `json:"speed"`
				Odometer float64 `json:"odometer"`
				SOC      float64 `json:"soc"`
				Lng      float64 `json:"lng"`
				Lat      float64 `json:"lat"`
				TempMax  float64 `json:"temp_max"`
				TempMin  float64 `json:"temp_min"`
			} `json:"vehicle_status"`
			BatteryStatus struct {
				Voltage      float64   `json:"voltage"`
				Current      float64   `json:"current"`
				CellVoltages []float64 `json:"cell_voltages"`
				ProbeTemps   []float64 `json:"probe_temps"`
			} `json:"battery_status"`
			Fault struct {
				FaultCodes []string `json:"fault_codes"`
			} `json:"fault"`
			Charging struct {
				RemainChargeMin int64   `json:"remain_charge_min"`
				ChargePower     float64 `json:"charge_power"`
				ChargeKWh       float64 `json:"charge_kwh"`
				PileID          int64   `json:"pile_id"`
				StationID       int64   `json:"station_id"`
				SlotNo          int64   `json:"slot_no"`
			} `json:"charging"`
			Work struct {
				RideState   string  `json:"ride_state"`
				RideMode    string  `json:"ride_mode"`
				MotorRPM    int64   `json:"motor_rpm"`
				MotorTorque float64 `json:"motor_torque"`
				MotorPower  float64 `json:"motor_power"`
				Throttle    int64   `json:"throttle"`
			} `json:"work"`
		} `json:"expect"`
	} `json:"decode"`
}

func loadCrossFixture(t *testing.T) crossFixture {
	t.Helper()
	p := filepath.Join("testdata", "crosscheck_full_frame.json")
	raw, err := os.ReadFile(p)
	if err != nil {
		t.Skipf("交叉样本不可读(%s): %v —— 单模块检出时跳过", p, err)
	}
	var f crossFixture
	if err := json.Unmarshal(raw, &f); err != nil {
		t.Fatalf("样本 JSON 非法: %v", err)
	}
	return f
}

func (f crossFixture) at(t *testing.T) time.Time {
	t.Helper()
	if len(f.TimeGMT8) != 6 {
		t.Fatalf("time_gmt8 必须是 6 个元素")
	}
	v := f.TimeGMT8
	return time.Date(v[0], time.Month(v[1]), v[2], v[3], v[4], v[5], 0,
		time.FixedZone("GMT+8", 8*3600))
}

func approxEq(t *testing.T, what string, got *float64, want float64) {
	t.Helper()
	if got == nil {
		t.Errorf("%s: 期望 %v, 实际未设置(字段被丢弃)", what, want)
		return
	}
	if math.Abs(*got-want) > 1e-6 {
		t.Errorf("%s: 期望 %v, 实际 %v(与造帧器的量化口径不一致)", what, want, *got)
	}
}

func findReport(t *testing.T, reports []vehicle.VehicleReport, typ vehicle.ReportType) vehicle.VehicleReport {
	t.Helper()
	for _, r := range reports {
		if r.Type == typ {
			return r
		}
	}
	got := make([]string, 0, len(reports))
	for _, r := range reports {
		got = append(got, string(r.Type))
	}
	t.Fatalf("未找到 type=%s 的 report, 实际: %v", typ, got)
	return vehicle.VehicleReport{}
}

func checkInt64(t *testing.T, what string, got *int64, want int64) {
	t.Helper()
	if got == nil {
		t.Errorf("%s: 期望 %d, 实际未设置", what, want)
		return
	}
	if *got != want {
		t.Errorf("%s: 期望 %d, 实际 %d", what, want, *got)
	}
}

func checkStr(t *testing.T, what string, got *string, want string) {
	t.Helper()
	if got == nil {
		t.Errorf("%s: 期望 %q, 实际未设置", what, want)
		return
	}
	if *got != want {
		t.Errorf("%s: 期望 %q, 实际 %q", what, want, *got)
	}
}

// TestCrossCheck_FixtureBytesDecodeAsExpected 造帧器产出的**托管字节**必须解出样本声明的字段值。
// 这是"造帧器 ↔ 解码器"闭环的解码侧一半; 造帧侧在 device-simulator/internal/simframe。
func TestCrossCheck_FixtureBytesDecodeAsExpected(t *testing.T) {
	f := loadCrossFixture(t)
	frame, err := hex.DecodeString(f.BytesHex)
	if err != nil {
		t.Fatalf("样本 bytes_hex 非法: %v", err)
	}

	pf, err := ParseFrame(frame)
	if err != nil {
		t.Fatalf("样本帧必须可解析(帧框架/BCC 口径与造帧器不一致): %v", err)
	}
	if pf.VIN != f.VIN {
		t.Errorf("VIN 不一致: 期望 %q, 实际 %q", f.VIN, pf.VIN)
	}

	reports, dlq, err := DecodeV1(pf)
	if err != nil {
		t.Fatalf("解码失败: %v", err)
	}
	if len(dlq) != 0 {
		t.Fatalf("合法样本不应产生 DLQ: %+v", dlq)
	}
	if len(reports) != f.Decode.ReportCount {
		t.Fatalf("应产出 %d 条 report, 实际 %d", f.Decode.ReportCount, len(reports))
	}

	wantTS := f.at(t).Unix()
	for _, r := range reports {
		if r.VIN != f.VIN || r.Ts != wantTS {
			t.Errorf("report 元信息不一致: vin=%q ts=%d(期望 %q/%d)", r.VIN, r.Ts, f.VIN, wantTS)
		}
	}

	ex := f.Decode.Expect

	vs := findReport(t, reports, vehicle.ReportVehicleStatus)
	approxEq(t, "vehicle_status.speed", vs.Data.Speed, ex.VehicleStatus.Speed)
	approxEq(t, "vehicle_status.odometer", vs.Data.Odometer, ex.VehicleStatus.Odometer)
	approxEq(t, "vehicle_status.soc", vs.Data.SOC, ex.VehicleStatus.SOC)
	approxEq(t, "vehicle_status.lng", vs.Data.Lng, ex.VehicleStatus.Lng)
	approxEq(t, "vehicle_status.lat", vs.Data.Lat, ex.VehicleStatus.Lat)
	approxEq(t, "vehicle_status.temp_max", vs.Data.TempMax, ex.VehicleStatus.TempMax)
	approxEq(t, "vehicle_status.temp_min", vs.Data.TempMin, ex.VehicleStatus.TempMin)

	bs := findReport(t, reports, vehicle.ReportBatteryStatus)
	approxEq(t, "battery_status.voltage", bs.Data.Voltage, ex.BatteryStatus.Voltage)
	approxEq(t, "battery_status.current", bs.Data.Current, ex.BatteryStatus.Current)
	if len(bs.Data.CellVoltages) != len(ex.BatteryStatus.CellVoltages) {
		t.Errorf("cell_voltages 个数: 期望 %d, 实际 %d", len(ex.BatteryStatus.CellVoltages), len(bs.Data.CellVoltages))
	} else {
		for i := range ex.BatteryStatus.CellVoltages {
			approxEq(t, "battery_status.cell_voltages[]", &bs.Data.CellVoltages[i], ex.BatteryStatus.CellVoltages[i])
		}
	}
	if len(bs.Data.ProbeTemps) != len(ex.BatteryStatus.ProbeTemps) {
		t.Errorf("probe_temps 个数: 期望 %d, 实际 %d", len(ex.BatteryStatus.ProbeTemps), len(bs.Data.ProbeTemps))
	} else {
		for i := range ex.BatteryStatus.ProbeTemps {
			approxEq(t, "battery_status.probe_temps[]", &bs.Data.ProbeTemps[i], ex.BatteryStatus.ProbeTemps[i])
		}
	}

	ft := findReport(t, reports, vehicle.ReportFault)
	if len(ft.Data.FaultCodes) != len(ex.Fault.FaultCodes) {
		t.Errorf("fault_codes 个数: 期望 %d, 实际 %d", len(ex.Fault.FaultCodes), len(ft.Data.FaultCodes))
	} else {
		for i := range ex.Fault.FaultCodes {
			if ft.Data.FaultCodes[i] != ex.Fault.FaultCodes[i] {
				t.Errorf("fault_codes[%d]: 期望 %q, 实际 %q", i, ex.Fault.FaultCodes[i], ft.Data.FaultCodes[i])
			}
		}
	}

	ch := findReport(t, reports, vehicle.ReportCharging)
	checkInt64(t, "charging.remain_charge_min", ch.Data.RemainChargeMin, ex.Charging.RemainChargeMin)
	approxEq(t, "charging.charge_power", ch.Data.ChargePower, ex.Charging.ChargePower)
	approxEq(t, "charging.charge_kwh", ch.Data.ChargeKWh, ex.Charging.ChargeKWh)
	checkInt64(t, "charging.pile_id", ch.Data.PileID, ex.Charging.PileID)
	checkInt64(t, "charging.station_id", ch.Data.StationID, ex.Charging.StationID)
	checkInt64(t, "charging.slot_no", ch.Data.SlotNo, ex.Charging.SlotNo)

	wk := findReport(t, reports, vehicle.ReportWork)
	checkStr(t, "work.ride_state", wk.Data.RideState, ex.Work.RideState)
	checkStr(t, "work.ride_mode", wk.Data.RideMode, ex.Work.RideMode)
	checkInt64(t, "work.motor_rpm", wk.Data.MotorRPM, ex.Work.MotorRPM)
	approxEq(t, "work.motor_torque", wk.Data.MotorTorque, ex.Work.MotorTorque)
	approxEq(t, "work.motor_power", wk.Data.MotorPower, ex.Work.MotorPower)
	checkInt64(t, "work.throttle", wk.Data.Throttle, ex.Work.Throttle)
}
