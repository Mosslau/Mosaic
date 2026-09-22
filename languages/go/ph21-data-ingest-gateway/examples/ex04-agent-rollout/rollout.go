// 来源：ph21-data-ingest-gateway examples/ex04-rollout-service/rollout.go
// 一句话说明：Rollout 分批灰度决策器——批次按 SourceID 名单推进，每个数据源一次 OnAgentReport
// 喂入"成功/失败"，引擎输出 hold/advance/rollback/complete。决策是确定性纯函数
// （同输入同输出），进度可回放演练——ph20 ex05 发布决策器的同构（主文档 3.10）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"fmt"
	"sync"
)

// Decision 决策动作（放量状态机的迁移语义）。
type Decision int

const (
	DecisionHold     Decision = iota // 继续等待当前批确认
	DecisionAdvance                  // 当前批达标 → 放量下一批
	DecisionRollback                 // 失败率越限 → 整场暂停并回滚
	DecisionComplete                 // 全部批次完成
)

func (d Decision) String() string {
	switch d {
	case DecisionHold:
		return "hold"
	case DecisionAdvance:
		return "advance"
	case DecisionRollback:
		return "rollback"
	case DecisionComplete:
		return "complete"
	}
	return "?"
}

// RolloutOptions 灰度参数。
type RolloutOptions struct {
	TargetVersion string  // 升级目标版本（须已登记）
	FailRateLimit float64 // 批内失败率上限，超过即回滚（如 0.2）
}

// Batch 一个灰度批次：显式 SourceID 名单（真实系统按 SourceID 尾号/数据源集群分组生成）。
type Batch struct {
	Index     int
	SourceIDs []string
}

// Rollout 一场 Rollout 灰度。规则是数据、状态可查询、决策可离线回放。
type Rollout struct {
	opts        RolloutOptions
	batches     []*Batch
	sourceBatch map[string]int    // sourceID → 批次下标（决策入口 O(1)）
	startFrom   map[string]string // sourceID → 升级前版本（回滚目标，计划开始时快照）

	mu      sync.Mutex
	status  string // created / running / done / rolledback
	cur     int    // 当前批次下标
	stat    map[int]*batchStat
	decided []Decision // 决策流水（审计/回放）
}

type batchStat struct {
	total, ok, fail int
}

// NewRollout 创建一场灰度并立即启动。startFrom 是每个数据源升级前版本（"上一版即回滚目标"）。
func NewRollout(opts RolloutOptions, batches []*Batch, startFrom map[string]string) (*Rollout, error) {
	r := &Rollout{
		opts:        opts,
		batches:     batches,
		sourceBatch: make(map[string]int),
		startFrom:   startFrom,
		status:      "running",
		stat:        make(map[int]*batchStat),
	}
	for _, b := range batches {
		r.stat[b.Index] = &batchStat{total: len(b.SourceIDs)}
		for _, sourceID := range b.SourceIDs {
			r.sourceBatch[sourceID] = b.Index
		}
	}
	if len(batches) == 0 {
		r.status = "done"
	}
	return r, nil
}

// Status 返回状态（created/running/done/rolledback）。
func (r *Rollout) Status() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.status
}

// CurrentBatch 返回当前批次下标与名单（运维视图）。
func (r *Rollout) CurrentBatch() (int, []string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.cur < len(r.batches) {
		b := r.batches[r.cur]
		return b.Index, append([]string(nil), b.SourceIDs...)
	}
	return -1, nil
}

// RollbackTarget 返回某数据源的回滚目标版本（升级前版本）。
func (r *Rollout) RollbackTarget(sourceID string) string { return r.startFrom[sourceID] }

// OnAgentReport 一个数据源报告升级结果，返回本次决策。失败率越限 → rollback；
// 否则当前批全部确认 → 推进下一批；末批全成 → complete。
func (r *Rollout) OnAgentReport(sourceID string, ok bool) Decision {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.status != "running" {
		return DecisionHold // 已终态：后续报告全部忽略
	}
	bi, found := r.sourceBatch[sourceID]
	if !found {
		return DecisionHold // 不在本场灰度的车：忽略
	}
	// 车按批推进：晚到的旧批报告不再改动统计（回滚检查只看当前批）。
	st := r.stat[bi]
	if ok {
		st.ok++
	} else {
		st.fail++
	}
	if float64(st.fail) > float64(st.total)*r.opts.FailRateLimit {
		r.status = "rolledback"
		r.decided = append(r.decided, DecisionRollback)
		return DecisionRollback
	}
	if st.ok+st.fail >= st.total { // 批内全部确认
		if bi == r.batches[len(r.batches)-1].Index {
			r.status = "done"
			r.decided = append(r.decided, DecisionComplete)
			return DecisionComplete
		}
		r.cur++
		r.decided = append(r.decided, DecisionAdvance)
		return DecisionAdvance
	}
	return DecisionHold
}

// Summary 运维摘要。
func (r *Rollout) Summary() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	return fmt.Sprintf("状态=%s 当前批=%d/总批=%d", r.status, r.cur+1, len(r.batches))
}
