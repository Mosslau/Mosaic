// 来源：ph21-data-ingest-gateway examples/ex04-ota-service/ex04_test.go
// 一句话说明：固件台账 + 灰度决策器测试——登记/查重/校验拦截、全批成功推进到
// complete、批内失败越限判 rollback、未知 VIN 忽略、末批判定。决策器确定性回放。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"errors"
	"fmt"
	"testing"
	"time"
)

func fw(version, content string) Firmware {
	sum := shaOf(content)
	return Firmware{Version: version, SHA256: sum, Size: 100, ReleasedAt: time.Now()}
}

func fleetBatch(vins []string, from, to int) *Batch {
	return &Batch{Index: from, VINs: vins[from:to]}
}

func mkVins(n int) []string {
	out := make([]string, n)
	for i := range out {
		out[i] = fmt.Sprintf("veh-%03d", i)
	}
	return out
}

func TestFirmwareStoreRegisterVerify(t *testing.T) {
	s := NewFirmwareStore()
	if err := s.Register(fw("v1.0", "f1")); err != nil {
		t.Fatal(err)
	}
	if err := s.Register(fw("v1.0", "dup")); err == nil {
		t.Error("重复版本应报错")
	}
	if err := s.Register(Firmware{Version: "bad", SHA256: "xyz", Size: 1}); err == nil {
		t.Error("非法 sha256 应报错")
	}
	if _, err := s.Get("v9.9"); !errors.Is(err, ErrFirmwareNotFound) {
		t.Errorf("未知版本应 ErrFirmwareNotFound, got %v", err)
	}
	if err := s.VerifyContent("v1.0", []byte("f1")); err != nil {
		t.Errorf("正确内容应通过校验: %v", err)
	}
	if err := s.VerifyContent("v1.0", []byte("tampered")); err == nil {
		t.Error("篡改内容应被拦下")
	}
	if vs := s.Versions(); len(vs) != 1 || vs[0] != "v1.0" {
		t.Errorf("版本列表异常: %v", vs)
	}
}

func TestRolloutFullSuccess(t *testing.T) {
	vins := mkVins(12)
	start := map[string]string{}
	for _, v := range vins {
		start[v] = "v1.0"
	}
	batches := []*Batch{fleetBatch(vins, 0, 4), fleetBatch(vins, 4, 8), fleetBatch(vins, 8, 12)}
	r, err := NewRollout(RolloutOptions{TargetVersion: "v2.0", FailRateLimit: 0.2}, batches, start)
	if err != nil {
		t.Fatal(err)
	}
	// 第 1、2 批：末台推进时 advance。
	for _, b := range batches[:2] {
		for i, v := range b.VINs {
			d := r.OnDeviceReport(v, true)
			if i == len(b.VINs)-1 && d != DecisionAdvance {
				t.Errorf("批内末台应 advance, got %v", d)
			}
		}
	}
	// 第 3 批末台 → complete。
	for i, v := range batches[2].VINs {
		d := r.OnDeviceReport(v, true)
		if i == len(batches[2].VINs)-1 && d != DecisionComplete {
			t.Errorf("末批末台应 complete, got %v", d)
		}
	}
	if r.Status() != "done" {
		t.Errorf("终态应 done, got %s", r.Status())
	}
}

func TestRolloutRollsBackOnHighFailRate(t *testing.T) {
	vins := mkVins(8)
	start := map[string]string{}
	for _, v := range vins {
		start[v] = "v1.0"
	}
	batches := []*Batch{fleetBatch(vins, 0, 4), fleetBatch(vins, 4, 8)}
	r, _ := NewRollout(RolloutOptions{TargetVersion: "v2.0", FailRateLimit: 0.2}, batches, start)
	for _, v := range batches[0].VINs {
		if r.OnDeviceReport(v, true) == DecisionRollback {
			t.Fatal("第一批不应回滚")
		}
	}
	// 第二批 4 台中第 2 台失败：1/4 = 25% > 20% → 立即 rollback。
	d := r.OnDeviceReport(batches[1].VINs[0], true)
	if d == DecisionRollback {
		t.Fatal("首批一台失败未越限")
	}
	d = r.OnDeviceReport(batches[1].VINs[1], false)
	if d != DecisionRollback {
		t.Fatalf("失败率越限应 rollback, got %v", d)
	}
	if r.Status() != "rolledback" {
		t.Errorf("状态应 rolledback, got %s", r.Status())
	}
	if got := r.RollbackTarget(batches[1].VINs[1]); got != "v1.0" {
		t.Errorf("回滚目标应 v1.0, got %s", got)
	}
	// 终态后报告应被忽略（不再改变状态）。
	if r.OnDeviceReport(batches[1].VINs[2], true) != DecisionHold {
		t.Error("终态后报告应 hold")
	}
}

func TestRolloutIgnoresUnknownVin(t *testing.T) {
	vins := mkVins(4)
	start := map[string]string{}
	for _, v := range vins {
		start[v] = "v1.0"
	}
	r, _ := NewRollout(RolloutOptions{TargetVersion: "v2.0", FailRateLimit: 0.2},
		[]*Batch{fleetBatch(vins, 0, 4)}, start)
	if d := r.OnDeviceReport("veh-999", true); d != DecisionHold {
		t.Errorf("未知 VIN 应 hold, got %v", d)
	}
}
