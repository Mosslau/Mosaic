// 来源：ph18-api-design-compat examples/ex02-error-struct-evolution/errs_test.go
// 一句话说明：错误结构演进的兼容性测试。四组断言对应主文档 3.4 的四条演进纪律：
// ① 老客户端读 v2 响应不炸（未知字段忽略）；② 新客户端读老响应不炸（可选字段缺失容忍）；
// ③ code/message 核心字段永在；④ 已发布错误码注册表只增不删。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...（本文件为主）；静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"errors"
	"strings"
	"testing"
)

// legacyClientError 模拟 2019 年发布的 v1 客户端：结构体里根本没有 requestId/details 字段。
type legacyClientError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

// TestLegacyClientReadsV2Payload：向前兼容——老客户端解析 v2 响应。
// json 默认忽略未知字段，新增字段对老客户端透明；若老客户端开了
// DisallowUnknownFields 反而会炸——严格模式与向后兼容天然冲突（主文档 3.4）。
func TestLegacyClientReadsV2Payload(t *testing.T) {
	v2 := New(CodeNotFound, "device not found", nil).
		WithRequestID("req-abc123").
		WithDetails(Detail{Field: "id", Issue: "no such device id"})
	payload, err := v2.EncodeJSON()
	if err != nil {
		t.Fatal(err)
	}

	var old legacyClientError
	if err := json.Unmarshal(payload, &old); err != nil {
		t.Fatalf("v1 client failed to parse v2 payload: %v", err)
	}
	if old.Code != string(CodeNotFound) || old.Message != "device not found" {
		t.Fatalf("legacy client read code/message = %q/%q", old.Code, old.Message)
	}
}

// TestNewClientReadsOldServer：向后兼容——v2 客户端解析老服务端（无新字段）的响应。
// 可选字段缺失时给零值，客户端不得假定 requestId/details 必然存在。
func TestNewClientReadsOldServer(t *testing.T) {
	old := New(CodeNotFound, "device not found", nil) // 不带 requestId/details
	payload, err := old.EncodeJSON()
	if err != nil {
		t.Fatal(err)
	}

	var fresh Error
	if err := json.Unmarshal(payload, &fresh); err != nil {
		t.Fatalf("v2 client failed to parse v1 payload: %v", err)
	}
	if fresh.RequestID != "" || len(fresh.Details) != 0 {
		t.Fatalf("optional fields should be zero-valued, got requestId=%q details=%v", fresh.RequestID, fresh.Details)
	}
	if fresh.Code != CodeNotFound {
		t.Fatalf("code = %q, want DEVICE_NOT_FOUND", fresh.Code)
	}
}

// TestCoreFieldsAlwaysPresent：code/message 序列化后永远存在（不带 omitempty 的承诺）。
// 未来任何一次演进都不允许让这两个字段变成"有时没有"。
func TestCoreFieldsAlwaysPresent(t *testing.T) {
	cases := map[string]*Error{
		"minimal": New(CodeInternal, "boom", nil),
		"withReq": New(CodeInternal, "boom", nil).WithRequestID("r1"),
		"withDet": New(CodeInternal, "boom", nil).WithDetails(Detail{Field: "a", Issue: "b"}),
	}
	for name, e := range cases {
		b, err := e.EncodeJSON()
		if err != nil {
			t.Fatal(err)
		}
		var m map[string]json.RawMessage
		if err := json.Unmarshal(b, &m); err != nil {
			t.Fatal(err)
		}
		for _, core := range []string{"code", "message"} {
			if _, ok := m[core]; !ok {
				t.Fatalf("%s: core field %q missing in %s", name, core, b)
			}
		}
	}
}

// TestPublishedCodesNeverRemoved：已发布错误码只增不删。
// 删除某个历史 code 会让本测试失败——这是"删码 = 破坏性变更"的编译期+测试期双重保险。
func TestPublishedCodesNeverRemoved(t *testing.T) {
	// v1.0 时代就对外发布的 code：无论后面演进多少版都不许从注册表消失。
	history := []Code{CodeBadRequest, CodeNotFound, CodeInternal}

	registered := map[Code]bool{}
	for _, c := range publishedCodes() {
		registered[c] = true
	}
	for _, c := range history {
		if !registered[c] {
			t.Fatalf("published code %q was removed from registry — 删码是破坏性变更", c)
		}
	}
}

// TestCodeIsStableAcrossVersions：业务错误码是给机器读的稳定标识，message 是给
// 人读的说明。message 措辞可以优化，code 一改客户端的分支逻辑就失效。
func TestCodeIsStableAcrossVersions(t *testing.T) {
	v1msg := New(CodeNotFound, "device not found", nil)
	v2msg := New(CodeNotFound, "device 不存在", nil) // message 措辞本地化可改
	if v1msg.Code != v2msg.Code {
		t.Fatal("code must not drift between versions")
	}
	if v1msg.Message == v2msg.Message {
		t.Fatal("test premise broken: messages should differ for this case")
	}
}

// TestUnwrapKeepsRootCause：*Error 实现 Unwrap，errors.Is/As 能沿链追根因
// （golang-patterns 规范的 errors.Is/As 纪律，也是 service 层日志排查的前提）。
func TestUnwrapKeepsRootCause(t *testing.T) {
	root := errors.New("no row in table devices")
	apiErr := New(CodeNotFound, "device not found", root)
	if !errors.Is(apiErr, root) {
		t.Fatal("errors.Is must reach the wrapped root cause")
	}
	var target *Error
	if !errors.As(apiErr, &target) {
		t.Fatal("errors.As must recover *Error from the chain")
	}
	if target.Code != CodeNotFound {
		t.Fatalf("code = %q, want DEVICE_NOT_FOUND", target.Code)
	}
}

// TestMessageOfKnownError：确保 Error() 输出可用于日志定位（code 前缀可 grep）。
func TestMessageOfKnownError(t *testing.T) {
	e := New(CodeNotFound, "device not found", nil)
	if !strings.HasPrefix(e.Error(), "DEVICE_NOT_FOUND") {
		t.Fatalf("Error() = %q, want DEVICE_NOT_FOUND prefix", e.Error())
	}
}
