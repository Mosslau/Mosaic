// 来源：ph21-data-ingest-gateway exercises/sol-02-metrics-receiver/sol02_test.go
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
	got, err := r.Handle([]byte(`{"sourceID":"src-001","seq":1,"value":1000}`))
	if err != nil {
		t.Fatal(err)
	}
	if got.ValuePct != 100 {
		t.Errorf("原始计数 1000 应换算 100%%, got %v", got.ValuePct)
	}
	if !strings.Contains(r.Summary(), "生效 1") {
		t.Error("汇总应含生效 1")
	}
}

func TestHandleBadData(t *testing.T) {
	r := NewReceiver(100)
	for _, raw := range []string{
		`not-json`,
		`{"seq":1,"value":10}`,                        // 缺 sourceID
		`{"sourceID":"src-001","value":10}`,           // 缺 seq
		`{"sourceID":"src-001","seq":2,"value":-1}`,   // 负量值
		`{"sourceID":"src-001","seq":3,"value":1500}`, // 超量程
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
	ok(`{"sourceID":"src-001","seq":1,"value":30}`)
	ok(`{"sourceID":"src-001","seq":2,"value":40}`)
	// 重复与乱序都该被拦。
	for _, raw := range []string{
		`{"sourceID":"src-001","seq":2,"value":40}`, // 重复
		`{"sourceID":"src-001","seq":1,"value":30}`, // 乱序迟到
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
		raw := `{"sourceID":"v","seq":` + strconv.Itoa(i) + `,"value":10}`
		if _, err := r.Handle([]byte(raw)); err != nil {
			t.Fatalf("第 %d 条应生效: %v", i, err)
		}
	}
	// 窗口淘汰的最老条目：单调水位仍拒（与 ex02 同构的语义）。
	if _, err := r.Handle([]byte(`{"sourceID":"v","seq":1,"value":10}`)); err == nil {
		t.Error("窗口外旧 seq 应被水位拒绝")
	}
	if _, err := r.Handle([]byte(`{"sourceID":"v","seq":51,"value":10}`)); err != nil {
		t.Errorf("新 seq 应生效: %v", err)
	}
}
