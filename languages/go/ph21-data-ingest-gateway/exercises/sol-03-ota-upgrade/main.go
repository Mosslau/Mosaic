// 来源：ph21-data-ingest-gateway exercises/sol-03-ota-upgrade/main.go
// 一句话说明：练习 3 演示——车队 9 台 v1.0，目标 v2.0 分 3 批；故事 A 全批成功走到
// complete 且台账更新为 v2.0；故事 B 第二批失败越限 → rollback，打印回滚目标。
// 用法：go run .
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，输出见下方预期）
package main

import "fmt"

func mkFleet(n int) *Fleet {
	f := NewFleet()
	for i := 1; i <= n; i++ {
		f.Register(Device{Vin: fmt.Sprintf("veh-%03d", i), Version: "v1.0"})
	}
	return f
}

func main() {
	const target = "v2.0"
	vins := []string{"veh-001", "veh-002", "veh-003", "veh-004", "veh-005", "veh-006", "veh-007", "veh-008", "veh-009"}

	// 故事 A。
	fleetA := mkFleet(9)
	groups := []*Group{{Name: "batch-1", VINs: sortedVINs(vins[0:3])},
		{Name: "batch-2", VINs: sortedVINs(vins[3:6])},
		{Name: "batch-3", VINs: sortedVINs(vins[6:9])}}
	ra, _ := NewRollout(target, 0.2, groups, fleetA)
	fmt.Println("== 故事 A：全批成功 ==")
	for _, g := range groups {
		for _, vin := range g.VINs {
			d := ra.Report(vin, true)
			if d == Advance || d == Complete {
				fleetA.Upgrade(vin, target) // 升级成功 → 更新台账
			}
			fmt.Printf("  %s → %s\n", vin, d)
		}
	}
	fmt.Printf("A 终态=%s；veh-009 台账=%s\n", ra.Status(), mustVersion(fleetA, "veh-009"))

	// 故事 B：第二批 1/3 失败 > 20% → rollback。
	fleetB := mkFleet(9)
	rb, _ := NewRollout(target, 0.2, groups, fleetB)
	fmt.Println("== 故事 B：第二批失败越限 ==")
	for _, vin := range groups[0].VINs {
		fmt.Printf("  %s → %s\n", vin, rb.Report(vin, true))
	}
	for i, vin := range groups[1].VINs {
		d := rb.Report(vin, i != 1) // 第 2 台失败
		fmt.Printf("  %s → %s\n", vin, d)
		if d == Rollback {
			fmt.Printf("  → 回滚目标 %s = %s\n", vin, rb.RollbackTarget(vin))
		}
	}
	fmt.Printf("B 终态=%s\n", rb.Status())
	fmt.Println("== sol-03 演示完成 ==")
}

func mustVersion(f *Fleet, vin string) string {
	v, ok := f.VersionOf(vin)
	if !ok {
		return "?"
	}
	return v
}
