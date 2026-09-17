package simdata

import "math/rand/v2"

// 二进制通道(0x08/0x09/0x80/0x81)仿真值构造器。
// 造数规则: 映射文档 §5.1"模拟器造数规则"; 编码归 simframe(两包分工:
// simdata 管数据分布, simframe 管字节布局, 与 codec 解码器对拍)。

// BatteryDetail 0x08/0x09 电池明细仿真值
type BatteryDetail struct {
	CellVoltages []float64 // 单体电压 V
	ProbeTemps   []float64 // 探针温度 ℃
}

// BuildBatteryDetail 单体电压: 名义值 ±50mV 抖动, 5% 概率造一节欠压(<2.5V)供告警链路演练;
// 探针温度: 基线 25~35℃, 充电时 +5~10℃, 1% 概率造 >60℃ 高温探针(对应 Flink 作业"高温电池")。
func BuildBatteryDetail(rng *rand.Rand, charging bool) BatteryDetail {
	const cells, probes = 16, 4 // 48V 包 16 串; 探针: 进线/电芯中部/出线/BMS MOS
	d := BatteryDetail{
		CellVoltages: make([]float64, cells),
		ProbeTemps:   make([]float64, probes),
	}
	for i := range d.CellVoltages {
		d.CellVoltages[i] = 3.45 + (rng.Float64()-0.5)*0.1 // 名义 3.45V ±50mV
	}
	if rng.Float64() < 0.05 {
		d.CellVoltages[rng.IntN(cells)] = 2.3 + rng.Float64()*0.2 // 欠压 2.3~2.5V
	}
	base := 25 + rng.Float64()*10
	if charging {
		base += 5 + rng.Float64()*5
	}
	for i := range d.ProbeTemps {
		d.ProbeTemps[i] = base + (rng.Float64()-0.5)*2
	}
	if rng.Float64() < 0.01 {
		d.ProbeTemps[rng.IntN(probes)] = 60 + rng.Float64()*20 // 高温探针 60~80℃
	}
	return d
}

// ChargingDetail 0x80 充电业务仿真值
type ChargingDetail struct {
	RemainMin uint16
	PowerKW   float64
	EnergyKWh float64
	PileID    uint32
	StationID uint32
	SlotNo    uint8
}

// BuildCharging 模拟一次换电柜/快充桩充电过程(仅在充电状态帧附带)。
func BuildCharging(rng *rand.Rand) ChargingDetail {
	return ChargingDetail{
		RemainMin: uint16(20 + rng.IntN(160)),          // 20~180 分钟
		PowerKW:   0.5 + rng.Float64()*2.5,             // 0.5~3 kW 两轮车快充
		EnergyKWh: rng.Float64() * 1.5,                 // 本次已充 0~1.5 kWh
		PileID:    uint32(1000 + rng.IntN(9000)),       // 桩号 1000~9999
		StationID: uint32(100 + rng.IntN(900)),         // 站号 100~999
		SlotNo:    uint8(1 + rng.IntN(12)),             // 仓号 1~12
	}
}

// WorkDetail 0x81 工况仿真值(L1 数字码见 simframe.RideXxx/ModeXxx)
type WorkDetail struct {
	RideState   byte
	RideMode    byte
	MotorRPM    uint16
	MotorTorque float64 // N·m
	MotorPower  float64 // W
	Throttle    uint8   // %
}

// BuildWork 按当前车速拟合工况: 停车时转速/功率归零、转把松开; 行驶中功率随速度;
// 小概率能量回收(转矩/功率为负)。
func BuildWork(rng *rand.Rand, speedKmh float64) WorkDetail {
	if speedKmh < 0.5 {
		return WorkDetail{RideState: 0x02 /*驻车*/, RideMode: byte(1 + rng.IntN(3))}
	}
	w := WorkDetail{
		RideState:   0x01, // 行驶
		RideMode:    byte(1 + rng.IntN(3)),
		MotorRPM:    uint16(speedKmh * 55),                    // ≈55 rpm/(km/h) 轮径拟合
		MotorTorque: 8 + rng.Float64()*25,                     // 8~33 N·m
		Throttle:    uint8(20 + rng.IntN(80)),                 // 20~100%
	}
	w.MotorPower = float64(w.MotorTorque) * float64(w.MotorRPM) / 9.5488 // P=T·ω
	if rng.Float64() < 0.03 {                                            // 3% 滑行回收
		w.MotorTorque = -w.MotorTorque / 3
		w.MotorPower = -w.MotorPower / 3
	}
	return w
}
