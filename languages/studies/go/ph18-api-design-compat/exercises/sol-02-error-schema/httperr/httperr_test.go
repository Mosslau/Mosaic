// 来源：ph18-api-design-compat exercises/sol-02-error-schema/httperr/httperr_test.go
// 一句话说明：映射层纯函数测试。覆盖：每种 code 的状态码、未知错误兜底 500、
// 包装链可达（errors.As 穿透 fmt.Errorf 包装）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...；静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package httperr_test

import (
	"errors"
	"fmt"
	"net/http"
	"testing"

	"tenetlang/go/ph18-api-design-compat/exercises/sol-02-error-schema/errs"
	"tenetlang/go/ph18-api-design-compat/exercises/sol-02-error-schema/httperr"
)

func TestCodeToStatusMapping(t *testing.T) {
	cases := []struct {
		code   errs.Code
		status int
	}{
		{errs.CodeValidation, http.StatusBadRequest},
		{errs.CodeNotFound, http.StatusNotFound},
		{errs.CodeConflict, http.StatusConflict},
		{errs.CodeRateLimit, http.StatusTooManyRequests},
		{errs.CodeInternal, http.StatusInternalServerError},
	}
	for _, c := range cases {
		status, out := httperr.Map(errs.New(c.code, "x", nil))
		if status != c.status {
			t.Fatalf("code %s -> status %d, want %d", c.code, status, c.status)
		}
		if out.Code != c.code {
			t.Fatalf("code %s round-trip = %s", c.code, out.Code)
		}
	}
}

func TestUnknownErrorFallsBackTo500(t *testing.T) {
	status, out := httperr.Map(errors.New("random go error"))
	if status != http.StatusInternalServerError {
		t.Fatalf("unknown error status = %d, want 500", status)
	}
	if out.Code != errs.CodeInternal {
		t.Fatalf("unknown error code = %s, want INTERNAL", out.Code)
	}
}

func TestWrappedErrorStillMaps(t *testing.T) {
	root := errs.New(errs.CodeConflict, "cannot reopen finished task", nil)
	wrapped := fmt.Errorf("reopen task 7: %w", root) // 业务层包装后仍要映射对
	status, out := httperr.Map(wrapped)
	if status != http.StatusConflict || out.Code != errs.CodeConflict {
		t.Fatalf("wrapped conflict maps to %d/%s, want 409/TASK_CONFLICT", status, out.Code)
	}
}
