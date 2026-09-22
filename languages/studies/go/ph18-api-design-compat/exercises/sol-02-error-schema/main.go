// 来源：ph18-api-design-compat exercises/sol-02-error-schema/main.go
// 一句话说明：打印"错误码文档表 + HTTP 映射"——练习 2 交付物里文档部分的最小落地。
// 这份表（doc + mapping）是写 OpenAPI 文档与客户端 SDK 字典时逐行照抄的来源。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .（本模块；跨包代码在 errs/ 与 httperr/ 下）
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"fmt"
	"net/http"

	"tenetlang/go/ph18-api-design-compat/exercises/sol-02-error-schema/errs"
	"tenetlang/go/ph18-api-design-compat/exercises/sol-02-error-schema/httperr"
)

func main() {
	fmt.Println("错误码文档表（注册表即文档）")
	fmt.Printf("%-18s %-6s %s\n", "code", "since", "语义 / 调用方可做什么")
	for _, m := range errs.Doc() {
		fmt.Printf("%-18s %-6s %s\n", m.Code, m.Since, m.Meaning)
	}
	fmt.Println()
	fmt.Println("错误码 → HTTP 状态码映射（httperr 集中登记）")
	for _, c := range errs.Codes() {
		status, _ := httperr.Map(errs.New(c, "example", nil))
		fmt.Printf("%-18s %d %s\n", c, status, http.StatusText(status))
	}
}
