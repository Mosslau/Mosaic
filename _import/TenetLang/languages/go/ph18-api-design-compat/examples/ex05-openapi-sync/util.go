// 来源：ph18-api-design-compat examples/ex05-openapi-sync/util.go
// 一句话说明：JSON 响应小工具。错误体 {code,message} 与 openapi.json 的 Error
// schema 保持一致——统一错误结构不是口头约定，而是文档里被 $ref 引用的共享 schema。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18105
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"net/http"
)

// errBody 与 openapi.json components/schemas/Error 一致：required code+message。
type errBody struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, errBody{Code: code, Message: msg})
}
