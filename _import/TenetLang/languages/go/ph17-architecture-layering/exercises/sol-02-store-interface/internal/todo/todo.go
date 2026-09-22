// 来源：ph17-architecture-layering exercises/sol-02-store-interface/internal/todo
// 一句话说明：领域包。ErrNotFound 哨兵定义在领域层——store 的实现（内存/文件）都返回它，
// service 用 errors.Is 判断；这样 service 不必 import 任何具体存储实现包（依赖方向干净）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package todo

import "errors"

// ErrNotFound 是"数据不存在"的跨层语义：各存储实现返回它，业务层翻译它。
// 放领域包而不是某个 store 包，是为了让 service 只依赖领域而不用 import 实现。
var ErrNotFound = errors.New("todo: not found")

// Todo 领域对象（json tag 为教学简化；文件存储直接用它做持久化格式）。
type Todo struct {
	ID    string `json:"id"`
	Title string `json:"title"`
	Done  bool   `json:"done"`
}
