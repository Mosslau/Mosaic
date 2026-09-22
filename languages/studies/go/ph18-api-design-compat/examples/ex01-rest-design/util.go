// 来源：ph18-api-design-compat examples/ex01-rest-design/util.go
// 一句话说明：排序与 JSON 读写的小工具，供 handler 复用（主文档 3.1）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18101
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"net/http"
	"sort"
)

func sortByID(devices []Device) {
	sort.Slice(devices, func(i, j int) bool { return devices[i].ID < devices[j].ID })
}

// writeJSON 写 JSON 响应；encoder.SetIndent 让 curl 冒烟时人类可读（生产通常不缩进省带宽）。
func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	_ = enc.Encode(v)
}

// writeError 写统一错误结构 {code,message}（本示例最简版；完整演进见 ex02）。
func writeError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, errBody{Code: code, Message: msg})
}

// decodeBody 解码请求体到 v，JSON 坏掉时回 400。
func decodeBody(w http.ResponseWriter, r *http.Request, v any) bool {
	if err := json.NewDecoder(r.Body).Decode(v); err != nil {
		writeError(w, http.StatusBadRequest, "BAD_REQUEST", "invalid json body: "+err.Error())
		return false
	}
	return true
}
