// 来源：ph20-config-release examples/ex05-rollout-decision/rollout.go
// 一句话说明：灰度/滚动发布的"决策器"——把「新版本健康 → 放量、不健康 →
// 暂停、持续不健康 → 回滚」写成可喂入健康采样、逐轮吐动作的状态机。
// 决策逻辑与载体（K8s 的 Deployment 数量、网关的流量权重，见 ph12 3.8）
// 解耦：本文件只回答"现在该前进/保持/回滚"，载体层去执行（主文档 3.4）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "fmt"

// Decision 是决策器每轮吐出的动作，由上层（发布控制器/人）执行。
type Decision int

const (
	DecisionHold     Decision = iota // 本阶段观察中/暂不动作（继续当前放量比例）
	DecisionAdvance                  // 健康达标，放量到下一阶段
	DecisionRollback                 // 新版本连续不健康，建议回滚到旧版本
	DecisionComplete                 // 已 100% 放量完成，发布结束
)

func (d Decision) String() string {
	switch d {
	case DecisionHold:
		return "hold(维持当前比例)"
	case DecisionAdvance:
		return "advance(放量到下一阶段)"
	case DecisionRollback:
		return "rollback(回滚旧版本)"
	case DecisionComplete:
		return "complete(发布完成)"
	}
	return "unknown"
}

// Phase 是发布计划里的一档放量档位：canary → 滚动逐步 → full。
// 真实载体是"新版本流量比例"（负载均衡权重）或"新版本副本数"（K8s），
// 这里统一抽象成百分比，载体差异由部署层消化（ph12 已讲载体，不重复）。
type Phase struct {
	Name               string  // 档位名：canary / rolling / full
	TargetPercent      int     // 本阶段放量到的新版本流量比例（0~100）
	MinHealthyRatio    float64 // 新版本健康比例下限（0~1），低于它=不健康轮
	MinObservations    int     // 本阶段需连续健康多少轮才放量（观察窗）
	MaxUnhealthyRounds int     // 连续不健康多少轮触发回滚建议
}

// Rollout 是发布计划的状态机：记录当前档位与连续健康/不健康轮数。
// 轮询模型：上层每隔一个观察周期喂一次新版本的健康采样（探针结果聚合），
// Decide 更新内部计数并返回动作。计数是"状态"，健康采样是"输入"——测试只需
// 喂一串预定的健康比例即可复现完整发布，无需任何真实服务。
type Rollout struct {
	Phases []Phase
	cur    int // 当前所在档位下标
	good   int // 本档连续健康轮
	bad    int // 本档连续不健康轮
}

// NewRollout 从档位列表构造状态机。
func NewRollout(phases []Phase) *Rollout {
	return &Rollout{Phases: phases}
}

// DefaultPhases 一组典型发布档位：canary 5% → rolling 30% → 70% → full 100%。
// 每个档位要求连续 3 轮健康（观察窗）才放量，连续 2 轮不健康触发回滚建议。
// 数值只是示例——真实取值由业务容忍度与历史发布数据决定。
func DefaultPhases() []Phase {
	return []Phase{
		{Name: "canary", TargetPercent: 5, MinHealthyRatio: 0.95, MinObservations: 3, MaxUnhealthyRounds: 2},
		{Name: "rolling-30", TargetPercent: 30, MinHealthyRatio: 0.95, MinObservations: 3, MaxUnhealthyRounds: 2},
		{Name: "rolling-70", TargetPercent: 70, MinHealthyRatio: 0.95, MinObservations: 3, MaxUnhealthyRounds: 2},
		{Name: "full-100", TargetPercent: 100, MinHealthyRatio: 0.95, MinObservations: 3, MaxUnhealthyRounds: 2},
	}
}

// Phase 返回当前档位。
func (r *Rollout) Phase() Phase { return r.Phases[r.cur] }

// Percent 返回当前已放量的比例（供上层执行）。
func (r *Rollout) Percent() int { return r.Phases[r.cur].TargetPercent }

// Observe 喂入本轮健康采样（healthyRatio ∈ [0,1]，由探针聚合保证），返回动作。
// 决策规则（每档独立，跨档不继承好印象）：
//   - 健康比例 ≥ MinHealthyRatio → good+1；攒够 MinObservations 轮才放量。
//   - 健康比例不达标 → bad+1（good 清零）；连续 bad 达到 MaxUnhealthyRounds → 回滚。
//
// 教学约定：输入前先 clamp/过滤非法采样是上层职责；本函数假设 healthyRatio ∈ [0,1]。
func (r *Rollout) Observe(healthyRatio float64) Decision {
	ph := r.Phases[r.cur]

	if healthyRatio < ph.MinHealthyRatio {
		r.good, r.bad = 0, r.bad+1
		if r.bad >= ph.MaxUnhealthyRounds {
			return DecisionRollback
		}
		return DecisionHold
	}

	r.good, r.bad = r.good+1, 0
	if r.good < ph.MinObservations {
		return DecisionHold // 观察窗没攒够，保持当前放量
	}

	// 本档健康达标：放量。计数清零，进入下一档（或发布完成）。
	r.good, r.bad = 0, 0
	if r.cur == len(r.Phases)-1 {
		return DecisionComplete
	}
	r.cur++
	return DecisionAdvance
}

// Run 是一次确定性回放：把健康采样列表逐轮喂给状态机，返回每轮决策记录。
// 发布走查、回滚演练、压测不同健康曲线都用它，不用真的发一次版。
func (r *Rollout) Run(samples []float64) []string {
	var log []string
	for i, s := range samples {
		ph := r.Phases[r.cur]
		d := r.Observe(s)
		log = append(log, fmt.Sprintf("轮 %2d：档=%s(放量%3d%%) 健康=%.0f%% → %s",
			i+1, ph.Name, ph.TargetPercent, s*100, d))
		if d == DecisionComplete || d == DecisionRollback {
			break // 终局：完成或回滚后不再消费采样
		}
	}
	return log
}
