// 来源：ph17-architecture-layering exercises/sol-01-layered-todo/internal/todo
// 一句话说明：练习 1 参考实现的领域包（Todo 带优先级字段，与 ex01 的形态略有差异，
// 避免直接照抄示例——练习练的是分层判断，不是抄结构）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package todo

// Priority 是三档优先级（业务词汇，service 校验、store 只存）。
type Priority string

const (
	PriorityHigh   Priority = "high"
	PriorityNormal Priority = "normal"
	PriorityLow    Priority = "low"
)

// Todo 领域对象：json tag 为教学简化（见主文档 3.2 取舍说明）。
type Todo struct {
	ID       string   `json:"id"`
	Title    string   `json:"title"`
	Priority Priority `json:"priority"`
	Done     bool     `json:"done"`
}
