// 来源：ph19-mq-event-driven examples/ex06-backlog-watch/simulate.go
// 一句话说明：把"生产速率 > 消费速率 → 积压爬升；上游停写 → 消费者追平"这一
// 现实节奏压成一个确定性的离散时间模拟（不真睡、不并发，纯算术）。每个时步
// 结束后调用 observe(step, produced, committed) 喂给 Watcher 采样——真实系统
// 里同等水位来自 broker 的高水位指标与消费者组的提交记录（主文档 3.7）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

// Observer 每时步结束后的采样回调。
type Observer func(step int, produced, committed []int)

// SimResult 模拟终态。
type SimResult struct {
	Produced  []int
	Committed []int
	CaughtUp  bool
}

// Simulate 离散时间模拟积压生命周期：
//
//	partitions   分区数
//	writeSteps   生产持续几个时步（之后上游停止写入）
//	produceRate  每个分区每时步新写入条数
//	consumeRate  消费者组每时步全组最多处理的总条数
//	totalSteps   模拟总时步
//	observe      每时步结束后的采样回调（可为 nil）
//
// 每时步顺序：先生产、后消费（与实际"先落盘、后拉取"一致）。
func Simulate(partitions, writeSteps, produceRate, consumeRate, totalSteps int, observe Observer) SimResult {
	produced := make([]int, partitions)
	committed := make([]int, partitions)
	for step := 1; step <= totalSteps; step++ {
		if step <= writeSteps {
			for p := range produced {
				produced[p] += produceRate // 上游持续生产：高水位上涨
			}
		}
		consumeUpTo(consumeRate, produced, committed)
		if observe != nil {
			observe(step, append([]int(nil), produced...), append([]int(nil), committed...))
		}
	}
	res := SimResult{Produced: produced, Committed: committed}
	res.CaughtUp = true
	for p := range produced {
		if committed[p] < produced[p] {
			res.CaughtUp = false
		}
	}
	return res
}

// consumeUpTo 用尽消费额度：逐轮把 1 条分给每个仍有积压的分区（欠缺点名均摊）。
// rate 用尽或全部追平即返回。
func consumeUpTo(rate int, produced, committed []int) {
	for rate > 0 {
		progressed := false
		for p := range produced {
			if committed[p] >= produced[p] {
				continue // 该分区已追平
			}
			committed[p]++
			rate--
			progressed = true
			if rate == 0 {
				return
			}
		}
		if !progressed {
			return // 全部追平：本轮无事可做
		}
	}
}
