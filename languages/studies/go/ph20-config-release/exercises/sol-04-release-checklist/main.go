// 来源：ph20-config-release exercises/sol-04-release-checklist/main.go
// 一句话说明：demo——对两份发布候选跑预检：一份合规通过，一份带四处问题
// （dev 版本、明文密钥、removed 开关忘关、破坏性迁移缺 expand 版本）被拦下
// （主文档 3.4/3.6）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import "fmt"

func main() {
	fmt.Println("== 发布候选 A：合规 ==")
	good := ReleaseCandidate{
		Version:    "v2.3.0",
		ConfigText: `{"port": 8443, "dbDsn": "postgres://app@prod-db/fleet"}`,
		Flags: []FlagState{
			{Name: "old-dark", MustBeOff: true, IsOff: true},
			{Name: "new-reports", MustBeOff: false, IsOff: false},
		},
		Migrations: []Migration{
			{ID: 1, Breaking: false, Note: "add speed_kmh column (expand)"},
			{ID: 2, Breaking: true, ExpandIn: "v2.2.0", Note: "drop legacy speed column (contract)"},
		},
		Released:     []string{"v2.2.0"},
		RollbackPlan: "rollout undo / 回退镜像 tag v2.2.0",
	}
	fmt.Print(Render(StandardChecks().Run(good)))

	fmt.Println("\n== 发布候选 B：四处问题 ==")
	bad := ReleaseCandidate{
		Version:    "dev", // 没注入
		ConfigText: `{"dbDsn": "postgres://app:SuperSecret@prod-db/fleet"}`,
		Flags: []FlagState{
			{Name: "old-dark", MustBeOff: true, IsOff: false}, // 忘关
		},
		Migrations: []Migration{
			{ID: 1, Breaking: true, ExpandIn: "", Note: "drop legacy speed column (contract)"}, // 无 expand
		},
		Released:     []string{"v2.2.0"},
		RollbackPlan: "",
	}
	fmt.Print(Render(StandardChecks().Run(bad)))
}
