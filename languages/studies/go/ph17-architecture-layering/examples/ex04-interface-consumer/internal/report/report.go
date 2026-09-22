// 来源：ph17-architecture-layering examples/ex04-interface-consumer/internal/report
// 一句话说明：消费方声明接口（Go 惯例，主文档 3.3）。ReportStore 只含 Generate
// 真正用到的方法 Sites——接口小到"恰好描述调用方需求"；
// 提供方 internal/sites 完全不 import 本包也能满足它（隐式实现）。
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
	"fmt"

	"tenetlang/go/ph17-architecture-layering/examples/ex04-interface-consumer/internal/domain"
)

// ReportStore 是本包（消费方）对数据源的全部需求。
// 若未来多一个"批量查询"，只在接口上加方法，所有实现一起升级——
// 接口变化由使用方驱动，而不是由实现方"顺便导出"。
type ReportStore interface {
	Sites(ctx context.Context) ([]domain.Site, error)
}

// Report 是服务的输出（聚合结果）。
type Report struct {
	Total     int      `json:"total"`
	Healthy   int      `json:"healthy"`
	Unhealthy []string `json:"unhealthy,omitempty"`
}

// Generate 以函数参数注入 store（函数级注入；字段级构造函数注入见 ex02）。
func Generate(ctx context.Context, store ReportStore) (Report, error) {
	sites, err := store.Sites(ctx)
	if err != nil {
		return Report{}, fmt.Errorf("load sites: %w", err)
	}
	r := Report{Total: len(sites)}
	for _, s := range sites {
		if s.Healthy {
			r.Healthy++
		} else {
			r.Unhealthy = append(r.Unhealthy, s.ID)
		}
	}
	return r, nil
}
