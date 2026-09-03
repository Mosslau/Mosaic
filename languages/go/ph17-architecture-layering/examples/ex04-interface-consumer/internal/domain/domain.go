// 来源：ph17-architecture-layering examples/ex04-interface-consumer/internal/domain
// 一句话说明：公共领域包（数据契约）。report（消费方）与 sites（提供方）都引用它，
// 但谁都不依赖"更外层"——domain 是全依赖图的汇点（主文档 3.7 依赖方向）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package domain

// Site 是站点可用性领域的对象：健康状态由谁写入不关心，这里只定义形状。
type Site struct {
	ID      string
	URL     string
	Healthy bool
}
