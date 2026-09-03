// 来源：ph18-api-design-compat examples/ex05-openapi-sync/contract_test.go
// 一句话说明：文档与实现同步的契约测试（主文档 3.7 的核心演示）。三组断言：
// ① 路由双向对齐：spec.paths 声明的每一条，实现必须都有；实现挂载的每一条，
// spec 必须都有（漂移双向拦截）；② 错误结构稳定：Error schema 强制 code+message 必填；
// ③ 字段级一致：真实 GET 响应的 JSON 字段集合必须被 spec schema 的 properties 覆盖——
// 谁在代码里悄悄加了响应字段，谁就破坏了这个测试。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...（本文件为主）；静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestRoutesMatchSpec：spec.paths 与实现 Routes() 双向一一对应。
func TestRoutesMatchSpec(t *testing.T) {
	spec, err := LoadSpec()
	if err != nil {
		t.Fatal(err)
	}
	// spec 侧
	specRoutes := map[string]bool{}
	for path, p := range spec.Paths {
		for _, m := range p.Methods() {
			specRoutes[m+" "+path] = true
		}
	}
	// 实现侧
	implRoutes := map[string]bool{}
	for _, rt := range Routes() {
		implRoutes[rt.Method+" "+rt.Path] = true
	}
	for k := range specRoutes {
		if !implRoutes[k] {
			t.Fatalf("spec declares %s but implementation has no such route — 文档已声明、实现没跟上", k)
		}
	}
	for k := range implRoutes {
		if !specRoutes[k] {
			t.Fatalf("implementation serves %s but spec does not declare it — 实现已漂移出文档", k)
		}
	}
}

// TestErrorSchemaIsStable：统一错误结构的必填字段在文档层面钉死。
// code/message 一旦成为 required，任何演进都不许让它们变成"有时没有"。
func TestErrorSchemaIsStable(t *testing.T) {
	spec, err := LoadSpec()
	if err != nil {
		t.Fatal(err)
	}
	errSchema := spec.Components.Schemas["Error"]
	if errSchema == nil {
		t.Fatal("components.schemas.Error is missing from the spec")
	}
	required := map[string]bool{}
	for _, k := range errSchema.Required {
		required[k] = true
	}
	for _, core := range []string{"code", "message"} {
		if !required[core] {
			t.Fatalf("Error schema does not require %q — 核心字段必须 required", core)
		}
	}
}

// TestErrorResponsesReferenceSharedSchema：所有非 2xx 错误响应都指向同一个
// ErrorResponse 共享组件（内部 $ref Error schema）——"错误结构稳定"还意味着
// 全 API 只有一种错误形态，不允许某接口自造错误体。
func TestErrorResponsesReferenceSharedSchema(t *testing.T) {
	spec, err := LoadSpec()
	if err != nil {
		t.Fatal(err)
	}
	for path, p := range spec.Paths {
		for _, op := range []*Operation{p.Get, p.Post, p.Delete} {
			if op == nil {
				continue
			}
			for code, resp := range op.Responses {
				if code[0] != '2' { // 非 2xx 都算错误响应
					resp = spec.Resolve(resp) // 解开 $ref → components/responses
					if resp == nil {
						t.Fatalf("%s 的错误响应无法解析", path+" "+code)
					}
					for _, media := range resp.Content {
						if media.Schema == nil || media.Schema.Ref != "#/components/schemas/Error" {
							t.Fatalf("%s 非 2xx 响应必须引用 Error schema，实际: %v", path+" "+code, media.Schema)
						}
					}
				}
			}
		}
	}
}

// TestResponseFieldsStayWithinSpec：真实响应字段不越出 spec 的 properties——
// 实现响应字段与文档 schema 的字段级同步。测试取 DeviceList 首项与 Device schema 对照。
func TestResponseFieldsStayWithinSpec(t *testing.T) {
	spec, err := LoadSpec()
	if err != nil {
		t.Fatal(err)
	}
	schema := spec.SchemaOf("#/components/schemas/Device")
	if schema == nil {
		t.Fatal("Device schema unresolvable")
	}

	mux := http.NewServeMux()
	NewServer().Register(mux)
	ts := httptest.NewServer(mux)
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/v1/devices")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d", resp.StatusCode)
	}
	raw, _ := io.ReadAll(resp.Body)
	var items []map[string]any
	if err := json.Unmarshal(raw, &items); err != nil {
		t.Fatal(err)
	}
	if len(items) == 0 {
		t.Fatal("want non-empty device list")
	}
	for key := range items[0] {
		if schema.Properties[key] == nil {
			t.Fatalf("response field %q not declared in spec Device schema — 实现比文档多了字段", key)
		}
	}
}
