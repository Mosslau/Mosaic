// 来源：ph21-data-ingest-gateway exercises/sol-03-rollout-upgrade/sol03_test.go
// 一句话说明：练习 3 验收测试——台账录入/查询/升级更新、全批成功 advance 到
// complete、失败率越限 rollback 且回滚目标=升级前版本、终态后报告无效、
// 批内失败但未越限仍可推进、未知 SourceID 忽略、非法 failLimit 拒绝创建。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package main

import "testing"

func mkSourceIDs(n int) []string {
	out := make([]string, n)
	for i := range out {
		out[i] = "veh-" + string(rune('0'+i/10)) + string(rune('0'+i%10))
	}
	return out
}

func mkFleetN(sourceIDs []string) *Registry {
	f := NewRegistry()
	for _, v := range sourceIDs {
		f.Register(Agent{SourceID: v, Version: "v1.0"})
	}
	return f
}

func threeGroups(sourceIDs []string) []*Group {
	return []*Group{
		{Name: "b1", SourceIDs: sortedSourceIDs(sourceIDs[0:3])},
		{Name: "b2", SourceIDs: sortedSourceIDs(sourceIDs[3:6])},
		{Name: "b3", SourceIDs: sortedSourceIDs(sourceIDs[6:9])},
	}
}

func TestFleetLedger(t *testing.T) {
	f := NewRegistry()
	f.Register(Agent{SourceID: "src-001", Version: "v1.0"})
	if v, ok := f.VersionOf("src-001"); !ok || v != "v1.0" {
		t.Fatalf("台账应 v1.0, got %q ok=%v", v, ok)
	}
	f.Upgrade("src-001", "v2.0")
	if v, _ := f.VersionOf("src-001"); v != "v2.0" {
		t.Errorf("升级后应 v2.0, got %s", v)
	}
}

func TestFullSuccessAdvancesToComplete(t *testing.T) {
	sourceIDs := mkSourceIDs(9)
	f := mkFleetN(sourceIDs)
	r, _ := NewRollout("v2.0", 0.2, threeGroups(sourceIDs), f)
	trolloutl, reports := 0, 0
	for _, g := range r.groups {
		trolloutl += len(g.SourceIDs)
	}
	for _, g := range r.groups {
		for _, sourceID := range g.SourceIDs {
			reports++
			act := r.Report(sourceID, true)
			if reports == trolloutl { // 整场最后一台上报 → complete
				if act != Complete {
					t.Fatalf("末台上报应 Complete, got %v", act)
				}
			} else if act == Complete {
				t.Fatal("未到最后一台不应 Complete")
			}
		}
	}
	if r.Status() != "done" {
		t.Errorf("终态应 done, got %s", r.Status())
	}
}

func TestRollbackOnHighFailure(t *testing.T) {
	sourceIDs := mkSourceIDs(9)
	f := mkFleetN(sourceIDs)
	r, _ := NewRollout("v2.0", 0.2, threeGroups(sourceIDs), f)
	for _, sourceID := range r.groups[0].SourceIDs {
		r.Report(sourceID, true)
	}
	// 第二批第 1 台成功、第 2 台失败 → 1/3=33% > 20% 越限 → rollback。
	r.Report(r.groups[1].SourceIDs[0], true)
	if act := r.Report(r.groups[1].SourceIDs[1], false); act != Rollback {
		t.Fatalf("越限应 Rollback, got %v", act)
	}
	if r.Status() != "rolledback" {
		t.Errorf("状态应 rolledback, got %s", r.Status())
	}
	if got := r.RollbackTarget(r.groups[1].SourceIDs[1]); got != "v1.0" {
		t.Errorf("回滚目标应 v1.0, got %s", got)
	}
	// 终态后报告无效。
	if act := r.Report(r.groups[1].SourceIDs[2], true); act != Hold {
		t.Errorf("终态后应 Hold, got %v", act)
	}
}

func TestFailureBelowLimitStillAdvances(t *testing.T) {
	sourceIDs := mkSourceIDs(9)
	f := mkFleetN(sourceIDs)
	// failLimit 0.5：批内 1/3 失败 = 33% 未越限 → 全部确认后推进。
	r, _ := NewRollout("v2.0", 0.5, threeGroups(sourceIDs), f)
	acts := []Action{}
	first := r.groups[0].SourceIDs[0]
	for _, sourceID := range r.groups[0].SourceIDs {
		acts = append(acts, r.Report(sourceID, sourceID != first)) // 第 1 台失败，其余成功
	}
	if acts[len(acts)-1] != Advance {
		t.Errorf("未越限应推进, got %v", acts)
	}
}

func TestUnknownSourceIDIgnoredAndInvalidLimit(t *testing.T) {
	sourceIDs := mkSourceIDs(9)
	f := mkFleetN(sourceIDs)
	r, _ := NewRollout("v2.0", 0.2, threeGroups(sourceIDs), f)
	if act := r.Report("veh-999", false); act != Hold {
		t.Errorf("未知 SourceID 应 Hold, got %v", act)
	}
	if _, err := NewRollout("v2.0", 1.5, threeGroups(sourceIDs), f); err == nil {
		t.Error("非法 failLimit 应拒绝创建")
	}
}
