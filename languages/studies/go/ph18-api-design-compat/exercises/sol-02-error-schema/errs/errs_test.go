// 来源：ph18-api-design-compat exercises/sol-02-error-schema/errs/errs_test.go
// 一句话说明：错误结构稳定性测试（外部包视角：只通过导出 API 断言）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...；静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package errs_test

import (
	"encoding/json"
	"errors"
	"testing"

	"tenetlang/go/ph18-api-design-compat/exercises/sol-02-error-schema/errs"
)

// legacyClientError 模拟 v1 客户端：结构体只有 code/message。
type legacyClientError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

// TestLegacyClientReadsNewStructure：老客户端解析带 requestId/details 的新响应不炸。
func TestLegacyClientReadsNewStructure(t *testing.T) {
	e := errs.New(errs.CodeNotFound, "task 42 not found", nil).
		WithRequestID("req-1").
		WithDetails(errs.Detail{Field: "id", Issue: "no such task"})
	payload, err := e.EncodeJSON()
	if err != nil {
		t.Fatal(err)
	}
	var old legacyClientError
	if err := json.Unmarshal(payload, &old); err != nil {
		t.Fatalf("legacy client cannot parse new payload: %v", err)
	}
	if old.Code != "TASK_NOT_FOUND" || old.Message != "task 42 not found" {
		t.Fatalf("legacy client read %q/%q", old.Code, old.Message)
	}
}

// TestNewClientToleratesOldStructure：新客户端解析老响应（无可选字段）不炸。
func TestNewClientToleratesOldStructure(t *testing.T) {
	e := errs.New(errs.CodeNotFound, "task 42 not found", nil) // 无 requestId/details
	payload, err := e.EncodeJSON()
	if err != nil {
		t.Fatal(err)
	}
	var fresh errs.Error
	if err := json.Unmarshal(payload, &fresh); err != nil {
		t.Fatalf("new client cannot parse legacy payload: %v", err)
	}
	if fresh.RequestID != "" || len(fresh.Details) != 0 {
		t.Fatalf("optional fields must be zero on legacy payload")
	}
}

// TestPublishedCodesNeverRemoved：v1.0/v1.2/v2.0 各代发布的 code 全量保留。
// 本测试就是"删码是破坏性变更"的保险丝——任何人从 registry 删除历史 code，这里必红。
func TestPublishedCodesNeverRemoved(t *testing.T) {
	history := []errs.Code{
		errs.CodeValidation, // v1.0
		errs.CodeNotFound,   // v1.0
		errs.CodeInternal,   // v1.0
		errs.CodeConflict,   // v1.2
		errs.CodeRateLimit,  // v2.0
	}
	registered := map[errs.Code]bool{}
	for _, c := range errs.Codes() {
		registered[c] = true
	}
	for _, c := range history {
		if !registered[c] {
			t.Fatalf("published code %q was removed from registry", c)
		}
	}
}

// TestErrorChain：包装与 errors.Is/As 语义可用（golang-patterns 纪律）。
func TestErrorChain(t *testing.T) {
	root := errors.New("db connection reset")
	apiErr := errs.New(errs.CodeInternal, "store unavailable", root)
	if !errors.Is(apiErr, root) {
		t.Fatal("errors.Is must reach wrapped root")
	}
	var target *errs.Error
	if !errors.As(apiErr, &target) || target.Code != errs.CodeInternal {
		t.Fatal("errors.As must recover *errs.Error")
	}
}

// TestCoreFieldsAlwaysPresent：code/message 序列化后永远存在。
func TestCoreFieldsAlwaysPresent(t *testing.T) {
	e := errs.New(errs.CodeValidation, "bad input", nil)
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
			t.Fatalf("core field %q missing in %s", core, b)
		}
	}
}
