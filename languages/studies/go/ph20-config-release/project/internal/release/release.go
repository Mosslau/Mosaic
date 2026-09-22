// Package release 把"发布检查清单"固化为可执行预检器：版本/密钥/开关/迁移/
// 回滚预案逐项自动检查，输出 PASS/FAIL/WARN 报表，供发布走查与 CI 卡点。
// 本包是 sol-04 思路的工程化提炼，检查项可插拔。
package release

import (
	"fmt"
	"regexp"
	"sort"
	"strings"
)

// Candidate 是待发布候选（只留可自动检查的最小字段集）。
type Candidate struct {
	Version      string      // 语义版本（构建注入）
	ConfigText   string      // 待发布配置全文（从文件读出），扫明文 secret
	Flags        []FlagState // 本次版本 feature 开关状态
	Migrations   []Migration // 本次要跑的迁移
	Released     []string    // 已发布版本（不含本次）
	RollbackPlan string      // 回滚预案（非空才可发布）
}

// FlagState 是 feature 开关快照。
type FlagState struct {
	Name      string
	MustBeOff bool
	IsOff     bool
}

// Migration 是迁移元数据。破坏性迁移必须走 expand-contract 两阶段。
type Migration struct {
	ID       int    // 单调递增序号（对应迁移文件 001_xxx.sql 的 001）
	Breaking bool   // 破坏性（删列/改类型/重构）→ 需 ExpandIn
	ExpandIn string // 前置 expand 迁移所在版本（Breaking=true 时必填且须已发布）
	Note     string // 人读说明
}

// Status 是单项检查结果。
type Status int

const (
	StatusPass Status = iota
	StatusFail
	StatusWarn
)

func (s Status) String() string {
	switch s {
	case StatusPass:
		return "PASS"
	case StatusFail:
		return "FAIL"
	case StatusWarn:
		return "WARN"
	}
	return "?"
}

// Report 是单项输出。
type Report struct {
	ID          string
	Description string
	Status      Status
	Detail      string
}

// Check 是可执行检查项。
type Check struct {
	ID          string
	Description string
	Warn        bool // true：失败记 WARN（不阻塞）
	Run         func(c Candidate) error
}

// Suite 是检查项集合。
type Suite struct{ Checks []Check }

// Run 执行全部检查，按 ID 排序返回报表。
func (s Suite) Run(c Candidate) []Report {
	reports := make([]Report, 0, len(s.Checks))
	for _, ch := range s.Checks {
		r := Report{ID: ch.ID, Description: ch.Description, Status: StatusPass}
		if err := ch.Run(c); err != nil {
			r.Detail = err.Error()
			if ch.Warn {
				r.Status = StatusWarn
			} else {
				r.Status = StatusFail
			}
		}
		reports = append(reports, r)
	}
	sort.Slice(reports, func(i, j int) bool { return reports[i].ID < reports[j].ID })
	return reports
}

// StandardChecks 是工程默认发布预检清单。
func StandardChecks() Suite {
	return Suite{Checks: []Check{
		{
			ID: "version-injected", Description: "语义版本已注入（非 dev）",
			Run: func(c Candidate) error {
				if c.Version == "" || c.Version == "dev" {
					return fmt.Errorf("version=%q：发布必须带 ldflags 注入的语义版本", c.Version)
				}
				return nil
			},
		},
		{
			ID: "no-plaintext-secret", Description: "配置不含明文密钥",
			Run: func(c Candidate) error {
				re := regexp.MustCompile(`(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*[^"'\s,}]+|://[^:/\s]+:[^@/\s]+@`)
				if m := re.FindString(c.ConfigText); m != "" {
					return fmt.Errorf("检测到疑似明文密钥: %q", m)
				}
				return nil
			},
		},
		{
			ID: "removed-flags-off", Description: "摘除期 feature 已强制关闭",
			Run: func(c Candidate) error {
				for _, f := range c.Flags {
					if f.MustBeOff && !f.IsOff {
						return fmt.Errorf("feature %q 必须先强制关闭再发布（见灰度生命周期）", f.Name)
					}
				}
				return nil
			},
		},
		{
			ID: "migration-ids-monotonic", Description: "迁移编号单调连续",
			Run: func(c Candidate) error {
				for i, m := range c.Migrations {
					if m.ID != i+1 {
						return fmt.Errorf("迁移编号应为 %d 却得到 %d（编号须连续单调）", i+1, m.ID)
					}
				}
				return nil
			},
		},
		{
			ID: "breaking-migration-expanded", Description: "破坏性迁移已按 expand-contract 展开",
			Run: func(c Candidate) error {
				released := map[string]bool{}
				for _, v := range c.Released {
					released[v] = true
				}
				for _, m := range c.Migrations {
					if !m.Breaking {
						continue
					}
					if m.ExpandIn == "" {
						return fmt.Errorf("破坏性迁移 #%d (%s) 缺少前置 expand 版本", m.ID, m.Note)
					}
					if !released[m.ExpandIn] {
						return fmt.Errorf("破坏性迁移 #%d 的 expand 版本 %q 尚未发布（须等旧服务全部升级）", m.ID, m.ExpandIn)
					}
				}
				return nil
			},
		},
		{
			ID: "rollback-plan-present", Description: "回滚预案存在",
			Run: func(c Candidate) error {
				if strings.TrimSpace(c.RollbackPlan) == "" {
					return fmt.Errorf("缺少回滚预案：镜像 tag / 上一版本 / 撤销步骤至少一条")
				}
				return nil
			},
		},
		{
			ID: "semver-format", Description: "版本号符合语义化版本", Warn: true,
			Run: func(c Candidate) error {
				if c.Version == "" || c.Version == "dev" {
					return nil
				}
				re := regexp.MustCompile(`^v?\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$`)
				if !re.MatchString(c.Version) {
					return fmt.Errorf("version=%q 不符合 semver（期望 v1.2.3 或 v1.2.3-beta.1）", c.Version)
				}
				return nil
			},
		},
	}}
}

// Render 渲染报表文本。
func Render(reports []Report) string {
	var sb strings.Builder
	fail := 0
	for _, r := range reports {
		mark := "  "
		switch r.Status {
		case StatusPass:
			mark = "✔"
		case StatusFail:
			mark = "✘"
			fail++
		case StatusWarn:
			mark = "!"
		}
		line := fmt.Sprintf("%s [%s] %s", mark, r.Status, r.Description)
		if r.Detail != "" {
			line += "  ← " + r.Detail
		}
		sb.WriteString(line + "\n")
	}
	if fail > 0 {
		sb.WriteString(fmt.Sprintf("\n结果：%d 项阻塞性失败——禁止发布。\n", fail))
	} else {
		sb.WriteString("\n结果：无阻塞项——可进入发布流程（WARN 项建议处理）。\n")
	}
	return sb.String()
}
