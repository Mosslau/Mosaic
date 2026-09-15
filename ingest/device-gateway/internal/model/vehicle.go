// Package model 定义 OceanVerse 平台的车端数据契约。
// 本文件是全平台数据流的"宪法": Flink DDL、ClickHouse 表结构、
// Java 服务 DTO 均以此为源头派生。修改它必须走评审。
package model

import (
	"encoding/json"
	"fmt"
	"time"
)

// ReportType 上报数据类型
type ReportType string

const (
	ReportVehicleStatus ReportType = "vehicle_status" // 整车状态(位置/速度/SOC)
	ReportBatteryStatus ReportType = "battery_status" // 电池详细状态(BMS)
	ReportFault         ReportType = "fault"          // 故障码上报
	ReportCharging      ReportType = "charging"       // 充电状态
)

// validTypes 合法类型集合
var validTypes = map[ReportType]bool{
	ReportVehicleStatus: true,
	ReportBatteryStatus: true,
	ReportFault:         true,
	ReportCharging:      true,
}

// ReportData 上报数据载荷。字段全部可选(omitempty), 不同 type 使用不同子集。
// 数值语义:
//   - Speed:    km/h
//   - SOC:      电池剩余电量百分比 [0,100]
//   - Voltage:  电池总电压 V
//   - Current:  电池电流 A, 放电为正、充电为负
//   - TempMax:  电池最高单体温度 ℃
//   - TempMin:  电池最低单体温度 ℃
//   - Lng/Lat:  WGS84 经纬度
//   - Odometer: 累计里程 km
type ReportData struct {
	Speed      *float64 `json:"speed,omitempty"`
	SOC        *float64 `json:"soc,omitempty"`
	Voltage    *float64 `json:"voltage,omitempty"`
	Current    *float64 `json:"current,omitempty"`
	TempMax    *float64 `json:"temp_max,omitempty"`
	TempMin    *float64 `json:"temp_min,omitempty"`
	Lng        *float64 `json:"lng,omitempty"`
	Lat        *float64 `json:"lat,omitempty"`
	Odometer   *float64 `json:"odometer,omitempty"`
	FaultCodes []string `json:"fault_codes,omitempty"`
}

// VehicleReport 车端上报标准消息(平台数据契约 v1)
type VehicleReport struct {
	VIN  string     `json:"vin"`  // 车辆唯一标识(车架号)
	Ts   int64      `json:"ts"`   // 事件时间戳(Unix 秒)
	Type ReportType `json:"type"` // 数据类型
	Data ReportData `json:"data"` // 数据载荷
}

// Validate 校验一条上报是否合法。返回 nil 表示通过。
// 网关第一道防线: 不让垃圾数据污染 Kafka 和数据湖。
func (r *VehicleReport) Validate() error {
	if len(r.VIN) < 5 || len(r.VIN) > 32 {
		return fmt.Errorf("vin 长度必须在 5~32 之间, 实际 %d", len(r.VIN))
	}
	if !validTypes[r.Type] {
		return fmt.Errorf("未知 type: %q", r.Type)
	}
	// 时间戳容差: 过去 7 天 ~ 未来 5 分钟
	now := time.Now().Unix()
	if r.Ts < now-7*86400 || r.Ts > now+300 {
		return fmt.Errorf("ts 超出合理范围: %d (now=%d)", r.Ts, now)
	}
	if r.Data.SOC != nil && (*r.Data.SOC < 0 || *r.Data.SOC > 100) {
		return fmt.Errorf("soc 超出 [0,100]: %v", *r.Data.SOC)
	}
	if r.Data.Speed != nil && (*r.Data.Speed < 0 || *r.Data.Speed > 300) {
		return fmt.Errorf("speed 超出 [0,300]: %v", *r.Data.Speed)
	}
	if r.Data.TempMax != nil && (*r.Data.TempMax < -40 || *r.Data.TempMax > 150) {
		return fmt.Errorf("temp_max 超出 [-40,150]: %v", *r.Data.TempMax)
	}
	if r.Data.Lat != nil && (*r.Data.Lat < -90 || *r.Data.Lat > 90) {
		return fmt.Errorf("lat 超出 [-90,90]: %v", *r.Data.Lat)
	}
	if r.Data.Lng != nil && (*r.Data.Lng < -180 || *r.Data.Lng > 180) {
		return fmt.Errorf("lng 超出 [-180,180]: %v", *r.Data.Lng)
	}
	if r.Type == ReportFault && len(r.Data.FaultCodes) == 0 {
		return fmt.Errorf("type=fault 时 fault_codes 不能为空")
	}
	return nil
}

// Key 返回 Kafka 消息 key: 用 VIN 保证同一辆车的数据进入同一分区(局部有序)。
func (r *VehicleReport) Key() []byte {
	return []byte(r.VIN)
}

// Encode 序列化为 Kafka 消息体(JSON)。
func (r *VehicleReport) Encode() ([]byte, error) {
	return json.Marshal(r)
}
