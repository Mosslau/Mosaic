// 来源：ph20-config-release exercises/sol-03-feature-flag/feature_test.go
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"errors"
	"fmt"
	"testing"
)

func pool(n int) []string {
	out := make([]string, 0, n)
	for i := 0; i < n; i++ {
		out = append(out, fmt.Sprintf("user-%04d", i))
	}
	return out
}

func count(f Feature, users []string) int {
	n := 0
	for _, u := range users {
		if f.Evaluate(u) {
			n++
		}
	}
	return n
}

func TestHardOffOverridesEverything(t *testing.T) {
	// HardOff 是最高优先级：即使白名单命中、percent=100，也一律 false。
	f := Feature{
		Name:    "x",
		HardOff: true,
		Allow:   func(string) bool { return true },
		Percent: 100,
	}
	if f.Evaluate("user-0000") {
		t.Error("HardOff=true 时任何用户都应为 false")
	}
}

func TestAllowlistWinsOverLowPercent(t *testing.T) {
	// 白名单成员在 percent=0（仅白名单阶段）仍可用。
	f := Feature{Name: "x", Allow: internalUsers, Percent: 0}
	if !f.Evaluate("user-0000") {
		t.Error("白名单成员应在 percent=0 时可用")
	}
	if f.Evaluate("user-0042") { // 非白名单，percent=0 → 关
		t.Error("非白名单成员在 percent=0 时应为 false")
	}
}

func TestAllowlistPlusPercentStack(t *testing.T) {
	// beta 叠加：白名单成员一定开；对外约 30% 命中。
	internal := internalUsers("user-0000")
	users := pool(5000)
	f := Feature{Name: "x", Allow: internalUsers, Percent: 30}
	got := count(f, users)
	// 5000 个 user-0000~user-4999 里白名单只有 user-0000..0002 三个，
	// 其余全按 percent=30 判断：命中应 ≈ 3 + 30%*(4997) ≈ 1502，取宽区间。
	if !internal {
		t.Fatal("预期 user-0000 是白名单")
	}
	if got < 1300 || got > 1700 {
		t.Errorf("白名单+30%% 命中 %d/5000，期望约 1500", got)
	}
}

func TestEvaluateDeterministic(t *testing.T) {
	f := Feature{Name: "x", Percent: 50}
	for _, u := range pool(300) {
		if f.Evaluate(u) != f.Evaluate(u) {
			t.Fatalf("用户 %s 两次裁决不一致", u)
		}
	}
}

func TestPercentBounds(t *testing.T) {
	users := pool(200)
	all := Feature{Name: "x", Percent: 100}
	if n := count(all, users); n != len(users) {
		t.Errorf("percent=100 命中 %d, want %d", n, len(users))
	}
	none := Feature{Name: "x", Percent: 0}
	if n := count(none, users); n != 0 {
		t.Errorf("percent=0 命中 %d, want 0", n)
	}
}

func TestAnonymousUserFallsBack(t *testing.T) {
	// 需要分桶却没有身份（批量任务、服务端路径）→ 不猜，给 Fallback。
	off := Feature{Name: "x", Percent: 50, Fallback: false}
	if off.Evaluate("") {
		t.Error("空身份 + Fallback=false 应为 false")
	}
	on := Feature{Name: "x", Percent: 50, Fallback: true}
	if !on.Evaluate("") {
		t.Error("空身份 + Fallback=true 应为 true")
	}
}

func TestValidateRejectsRemovedFeatureStillOn(t *testing.T) {
	f := Feature{Name: "old", Stage: StageRemoved, Percent: 100} // 忘设 HardOff
	if err := f.Validate(); !errors.Is(err, ErrRemovedMustBeOff) {
		t.Errorf("期望 ErrRemovedMustBeOff，got %v", err)
	}
	f.HardOff = true
	if err := f.Validate(); err != nil {
		t.Errorf("HardOff=true 的 removed feature 应通过校验：%v", err)
	}
}

func TestRolloutMonotonic(t *testing.T) {
	// 放量 20→50：原本开的必须保持开（只增不减）。
	f20 := Feature{Name: "m", Percent: 20}
	f50 := Feature{Name: "m", Percent: 50}
	for _, u := range pool(2000) {
		if f20.Evaluate(u) && !f50.Evaluate(u) {
			t.Fatalf("用户 %s 在 20%% 开、50%% 反而关——放量不可回退", u)
		}
	}
}
