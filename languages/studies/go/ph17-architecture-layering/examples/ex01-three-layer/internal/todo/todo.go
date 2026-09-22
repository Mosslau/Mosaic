// 来源：ph17-architecture-layering examples/ex01-three-layer/internal/todo
// 一句话说明：领域模型包。Todo 是最内层，不 import 任何业务包——
// handler/service/store 都引用它，它引用谁都不行（依赖方向指向最内）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package todo

// Todo 是领域模型：ID 与 Done 承载业务不变量，Title 是业务数据。
// 字段上的 json tag 是教学简化——生产 API 常用 DTO 隔离领域与传输格式
// （见主文档 3.2 与 project/ 的取舍说明）。
type Todo struct {
	ID    string `json:"id"`
	Title string `json:"title"`
	Done  bool   `json:"done"`
}
