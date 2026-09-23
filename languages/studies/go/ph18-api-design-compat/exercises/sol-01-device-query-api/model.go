// 来源：ph18-api-design-compat exercises/sol-01-device-query-api（练习 1 参考实现）
// 一句话说明：设备查询 API 从零设计（roadmap §18 练习 1）。字段、端点、查询语义都
// 是"设计产物"——把设计约束写进注释，是对"API 文档应和实现同步"的最低要求：
// 每个 query 参数的取值范围、排序白名单、分页默认值都必须有唯一答案。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18201
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import "fmt"

// Device 设备查询的返回对象。
type Device struct {
	ID     string `json:"id"`
	Plate  string `json:"plate"`
	Status string `json:"status"` // online | offline | maintenance
}

// makeFleet 生成 57 辆确定性设备组（固定种子模式，测试可复现）。
func makeFleet() []Device {
	out := make([]Device, 0, 57)
	statusSeq := []string{"online", "offline", "maintenance", "online"}
	for i := 0; i < 57; i++ {
		out = append(out, Device{
			ID:     fmt.Sprintf("veh-%03d", i),
			Plate:  fmt.Sprintf("京A-%03d", i),
			Status: statusSeq[i%len(statusSeq)],
		})
	}
	return out
}
