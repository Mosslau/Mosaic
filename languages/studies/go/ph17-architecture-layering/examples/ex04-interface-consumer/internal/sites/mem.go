// 来源：ph17-architecture-layering examples/ex04-interface-consumer/internal/sites
// 一句话说明：提供方实现。关键点：本包不 import internal/report——
// 它不知道自己被 report 消费。mem.Store 是否满足 report.ReportStore
// 由组装点（main）用 var _ 断言保证，不靠实现包反向引用消费方。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package sites

import (
	"context"

	"tenetlang/go/ph17-architecture-layering/examples/ex04-interface-consumer/internal/domain"
)

// Store 是静态内存数据源（repository 角色）。
type Store struct {
	sites []domain.Site
}

func New(sites []domain.Site) *Store {
	return &Store{sites: sites}
}

// Sites 的方法签名与 report.ReportStore 要求一致即自动满足接口。
// 真实实现会在这里访问数据库/外部健康检查服务（repository 隔离存储细节）。
func (s *Store) Sites(ctx context.Context) ([]domain.Site, error) {
	out := make([]domain.Site, len(s.sites))
	copy(out, s.sites) // 返回副本：防止调用方修改内部状态
	return out, nil
}

// Ping 是 Store 的"额外能力"，不在 ReportStore 接口里。
// 调用方用不到的方法不该出现在接口上（接口最小化）；实现可以比接口更丰富。
func (s *Store) Ping(ctx context.Context) error {
	return nil // 无外部依赖可探活；仅演示"实现可拥有接口之外的更多方法"
}
