// 来源：ph17-architecture-layering examples/ex02-constructor-injection/notifier_test.go
// 一句话说明：注入的意义在测试里兑现——fakeSender 替掉真实渠道，单测不发网络请求。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"context"
	"errors"
	"testing"
)

// fakeSender 是测试替身：统计调用次数，可按需注入失败。
type fakeSender struct {
	calls int
	fail  bool
}

func (f *fakeSender) Send(ctx context.Context, to, body string) error {
	f.calls++
	if f.fail {
		return errors.New("channel down")
	}
	return nil
}

func TestNotifyRetriesUntilSuccess(t *testing.T) {
	f := &fakeSender{fail: true}
	nf := NewNotifier(f, WithRetries(3))
	err := nf.Notify(context.Background(), "a@b.c", "hi")
	if err == nil {
		t.Fatal("want error after all retries failed")
	}
	if f.calls != 3 {
		t.Fatalf("calls = %d, want 3 (重试次数由注入的 Option 决定)", f.calls)
	}
}

func TestNotifySucceedsOnFirstTry(t *testing.T) {
	f := &fakeSender{}
	nf := NewNotifier(f) // 不传 Option：用默认 retries=1
	if err := nf.Notify(context.Background(), "a@b.c", "hi"); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if f.calls != 1 {
		t.Fatalf("calls = %d, want 1", f.calls)
	}
}
