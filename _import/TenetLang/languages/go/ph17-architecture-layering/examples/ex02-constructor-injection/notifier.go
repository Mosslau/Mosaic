// 来源：ph17-architecture-layering examples/ex02-constructor-injection/notifier.go
// 一句话说明：手写构造函数注入 + 选项函数（functional options）。
// Notifier 不自己 new 发送渠道，而是通过构造函数把 Sender 注入进来——
// 测 Notifier 时塞 fakeSender，跑生产时塞 SMS/EmailSender，业务代码零改动（主文档 3.4）。
// 本示例刻意不用 wire/dig/fx 等容器：Go 社区默认手写注入，理由见主文档 3.4 对比表。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"context"
	"fmt"
)

// Sender 是 Notifier 对发送渠道的全部需求（接口最小、定义在使用方附近，见主文档 3.3）。
// 具体实现 SMSSender/EmailSender 不声明"我实现了 Sender"——Go 的接口是隐式满足的。
type Sender interface {
	Send(ctx context.Context, to, body string) error
}

// Notifier 的业务与渠道无关：只认 Sender 这一个动作。
type Notifier struct {
	sender  Sender
	retries int
}

// Option 是选项函数：用来注入"可省略的依赖"（如重试次数），默认值在构造时兜底。
type Option func(*Notifier)

// WithRetries 把重试次数注入 Notifier（选项函数模式，见 golang-patterns 规范）。
func WithRetries(n int) Option {
	return func(nf *Notifier) { nf.retries = n }
}

// NewNotifier 构造函数注入：sender 是必选依赖，直接进参数；
// retries 等可选配置走 Option。构造完成后字段全部确定，之后不可再改。
func NewNotifier(sender Sender, opts ...Option) *Notifier {
	nf := &Notifier{sender: sender, retries: 1} // 默认重试 1 次
	for _, opt := range opts {
		opt(nf)
	}
	return nf
}

// Notify 的业务规则：发送失败重试 retries 次——这条规则不关心走短信还是邮件。
func (n *Notifier) Notify(ctx context.Context, to, body string) error {
	var err error
	for attempt := 0; attempt < n.retries; attempt++ {
		if err = n.sender.Send(ctx, to, body); err == nil {
			return nil
		}
	}
	return fmt.Errorf("notify %s after %d attempt(s): %w", to, n.retries, err)
}

// SMSSender 是渠道实现之一，可以带自己的配置字段（prefix）。
type SMSSender struct {
	prefix string
}

func (s *SMSSender) Send(ctx context.Context, to, body string) error {
	// 教学简化：真实实现会调短信网关；这里只打印代表"发出去了"
	fmt.Printf("%s to=%s body=%s\n", s.prefix, to, body)
	return nil
}

// EmailSender 是渠道实现之二：main 里改一行构造就能整体切换渠道。
type EmailSender struct{}

func (s *EmailSender) Send(ctx context.Context, to, body string) error {
	fmt.Printf("[email] to=%s body=%s\n", to, body)
	return nil
}
