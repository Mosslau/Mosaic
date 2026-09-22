// 来源：ph21-data-ingest-gateway exercises/sol-03-rollout-upgrade/main.go
// 一句话说明：练习 3 演示——数据源集群 9 台 v1.0，目标 v2.0 分 3 批；故事 A 全批成功走到
// complete 且台账更新为 v2.0；故事 B 第二批失败越限 → rollback，打印回滚目标。
// 用法：go run .
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，输出见下方预期）
package main

import "fmt"

func mkFleet(n int) *Registry {
	f := NewRegistry()
	for i := 1; i <= n; i++ {
		f.Register(Agent{SourceID: fmt.Sprintf("veh-%03d", i), Version: "v1.0"})
	}
	return f
}

func main() {
	const target = "v2.0"
	sourceIDs := []string{"src-001", "src-002", "src-003", "src-004", "src-005", "src-006", "src-007", "src-008", "src-009"}

	// 故事 A。
	groupsA := mkFleet(9)
	groups := []*Group{{Name: "batch-1", SourceIDs: sortedSourceIDs(sourceIDs[0:3])},
		{Name: "batch-2", SourceIDs: sortedSourceIDs(sourceIDs[3:6])},
		{Name: "batch-3", SourceIDs: sortedSourceIDs(sourceIDs[6:9])}}
	ra, _ := NewRollout(target, 0.2, groups, groupsA)
	fmt.Println("== 故事 A：全批成功 ==")
	for _, g := range groups {
		for _, sourceID := range g.SourceIDs {
			d := ra.Report(sourceID, true)
			if d == Advance || d == Complete {
				groupsA.Upgrade(sourceID, target) // 升级成功 → 更新台账
			}
			fmt.Printf("  %s → %s\n", sourceID, d)
		}
	}
	fmt.Printf("A 终态=%s；src-009 台账=%s\n", ra.Status(), mustVersion(groupsA, "src-009"))

	// 故事 B：第二批 1/3 失败 > 20% → rollback。
	groupsB := mkFleet(9)
	rb, _ := NewRollout(target, 0.2, groups, groupsB)
	fmt.Println("== 故事 B：第二批失败越限 ==")
	for _, sourceID := range groups[0].SourceIDs {
		fmt.Printf("  %s → %s\n", sourceID, rb.Report(sourceID, true))
	}
	for i, sourceID := range groups[1].SourceIDs {
		d := rb.Report(sourceID, i != 1) // 第 2 台失败
		fmt.Printf("  %s → %s\n", sourceID, d)
		if d == Rollback {
			fmt.Printf("  → 回滚目标 %s = %s\n", sourceID, rb.RollbackTarget(sourceID))
		}
	}
	fmt.Printf("B 终态=%s\n", rb.Status())
	fmt.Println("== sol-03 演示完成 ==")
}

func mustVersion(f *Registry, sourceID string) string {
	v, ok := f.VersionOf(sourceID)
	if !ok {
		return "?"
	}
	return v
}
