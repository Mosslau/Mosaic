// 来源：ph17-architecture-layering exercises/sol-04-error-codes/internal/orders
// 一句话说明：业务层（练习 4 参考实现）。规则错误统一返回 *errs.Error；
// 存储"不存在"的根因哨兵 errNoOrder 被包装进 Err 链——翻译层（internal/httperr）
// 只认 Code，排障只看根因链，两层职责不互相泄漏。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package orders

import (
	"errors"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-04-error-codes/internal/errs"
)

// errNoOrder 存储层哨兵（模拟 sql.ErrNoRows；根因，不对外）。
var errNoOrder = errors.New("orders: no such order")

// 订单状态机（本练习只取两条规则演示，状态机全量设计超出范围）。
const (
	statusCreated   = "created"
	statusPaid      = "paid"
	statusCancelled = "cancelled"
)

// Store 是极简"存储 + 规则"合体（教学简化：聚焦错误码；分层见练习 1 的 sol-01）。
type Store struct {
	m map[string]string // id -> status
}

func New() *Store {
	return &Store{m: make(map[string]string)}
}

// Pay 的规则：订单必须存在；已支付不能重复支付。
func (s *Store) Pay(id string) error {
	st, ok := s.m[id]
	if !ok {
		return errs.Wrap(errs.CodeNotFound, "订单不存在", errNoOrder)
	}
	if st == statusPaid {
		return errs.New(errs.CodeConflict, "订单已支付，不能重复支付")
	}
	s.m[id] = statusPaid
	return nil
}

// Cancel 的规则：订单必须存在；已支付订单不能取消。
func (s *Store) Cancel(id string) error {
	st, ok := s.m[id]
	if !ok {
		return errs.Wrap(errs.CodeNotFound, "订单不存在", errNoOrder)
	}
	if st == statusPaid {
		return errs.New(errs.CodeConflict, "已支付订单不能取消")
	}
	s.m[id] = statusCancelled
	return nil
}
