// 来源：ph18-api-design-compat project/internal/spec/spec.go
// 一句话说明：OpenAPI JSON 文档的最小解析器（project 版本）。本包目录下的
// openapi.json 是设备管理 API 的"唯一权威规范"——它被 //go:embed 打包进包内，
// 契约测试只能通过它来对账，避免"规范人读一份、测试走另一份"的漂移。
// 相比 examples/ex05 与 sol-03 的解析器，本版本额外暴露"每个 operation 的方法 +
// path"与"schema 引用解析"，供根目录 contract_test.go 做双向对账与字段演进断言。
// 真实工程会用 oapi-codegen / swaggo 等工具链；这里零第三方手写，只为演示契约思想。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package spec

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"sort"
	"strings"
)

//go:embed openapi.json
var Source []byte

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

// Path 一个路径的方法集合。
type Path struct {
	Get    *Operation `json:"get"`
	Post   *Operation `json:"post"`
	Delete *Operation `json:"delete"`
}

// Operation 一个方法操作。
type Operation struct {
	Summary    string               `json:"summary"`
	Parameters []*Parameter         `json:"parameters"`
	Responses  map[string]*Response `json:"responses"`
}

// Parameter query/path 参数声明。
type Parameter struct {
	Name     string  `json:"name"`
	In       string  `json:"in"`
	Required bool    `json:"required"`
	Schema   *Schema `json:"schema"`
}

// Response 状态码响应（可能是 $ref）。
type Response struct {
	Description string                `json:"description"`
	Content     map[string]*MediaType `json:"content"`
	Ref         string                `json:"$ref"`
}

// MediaType 媒体类型下的 schema 与 example。
type MediaType struct {
	Schema  *SchemaRef      `json:"schema"`
	Example json.RawMessage `json:"example"`
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

// Load 解析嵌入的规范。返回的 Spec 只读使用。
func Load() (*Spec, error) {
	var s Spec
	if err := json.Unmarshal(Source, &s); err != nil {
		return nil, fmt.Errorf("parse openapi spec: %w", err)
	}
	return &s, nil
}

// Resolve 解开响应上的 $ref（指向 components/responses）。
func (s *Spec) Resolve(resp *Response) *Response {
	if resp.Ref == "" {
		return resp
	}
	return s.Components.Responses[strings.TrimPrefix(resp.Ref, "#/components/responses/")]
}

// SchemaOf 按 $ref 解析 components/schemas 下的 schema。
func (s *Spec) SchemaOf(ref string) *Schema {
	name := strings.TrimPrefix(ref, "#/components/schemas/")
	if name == ref {
		return nil
	}
	return s.Components.Schemas[name]
}

// Routes spec 声明的 (方法, 路径) 有序列表，供契约测试与实现 Routes() 对账。
func (s *Spec) Routes() []string {
	var out []string
	for path, p := range s.Paths {
		for _, m := range p.Methods() {
			out = append(out, m+" "+path)
		}
	}
	sort.Strings(out)
	return out
}

// Methods path 上声明的方法名（规范顺序 GET/POST/DELETE）。
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

// QueryParameterNames operation 声明的 query 参数名。
func (op *Operation) QueryParameterNames() map[string]bool {
	out := map[string]bool{}
	for _, p := range op.Parameters {
		if p.In == "query" {
			out[p.Name] = true
		}
	}
	return out
}
