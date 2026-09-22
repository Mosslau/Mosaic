// 来源：ph20-config-release examples/ex06-hot-reload-boundary/main.go
// 一句话说明：两个画面——(1) 哪些配置可热更、哪些必须重启的分类表；(2) 一个
// 服务"运行中"收到新 log.level 后，后续请求立即用新值、无需重启的原子热更
// 演示（配置中心 watch → 进程内热更的落地形态，见主文档 3.7）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
	"time"
)

func main() {
	// 画面 1：边界分类表。配置中心/热更框架"能"热更一切，但工程上按类别区分。
	fmt.Println("== 配置更新的边界 ==")
	fmt.Print(Describe())

	// 画面 2：原子热更。服务跑起来后，模拟"配置中心推送新日志级别"。
	fmt.Println("\n== 服务运行中热更 log.level（每 200ms 一个请求）==")
	lc := NewLiveConfig(&Snapshot{Version: 1, LogLevel: "INFO", MaxQPS: 100})
	stop := make(chan struct{})
	done := make(chan struct{})

	// 请求 goroutine：每个请求无锁拿当前快照，按其 logLevel 决定是否打 debug。
	go func() {
		defer close(done)
		n := 0
		for {
			select {
			case <-stop:
				return
			case <-time.After(200 * time.Millisecond):
				n++
				s := lc.Load()
				msg := fmt.Sprintf("  请求 #%-2d snapshot=v%d logLevel=%s maxQPS=%d",
					n, s.Version, s.LogLevel, s.MaxQPS)
				if s.LogLevel == "DEBUG" {
					msg += "   [debug 详情已打印]"
				}
				fmt.Println(msg)
			}
		}
	}()

	// 700ms 后配置中心推入 v2：log.level=DEBUG。旧请求进程还在，无重启。
	time.Sleep(700 * time.Millisecond)
	fmt.Println("── 配置中心推送：log.level INFO → DEBUG（version 1 → 2）──")
	lc.Store(&Snapshot{Version: 2, LogLevel: "DEBUG", MaxQPS: 300})

	// 再等 ~800ms 后推入 v3（把 log level 调回，模拟调优），随后收尾。
	time.Sleep(900 * time.Millisecond)
	fmt.Println("── 配置中心推送：rate.limit.qps 300 → 250（version 2 → 3）──")
	lc.Store(&Snapshot{Version: 3, LogLevel: "DEBUG", MaxQPS: 250})

	time.Sleep(700 * time.Millisecond)
	close(stop)
	<-done

	fmt.Println("\n要点：请求无锁读新值即刻生效——但注意 log.level/rate.limit 在分类表里")
	fmt.Println("     属于 hot，而 server.port/db.dsn/tls.* 属于 restart：机制上都能推，")
	fmt.Println("     边界在「改了能不能安全生效」，不在「推送通道通不通」。")
}
