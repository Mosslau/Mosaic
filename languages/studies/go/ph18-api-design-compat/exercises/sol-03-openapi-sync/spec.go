// 来源：ph18-api-design-compat exercises/sol-03-openapi-sync/spec.go
// 一句话说明：OpenAPI JSON 的最小解析器（与 examples/ex05 同构，追加对 query
// parameters 与 example 的支持）。练习 3 的契约测试在此基础上扩展了三条：
// 每个 operation 必须带 summary、2xx 响应必须带 example、query 参数声明集合
// 必须与实现解析的键集合一致（主文档 3.7）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18203
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"strings"
)

//go:embed api/openapi.json
var specSource []byte

// Spec OpenAPI 文档的最小可解析形态。
type Spec struct {
	OpenAPI    string           `json:"openapi"`
	Info       Info             `json:"info"`
	Paths      map[string]*Path `json:"paths"`
	Components Components       `json:"components"`
}

// Info 文档元信息。
type Info struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	Version     string `json:"version"`
}

// Path 一个路径的方法集合。
type Path struct {
	Get *Operation `json:"get"`
}

// Operation 一个方法操作。
type Operation struct {
	Summary    string               `json:"summary"`
	Parameters []*Parameter         `json:"parameters"`
	Responses  map[string]*Response `json:"responses"`
}

// Parameter 路径/查询参数声明。
type Parameter struct {
	Name     string  `json:"name"`
	In       string  `json:"in"`
	Required bool    `json:"required"`
	Schema   *Schema `json:"schema"`
}

// Response 一个状态码的响应。
type Response struct {
	Description string                `json:"description"`
	Content     map[string]*MediaType `json:"content"`
	Ref         string                `json:"$ref"`
}

// MediaType 媒体类型下的 schema 与示例。
type MediaType struct {
	Schema  *SchemaRef     `json:"schema"`
	Example map[string]any `json:"example"`
}

// SchemaRef $ref 引用。
type SchemaRef struct {
	Ref string `json:"$ref"`
}

// Components 共享组件。
type Components struct {
	Schemas   map[string]*Schema   `json:"schemas"`
	Responses map[string]*Response `json:"responses"`
}

// Schema JSON Schema 子集。
type Schema struct {
	Type       string             `json:"type"`
	Required   []string           `json:"required"`
	Properties map[string]*Schema `json:"properties"`
	Items      *SchemaRef         `json:"items"`
}

// LoadSpec 解析嵌入的规范。
func LoadSpec() (*Spec, error) {
	var s Spec
	if err := json.Unmarshal(specSource, &s); err != nil {
		return nil, fmt.Errorf("parse openapi spec: %w", err)
	}
	return &s, nil
}

// Resolve 解开响应上的 $ref。
func (s *Spec) Resolve(resp *Response) *Response {
	if resp.Ref == "" {
		return resp
	}
	name := strings.TrimPrefix(resp.Ref, "#/components/responses/")
	return s.Components.Responses[name]
}

// QueryParameters 返回 operation 里 in=query 的参数名集合。
func (op *Operation) QueryParameters() map[string]bool {
	out := map[string]bool{}
	for _, p := range op.Parameters {
		if p.In == "query" {
			out[p.Name] = true
		}
	}
	return out
}
