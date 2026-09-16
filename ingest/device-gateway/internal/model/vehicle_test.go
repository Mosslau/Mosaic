package model

import (
	"encoding/json"
	"testing"
	"time"
)

func f64(v float64) *float64 { return &v }

// validReport 返回一条合法基准上报, 各用例在此基础上改坏
func validReport() VehicleReport {
	return VehicleReport{
		VIN:  "OV20260001",
		Ts:   time.Now().Unix(),
		Type: ReportVehicleStatus,
		Data: ReportData{SOC: f64(78), Speed: f64(32.5)},
	}
}

func TestValidate_OK(t *testing.T) {
	r := validReport()
	if err := r.Validate(); err != nil {
		t.Fatalf("合法上报应通过, 实际: %v", err)
	}
}

func TestValidate_VIN(t *testing.T) {
	for _, vin := range []string{"", "abc", " OV1", string(make([]byte, 33))} {
		r := validReport()
		r.VIN = vin
		if err := r.Validate(); err == nil {
			t.Errorf("vin=%q 应拒绝", vin)
		}
	}
}

func TestValidate_Timestamp(t *testing.T) {
	now := time.Now().Unix()
	cases := []struct {
		name string
		ts   int64
		ok   bool
	}{
		{"现在", now, true},
		{"6天前", now - 6*86400, true},
		{"8天前", now - 8*86400, false},
		{"未来4分钟", now + 240, true},
		{"未来10分钟", now + 600, false},
		{"1970年", 0, false},
	}
	for _, c := range cases {
		r := validReport()
		r.Ts = c.ts
		err := r.Validate()
		if c.ok && err != nil {
			t.Errorf("%s: 应通过, 实际 %v", c.name, err)
		}
		if !c.ok && err == nil {
			t.Errorf("%s: 应拒绝", c.name)
		}
	}
}

func TestValidate_Ranges(t *testing.T) {
	cases := []struct {
		name   string
		mutate func(*VehicleReport)
		ok     bool
	}{
		{"soc=0 边界", func(r *VehicleReport) { r.Data.SOC = f64(0) }, true},
		{"soc=100 边界", func(r *VehicleReport) { r.Data.SOC = f64(100) }, true},
		{"soc=300 越界", func(r *VehicleReport) { r.Data.SOC = f64(300) }, false},
		{"soc=-1 越界", func(r *VehicleReport) { r.Data.SOC = f64(-1) }, false},
		{"speed=300 边界", func(r *VehicleReport) { r.Data.Speed = f64(300) }, true},
		{"speed=500 越界", func(r *VehicleReport) { r.Data.Speed = f64(500) }, false},
		{"temp=-40 边界", func(r *VehicleReport) { r.Data.TempMax = f64(-40) }, true},
		{"temp=151 越界", func(r *VehicleReport) { r.Data.TempMax = f64(151) }, false},
		{"lat=91 越界", func(r *VehicleReport) { r.Data.Lat = f64(91) }, false},
		{"lng=-181 越界", func(r *VehicleReport) { r.Data.Lng = f64(-181) }, false},
	}
	for _, c := range cases {
		r := validReport()
		c.mutate(&r)
		err := r.Validate()
		if c.ok && err != nil {
			t.Errorf("%s: 应通过, 实际 %v", c.name, err)
		}
		if !c.ok && err == nil {
			t.Errorf("%s: 应拒绝", c.name)
		}
	}
}

func TestValidate_Type(t *testing.T) {
	// 未知类型拒绝
	r := validReport()
	r.Type = "hacked_type"
	if err := r.Validate(); err == nil {
		t.Error("未知 type 应拒绝")
	}
	// 四种合法类型通过
	for _, typ := range []ReportType{ReportVehicleStatus, ReportBatteryStatus, ReportCharging} {
		r = validReport()
		r.Type = typ
		if err := r.Validate(); err != nil {
			t.Errorf("type=%s 应通过, 实际 %v", typ, err)
		}
	}
	// fault 必须带 fault_codes
	r = validReport()
	r.Type = ReportFault
	r.Data.FaultCodes = nil
	if err := r.Validate(); err == nil {
		t.Error("fault 无 fault_codes 应拒绝")
	}
	r.Data.FaultCodes = []string{"E1001"}
	if err := r.Validate(); err != nil {
		t.Errorf("fault 带 fault_codes 应通过, 实际 %v", err)
	}
}

func TestValidate_SchemaEnvelope(t *testing.T) {
	// 缺省回填 v1(历史报文无该字段)
	r := validReport()
	if err := r.Validate(); err != nil {
		t.Fatalf("合法上报应通过, 实际: %v", err)
	}
	if r.SchemaVersion != SchemaV1 {
		t.Errorf("schema_version 缺省应回填 %q, 实际 %q", SchemaV1, r.SchemaVersion)
	}
	// 显式 v1 保持不变
	r = validReport()
	r.SchemaVersion = SchemaV1
	if err := r.Validate(); err != nil {
		t.Errorf("显式 v1 应通过, 实际 %v", err)
	}
	// 未知版本拒绝(fail-fast, 防止按错误格式解析未来报文)
	r = validReport()
	r.SchemaVersion = "v99"
	if err := r.Validate(); err == nil {
		t.Error("未知 schema_version 应拒绝")
	}
	// model 可缺省、可携带
	r = validReport()
	r.Model = "A100"
	if err := r.Validate(); err != nil {
		t.Errorf("携带 model 应通过, 实际 %v", err)
	}
}

func TestKeyAndEncode(t *testing.T) {
	r := validReport()
	if string(r.Key()) != r.VIN {
		t.Errorf("Key() 应为 VIN, 实际 %s", r.Key())
	}
	b, err := r.Encode()
	if err != nil {
		t.Fatalf("Encode 失败: %v", err)
	}
	if len(b) == 0 {
		t.Error("Encode 结果为空")
	}
}

// 信封 v2: Validate 通过后再 Encode 的消息必须显式携带 schema_version,
// 保证 Kafka/数据湖里的数据自带版本(期④ Schema Registry 接管的前提)。
func TestEncode_IncludesSchemaVersion(t *testing.T) {
	r := validReport()
	if err := r.Validate(); err != nil { // 触发缺省回填
		t.Fatalf("Validate 应通过: %v", err)
	}
	b, err := r.Encode()
	if err != nil {
		t.Fatalf("Encode 失败: %v", err)
	}
	var decoded map[string]any
	if err := json.Unmarshal(b, &decoded); err != nil {
		t.Fatalf("Encode 结果应为合法 JSON: %v", err)
	}
	if decoded["schema_version"] != SchemaV1 {
		t.Errorf("编码后应显式携带 schema_version=%q, 实际 %v", SchemaV1, decoded["schema_version"])
	}
}
