// 来源：ph17-architecture-layering exercises/sol-04-error-codes/internal/httperr/httperr_test.go
// 一句话说明：映射函数单测——Code 查表、未知错误兜底 500、消息不透出内部细节。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package httperr

import (
	"errors"
	"net/http"
	"testing"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-04-error-codes/internal/errs"
)

func TestMapKnownCodes(t *testing.T) {
	cases := []struct {
		name string
		err  error
		code errs.Code
		want int
	}{
		{"not found", errs.New(errs.CodeNotFound, "订单不存在"), errs.CodeNotFound, http.StatusNotFound},
		{"conflict", errs.New(errs.CodeConflict, "已支付"), errs.CodeConflict, http.StatusConflict},
		{"bad request", errs.New(errs.CodeBadRequest, "参数错"), errs.CodeBadRequest, http.StatusBadRequest},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			status, body := Map(tc.err)
			if status != tc.want {
				t.Fatalf("status = %d, want %d", status, tc.want)
			}
			if body.Code != tc.code || body.Message == "" {
				t.Fatalf("body = %+v, want code %q with message", body, tc.code)
			}
		})
	}
}

func TestMapUnknownErrorFallsBackTo500(t *testing.T) {
	boom := errors.New("unexpected: nil pointer dereference")
	status, body := Map(boom)
	if status != http.StatusInternalServerError {
		t.Fatalf("status = %d, want 500", status)
	}
	if body.Code != errs.CodeInternal {
		t.Fatalf("code = %q, want INTERNAL", body.Code)
	}
	if body.Message == boom.Error() {
		t.Fatal("内部错误细节不得透出到响应体（应只记日志）")
	}
}

func TestMapWrappedErrorStillMaps(t *testing.T) {
	// 场景：service 返回包装链 *errs.Error → 普通 fmt 包装——As 应能穿透
	wrapped := errors.New("transport wrap")
	inner := errs.New(errs.CodeConflict, "已支付")
	joined := errors.Join(inner, wrapped)
	status, body := Map(joined)
	if status != http.StatusConflict || body.Code != errs.CodeConflict {
		t.Fatalf("got status=%d code=%q, want 409/ORDER_STATE_CONFLICT", status, body.Code)
	}
}
