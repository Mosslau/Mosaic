package gbt32960

import (
	"encoding/binary"
	"fmt"
	"math"

	"github.com/Mosslau/OceanVerse/ingest/device-contracts/vehicle"
)

// 信息类型标志(§4 启用表)
const (
	typeVehicle     = 0x01
	typePosition    = 0x05
	typeExtremes    = 0x06
	typeAlarm       = 0x07
	typeBatteryVolt = 0x08
	typeBatteryTemp = 0x09
	typeCharging    = 0x80
	typeWork        = 0x81
)

// DLQItem 单元级/帧级失败记录(§5.2: 整单元版本未知才进 DLQ; 单字段非法只丢字段)
type DLQItem struct {
	UnitType int    // 信息类型标志(帧级错误时为 -1)
	Reason   string // 失败原因
}

// DecodeV1 按 v1 协议(映射文档 §5/§5.1/§5.2)把一帧解码为若干条 VehicleReport。
//
// 拆分粒度(§8-④): 0x01+0x05+0x06 合并为一条 vehicle_status;
// 0x07 独立成 fault; 0x08/0x09 合并为 battery_status; 0x80 → charging; 0x81 → work。
//
// 返回: reports(契约消息) + dlq(单元级失败, 帧级失败由 ParseFrame 直接报错)。
func DecodeV1(f *Frame) ([]vehicle.VehicleReport, []DLQItem, error) {
	ts, err := parseTime(f.Data)
	if err != nil {
		return nil, nil, err
	}

	var (
		vs      *vehicle.VehicleReport // vehicle_status(懒创建)
		batt    *vehicle.VehicleReport // battery_status
		reports []vehicle.VehicleReport
		dlq     []DLQItem
	)
	newReport := func(t vehicle.ReportType) *vehicle.VehicleReport {
		return &vehicle.VehicleReport{
			VIN: f.VIN, Ts: ts, Type: t, SchemaVersion: vehicle.SchemaV1,
		}
	}
	vehicleStatus := func() *vehicle.VehicleReport {
		if vs == nil {
			vs = newReport(vehicle.ReportVehicleStatus)
		}
		return vs
	}
	batteryStatus := func() *vehicle.VehicleReport {
		if batt == nil {
			batt = newReport(vehicle.ReportBatteryStatus)
		}
		return batt
	}

	du := f.Data
	i := 6 // 跳过时间字段
	for i < len(du) {
		unit := du[i]
		i++
		switch unit {
		case typeVehicle: // 0x01 整车(国标 16B)
			if len(du)-i < 16 {
				dlq = append(dlq, DLQItem{int(unit), "0x01 整车信息体长度不足"})
				i = len(du)
				break
			}
			d := &vehicleStatus().Data
			// 无效值约定(§5): 0xFFFF/0xFFFFFFFF 一律丢弃, 否则会解出 6553.5km/h 这类垃圾
			if v := binary.BigEndian.Uint16(du[i+3 : i+5]); v != 0xFFFF {
				d.Speed = f64(float64(v) * 0.1)
			}
			if v := binary.BigEndian.Uint32(du[i+5 : i+9]); v != 0xFFFFFFFF {
				d.Odometer = f64(float64(v) * 0.1)
			}
			if du[i+9] != 0xFF {
				d.SOC = f64(float64(du[i+9]))
			}
			i += 16

		case typePosition: // 0x05 位置(定位状态 1B + 经纬度各 4B)
			if len(du)-i < 9 {
				dlq = append(dlq, DLQItem{int(unit), "0x05 位置信息体长度不足"})
				i = len(du)
				break
			}
			if du[i]&0x01 == 0 { // bit0=0 定位有效
				d := &vehicleStatus().Data
				if v := binary.BigEndian.Uint32(du[i+1 : i+5]); v != 0xFFFFFFFF {
					d.Lng = f64(round6(float64(v) / 1e6))
				}
				if v := binary.BigEndian.Uint32(du[i+5 : i+9]); v != 0xFFFFFFFF {
					d.Lat = f64(round6(float64(v) / 1e6))
				}
			}
			i += 9

		case typeExtremes: // 0x06 极值(国标 14B; 只用温度极值, §5)
			if len(du)-i < 14 {
				dlq = append(dlq, DLQItem{int(unit), "0x06 极值信息体长度不足"})
				i = len(du)
				break
			}
			d := &vehicleStatus().Data
			if du[i+10] != 0xFF {
				d.TempMax = f64(float64(int(du[i+10]) - 40))
			}
			if du[i+13] != 0xFF {
				d.TempMin = f64(float64(int(du[i+13]) - 40))
			}
			i += 14

		case typeAlarm: // 0x07 报警 → 独立 fault(§8-④)
			levelOff, flagOff := i, i+1 // 等级 + 通用标志(暂不逐位进 L2)
			_ = levelOff
			j := flagOff + 4
			var codes []string
			ok := true
			for list := 0; list < 4; list++ { // 储能/电机/发动机/其他 四类故障码列表
				if j >= len(du) {
					ok = false
					break
				}
				n := int(du[j])
				j++
				if len(du)-j < n*4 {
					ok = false
					break
				}
				if list == 0 { // 只用可充电储能装置故障码(两轮车简化)
					for k := 0; k < n; k++ {
						codes = append(codes, fmt.Sprintf("%X", binary.BigEndian.Uint32(du[j+4*k:j+4*k+4])))
					}
				}
				j += n * 4
			}
			if !ok {
				dlq = append(dlq, DLQItem{int(unit), "0x07 报警信息体长度不足"})
				i = len(du)
				break
			}
			if len(codes) > 0 {
				r := newReport(vehicle.ReportFault)
				r.Data.FaultCodes = codes
				reports = append(reports, *r)
			}
			i = j

		case typeBatteryVolt: // 0x08 储能电压(§5.1: 单子系统, 不分帧)
			if len(du)-i < 10 {
				dlq = append(dlq, DLQItem{int(unit), "0x08 电压信息体长度不足"})
				i = len(du)
				break
			}
			n := int(du[i]) // 子系统个数(本项目恒 1)
			j := i + 1
			for s := 0; s < n; s++ {
				if len(du)-j < 10 {
					dlq = append(dlq, DLQItem{int(unit), "0x08 子系统段长度不足"})
					j = len(du)
					break
				}
				d := &batteryStatus().Data
				if v := binary.BigEndian.Uint16(du[j+1 : j+3]); v != 0xFFFF {
					d.Voltage = f64(float64(v) * 0.1)
				}
				if c := binary.BigEndian.Uint16(du[j+3 : j+5]); c != 0xFFFF {
					d.Current = f64(math.Round((float64(c)*0.1-1000)*10) / 10)
				}
				m := int(du[j+9]) // 本帧单体个数(起始序号固定 1, 不分帧)
				j += 10           // 子系统头 = 号1+电压2+电流2+总数2+起始2+个数1
				if len(du)-j < m*2 {
					dlq = append(dlq, DLQItem{int(unit), "0x08 单体电压列表长度不足"})
					j = len(du)
					break
				}
				for k := 0; k < m; k++ {
					v := binary.BigEndian.Uint16(du[j+2*k : j+2*k+2])
					if v == 0xFFFF {
						continue // 无效值丢弃
					}
					d.CellVoltages = append(d.CellVoltages, float64(v)/1000) // 除法正确舍入(×0.001 会引入 1 ulp 误差)
				}
				j += m * 2
			}
			i = j

		case typeBatteryTemp: // 0x09 储能温度(§5.1)
			if len(du)-i < 4 {
				dlq = append(dlq, DLQItem{int(unit), "0x09 温度信息体长度不足"})
				i = len(du)
				break
			}
			n := int(du[i])
			j := i + 1
			for s := 0; s < n; s++ {
				if len(du)-j < 3 {
					dlq = append(dlq, DLQItem{int(unit), "0x09 子系统段长度不足"})
					j = len(du)
					break
				}
				m := int(binary.BigEndian.Uint16(du[j+1 : j+3]))
				j += 3
				if len(du)-j < m {
					dlq = append(dlq, DLQItem{int(unit), "0x09 探针温度列表长度不足"})
					j = len(du)
					break
				}
				d := &batteryStatus().Data
				for k := 0; k < m; k++ {
					if du[j+k] == 0xFF {
						continue
					}
					d.ProbeTemps = append(d.ProbeTemps, float64(int(du[j+k])-40))
				}
				j += m
			}
			i = j

		default: // 0x80+ 自定义单元(统一头: 版本 1B + 长度 2B)
			if unit < 0x80 {
				dlq = append(dlq, DLQItem{int(unit), "未启用的固有信息类型"})
				i = len(du) // 无长度头无法安全跳过, 终止本帧解析
				break
			}
			if len(du)-i < 3 {
				dlq = append(dlq, DLQItem{int(unit), "自定义单元统一头长度不足"})
				i = len(du)
				break
			}
			ver := du[i]
			plen := int(binary.BigEndian.Uint16(du[i+1 : i+3]))
			if ver != 0x01 {
				dlq = append(dlq, DLQItem{int(unit), fmt.Sprintf("未知自定义单元版本 v%d(版本纪律: 不猜)", ver)})
				i += 3 + plen
				continue
			}
			if len(du)-i-3 < plen {
				dlq = append(dlq, DLQItem{int(unit), "自定义单元 payload 长度越界"})
				i = len(du)
				break
			}
			payload := du[i+3 : i+3+plen]
			i += 3 + plen
			switch unit {
			case typeCharging:
				reports = append(reports, *decodeCharging(newReport(vehicle.ReportCharging), payload))
			case typeWork:
				reports = append(reports, *decodeWork(newReport(vehicle.ReportWork), payload))
			default:
				// 0x82~0xFE 预留: 跳过并计数(§5.2)——计数由调用方以 len(dlq) 之外的方式扩展
			}
		}
	}

	if vs != nil {
		reports = append([]vehicle.VehicleReport{*vs}, reports...)
	}
	if batt != nil {
		reports = append([]vehicle.VehicleReport{*batt}, reports...)
	}
	return reports, dlq, nil
}

// decodeCharging 0x80 charging(§5.2, payload 定长 15B)
func decodeCharging(r *vehicle.VehicleReport, p []byte) *vehicle.VehicleReport {
	if len(p) != 15 {
		return r // 长度不符: 字段全部不设置(保守); 严格化由版本演进处理
	}
	d := &r.Data
	// 无效值约定(§5): 0xFFFF 丢弃
	if v := binary.BigEndian.Uint16(p[0:2]); v != 0xFFFF {
		d.RemainChargeMin = i64(int64(v))
	}
	if v := binary.BigEndian.Uint16(p[2:4]); v != 0xFFFF {
		d.ChargePower = f64(float64(v) * 0.01)
	}
	if v := binary.BigEndian.Uint16(p[4:6]); v != 0xFFFF {
		d.ChargeKWh = f64(float64(v) * 0.01)
	}
	if v := binary.BigEndian.Uint32(p[6:10]); v != 0 {
		d.PileID = i64(int64(v))
	}
	if v := binary.BigEndian.Uint32(p[10:14]); v != 0 {
		d.StationID = i64(int64(v))
	}
	if p[14] != 0xFF {
		d.SlotNo = i64(int64(p[14]))
	}
	return r
}

// decodeWork 0x81 工况(§5.2, payload 定长 9B; 枚举数字码 → L2 字符串)
func decodeWork(r *vehicle.VehicleReport, p []byte) *vehicle.VehicleReport {
	if len(p) != 9 {
		return r
	}
	d := &r.Data
	if s, ok := rideStateStr[p[0]]; ok {
		d.RideState = &s
	}
	if m, ok := rideModeStr[p[1]]; ok {
		d.RideMode = &m
	}
	// 无效值约定(§5): 0xFFFF/0xFF 丢弃(有符号字段的 0xFFFF 同样视为无效)
	if v := binary.BigEndian.Uint16(p[2:4]); v != 0xFFFF {
		d.MotorRPM = i64(int64(v))
	}
	if v := binary.BigEndian.Uint16(p[4:6]); v != 0xFFFF {
		d.MotorTorque = f64(float64(int16(v)) * 0.1)
	}
	if v := binary.BigEndian.Uint16(p[6:8]); v != 0xFFFF {
		d.MotorPower = f64(float64(int16(v)))
	}
	if p[8] != 0xFF {
		d.Throttle = i64(int64(p[8]))
	}
	return r
}

// 枚举翻译表(§5.2: L1 数字码 → L2 字符串; 非法码值 = 字段丢弃, 不进 DLQ)
var rideStateStr = map[byte]string{0x01: "riding", 0x02: "parked", 0x03: "pushing", 0x04: "reverse"}
var rideModeStr = map[byte]string{0x01: "eco", 0x02: "standard", 0x03: "sport"}

func f64(v float64) *float64 { return &v }
func i64(v int64) *int64     { return &v }

// round6 经纬度保留 6 位小数(1e-6° 精度)
func round6(v float64) float64 { return math.Round(v*1e6) / 1e6 }
