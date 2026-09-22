// 来源：ph20-config-release exercises/sol-04-release-checklist/checklist_test.go
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "testing"

func statusByID(reports []Report) map[string]Status {
	m := make(map[string]Status, len(reports))
	for _, r := range reports {
		m[r.ID] = r.Status
	}
	return m
}

func TestGoodCandidatePassesEverything(t *testing.T) {
	good := ReleaseCandidate{
		Version:    "v2.3.0",
		ConfigText: `{"dbDsn": "postgres://app@prod-db/fleet"}`, // 无明文口令
		Flags: []FlagState{
			{Name: "old-dark", MustBeOff: true, IsOff: true},
		},
		Migrations: []Migration{
			{ID: 1, Breaking: false, Note: "expand"},
			{ID: 2, Breaking: true, ExpandIn: "v2.2.0", Note: "contract"},
		},
		Released:     []string{"v2.2.0"},
		RollbackPlan: "rollout undo",
	}
	st := statusByID(StandardChecks().Run(good))
	for id, want := range map[string]Status{
		"version-injected":            StatusPass,
		"no-plaintext-secret":         StatusPass,
		"removed-flags-off":           StatusPass,
		"breaking-migration-expanded": StatusPass,
		"rollback-plan-present":       StatusPass,
		"semver-format":               StatusPass,
	} {
		if st[id] != want {
			t.Errorf("check %s = %v, want %v", id, st[id], want)
		}
	}
}

func TestPlaintextSecretBlocked(t *testing.T) {
	c := ReleaseCandidate{
		Version:      "v2.3.0",
		ConfigText:   `{"dsn": "postgres://app:SuperSecret@db/fleet", "token": "abc"}`,
		RollbackPlan: "rollout undo",
	}
	st := statusByID(StandardChecks().Run(c))
	if st["no-plaintext-secret"] != StatusFail {
		t.Errorf("含明文口令应 FAIL，got %v", st["no-plaintext-secret"])
	}
}

func TestDevVersionBlockedButWarnStaysNeutral(t *testing.T) {
	c := ReleaseCandidate{Version: "dev", RollbackPlan: "x"}
	st := statusByID(StandardChecks().Run(c))
	if st["version-injected"] != StatusFail {
		t.Errorf("dev 版本应 FAIL，got %v", st["version-injected"])
	}
	if st["semver-format"] != StatusPass {
		// semver-format 对 dev 不重复报警（由 version-injected 拦），保持 PASS。
		t.Errorf("dev 在 semver-format 应 PASS（避免重复告警），got %v", st["semver-format"])
	}
}

func TestRemovedFlagStillOnBlocked(t *testing.T) {
	c := ReleaseCandidate{
		Version:      "v2.3.0",
		RollbackPlan: "x",
		Flags:        []FlagState{{Name: "old-dark", MustBeOff: true, IsOff: false}},
	}
	st := statusByID(StandardChecks().Run(c))
	if st["removed-flags-off"] != StatusFail {
		t.Errorf("removed 开关未关应 FAIL，got %v", st["removed-flags-off"])
	}
}

func TestBreakingMigrationNeedsReleasedExpand(t *testing.T) {
	// 情形 1：无 ExpandIn。
	c := ReleaseCandidate{
		Version:      "v2.3.0",
		RollbackPlan: "x",
		Migrations:   []Migration{{ID: 1, Breaking: true, Note: "drop column"}},
	}
	st := statusByID(StandardChecks().Run(c))
	if st["breaking-migration-expanded"] != StatusFail {
		t.Errorf("缺少 ExpandIn 应 FAIL，got %v", st["breaking-migration-expanded"])
	}

	// 情形 2：ExpandIn 写了但没在已发布版本里（老服务还没全部升级）。
	c2 := c
	c2.Migrations = []Migration{{ID: 1, Breaking: true, ExpandIn: "v2.2.0", Note: "drop column"}}
	c2.Released = []string{"v2.1.0"} // v2.2.0 尚未发布
	st = statusByID(StandardChecks().Run(c2))
	if st["breaking-migration-expanded"] != StatusFail {
		t.Errorf("expand 版本未发布应 FAIL，got %v", st["breaking-migration-expanded"])
	}

	// 情形 3：非破坏性迁移不需要 expand 门槛。
	c3 := c
	c3.Migrations = []Migration{{ID: 1, Breaking: false, Note: "add column"}}
	st = statusByID(StandardChecks().Run(c3))
	if st["breaking-migration-expanded"] != StatusPass {
		t.Errorf("非破坏迁移应 PASS，got %v", st["breaking-migration-expanded"])
	}
}

func TestMissingRollbackPlanBlocked(t *testing.T) {
	c := ReleaseCandidate{Version: "v2.3.0", RollbackPlan: "  "}
	st := statusByID(StandardChecks().Run(c))
	if st["rollback-plan-present"] != StatusFail {
		t.Errorf("空回滚预案应 FAIL，got %v", st["rollback-plan-present"])
	}
}

func TestNonSemverVersionWarnsOnly(t *testing.T) {
	// 版本号缺 patch（v2.3）不合法 → WARN 不阻塞。
	c := ReleaseCandidate{Version: "v2.3", RollbackPlan: "x"}
	st := statusByID(StandardChecks().Run(c))
	if st["semver-format"] != StatusWarn {
		t.Errorf("非严格 semver 应 WARN，got %v", st["semver-format"])
	}
	if st["version-injected"] != StatusPass {
		t.Errorf("版本非 dev 时 version-injected 应 PASS，got %v", st["version-injected"])
	}

	// prerelease（v2.3.0-beta.1）是合法 semver，不应告警。
	ok := ReleaseCandidate{Version: "v2.3.0-beta.1", RollbackPlan: "x"}
	if got := statusByID(StandardChecks().Run(ok))["semver-format"]; got != StatusPass {
		t.Errorf("prerelease semver 应 PASS，got %v", got)
	}
}
