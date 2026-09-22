// 来源：ph20-config-release examples/ex03-feature-flag/feature_test.go
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
	"testing"
)

// pool 生成一批确定性用户 key。
func pool(n int) []string {
	out := make([]string, 0, n)
	for i := 0; i < n; i++ {
		out = append(out, fmt.Sprintf("user-%05d", i))
	}
	return out
}

func countEnabled(f Feature, users []string) int {
	n := 0
	for _, u := range users {
		if f.IsEnabled(u) {
			n++
		}
	}
	return n
}

func TestOffAndOnStrategies(t *testing.T) {
	users := pool(200)
	off := Feature{Name: "x", Strategy: Strategy{Kind: StrategyOff}, Stage: StageGA}
	if n := countEnabled(off, users); n != 0 {
		t.Errorf("off 策略命中 %d 人，want 0", n)
	}
	on := Feature{Name: "x", Strategy: Strategy{Kind: StrategyOn}, Stage: StageGA}
	if n := countEnabled(on, users); n != len(users) {
		t.Errorf("on 策略命中 %d 人，want %d", n, len(users))
	}
}

func TestPercentBoundaries(t *testing.T) {
	users := pool(500)
	// 0% 等价于关；100% 等价于开——放量两端必须与显式 Off/On 一致。
	zero := Feature{Name: "x", Strategy: Strategy{Kind: StrategyPercent, Percent: 0}}
	if n := countEnabled(zero, users); n != 0 {
		t.Errorf("percent=0 命中 %d 人，want 0", n)
	}
	all := Feature{Name: "x", Strategy: Strategy{Kind: StrategyPercent, Percent: 100}}
	if n := countEnabled(all, users); n != len(users) {
		t.Errorf("percent=100 命中 %d 人，want %d", n, len(users))
	}
}

func TestDecisionDeterministicAcrossInstances(t *testing.T) {
	// 纯函数：同一 (feature, user) 重复判定结果恒等 → 多实例灰度一致的地基。
	f := Feature{Name: "x", Strategy: Strategy{Kind: StrategyPercent, Percent: 50}, Stage: StageBeta}
	for _, u := range pool(300) {
		if f.IsEnabled(u) != f.IsEnabled(u) {
			t.Fatalf("用户 %s 两次判定不一致", u)
		}
	}
}

func TestPercentHitsRoughlyItsRate(t *testing.T) {
	// percent=30 应命中约 30%（宽区间 25%~35% 吸收哈希分布波动）。
	users := pool(20000)
	f := Feature{Name: "x", Strategy: Strategy{Kind: StrategyPercent, Percent: 30}, Stage: StageBeta}
	got := countEnabled(f, users)
	if got < 5000 || got > 7000 {
		t.Errorf("percent=30 命中 %d/20000，期望约 6000（25%%~35%% 区间）", got)
	}
}

func TestRolloutIsMonotonic(t *testing.T) {
	// 灰度放量单调性：20% → 50% 时，原本可见的用户必须保持可见，只会新增。
	users := pool(2000)
	f20 := Feature{Name: "m", Strategy: Strategy{Kind: StrategyPercent, Percent: 20}, Stage: StageBeta}
	f50 := Feature{Name: "m", Strategy: Strategy{Kind: StrategyPercent, Percent: 50}, Stage: StageBeta}
	for _, u := range users {
		if f20.IsEnabled(u) && !f50.IsEnabled(u) {
			t.Fatalf("用户 %s 在 20%% 可见、50%% 反而不可见——放量不可回退", u)
		}
	}
}

func TestFeaturesAreIndependent(t *testing.T) {
	// 两个独立 50% feature 的同时命中率应接近 25%（相乘），证明 salt 隔离生效。
	users := pool(10000)
	fa := Feature{Name: "realtime-map", Strategy: Strategy{Kind: StrategyPercent, Percent: 50}}
	fb := Feature{Name: "new-search", Strategy: Strategy{Kind: StrategyPercent, Percent: 50}}
	both := 0
	for _, u := range users {
		if fa.IsEnabled(u) && fb.IsEnabled(u) {
			both++
		}
	}
	if both < 2200 || both > 2800 {
		t.Errorf("两个独立 50%% 命中 %d/10000，期望约 2500（相乘独立性）", both)
	}
}

func TestUnknownKindFallsBackSafely(t *testing.T) {
	// 策略被写坏（非法 Kind）时走 Fallback，而不是 panic。
	f := Feature{Name: "x", Strategy: Strategy{Kind: StrategyKind(99)}, Fallback: true}
	if !f.IsEnabled("user-00001") {
		t.Error("非法 Kind 应回退到 Fallback=true")
	}
	f.Fallback = false
	if f.IsEnabled("user-00001") {
		t.Error("非法 Kind 应回退到 Fallback=false")
	}
}

func TestStageString(t *testing.T) {
	cases := map[Stage]string{
		StageIntroduced: "introduced(内测)",
		StageBeta:       "beta(灰度)",
		StageGA:         "GA(全量)",
		StageRemoved:    "removed(摘除中)",
	}
	for s, want := range cases {
		if got := s.String(); got != want {
			t.Errorf("Stage(%d).String() = %q, want %q", int(s), got, want)
		}
	}
}
