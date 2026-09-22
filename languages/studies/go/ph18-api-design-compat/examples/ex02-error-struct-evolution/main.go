// 来源：ph18-api-design-compat examples/ex02-error-struct-evolution/main.go
// 一句话说明：演进时间线演示。分别以 v1（老服务端）与 v2（新服务端）的视角
// 序列化同一个业务错误，对比"加了可选字段"之后 v1 客户端是否仍能读懂响应
// （主文档 3.4）。真正的兼容性断言见 errs_test.go。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import "fmt"

func main() {
	// v1 形态：错误只带 code+message（2019 年对外发布时的结构）。
	v1 := New(CodeNotFound, "device not found", fmt.Errorf("no row"))
	b1, _ := v1.EncodeJSON()

	// v2 形态：两年后加上 requestId 与 details，业务错误码与 message 一字未动。
	v2 := New(CodeNotFound, "device not found", fmt.Errorf("no row")).
		WithRequestID("req-abc123").
		WithDetails(Detail{Field: "id", Issue: "no such device id"})
	b2, _ := v2.EncodeJSON()

	fmt.Println("v1 序列化：", string(b1))
	fmt.Println("v2 序列化：", string(b2))
	fmt.Println()
	fmt.Println("关键观察：code/message 完全不变；新字段是追加的、可选的。")
	fmt.Println("老客户端（只认识 code+message）解析 v2 响应时按未知字段忽略——errs_test.go 用测试钉死这条兼容性。")
}
