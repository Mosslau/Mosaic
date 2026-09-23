// 来源：ph18-api-design-compat examples/ex03-pagination-filter/data.go
// 一句话说明：数据集生成与解析。列表接口的第一步是"把数据做成可翻页的稳定序列"：
// 分页建立在"确定性顺序"之上，顺序不稳定则翻页会重复/遗漏（主文档 3.5）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18103（然后 curl 冒烟，示例见 examples/README.md）
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import "fmt"

// Device 列表项。list 接口的每个字段都是对外契约的一部分——字段只增不删（主文档 3.6）。
type Device struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Status string `json:"status"` // online | offline | maintenance
}

// makeDataset 生成 n 台确定性数据集（固定种子），保证测试与演示可复现。
// 名字故意用固定前缀 + 序号，便于演示按名字模糊过滤。
func makeDataset(n int) []Device {
	out := make([]Device, 0, n)
	for i := 0; i < n; i++ {
		status := "online"
		switch i % 3 {
		case 1:
			status = "offline"
		case 2:
			status = "maintenance"
		}
		out = append(out, Device{
			ID:     fmt.Sprintf("dev-%03d", i),
			Name:   fmt.Sprintf("设备组A-%d号设备", i),
			Status: status,
		})
	}
	return out
}
