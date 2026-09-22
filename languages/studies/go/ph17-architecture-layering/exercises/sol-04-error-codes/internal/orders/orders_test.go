// 来源：ph17-architecture-layering exercises/sol-04-error-codes/internal/orders/orders_test.go
// 一句话说明：业务规则单测：根因链可 errors.Is 穿透、Code 可 errors.As 取回。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package orders

import (
	"errors"
	"testing"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-04-error-codes/internal/errs"
)

func TestPayUnknownOrderKeepsRootCause(t *testing.T) {
	s := New()
	err := s.Pay("nope")
	var de *errs.Error
	if !errors.As(err, &de) {
		t.Fatalf("want *errs.Error, got %T", err)
	}
	if de.Code != errs.CodeNotFound {
		t.Fatalf("code = %q, want %q", de.Code, errs.CodeNotFound)
	}
	if !errors.Is(err, errNoOrder) {
		t.Fatal("errors.Is(err, errNoOrder) = false, want true（根因必须可追溯）")
	}
}

func TestPayTwiceConflicts(t *testing.T) {
	s := New()
	s.m["o1"] = statusCreated
	if err := s.Pay("o1"); err != nil {
		t.Fatalf("first pay: %v", err)
	}
	err := s.Pay("o1")
	var de *errs.Error
	if !errors.As(err, &de) {
		t.Fatalf("want *errs.Error, got %T", err)
	}
	if de.Code != errs.CodeConflict {
		t.Fatalf("code = %q, want %q", de.Code, errs.CodeConflict)
	}
}

func TestCancelPaidOrderConflicts(t *testing.T) {
	s := New()
	s.m["o2"] = statusPaid
	err := s.Cancel("o2")
	var de *errs.Error
	if !errors.As(err, &de) {
		t.Fatalf("want *errs.Error, got %T", err)
	}
	if de.Code != errs.CodeConflict {
		t.Fatalf("code = %q, want %q", de.Code, errs.CodeConflict)
	}
}

func TestCancelCreatedOrderOK(t *testing.T) {
	s := New()
	s.m["o3"] = statusCreated
	if err := s.Cancel("o3"); err != nil {
		t.Fatalf("cancel created order: %v", err)
	}
	if s.m["o3"] != statusCancelled {
		t.Fatalf("status = %q, want cancelled", s.m["o3"])
	}
}
