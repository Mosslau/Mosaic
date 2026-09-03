// 来源：ph18-api-design-compat project/doc.go
// 一句话说明：本 module 根包的存在意义——让契约测试（contract_test.go）有个
// package 可以放。契约测试是"设备管理 API 规范"项目的心脏：它把 internal/spec/openapi.json
// 这份权威规范与实现逐条对账，任何漂移都在 CI 失败（主文档 3.7 的完整落地）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package project
