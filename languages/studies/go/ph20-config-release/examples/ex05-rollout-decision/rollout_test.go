// 来源：ph20-config-release examples/ex05-rollout-decision/rollout_test.go
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"reflect"
	"testing"
)

// drive 把采样逐轮喂给状态机，收集动作序列（到终局即停）。
func drive(r *Rollout, samples []float64) []Decision {
	var out []Decision
	for _, s := range samples {
		d := r.Observe(s)
		out = append(out, d)
		if d == DecisionComplete || d == DecisionRollback {
			break
		}
	}
	return out
}

func TestHappyPathAdvancesToComplete(t *testing.T) {
	// 4 档各喂 3 轮健康：canary/rolling-30/rolling-70 各在第三轮 advance，
	// full-100 第三轮 complete。共 12 轮。
	r := NewRollout(DefaultPhases())
	got := drive(r, []float64{
		1, 1, 1,
		1, 1, 1,
		1, 1, 1,
		1, 1, 1,
	})
	want := []Decision{
		DecisionHold, DecisionHold, DecisionAdvance, // canary 观察窗满 → 放量
		DecisionHold, DecisionHold, DecisionAdvance, // rolling-30 → 放量
		DecisionHold, DecisionHold, DecisionAdvance, // rolling-70 → 放量
		DecisionHold, DecisionHold, DecisionComplete, // full-100 → 完成
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("动作序列不符\ngot:  %v\nwant: %v", got, want)
	}
}

func TestCanaryFailureTriggersRollback(t *testing.T) {
	// 1 好 + 连续 2 坏（达到 MaxUnhealthyRounds=2）→ 金丝雀期回滚。
	r := NewRollout(DefaultPhases())
	got := drive(r, []float64{1.0, 0.4, 0.3})
	want := []Decision{DecisionHold, DecisionHold, DecisionRollback}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("动作序列 = %v, want %v", got, want)
	}
}

func TestRollbackAfterMidRolloutRegression(t *testing.T) {
	// canary 全好 advance 到 rolling-30；随后 1 好 2 坏 → 中途回滚。
	r := NewRollout(DefaultPhases())
	got := drive(r, []float64{1.0, 1.0, 1.0, 1.0, 0.5, 0.3})
	want := []Decision{
		DecisionHold, DecisionHold, DecisionAdvance, // canary 放量
		DecisionHold,                   // rolling-30 第 1 轮健康（观察窗 3 未满）
		DecisionHold, DecisionRollback, // 连续不健康 2 轮 → 回滚
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("动作序列 = %v, want %v", got, want)
	}
}

func TestBadRoundResetsObservationWindow(t *testing.T) {
	// 2 好 1 坏再 3 好：坏的一轮清掉观察进度，放量被推迟到第 6 轮才触发。
	r := NewRollout(DefaultPhases())
	got := drive(r, []float64{1.0, 1.0, 0.0, 1.0, 1.0, 1.0})
	want := []Decision{
		DecisionHold, DecisionHold, // 轮1~2 好
		DecisionHold,               // 轮3 坏：观察进度清零
		DecisionHold, DecisionHold, // 轮4~5 重新攒 2 好
		DecisionAdvance, // 轮6 攒满 → 放量
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("动作序列 = %v, want %v", got, want)
	}
	// 此时应已进入 rolling-30 档。
	if r.Phase().Name != "rolling-30" {
		t.Errorf("当前档 = %q, want rolling-30", r.Phase().Name)
	}
}

func TestPercentGrowsWithPhases(t *testing.T) {
	// 健康放量过程中，每档放量后应进入更高的目标比例，最终停在 100%。
	r := NewRollout(DefaultPhases())
	seen := []int{}
	for i := 0; i < 12; i++ {
		d := r.Observe(1.0)
		if d == DecisionAdvance {
			seen = append(seen, r.Percent()) // advance 后 Percent() 是下一档目标
		}
	}
	want := []int{30, 70, 100}
	if !reflect.DeepEqual(seen, want) {
		t.Errorf("放量推进档位 = %v, want %v", seen, want)
	}
	// 发布完成时当前档就是 full-100。
	if r.Phase().TargetPercent != 100 {
		t.Errorf("完成后当前档 TargetPercent = %d, want 100", r.Phase().TargetPercent)
	}
}
