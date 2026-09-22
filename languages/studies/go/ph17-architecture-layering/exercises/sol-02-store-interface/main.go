// 来源：ph17-architecture-layering exercises/sol-02-store-interface/main.go
// 一句话说明：组装点。换存储实现只改这里的一处 switch——
// service 代码（internal/service）不感知内存还是文件。
// 运行两次对比：-store=file 时第二次运行 Add 会报"已存在"，
// 证明数据跨进程保留（-store=mem 则不会）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -store mem          # 内存：重启即空
//
//	go run . -store file -file /tmp/ph17-sol02-todos.json   # 文件：重启仍在
//
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"flag"
	"fmt"
	"log"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-02-store-interface/internal/service"
	"tenetlang/go/ph17-architecture-layering/exercises/sol-02-store-interface/internal/store"
)

// 编译期断言：两个具体实现都满足消费方接口 service.Store。
// 断言放组装点，不在实现包里 import 消费方（主文档 3.7）。
var (
	_ service.Store = (*store.Mem)(nil)
	_ service.Store = (*store.File)(nil)
)

func main() {
	kind := flag.String("store", "mem", "存储实现: mem | file")
	path := flag.String("file", "/tmp/ph17-sol02-todos.json", "-store=file 时的数据文件")
	flag.Parse()

	st, err := newStore(*kind, *path)
	if err != nil {
		log.Fatalf("open store: %v", err)
	}
	svc := service.New(st)

	// 演示：同一批操作跑两遍（第二次对 file 存储应报"已存在"）
	for _, op := range [][2]string{{"a", "学习分层"}, {"b", "学习依赖注入"}, {"c", "学习错误码"}} {
		if err := svc.Add(op[0], op[1]); err != nil {
			fmt.Printf("add %s: %v\n", op[0], err)
		} else {
			fmt.Printf("add %s: ok\n", op[0])
		}
	}
	if err := svc.Toggle("b"); err != nil {
		fmt.Printf("toggle b: %v\n", err)
	} else {
		fmt.Println("toggle b: ok")
	}

	items, err := svc.List()
	if err != nil {
		log.Fatalf("list: %v", err)
	}
	for _, t := range items {
		fmt.Printf("- %s %q done=%v\n", t.ID, t.Title, t.Done)
	}
}

// newStore 是"存储选型"的唯一落点：加第三种实现（如数据库）只扩展这里。
func newStore(kind, path string) (service.Store, error) {
	switch kind {
	case "mem":
		return store.NewMem(), nil
	case "file":
		return store.NewFile(path)
	default:
		return nil, fmt.Errorf("unknown store kind %q (want mem|file)", kind)
	}
}
