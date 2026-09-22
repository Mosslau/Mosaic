// Package simdata 车端仿真数据构造器。
// HTTP 模拟器(cmd/simulator)与 MQTT 模拟器(cmd/mqtt-simulator)共用,
// 保证两条通道压测产生的数据分布完全一致。
package simdata

import (
	"math/rand/v2"
	"time"

	"github.com/Mosslau/OceanVerse/ingest/device-contracts/vehicle"
)

// SimModel 仿真车型。真实车队多车型接入后, 可按车型扩展构造器。
const SimModel = "A100"

// BuildVehicleStatus 构造一条仿真的整车状态上报。
// soc 由调用方持有(每辆车独立), 本函数模拟行驶耗电与换电满电。
func BuildVehicleStatus(vin string, rng *rand.Rand, soc *float64) *vehicle.VehicleReport {
	speed := rng.Float64() * 45 // 0~45 km/h 市区骑行
	*soc -= 0.01 + rng.Float64()*0.05
	if *soc < 5 {
		*soc = 100 // 模拟换电
	}
	return &vehicle.VehicleReport{
		VIN:  vin,
		Ts:   time.Now().Unix(),
		Type: vehicle.ReportVehicleStatus,
		// 信封 v2: 新产生的数据显式携带版本与车型
		SchemaVersion: vehicle.SchemaV1,
		Model:         SimModel,
		Data: vehicle.ReportData{
			Speed:    f64(speed),
			SOC:      f64(*soc),
			Voltage:  f64(55 + rng.Float64()*12),     // 48V/60V 平台
			Current:  f64(-(2 + rng.Float64()*10)),   // 放电 2~12A
			TempMax:  f64(20 + rng.Float64()*25),     // 20~45℃
			Lng:      f64(113.9 + rng.Float64()*0.2), // 深圳南山附近
			Lat:      f64(22.5 + rng.Float64()*0.2),
			Odometer: f64(rng.Float64() * 20000),
		},
	}
}

// BuildFault 构造一条故障码上报(事件触发型, 与周期状态不同)
func BuildFault(vin string, rng *rand.Rand) *vehicle.VehicleReport {
	codes := []string{"E1001", "E2003", "E3002", "P0A7F", "B1012"}
	return &vehicle.VehicleReport{
		VIN:  vin,
		Ts:   time.Now().Unix(),
		Type: vehicle.ReportFault,
		// 信封 v2
		SchemaVersion: vehicle.SchemaV1,
		Model:         SimModel,
		Data: vehicle.ReportData{
			FaultCodes: []string{codes[rng.IntN(len(codes))]},
		},
	}
}

func f64(v float64) *float64 { return &v }
