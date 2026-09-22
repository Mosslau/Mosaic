// 来源：ph17-architecture-layering examples/ex02-constructor-injection/main.go
// 一句话说明：组装点。渠道选型（sms/email）只在 main 发生一次——
// 业务代码 Notifier 完全不感知"世界上有几种渠道"。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -sender sms    （-sender email 切换渠道）
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"context"
	"flag"
	"log"
)

func main() {
	sender := flag.String("sender", "email", "通知渠道: sms | email")
	flag.Parse()

	// 依赖的选择与装配只在这里：构造的具体类型实现 Sender 即可被注入
	var s Sender
	switch *sender {
	case "sms":
		s = &SMSSender{prefix: "[sms]"}
	default:
		s = &EmailSender{}
	}

	nf := NewNotifier(s, WithRetries(2))
	if err := nf.Notify(context.Background(), "ops@example.com", "ph17 ex02: hello DI"); err != nil {
		log.Fatal(err)
	}
}
