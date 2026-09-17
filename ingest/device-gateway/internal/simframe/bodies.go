package simframe

import (
	"encoding/binary"
	"math"
)

// 信息类型标志(§4 启用表)
const (
	TypeVehicle     = 0x01 // 整车数据
	TypePosition    = 0x05 // 车辆位置
	TypeExtremes    = 0x06 // 极值数据
	TypeAlarm       = 0x07 // 报警数据
	TypeBatteryVolt = 0x08 // 储能装置电压
	TypeBatteryTemp = 0x09 // 储能装置温度
	TypeCharging    = 0x80 // 自定义: charging 充电业务(§5.2)
	TypeWork        = 0x81 // 自定义: 工况 work(§5.2)
)

// ---- 无效值(§5 无效值约定: 未安装/不支持的字段填国标无效值, codec 丢弃) ----
const (
	invalidU8  = 0xFF
	invalidU16 = 0xFFFF
)

// ---- 0x01 整车数据(国标 2016 布局 16B; 不上报字段填无效值) ----

// VehicleBody 0x01 整车信息体输入。Voltage/Current 不在 0x01 内,
// 由 0x08 子系统电压/电流承载(§5/§5.1, codec 可交叉校验)。
type VehicleBody struct {
	VehicleStatus byte    // 车辆状态: 0x01 启动(其余见国标)
	ChargeStatus  byte    // 充电状态: 0x01 停车充电 / 0x03 未充电 / 0x04 充电完成
	SpeedKmh      float64 // 0.1 km/h
	OdometerKm    float64 // 0.1 km
	SOC           float64 // 1%
}

func BodyVehicle(b VehicleBody) []byte {
	out := []byte{TypeVehicle, b.VehicleStatus, b.ChargeStatus, invalidU8 /*运行模式*/}
	out = binary.BigEndian.AppendUint16(out, uint16(math.Round(b.SpeedKmh*10)))
	out = binary.BigEndian.AppendUint32(out, uint32(math.Round(b.OdometerKm*10)))
	out = append(out, byte(math.Round(b.SOC)))
	out = append(out, invalidU8 /*DC-DC状态*/, invalidU8 /*档位*/)
	out = binary.BigEndian.AppendUint16(out, invalidU16) // 绝缘电阻
	out = append(out, invalidU8 /*加速踏板*/, invalidU8 /*制动踏板*/)
	return out // 1 + 16 = 17B
}

// ---- 0x05 车辆位置(国标布局: 定位状态 1B + 经度 4B + 纬度 4B) ----

// BodyPosition 定位状态固定 0x00 = 定位有效 + 北纬 + 东经(深圳车队)。
func BodyPosition(lng, lat float64) []byte {
	out := []byte{TypePosition, 0x00}
	out = binary.BigEndian.AppendUint32(out, uint32(math.Round(lng*1e6))) // 1e-6°, WGS84
	out = binary.BigEndian.AppendUint32(out, uint32(math.Round(lat*1e6)))
	return out
}

// ---- 0x06 极值数据(国标布局 14B; 电压极值本项目暂不暴露 → 无效值) ----

// BodyExtremes 只承载 tempMax/tempMin(§5: 附带子系统号/探针号, L2 暂不暴露)。
func BodyExtremes(tempMax, tempMin float64) []byte {
	out := []byte{TypeExtremes}
	out = append(out, invalidU8, invalidU8)                       // 最高电压子系统号/单体号
	out = binary.BigEndian.AppendUint16(out, invalidU16)          // 最高单体电压
	out = append(out, invalidU8, invalidU8)                       // 最低电压子系统号/单体号
	out = binary.BigEndian.AppendUint16(out, invalidU16)          // 最低单体电压
	out = append(out, invalidU8, invalidU8, tempByte(tempMax))    // 最高温度子系统号/探针号/值
	out = append(out, invalidU8, invalidU8, tempByte(tempMin))    // 最低温度子系统号/探针号/值
	return out // 1 + 14 = 15B
}

// tempByte 温度编码: 偏移 -40℃, raw = ℃ + 40(§5)
func tempByte(celsius float64) byte {
	return byte(int(math.Round(celsius)) + 40)
}

// ---- 0x07 报警数据(国标布局: 等级 + 通用标志 4B + 四类故障码列表) ----

// BodyAlarm 故障码为 4B 十六进制码, L2 侧 hex 大写无前缀(§8-⑤)。
// 只使用"可充电储能装置故障"一类; 驱动电机/发动机/其他故障总数恒 0(两轮车简化)。
func BodyAlarm(level byte, faultCodes []uint32) []byte {
	out := []byte{TypeAlarm, level}
	out = append(out, 0, 0, 0, 0) // 通用报警标志(暂不逐位置位)
	out = append(out, byte(len(faultCodes)))
	for _, c := range faultCodes {
		out = binary.BigEndian.AppendUint32(out, c)
	}
	out = append(out, 0, 0, 0) // 驱动电机/发动机/其他故障总数
	return out
}

// ---- 0x08 储能装置电压(§5.1: 单储能子系统, 一帧不分帧) ----

type BatteryVoltBody struct {
	Voltage      float64   // 子系统电压 V(0.1V)——与整车口径一致, codec 可交叉校验
	Current      float64   // 子系统电流 A(0.1A, 偏移 1000A, 放电正/充电负)
	CellVoltages []float64 // 单体电压 V(0.001V)
}

func BodyBatteryVolt(b BatteryVoltBody) []byte {
	out := []byte{TypeBatteryVolt, 0x01, 0x01} // N=1, 子系统号=1
	out = binary.BigEndian.AppendUint16(out, uint16(math.Round(b.Voltage*10)))
	out = binary.BigEndian.AppendUint16(out, uint16(math.Round((b.Current+1000)*10)))
	n := len(b.CellVoltages)
	out = binary.BigEndian.AppendUint16(out, uint16(n)) // 单体总数
	out = binary.BigEndian.AppendUint16(out, 1)         // 本帧起始序号=1(不分帧)
	out = append(out, byte(n))                          // 本帧个数=总数
	for _, v := range b.CellVoltages {
		out = binary.BigEndian.AppendUint16(out, uint16(math.Round(v*1000)))
	}
	return out
}

// ---- 0x09 储能装置温度(§5.1) ----

func BodyBatteryTemp(probeTemps []float64) []byte {
	out := []byte{TypeBatteryTemp, 0x01, 0x01} // N=1, 子系统号=1
	out = binary.BigEndian.AppendUint16(out, uint16(len(probeTemps)))
	for _, t := range probeTemps {
		out = append(out, tempByte(t))
	}
	return out
}

// ---- 自定义单元统一头(§6): [单元类型 1B][协议版本 1B][长度 2B][payload] ----

func customBody(unitType byte, payload []byte) []byte {
	out := []byte{unitType, ProtoV1}
	out = binary.BigEndian.AppendUint16(out, uint16(len(payload)))
	return append(out, payload...)
}

// ---- 0x80 charging 充电业务(§5.2, payload 定长 15B) ----

type ChargingBody struct {
	RemainMin  uint16  // 剩余充电时间 min
	PowerKW    float64 // 充电功率 0.01 kW
	EnergyKWh  float64 // 本次充电电量 0.01 kWh
	PileID     uint32  // 充电桩号, 0=无
	StationID  uint32  // 换电站 ID, 0=无
	SlotNo     byte    // 换电柜仓号 1~254, 0xFF=无
}

func BodyCharging(b ChargingBody) []byte {
	p := make([]byte, 0, 15)
	p = binary.BigEndian.AppendUint16(p, b.RemainMin)
	p = binary.BigEndian.AppendUint16(p, uint16(math.Round(b.PowerKW*100)))
	p = binary.BigEndian.AppendUint16(p, uint16(math.Round(b.EnergyKWh*100)))
	p = binary.BigEndian.AppendUint32(p, b.PileID)
	p = binary.BigEndian.AppendUint32(p, b.StationID)
	p = append(p, b.SlotNo)
	return customBody(TypeCharging, p)
}

// ---- 0x81 工况 work(§5.2, payload 定长 9B) ----

// 骑行状态/模式(L1 数字码; codec 译为 L2 字符串)
const (
	RideRiding  = 0x01 // 行驶
	RideParked  = 0x02 // 驻车
	RidePushing = 0x03 // 推行
	RideReverse = 0x04 // 倒车

	ModeEco      = 0x01 // 经济
	ModeStandard = 0x02 // 标准
	ModeSport    = 0x03 // 运动
)

type WorkBody struct {
	RideState   byte    // RideXxx
	RideMode    byte    // ModeXxx
	MotorRPM    uint16  // 1 rpm
	MotorTorque float64 // 0.1 N·m, 有符号(负=能量回收)
	MotorPower  float64 // 1 W, 有符号(负=能量回收)
	Throttle    uint8   // 转把开度 %
}

func BodyWork(b WorkBody) []byte {
	p := []byte{b.RideState, b.RideMode}
	p = binary.BigEndian.AppendUint16(p, b.MotorRPM)
	p = binary.BigEndian.AppendUint16(p, uint16(int16(math.Round(b.MotorTorque*10))))
	p = binary.BigEndian.AppendUint16(p, uint16(int16(math.Round(b.MotorPower))))
	p = append(p, b.Throttle)
	return customBody(TypeWork, p)
}
