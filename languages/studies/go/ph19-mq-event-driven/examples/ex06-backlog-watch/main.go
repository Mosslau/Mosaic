// 来源：ph19-mq-event-driven examples/ex06-backlog-watch/main.go
// 一句话说明：跑一次积压生命周期并打印水位表——生产 10 步（每分区每步 +3）
// 但消费每步只处理 2 条，lag 一路爬升越过阈值告警；上游停写后消费者逐步追平
// 到 lag=0（主文档 3.7）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "fmt"

func main() {
	const (
		partitions  = 2
		writeSteps  = 10 // 前 10 步上游持续生产
		produceRate = 3  // 每分区每步 +3
		consumeRate = 4  // 全组每步最多消费 4（合计速率 6 → 必然积压）
		totalSteps  = 30
		warn        = 8 // 单分区 lag >= 8 告警
	)

	w := NewWatcher(warn)
	res := Simulate(partitions, writeSteps, produceRate, consumeRate, totalSteps,
		func(step int, produced, committed []int) {
			snap := w.Observe(step, produced, committed)
			// 每隔几步打印一次水位，避免刷屏
			if step%2 == 1 || step <= 3 {
				lags := make([]int, len(snap.Partitions))
				anyWarn := false
				for i, pl := range snap.Partitions {
					lags[i] = pl.Lag
					if pl.Lag >= warn {
						anyWarn = true
					}
				}
				mark := ""
				if anyWarn {
					mark = "  ⚠️ 有分区越过阈值"
				}
				fmt.Printf("step %2d  HW=%v committed=%v lag=%v total=%d%s\n",
					step, produced, committed, lags, snap.TotalLag, mark)
			}
		})

	fmt.Println()
	for _, a := range w.Alerts() {
		fmt.Printf("🚨 告警 step=%d partition=%d lag=%d（>= %d）\n", a.Step, a.Partition, a.Lag, warn)
	}
	if last, ok := w.LastSnapshot(); ok {
		fmt.Printf("最终 TotalLag=%d\n", last.TotalLag)
	}
	fmt.Printf("模拟结束 caughtUp=%v（生产停写后消费者追平 = 积压可恢复）\n", res.CaughtUp)
}
