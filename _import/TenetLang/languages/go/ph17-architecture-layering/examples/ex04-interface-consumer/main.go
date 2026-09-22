// 来源：ph17-architecture-layering examples/ex04-interface-consumer/main.go
// 一句话说明：组装点 + 编译期断言。换数据源时（mem → 文件 → 数据库）
// 只改 main 里的构造，report 包零改动；var _ 断言把"满足接口"提前到编译期。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"tenetlang/go/ph17-architecture-layering/examples/ex04-interface-consumer/internal/domain"
	"tenetlang/go/ph17-architecture-layering/examples/ex04-interface-consumer/internal/report"
	"tenetlang/go/ph17-architecture-layering/examples/ex04-interface-consumer/internal/sites"
)

// 编译期断言：sites.Store 确实满足 report.ReportStore。
// 断言写在"双方第一次碰面"的组装点 main，而不是在实现包里 import 消费方接口——
// 后者会把依赖方向倒过来（实现包依赖消费方），是本示例想避免的反模式（主文档 3.7）。
var _ report.ReportStore = (*sites.Store)(nil)

func main() {
	// 换数据源只改这里一行：例如以后换成读数据库的实现，report.Generate 不用动
	st := sites.New([]domain.Site{
		{ID: "billing", URL: "https://billing.example.com", Healthy: true},
		{ID: "queue", URL: "https://queue.example.com", Healthy: false},
	})

	r, err := report.Generate(context.Background(), st)
	if err != nil {
		log.Printf("generate report: %v", err)
		os.Exit(1)
	}
	fmt.Printf("total=%d healthy=%d unhealthy=%v\n", r.Total, r.Healthy, r.Unhealthy)
}
