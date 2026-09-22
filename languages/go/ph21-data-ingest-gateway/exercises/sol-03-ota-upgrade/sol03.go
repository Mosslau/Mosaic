// 来源：ph21-data-ingest-gateway exercises/sol-03-ota-upgrade/sol03.go
// 一句话说明：练习 3 参考实现——OTA 分批灰度决策器：车队基线快照、VIN 分组下发、
// 逐台上报驱动 hold/advance/rollback/complete；决策确定性纯函数可离线回放。
// 差异点 vs ex04：这里把"车队版本基线"独立成 FLEET 结构，Rollout 从基线快照生成
// 回滚目标（升级前的版本），贴近"OTA 服务要有车端版本台账"的要求（主文档 3.10）。
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

// Device 车端台账条目（服务端维护"每车现在装什么版本"）。
type Device struct {
	Vin     string
	Version string
}

// Fleet 车队版本台账。
type Fleet struct {
	mu      sync.RWMutex
	devices map[string]*Device // vin → 台账
}

// NewFleet 建车队台账。
func NewFleet() *Fleet { return &Fleet{devices: map[string]*Device{}} }

// Register 录入一台车（上线/首次联网时上报当前版本）。
func (f *Fleet) Register(d Device) {
	f.mu.Lock()
	f.devices[d.Vin] = &d
	f.mu.Unlock()
}

// VersionOf 查某车当前版本。
func (f *Fleet) VersionOf(vin string) (string, bool) {
	f.mu.RLock()
	defer f.mu.RUnlock()
	d, ok := f.devices[vin]
	if !ok {
		return "", false
	}
	return d.Version, true
}

// Upgrade 车辆升级成功后的台账更新。
func (f *Fleet) Upgrade(vin, newVersion string) {
	f.mu.Lock()
	if d, ok := f.devices[vin]; ok {
		d.Version = newVersion
	}
	f.mu.Unlock()
}

// Group 灰度批次：一批 VIN。
type Group struct {
	Name string
	VINs []string
}

// Rollout 一场 OTA 灰度。
type Rollout struct {
	target     string
	failLimit  float64
	groups     []*Group
	vinGroup   map[string]int
	oldVersion map[string]string // 升级前版本快照 = 回滚目标

	mu     sync.Mutex
	status string // running/done/rolledback
	cur    int
	stat   map[string]*groupStat
}

type groupStat struct {
	total, ok, fail int
}

// NewRollout 从车队台账快照创建一场灰度。目标版本 t 必须 != 任一车当前版本由调用方保证。
func NewRollout(target string, failLimit float64, groups []*Group, fleet *Fleet) (*Rollout, error) {
	if failLimit <= 0 || failLimit >= 1 {
		return nil, fmt.Errorf("失败率上限须在 (0,1) 内, got %v", failLimit)
	}
	r := &Rollout{
		target:     target,
		failLimit:  failLimit,
		groups:     groups,
		vinGroup:   make(map[string]int),
		oldVersion: make(map[string]string),
		status:     "running",
		stat:       make(map[string]*groupStat),
	}
	for gi, g := range groups {
		r.stat[g.Name] = &groupStat{total: len(g.VINs)}
		for _, vin := range g.VINs {
			r.vinGroup[vin] = gi
			if v, ok := fleet.VersionOf(vin); ok {
				r.oldVersion[vin] = v // 升级前版本 → 回滚目标
			}
		}
	}
	if len(groups) == 0 {
		r.status = "done"
	}
	return r, nil
}

// Report 一台车上报升级结果；返回本次决策。
func (r *Rollout) Report(vin string, ok bool) Action {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.status != "running" {
		return Hold
	}
	gi, found := r.vinGroup[vin]
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

// RollbackTarget 某车回滚到哪个版本（升级前版本；台账里没有则空）。
func (r *Rollout) RollbackTarget(vin string) string { return r.oldVersion[vin] }

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

// sortedVINs 测试辅助：排序（保证批内顺序稳定可断言）。
func sortedVINs(vins []string) []string {
	out := append([]string(nil), vins...)
	sort.Strings(out)
	return out
}
