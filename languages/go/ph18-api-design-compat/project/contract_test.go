// 来源：ph18-api-design-compat project/contract_test.go
// 一句话说明：spec-first 契约测试（综合项目的心脏）。api/openapi.json 是唯一权威
// 规范，本文件把它与实现逐条对账：
// ① 路由双向对齐（spec.paths ⇔ devices.Routes()）；② 错误结构在文档层钉死
// （Error required code/message，全部错误响应引用共享组件）；③ v2 schema 是 v1 的
// 字段超集（v1 properties ⊆ v2 properties——字段演进方向被文档层面保证）；
// ④ 每个 2xx 响应带 example、每个 operation 带 summary；⑤ v1/v2 的 query 参数
// 声明与实现解析集合一致。任何一条被破坏，本文件就是第一个红起来的测试。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...（根目录，与 internal/ 测试一起跑）；静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package project

import (
	"testing"

	"tenetlang/go/ph18-api-design-compat/project/internal/devices"
	"tenetlang/go/ph18-api-design-compat/project/internal/spec"
)

// TestRoutesMatchSpec：文档与实现的路由双向一一对应。
func TestRoutesMatchSpec(t *testing.T) {
	s, err := spec.Load()
	if err != nil {
		t.Fatal(err)
	}
	specRoutes := map[string]bool{}
	for _, r := range s.Routes() {
		specRoutes[r] = true
	}
	implRoutes := map[string]bool{}
	for _, rt := range devices.Routes() {
		implRoutes[rt.Method+" "+rt.Path] = true
	}
	for k := range specRoutes {
		if !implRoutes[k] {
			t.Fatalf("spec declares %s but implementation lacks it", k)
		}
	}
	for k := range implRoutes {
		if !specRoutes[k] {
			t.Fatalf("implementation serves %s but spec does not declare it", k)
		}
	}
}

// TestErrorContractInSpec：错误结构稳定性在文档层钉死。
func TestErrorContractInSpec(t *testing.T) {
	s, err := spec.Load()
	if err != nil {
		t.Fatal(err)
	}
	errSchema := s.Components.Schemas["Error"]
	if errSchema == nil {
		t.Fatal("components.schemas.Error missing")
	}
	required := map[string]bool{}
	for _, k := range errSchema.Required {
		required[k] = true
	}
	for _, core := range []string{"code", "message"} {
		if !required[core] {
			t.Fatalf("Error schema must require %q", core)
		}
	}
	// 每个 path 的每个方法：非 2xx 响应必须引用共享 ErrorResponse 组件。
	for path, p := range s.Paths {
		for _, method := range p.Methods() {
			op := operationOf(p, method)
			if op == nil {
				continue
			}
			for code, resp := range op.Responses {
				if code[0] != '2' && resp.Ref != "#/components/responses/ErrorResponse" {
					t.Fatalf("%s %s error response must $ref ErrorResponse, got %q", method, path, resp.Ref)
				}
			}
		}
	}
}

// TestV2SchemaIsSupersetOfV1：v2 的 schema 必须包含 v1 的全部字段（且 required
// 不丢失）——"字段只增不删"在版本演进里的文档层保证。
func TestV2SchemaIsSupersetOfV1(t *testing.T) {
	s, err := spec.Load()
	if err != nil {
		t.Fatal(err)
	}
	v1 := s.Components.Schemas["DeviceV1"]
	v2 := s.Components.Schemas["DeviceV2"]
	if v1 == nil || v2 == nil {
		t.Fatal("DeviceV1/DeviceV2 schemas must exist")
	}
	for field := range v1.Properties {
		if v2.Properties[field] == nil {
			t.Fatalf("v2 schema dropped v1 field %q — v2 必须是 v1 的超集", field)
		}
	}
	// v1 的必填字段在 v2 里也必填（不能从 required 悄悄降级）
	v2Required := map[string]bool{}
	for _, f := range v2.Required {
		v2Required[f] = true
	}
	for _, f := range v1.Required {
		if !v2Required[f] {
			t.Fatalf("v2 schema no longer requires v1 field %q", f)
		}
	}
	if v2.Properties["model"] == nil || v2.Properties["lastSeen"] == nil {
		t.Fatal("v2 must add model/lastSeen fields")
	}
}

// TestEveryOperationDocumented：每个 operation 有 summary，2xx 响应有 example
// （roadmap 验收：能给 API 写示例和错误说明）。
func TestEveryOperationDocumented(t *testing.T) {
	s, err := spec.Load()
	if err != nil {
		t.Fatal(err)
	}
	for path, p := range s.Paths {
		for _, method := range p.Methods() {
			op := operationOf(p, method)
			if op == nil {
				t.Fatalf("%s %s has no operation object", method, path)
			}
			if op.Summary == "" {
				t.Fatalf("%s %s lacks summary", method, path)
			}
			for code, resp := range op.Responses {
				resp = s.Resolve(resp)
				if resp == nil {
					t.Fatalf("%s %s %s response unresolvable", method, path, code)
				}
				if code[0] == '2' && len(resp.Content) > 0 {
					// 有 body 的 2xx（如 200/201）必须带 example；204 无 body 豁免。
					hasExample := false
					for _, media := range resp.Content {
						if len(media.Example) > 0 {
							hasExample = true
						}
					}
					if !hasExample {
						t.Fatalf("%s %s %s lacks example", method, path, code)
					}
				}
			}
		}
	}
}

// TestQueryParamsAlign：v1/v2 列表端点的 query 参数声明与实现解析集合一致。
func TestQueryParamsAlign(t *testing.T) {
	s, err := spec.Load()
	if err != nil {
		t.Fatal(err)
	}
	for _, ver := range []string{"v1", "v2"} {
		op := s.Paths["/"+ver+"/devices"].Get
		declared := op.QueryParameterNames()
		implemented := devices.QueryKeys(ver)
		for k := range declared {
			if !implemented[k] {
				t.Fatalf("%s spec declares query param %q but implementation lacks it", ver, k)
			}
		}
		for k := range implemented {
			if !declared[k] {
				t.Fatalf("%s implementation parses %q but spec does not declare it", ver, k)
			}
		}
	}
}

func operationOf(p *spec.Path, method string) *spec.Operation {
	switch method {
	case "GET":
		return p.Get
	case "POST":
		return p.Post
	case "DELETE":
		return p.Delete
	}
	return nil
}
