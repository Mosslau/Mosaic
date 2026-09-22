// 来源：ph17-architecture-layering exercises/sol-03-service-unit-tests/internal/todo
// 一句话说明：领域包（与练习 2 同款语义：哨兵在领域层，service 不用 import 存储实现）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package todo

import "errors"

// ErrNotFound：跨层"数据不存在"语义。
var ErrNotFound = errors.New("todo: not found")

// Todo 领域对象。
type Todo struct {
	ID    string `json:"id"`
	Title string `json:"title"`
	Done  bool   `json:"done"`
}
