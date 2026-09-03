// 来源：ph18-api-design-compat examples/ex05-openapi-sync/spec.go
// 一句话说明：OpenAPI 文档的最小解析器（主文档 3.7）。真实工程用 oapi-codegen /
// swaggo 等工具链消费 YAML/JSON 规范；本示例为保持"零第三方"，用标准库 encoding/json
// 解析一个 OpenAPI 3.0 文档，只提取契约测试需要的最小信息集：
// paths → 每个 path 的 get/post 方法 → 各状态码的响应 schema 引用 → components.schemas。
// 教学要点：OpenAPI 本质上只是一份"JSON 可表达的文档"，schema 结构可以用 struct 描述。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18105
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
	Title   string `json:"title"`
	Version string `json:"version"`
}

// Path 一个路径下的方法集合（本示例只关心 get/post/delete；OpenAPI 还有 put/patch 等）。
type Path struct {
	Get    *Operation `json:"get"`
	Post   *Operation `json:"post"`
	Delete *Operation `json:"delete"`
}

// Operation 一个方法操作。
type Operation struct {
	Summary   string               `json:"summary"`
	Responses map[string]*Response `json:"responses"`
}

// Response 一个状态码的响应描述。可能是一个内联响应，也可能是对
// components/responses 的 $ref 引用（OpenAPI 允许把重复响应块抽成共享组件）。
type Response struct {
	Description string                `json:"description"`
	Content     map[string]*MediaType `json:"content"`
	Ref         string                `json:"$ref"`
}

// MediaType 媒体类型下的 schema 引用。
type MediaType struct {
	Schema *SchemaRef `json:"schema"`
}

// SchemaRef 对 schema 的 $ref 引用或内联 schema。
type SchemaRef struct {
	Ref    string  `json:"$ref"`
	Schema *Schema `json:"-"`
}

// Components 文档的共享组件（schemas 与 responses）。
type Components struct {
	Schemas   map[string]*Schema   `json:"schemas"`
	Responses map[string]*Response `json:"responses"`
}

// Schema JSON Schema 子集：type/required/properties/items（契约测试够用）。
type Schema struct {
	Type       string             `json:"type"`
	Required   []string           `json:"required"`
	Properties map[string]*Schema `json:"properties"`
	Items      *SchemaRef         `json:"items"`
}

// LoadSpec 从嵌入的 api/openapi.json 解析规范。
func LoadSpec() (*Spec, error) {
	var s Spec
	if err := json.Unmarshal(specSource, &s); err != nil {
		return nil, fmt.Errorf("parse openapi spec: %w", err)
	}
	return &s, nil
}

// SchemaOf 按 $ref 解析指向 components.schemas 的 schema；解析失败返回 nil。
// 例如 "#/components/schemas/Device" → components.schemas["Device"]。
func (s *Spec) SchemaOf(ref string) *Schema {
	name := strings.TrimPrefix(ref, "#/components/schemas/")
	if name == ref {
		return nil
	}
	return s.Components.Schemas[name]
}

// Methods 返回某个 path 上声明了的方法集合（本示例只有 get/post/delete）。
func (p *Path) Methods() []string {
	var out []string
	if p.Get != nil {
		out = append(out, "GET")
	}
	if p.Post != nil {
		out = append(out, "POST")
	}
	if p.Delete != nil {
		out = append(out, "DELETE")
	}
	return out
}

// Resolve 解析响应上的 $ref（指向 components/responses）；无引用时原样返回。
func (s *Spec) Resolve(resp *Response) *Response {
	if resp.Ref == "" {
		return resp
	}
	name := strings.TrimPrefix(resp.Ref, "#/components/responses/")
	return s.Components.Responses[name]
}
