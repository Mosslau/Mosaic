// 来源：ph18-api-design-compat project/internal/apierr/apierr_test.go
// 一句话说明：错误码注册表与错误链测试（"错误码只增不删"承诺的测试化）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...；静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package apierr

import (
	"errors"
	"testing"
)

// TestPublishedCodesNeverRemoved：v1.0 发布的全部 code 必须仍在注册表。
// 从 registry 删除任何历史 code，本测试必红——删码会让老客户端把错误当未知处理。
func TestPublishedCodesNeverRemoved(t *testing.T) {
	v1Published := []Code{CodeBadRequest, CodeNotFound, CodeInternal}
	registered := map[Code]bool{}
	for _, c := range Codes() {
		registered[c] = true
	}
	for _, c := range v1Published {
		if !registered[c] {
			t.Fatalf("v1.0 published code %q removed from registry", c)
		}
	}
}

// TestErrorChain：errors.Is/As 可沿链追根因（golang-patterns 纪律）。
func TestErrorChain(t *testing.T) {
	root := errors.New("no row")
	apiErr := New(CodeNotFound, "device not found", root)
	if !errors.Is(apiErr, root) {
		t.Fatal("errors.Is must reach root")
	}
	var e *Error
	if !errors.As(apiErr, &e) || e.Code != CodeNotFound {
		t.Fatal("errors.As must recover *Error")
	}
}

// TestCodeStableSemantics：code 是稳定标识，不能随措辞优化而改。
func TestCodeStableSemantics(t *testing.T) {
	e1 := New(CodeNotFound, "device not found", nil)
	e2 := New(CodeNotFound, "device 不存在", nil)
	if e1.Code != e2.Code {
		t.Fatal("code must not drift with message wording")
	}
}
