// 来源：ph20-config-release exercises/sol-04-release-checklist/checklist.go
// 一句话说明：练习 4 参考实现——把「发布检查清单」固化成可执行的预检器：
// 对发布候选（版本/配置/开关/迁移/回滚预案）逐项自动检查并出报表。
// 人类清单易漏，机器清单可在 CI 上卡发布（主文档 3.4/3.6）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
	"regexp"
	"sort"
	"strings"
)

// ReleaseCandidate 描述一次待发布的"候选"。字段刻意只留可自动检查的最小集，
// 其余（变更说明、审批人）属于流程系统，不进预检器。
type ReleaseCandidate struct {
	Version      string      // 语义版本（构建注入）
	ConfigText   string      // 待发布配置全文（真实项目从文件读出），扫描明文 secret
	Flags        []FlagState // 本次版本涉及的 feature 开关
	Migrations   []Migration // 本次版本要跑的数据库迁移
	Released     []string    // 已发布版本列表（不含本次）
	RollbackPlan string      // 回滚预案（命令/步骤），非空才可发布
}

// FlagState 是 feature 开关在发布时的状态快照。
type FlagState struct {
	Name      string // feature 名
	MustBeOff bool   // 生命周期要求：进入 removed 前必须强制关（见 sol-03）
	IsOff     bool   // 实际是否已关
}

// Migration 是迁移脚本元数据。expand/contract 两阶段语义见 checkMigration。
type Migration struct {
	ID       int    // 单调递增序号（对应迁移文件名 001_xxx.sql 的 001）
	Breaking bool   // 破坏性变更（删列/改类型/重构），需 expand-contract
	ExpandIn string // 前置 expand 迁移所在版本（Breaking=true 时必填）
	Note     string // 人读说明
}

// Status 是单条检查的结果。
type Status int

const (
	StatusPass Status = iota
	StatusFail        // 阻塞发布
	StatusWarn        // 不阻塞但强烈建议处理
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

// Report 是单条检查的输出。
type Report struct {
	ID          string // check 的稳定标识
	Description string
	Status      Status
	Detail      string
}

// Check 是一个可执行检查项：Run 返回 error（nil = 通过）；Warn 决定失败算 FAIL 还是 WARN。
type Check struct {
	ID          string
	Description string
	Warn        bool
	Run         func(c ReleaseCandidate) error
}

// Suite 是把清单固化为可执行序列的容器。
type Suite struct {
	Checks []Check
}

// Run 执行全部检查，按 ID 排序输出报表。nil candidate 字段按零值处理。
func (s Suite) Run(c ReleaseCandidate) []Report {
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

// StandardChecks 是本仓库推荐的发布预检清单（每阶段可按业务增删）。
func StandardChecks() Suite {
	return Suite{Checks: []Check{
		{
			ID:          "version-injected",
			Description: "语义版本已注入（非 dev）",
			Run: func(c ReleaseCandidate) error {
				if c.Version == "" || c.Version == "dev" {
					return fmt.Errorf("version=%q：发布必须携带 ldflags 注入的语义版本", c.Version)
				}
				return nil
			},
		},
		{
			ID:          "no-plaintext-secret",
			Description: "配置不含明文密钥",
			Run: func(c ReleaseCandidate) error {
				secretPattern := regexp.MustCompile(`(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*[^"'\s,}]+|://[^:/\s]+:[^@/\s]+@`)
				if m := secretPattern.FindString(c.ConfigText); m != "" {
					return fmt.Errorf("检测到疑似明文密钥: %q", m)
				}
				return nil
			},
		},
		{
			ID:          "removed-flags-off",
			Description: "进入摘除期的 feature 已强制关闭",
			Run: func(c ReleaseCandidate) error {
				for _, f := range c.Flags {
					if f.MustBeOff && !f.IsOff {
						return fmt.Errorf("feature %q 必须强制关闭后再发布（见灰度开关生命周期）", f.Name)
					}
				}
				return nil
			},
		},
		{
			ID:          "breaking-migration-expanded",
			Description: "破坏性迁移已按 expand-contract 两阶段展开",
			Run: func(c ReleaseCandidate) error {
				for _, m := range c.Migrations {
					if !m.Breaking {
						continue
					}
					if m.ExpandIn == "" {
						return fmt.Errorf("破坏性迁移 #%d (%s) 缺少前置 expand 版本", m.ID, m.Note)
					}
					released := false
					for _, v := range c.Released {
						if v == m.ExpandIn {
							released = true
							break
						}
					}
					if !released {
						return fmt.Errorf("破坏性迁移 #%d 的前置 expand 版本 %q 尚未发布（要等旧服务全部升级）", m.ID, m.ExpandIn)
					}
				}
				return nil
			},
		},
		{
			ID:          "rollback-plan-present",
			Description: "回滚预案存在",
			Run: func(c ReleaseCandidate) error {
				if strings.TrimSpace(c.RollbackPlan) == "" {
					return fmt.Errorf("缺少回滚预案：镜像 tag / 上一版本 / 撤销步骤至少写一条")
				}
				return nil
			},
		},
		{
			ID:          "semver-format",
			Description: "版本号符合语义化版本",
			Warn:        true, // 非阻塞：提醒用标准 semver 便于自动化比较
			Run: func(c ReleaseCandidate) error {
				if c.Version == "" || c.Version == "dev" {
					return nil // version-injected 已拦
				}
				// 完整 semver（含 prerelease/build 元数据），尾部锚定防止前缀误判。
				semverRe := regexp.MustCompile(`^v?\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$`)
				if !semverRe.MatchString(c.Version) {
					return fmt.Errorf("version=%q 不符合 semver（期望 v1.2.3 或 v1.2.3-beta.1）", c.Version)
				}
				return nil
			},
		},
	}}
}

// Render 把报表渲染成终端友好的文本。
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
