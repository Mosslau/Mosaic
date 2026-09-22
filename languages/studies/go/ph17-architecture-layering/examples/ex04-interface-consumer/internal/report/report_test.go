// 来源：ph17-architecture-layering examples/ex04-interface-consumer/internal/report/report_test.go
// 一句话说明：fake 测试替身。测试不需要 import 真实实现（internal/sites）——
// fakeStore 的方法签名满足 ReportStore 即注入成功，这正是"接口定义在使用方"的测试红利。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package report

import (
	"context"
	"errors"
	"testing"

	"tenetlang/go/ph17-architecture-layering/examples/ex04-interface-consumer/internal/domain"
)

// fakeStore 是测试替身：可控返回数据与错误，与真实实现互不 import。
type fakeStore struct {
	sites []domain.Site
	err   error
}

func (f fakeStore) Sites(ctx context.Context) ([]domain.Site, error) {
	return f.sites, f.err
}

var _ ReportStore = fakeStore{} // 替身也受编译期约束：签名变了立刻在测试里暴露

func TestGenerateHealthySummary(t *testing.T) {
	f := fakeStore{sites: []domain.Site{
		{ID: "a", Healthy: true},
		{ID: "b", Healthy: false},
	}}
	r, err := Generate(context.Background(), f)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if r.Total != 2 || r.Healthy != 1 {
		t.Fatalf("Total=%d Healthy=%d, want 2/1", r.Total, r.Healthy)
	}
	if len(r.Unhealthy) != 1 || r.Unhealthy[0] != "b" {
		t.Fatalf("Unhealthy = %v, want [b]", r.Unhealthy)
	}
}

func TestGeneratePropagatesStoreError(t *testing.T) {
	boom := errors.New("storage down")
	f := fakeStore{err: boom}
	_, err := Generate(context.Background(), f)
	if !errors.Is(err, boom) {
		t.Fatalf("want wrapped %v, got %v", boom, err)
	}
}
