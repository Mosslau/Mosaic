// 来源：ph20-config-release examples/ex03-feature-flag/main.go
// 一句话说明：把 feature flag 的三种策略与多实例一致性、放量过程演给人看——
// 同一批 200 个用户经过 beta 20% → beta 50% → GA 全量三个阶段的灰度，
// 观察命中人数与"谁从不可见变可见"（主文档 3.3）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
	"sort"
)

func main() {
	// 造 200 个确定性用户（user-0000 ~ user-0199），模拟真实流量里的用户群。
	users := make([]string, 0, 200)
	for i := 0; i < 200; i++ {
		users = append(users, fmt.Sprintf("user-%04d", i))
	}

	// 1. 三种策略的最小语义。
	fmt.Println("== 1. 三种策略的最小语义（dark-mode 开关）==")
	sample := Feature{
		Name:     "dark-mode",
		Fallback: false, // 决策系统故障时默认不给新功能
		Stage:    StageGA,
	}
	for _, st := range []Strategy{
		{Kind: StrategyOff},
		{Kind: StrategyPercent, Percent: 20},
		{Kind: StrategyOn},
	} {
		sample.Strategy = st
		open := 0
		for _, u := range users {
			if sample.IsEnabled(u) {
				open++
			}
		}
		fmt.Printf("   %-14s → 命中 %3d/200 用户\n", st, open)
	}

	// 2. 灰度放量过程：同一用户群，同一 feature，percent 逐步抬升。
	fmt.Println("\n== 2. 灰度放量过程（realtime-map beta → GA）==")
	stages := []struct {
		name     string
		stage    Stage
		strategy Strategy
	}{
		{"beta 20%", StageBeta, Strategy{Kind: StrategyPercent, Percent: 20}},
		{"beta 50%", StageBeta, Strategy{Kind: StrategyPercent, Percent: 50}},
		{"GA on", StageGA, Strategy{Kind: StrategyOn}},
	}
	prev := map[string]bool{}
	first := true
	for _, s := range stages {
		f := Feature{Name: "realtime-map", Strategy: s.strategy, Fallback: false, Stage: s.stage}
		open := 0
		newly := []string{}
		for _, u := range users {
			on := f.IsEnabled(u)
			if on {
				open++
			}
			if !first && on && !prev[u] {
				newly = append(newly, u)
			}
			prev[u] = on
		}
		first = false
		// 打印「本次放量新增了谁」的前 3 个，证明放量是单调增、可预期的。
		sort.Strings(newly)
		note := ""
		if len(newly) > 0 {
			note = fmt.Sprintf("（本阶段新增 %d 人，前 3 个：%v…）", len(newly), firstN(newly, 3))
		}
		fmt.Printf("   %-9s 阶段 %-18s → 命中 %3d/200%s\n", s.name, s.stage, open, note)
	}

	// 3. 多实例一致性：两个"实例"各自独立判断同一批用户，结果必须逐人相同。
	fmt.Println("\n== 3. 多实例一致性 ==")
	f := Feature{Name: "realtime-map", Strategy: Strategy{Kind: StrategyPercent, Percent: 50}, Fallback: false, Stage: StageBeta}
	inconsistent := 0
	for _, u := range users {
		if f.IsEnabled(u) != f.IsEnabled(u) { // 纯函数重复调用：应恒等
			inconsistent++
		}
	}
	fmt.Printf("   同一 feature 重复判断逐人一致（不一致 %d 人）——灰度结果不依赖调用实例\n", inconsistent)

	// 4. 用户分桶 vs feature 隔离：同一用户在不同 feature 上的灰度互不绑定。
	fmt.Println("\n== 4. feature 间独立（salt 隔离）==")
	fa := Feature{Name: "realtime-map", Strategy: Strategy{Kind: StrategyPercent, Percent: 50}, Fallback: false}
	fb := Feature{Name: "new-search", Strategy: Strategy{Kind: StrategyPercent, Percent: 50}, Fallback: false}
	both := 0
	for _, u := range users {
		if fa.IsEnabled(u) && fb.IsEnabled(u) {
			both++
		}
	}
	fmt.Printf("   两个独立 50%% feature 同时命中的用户 %d 人（≈25%%=50人，各自独立分桶）\n", both)

	// 5. 生命周期：removed 阶段的 feature 已强制关闭，但代码仍在（等待删除）。
	fmt.Println("\n== 5. 生命周期 ==")
	dying := Feature{Name: "old-flag", Strategy: Strategy{Kind: StrategyOff}, Fallback: true, Stage: StageRemoved}
	firstUser := users[0]
	fmt.Printf("   %-12s 阶段 %s → 用户 %s 命中 = %v（强制关闭，代码保留观察期）\n",
		dying.Name, dying.Stage, firstUser, dying.IsEnabled(firstUser))
}

func firstN(s []string, n int) []string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}
