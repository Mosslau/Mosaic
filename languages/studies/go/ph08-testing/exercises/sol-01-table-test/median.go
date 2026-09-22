// 来源：ph08-testing 练习 1 参考实现 —— 给业务函数写表格驱动测试
// 一句话说明：Median 中位数函数（不修改入参），配套表驱动测试。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v -cover ./...
//
// 验证状态：已验证（go1.25.6，覆盖率 100%）
//
// 说明：本文件为纯测试目标，刻意不提供 main 入口——这样 go test -cover
// 统计的就是 Median 的全部语句，覆盖率可直接达到 100%（若保留 main，演示
// 入口会拖低整体百分比，详见 ph08 主文档示例 5 的覆盖率讨论）。
package main

import (
	"fmt"
	"sort"
)

// Median 返回中位数：偶数个元素取中间两数平均；不修改入参切片
func Median(values []float64) (float64, error) {
	if len(values) == 0 {
		return 0, fmt.Errorf("values 不能为空")
	}
	sorted := make([]float64, len(values)) // 拷贝后排序，保护入参
	copy(sorted, values)
	sort.Float64s(sorted)

	mid := len(sorted) / 2
	if len(sorted)%2 == 1 {
		return sorted[mid], nil
	}
	return (sorted[mid-1] + sorted[mid]) / 2, nil
}
