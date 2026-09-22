// 来源：ph21-data-ingest-gateway exercises/sol-03-rollout-upgrade/sol03.go
// 一句话说明：练习 3 参考实现——Rollout 分批灰度决策器：数据源集群基线快照、SourceID 分组下发、
// 逐台上报驱动 hold/advance/rollback/complete；决策确定性纯函数可离线回放。
// 差异点 vs ex04：这里把"数据源集群版本基线"独立成 FLEET 结构，Rollout 从基线快照生成
// 回滚目标（升级前的版本），贴近"Rollout 服务要有采集端版本台账"的要求（主文档 3.10）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"fmt"
	"sort"
	"sync"
)

// Action 决策动作。
type Action int

const (
	Hold Action = iota
	Advance
	Rollback
	Complete
)

func (a Action) String() string {
	switch a {
	case Hold:
		return "hold"
	case Advance:
		return "advance"
	case Rollback:
		return "rollback"
	case Complete:
		return "complete"
	}
	return "?"
}

// Agent 采集端台账条目（服务端维护"每个数据源现在装什么版本"）。
type Agent struct {
	SourceID string
	Version  string
}

// Registry 数据源集群版本台账。
type Registry struct {
	mu     sync.RWMutex
	agents map[string]*Agent // sourceID → 台账
}

// NewRegistry 建数据源集群台账。
func NewRegistry() *Registry { return &Registry{agents: map[string]*Agent{}} }

// Register 录入一个数据源（上线/首次联网时上报当前版本）。
func (f *Registry) Register(d Agent) {
	f.mu.Lock()
	f.agents[d.SourceID] = &d
	f.mu.Unlock()
}

// VersionOf 查某数据源当前版本。
func (f *Registry) VersionOf(sourceID string) (string, bool) {
	f.mu.RLock()
	defer f.mu.RUnlock()
	d, ok := f.agents[sourceID]
	if !ok {
		return "", false
	}
	return d.Version, true
}

// Upgrade 数据源升级成功后的台账更新。
func (f *Registry) Upgrade(sourceID, newVersion string) {
	f.mu.Lock()
	if d, ok := f.agents[sourceID]; ok {
		d.Version = newVersion
	}
	f.mu.Unlock()
}

// Group 灰度批次：一批 SourceID。
type Group struct {
	Name      string
	SourceIDs []string
}

// Rollout 一场 Rollout 灰度。
type Rollout struct {
	target      string
	failLimit   float64
	groups      []*Group
	sourceGroup map[string]int
	oldVersion  map[string]string // 升级前版本快照 = 回滚目标

	mu     sync.Mutex
	status string // running/done/rolledback
	cur    int
	stat   map[string]*groupStat
}

type groupStat struct {
	total, ok, fail int
}

// NewRollout 从数据源集群台账快照创建一场灰度。目标版本 t 必须 != 任一个数据源当前版本由调用方保证。
func NewRollout(target string, failLimit float64, groups []*Group, registry *Registry) (*Rollout, error) {
	if failLimit <= 0 || failLimit >= 1 {
		return nil, fmt.Errorf("失败率上限须在 (0,1) 内, got %v", failLimit)
	}
	r := &Rollout{
		target:      target,
		failLimit:   failLimit,
		groups:      groups,
		sourceGroup: make(map[string]int),
		oldVersion:  make(map[string]string),
		status:      "running",
		stat:        make(map[string]*groupStat),
	}
	for gi, g := range groups {
		r.stat[g.Name] = &groupStat{total: len(g.SourceIDs)}
		for _, sourceID := range g.SourceIDs {
			r.sourceGroup[sourceID] = gi
			if v, ok := registry.VersionOf(sourceID); ok {
				r.oldVersion[sourceID] = v // 升级前版本 → 回滚目标
			}
		}
	}
	if len(groups) == 0 {
		r.status = "done"
	}
	return r, nil
}

// Report 一个数据源上报升级结果；返回本次决策。
func (r *Rollout) Report(sourceID string, ok bool) Action {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.status != "running" {
		return Hold
	}
	gi, found := r.sourceGroup[sourceID]
	if !found {
		return Hold
	}
	g := r.groups[gi]
	st := r.stat[g.Name]
	if ok {
		st.ok++
	} else {
		st.fail++
	}
	if float64(st.fail) > float64(st.total)*r.failLimit {
		r.status = "rolledback"
		return Rollback
	}
	if st.ok+st.fail >= st.total {
		if gi == len(r.groups)-1 {
			r.status = "done"
			return Complete
		}
		r.cur++
		return Advance
	}
	return Hold
}

// RollbackTarget 某数据源回滚到哪个版本（升级前版本；台账里没有则空）。
func (r *Rollout) RollbackTarget(sourceID string) string { return r.oldVersion[sourceID] }

// Target 目标版本（供回滚后反向下发旧包）。
func (r *Rollout) Target() string { return r.target }

// Status 当前状态。
func (r *Rollout) Status() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.status
}

// CurrentGroupName 当前批次名。
func (r *Rollout) CurrentGroupName() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.cur < len(r.groups) {
		return r.groups[r.cur].Name
	}
	return ""
}

// sortedSourceIDs 测试辅助：排序（保证批内顺序稳定可断言）。
func sortedSourceIDs(sourceIDs []string) []string {
	out := append([]string(nil), sourceIDs...)
	sort.Strings(out)
	return out
}
