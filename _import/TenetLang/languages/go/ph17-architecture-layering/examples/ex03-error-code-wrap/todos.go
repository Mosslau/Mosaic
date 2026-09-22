// 来源：ph17-architecture-layering examples/ex03-error-code-wrap/todos.go
// 一句话说明：把"存储 + 一条业务规则"刻意揉在一个类型里（教学简化，注释已声明）：
// 本示例聚焦错误码与包装机制；真实分层见 ex01 与 project/。
// 关键模式：存储层返回哨兵错误 errNoRows（仿 sql.ErrNoRows），
// 业务层把它包装成带 Code 的 *Error，根因不丢（Err 链）——分层换 HTTP 层翻译。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"errors"
	"strings"
)

// errNoRows 模拟存储层哨兵（真实工程是 sql.ErrNoRows / redis.Nil 之类）。
var errNoRows = errors.New("todos: no such row")

type todos struct {
	items map[string]string // id -> title（内存存储的"实现细节"）
}

func newTodos() *todos {
	return &todos{items: make(map[string]string)}
}

// rename 的业务规则：标题去空白后非空；目标必须存在。
// 统一返回 *Error：调用方（handler）只认 Code，不认 Go 错误类型。
func (t *todos) rename(id, title string) error {
	title = strings.TrimSpace(title)
	if title == "" {
		return New(CodeInvalid, "标题不能为空")
	}
	if _, ok := t.items[id]; !ok {
		// 包装存储层哨兵：errors.Is(err, errNoRows) 仍为 true（原因链保留）
		return Wrap(CodeNotFound, "todo 不存在", errNoRows)
	}
	t.items[id] = title
	return nil
}
