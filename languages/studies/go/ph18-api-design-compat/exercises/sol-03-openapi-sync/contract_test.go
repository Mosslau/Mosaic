// 来源：ph18-api-design-compat exercises/sol-03-openapi-sync/contract_test.go
// 一句话说明：文档 ↔ 实现同步的契约测试（练习 3 验收核心）。断言五条：
// ① 路由双向对齐；② 每个 operation 都有 summary（文档要能当目录读）；
// ③ 每个 2xx 响应都带 example（roadmap 验收"能给 API 写示例"）；
// ④ 统一错误结构在文档层面钉死（Error required code/message，非 2xx 全引用共享组件）；
// ⑤ query 参数声明集合与实现解析集合一致。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...（本文件为主）；静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"testing"
)

func TestRoutesMatchSpec(t *testing.T) {
	spec, err := LoadSpec()
	if err != nil {
		t.Fatal(err)
	}
	specRoutes := map[string]bool{}
	for path := range spec.Paths {
		if spec.Paths[path].Get != nil {
			specRoutes["GET "+path] = true
		}
	}
	implRoutes := map[string]bool{}
	for _, rt := range Routes() {
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

func TestEveryOperationHasSummaryAndExample(t *testing.T) {
	spec, err := LoadSpec()
	if err != nil {
		t.Fatal(err)
	}
	for path, p := range spec.Paths {
		op := p.Get
		if op == nil {
			t.Fatalf("path %s has no get", path)
		}
		if op.Summary == "" {
			t.Fatalf("operation GET %s lacks summary — 文档要能当目录读", path)
		}
		for code, resp := range op.Responses {
			resp = spec.Resolve(resp)
			if resp == nil {
				t.Fatalf("GET %s %s unresolvable response", path, code)
			}
			if code[0] == '2' { // 2xx 必须带 example（调用方可照抄联调）
				hasExample := false
				for _, media := range resp.Content {
					if media.Example != nil {
						hasExample = true
					}
				}
				if !hasExample {
					t.Fatalf("GET %s 200 lacks example", path)
				}
			}
		}
	}
}

func TestErrorStructureIsStableInDoc(t *testing.T) {
	spec, err := LoadSpec()
	if err != nil {
		t.Fatal(err)
	}
	errSchema := spec.Components.Schemas["Error"]
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
	// 非 2xx 响应必须全部指向共享 ErrorResponse 组件（不允许自造错误体）
	for _, p := range spec.Paths {
		for code, resp := range p.Get.Responses {
			if code[0] != '2' && resp.Ref != "#/components/responses/ErrorResponse" {
				t.Fatalf("error response %s must $ref ErrorResponse, got %q", code, resp.Ref)
			}
		}
	}
}

func TestQueryParamsAlign(t *testing.T) {
	spec, err := LoadSpec()
	if err != nil {
		t.Fatal(err)
	}
	declared := spec.Paths["/api/v1/devices"].Get.QueryParameters()
	implemented := QueryKeys()
	for k := range declared {
		if !implemented[k] {
			t.Fatalf("spec declares query param %q but implementation does not parse it", k)
		}
	}
	for k := range implemented {
		if !declared[k] {
			t.Fatalf("implementation parses query param %q but spec does not declare it", k)
		}
	}
}
