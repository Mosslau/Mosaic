// 来源：ph21-iot-vehicle-edge exercises/sol-02-telemetry-receiver/sol02_test.go
// 一句话说明：练习 2 验收测试——有效报文换算正确、缺字段/超量程/坏 JSON 归坏数据、
// 重复与乱序归重复、去重窗有界、窗口淘汰后旧 seq 仍被单调水位拦截。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"strconv"
	"strings"
	"testing"
)

func TestHandleValidAndConvert(t *testing.T) {
	r := NewReceiver(100)
	got, err := r.Handle([]byte(`{"vin":"veh-001","seq":1,"speed":100}`))
	if err != nil {
		t.Fatal(err)
	}
	if got.SpeedKmh != 360 {
		t.Errorf("100m/s 应换算 360km/h, got %v", got.SpeedKmh)
	}
	if !strings.Contains(r.Summary(), "生效 1") {
		t.Error("汇总应含生效 1")
	}
}

func TestHandleBadData(t *testing.T) {
	r := NewReceiver(100)
	for _, raw := range []string{
		`not-json`,
		`{"seq":1,"speed":10}`,                  // 缺 vin
		`{"vin":"veh-001","speed":10}`,          // 缺 seq
		`{"vin":"veh-001","seq":2,"speed":-1}`,  // 负速度
		`{"vin":"veh-001","seq":3,"speed":500}`, // 超量程
	} {
		if _, err := r.Handle([]byte(raw)); err == nil {
			t.Errorf("坏数据应被拒: %s", raw)
		}
	}
	if !strings.Contains(r.Summary(), "坏数据 5") {
		t.Errorf("坏数据计数异常: %s", r.Summary())
	}
}

func TestDuplicateAndOutOfOrder(t *testing.T) {
	r := NewReceiver(100)
	ok := func(raw string) {
		if _, err := r.Handle([]byte(raw)); err != nil {
			t.Fatalf("应生效: %s (%v)", raw, err)
		}
	}
	ok(`{"vin":"veh-001","seq":1,"speed":30}`)
	ok(`{"vin":"veh-001","seq":2,"speed":40}`)
	// 重复与乱序都该被拦。
	for _, raw := range []string{
		`{"vin":"veh-001","seq":2,"speed":40}`, // 重复
		`{"vin":"veh-001","seq":1,"speed":30}`, // 乱序迟到
	} {
		if _, err := r.Handle([]byte(raw)); err == nil {
			t.Errorf("应拒: %s", raw)
		}
	}
	if !strings.Contains(r.Summary(), "重复 2") {
		t.Errorf("重复计数异常: %s", r.Summary())
	}
}

func TestWindowBoundedAndCeilingHolds(t *testing.T) {
	r := NewReceiver(5)
	for i := 1; i <= 50; i++ {
		raw := `{"vin":"v","seq":` + strconv.Itoa(i) + `,"speed":10}`
		if _, err := r.Handle([]byte(raw)); err != nil {
			t.Fatalf("第 %d 条应生效: %v", i, err)
		}
	}
	// 窗口淘汰的最老条目：单调水位仍拒（与 ex02 同构的语义）。
	if _, err := r.Handle([]byte(`{"vin":"v","seq":1,"speed":10}`)); err == nil {
		t.Error("窗口外旧 seq 应被水位拒绝")
	}
	if _, err := r.Handle([]byte(`{"vin":"v","seq":51,"speed":10}`)); err != nil {
		t.Errorf("新 seq 应生效: %v", err)
	}
}
