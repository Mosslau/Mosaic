// 来源：ph18-api-design-compat examples/ex01-rest-design/model.go
// 一句话说明：资源模型。Device 就是本示例的"资源"——REST 设计的第一步是
// 想清楚"资源是什么、用什么名词命名"，动词进 HTTP 方法而不是进 URL（主文档 3.1）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18101（然后 curl 冒烟，示例见 examples/README.md）
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

// Device 设备资源。字段名即对外 JSON 字段的语义：
// 资源结构的稳定性 = 字段只增不删、字段语义不漂移（主文档 3.6 展开）。
type Device struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Online bool   `json:"online"`
}

// createRequest 创建请求体：只声明创建时允许携带的入参。
// 注意它刻意没有 ID 字段——ID 由服务端生成，客户端指定 ID 属于"覆盖服务端职责"。
type createRequest struct {
	Name string `json:"name"`
}

// errBody 本示例沿用的统一错误结构 {code,message}：
// 与 roadmap §18 示例同构，错误结构的"稳定与演进"在 ex02 专门展开（主文档 3.4）。
type errBody struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}
