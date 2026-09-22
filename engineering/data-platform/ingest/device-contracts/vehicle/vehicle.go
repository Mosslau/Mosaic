// Package vehicle 定义 OceanVerse 平台的车端数据契约（Go 绑定）。
// 本包是根 contracts/（语言无关形态）的 Go 投影；Kafka 上的 JSON 消息形态
// 是全平台数据流的"宪法"：Flink DDL、ClickHouse 表结构、Java 服务 DTO、
// device-codec 解析产物均与该 JSON 形态对齐。修改本包必须走评审。
//
// 位置说明: 本包原位于 ingest/device-gateway/internal/model，因 internal 包
// 编译器私有（device-codec 等兄弟模块无法 import）迁至共享模块；2026-09-17
// 按"语言无关在根 contracts/、Go 绑定随消费者"定址 ingest/device-contracts/。
package vehicle

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
	ReportWork          ReportType = "work"           // 工况(骑行状态/电机, 0x81 载体, v1.4 新增)
)

// validTypes 合法类型集合
var validTypes = map[ReportType]bool{
	ReportVehicleStatus: true,
	ReportBatteryStatus: true,
	ReportFault:         true,
	ReportCharging:      true,
	ReportWork:          true,
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

	// battery_status 扩展(0x08/0x09 载体, 映射文档 §5.1):
	CellVoltages []float64 `json:"cell_voltages,omitempty"` // 单体电压 V, 元素 ∈ [0,5]
	ProbeTemps   []float64 `json:"probe_temps,omitempty"`   // 探针温度 ℃, 元素 ∈ [-40,150]

	// charging 扩展(0x80 载体, 映射文档 §5.2):
	RemainChargeMin *int64   `json:"remain_charge_min,omitempty"` // 剩余充电时间 min ∈ [0,6000]
	ChargePower     *float64 `json:"charge_power,omitempty"`      // 充电功率 kW ∈ [0,100]
	ChargeKWh       *float64 `json:"charge_kwh,omitempty"`        // 本次充电电量 kWh ∈ [0,100]
	PileID          *int64   `json:"pile_id,omitempty"`           // 充电桩号, 0=无
	StationID       *int64   `json:"station_id,omitempty"`        // 换电站 ID, 0=无
	SlotNo          *int64   `json:"slot_no,omitempty"`           // 换电柜仓号 ∈ [1,254]

	// work 工况扩展(0x81 载体, 映射文档 §5.2):
	RideState   *string  `json:"ride_state,omitempty"`   // riding/parked/pushing/reverse
	RideMode    *string  `json:"ride_mode,omitempty"`    // eco/standard/sport
	MotorRPM    *int64   `json:"motor_rpm,omitempty"`    // 电机转速 ∈ [0,20000]
	MotorTorque *float64 `json:"motor_torque,omitempty"` // N·m, 负=能量回收
	MotorPower  *float64 `json:"motor_power,omitempty"`  // W, 负=能量回收
	Throttle    *int64   `json:"throttle,omitempty"`     // 转把开度 % ∈ [0,100]
}

// SchemaV1 契约初始版本。首批固件冻结前的历史报文没有 schema_version 字段,
// 缺省一律视为 v1(信封 v2 修订, 设计文档 §4.4)。
const SchemaV1 = "v1"

// VehicleReport 车端上报标准消息(平台数据契约)
type VehicleReport struct {
	VIN  string     `json:"vin"`  // 车辆唯一标识(车架号)
	Ts   int64      `json:"ts"`   // 事件时间戳(Unix 秒)
	Type ReportType `json:"type"` // 数据类型
	Data ReportData `json:"data"` // 数据载荷

	// 信封 v2 字段:
	//   SchemaVersion: 契约版本, 缺省回填为 SchemaV1; 网关只接受已知版本, 未知版本拒绝(fail-fast)
	//   Model: 车型, 用于按车型选择校验/解析规则; 暂可缺省, Schema Registry 落地(第 4 阶段)后必填
	SchemaVersion string `json:"schema_version,omitempty"`
	Model         string `json:"model,omitempty"`
}

// VINMinLen/VINMaxLen VIN 长度契约(唯一源)。网关(HTTP/MQTT 通道)与 codec(二进制通道)
// 必须用同一组边界 —— 2026-09-20 修复"两侧校验不对称": 二进制通道的 VIN 来自帧内字节,
// 此前只判空, 于是一个 1 字节 VIN 也能产出成合法 L2 数据。
const (
	VINMinLen = 5
	VINMaxLen = 32
)

// VINContractReason 判断 VIN 是否符合契约, 返回空串表示合法, 否则返回人话原因。
// 调用方直接把它拼进错误/DLQ reason, 保证三条通道的判据与措辞同源。
func VINContractReason(vin string) string {
	if n := len(vin); n < VINMinLen || n > VINMaxLen {
		return fmt.Sprintf("长度必须在 %d~%d 之间, 实际 %d", VINMinLen, VINMaxLen, n)
	}
	return ""
}

// Validate 校验一条上报是否合法。返回 nil 表示通过。
// 网关第一道防线: 不让垃圾数据污染 Kafka 和数据湖。
// 注意: 会做缺省回填(schema_version 空→v1), 调用方应在 Validate 通过后再 Encode,
// 以保证写进 Kafka 的消息显式携带版本(回填放在双通道的唯一漏斗里, 不会漏)。
func (r *VehicleReport) Validate() error {
	if r.SchemaVersion == "" {
		r.SchemaVersion = SchemaV1
	}
	if r.SchemaVersion != SchemaV1 {
		return fmt.Errorf("未知 schema_version: %q (当前仅支持 %s)", r.SchemaVersion, SchemaV1)
	}
	if reason := VINContractReason(r.VIN); reason != "" {
		return fmt.Errorf("vin %s", reason)
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
	// battery_status 扩展(§5.1)
	for i, v := range r.Data.CellVoltages {
		if v < 0 || v > 5 {
			return fmt.Errorf("cell_voltages[%d] 超出 [0,5]: %v", i, v)
		}
	}
	for i, t := range r.Data.ProbeTemps {
		if t < -40 || t > 150 {
			return fmt.Errorf("probe_temps[%d] 超出 [-40,150]: %v", i, t)
		}
	}
	// charging 扩展(§5.2)
	if v := r.Data.RemainChargeMin; v != nil && (*v < 0 || *v > 6000) {
		return fmt.Errorf("remain_charge_min 超出 [0,6000]: %v", *v)
	}
	if v := r.Data.ChargePower; v != nil && (*v < 0 || *v > 100) {
		return fmt.Errorf("charge_power 超出 [0,100]: %v", *v)
	}
	if v := r.Data.ChargeKWh; v != nil && (*v < 0 || *v > 100) {
		return fmt.Errorf("charge_kwh 超出 [0,100]: %v", *v)
	}
	if v := r.Data.SlotNo; v != nil && (*v < 1 || *v > 254) {
		return fmt.Errorf("slot_no 超出 [1,254]: %v", *v)
	}
	// work 扩展(§5.2)
	if v := r.Data.RideState; v != nil && !validRideState[*v] {
		return fmt.Errorf("未知 ride_state: %q", *v)
	}
	if v := r.Data.RideMode; v != nil && !validRideMode[*v] {
		return fmt.Errorf("未知 ride_mode: %q", *v)
	}
	if v := r.Data.MotorRPM; v != nil && (*v < 0 || *v > 20000) {
		return fmt.Errorf("motor_rpm 超出 [0,20000]: %v", *v)
	}
	if v := r.Data.Throttle; v != nil && (*v < 0 || *v > 100) {
		return fmt.Errorf("throttle 超出 [0,100]: %v", *v)
	}
	return nil
}

// 枚举值集合(§5.2: L1 数字码由 codec 译为 L2 字符串)
var validRideState = map[string]bool{"riding": true, "parked": true, "pushing": true, "reverse": true}
var validRideMode = map[string]bool{"eco": true, "standard": true, "sport": true}

// Key 返回 Kafka 消息 key: 用 VIN 保证同一辆车的数据进入同一分区(局部有序)。
func (r *VehicleReport) Key() []byte {
	return []byte(r.VIN)
}

// Encode 序列化为 Kafka 消息体(JSON)。
func (r *VehicleReport) Encode() ([]byte, error) {
	return json.Marshal(r)
}
