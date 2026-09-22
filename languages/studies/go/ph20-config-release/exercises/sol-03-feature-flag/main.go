// 来源：ph20-config-release exercises/sol-03-feature-flag/main.go
// 一句话说明：demo——一个 feature 从白名单内测走到 GA、再被紧急下线的全程，
// 观察不同用户在每种规则下的裁决（主文档 3.3）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
)

// internalUsers 模拟内部名单（内测白名单）。
func internalUsers(u string) bool {
	switch u {
	case "user-0000", "user-0001", "user-0002":
		return true
	}
	return false
}

func main() {
	users := []string{"user-0000", "user-0001", "user-0002", "user-0042", "user-0099"}

	// 阶段一：introduced，只对白名单（内部）开放，不对外放量。
	f1 := Feature{Name: "beta-reports", Stage: StageIntroduced, Allow: internalUsers, Percent: 0}
	fmt.Println("== introduced：仅白名单 ==")
	printRule(f1, users)

	// 阶段二：beta，白名单保留 + 对外放量 30%。
	f2 := Feature{Name: "beta-reports", Stage: StageBeta, Allow: internalUsers, Percent: 30}
	fmt.Println("\n== beta：白名单 + 30% 放量 ==")
	printRule(f2, users)

	// 阶段三：GA 全量。
	f3 := Feature{Name: "beta-reports", Stage: StageGA, Percent: 100}
	fmt.Println("\n== GA：全量 ==")
	printRule(f3, users)

	// 阶段四：事故应急——HardOff 立即下线（regression 被发现）。
	f4 := Feature{Name: "beta-reports", Stage: StageRemoved, HardOff: true, Percent: 100}
	fmt.Println("\n== removed/紧急关闭：HardOff 越过一切 ==")
	printRule(f4, users)

	// 生命周期校验：removed 必须 HardOff。
	if err := f4.Validate(); err != nil {
		fmt.Println("校验失败（不应发生）：", err)
	}
	bad := Feature{Name: "beta-reports", Stage: StageRemoved, Percent: 100} // 忘关
	if err := bad.Validate(); err != nil {
		fmt.Println("\n校验拦截：", err)
	}
}

func printRule(f Feature, users []string) {
	for _, u := range users {
		fmt.Printf("   %-10s → %-5v\n", u, f.Evaluate(u))
	}
}
