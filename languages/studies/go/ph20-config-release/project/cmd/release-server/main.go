// 来源：ph20-config-release project cmd/release-server/main.go
// 一句话说明：组装点——把 config（多环境加载）/version（自报）/feature（灰度）
// /release（发布预检）四件套拧成一个「离线发布走查 CLI」：跑一遍 = 看到一份
// 服务在某个环境里的完整发布准备报告（主文档 3.2~3.6 落地）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行（dev，预检会被版本拦住）：go run ./cmd/release-server -profile test
// 演示全绿（模拟注入）：go run ./cmd/release-server -profile test -as-version v2.1.0
// 真实注入构建：
//
//	go build -ldflags "-X tenetlang/go/ph20-config-release/project/internal/version.Version=v2.1.0 \
//	  -X tenetlang/go/ph20-config-release/project/internal/version.Commit=abc1234" -o /tmp/ph20-server ./cmd/release-server
//	/tmp/ph20-server -profile prod         验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"fmt"
	"io"
	"os"
	"strings"

	"tenetlang/go/ph20-config-release/project/internal/config"
	"tenetlang/go/ph20-config-release/project/internal/feature"
	"tenetlang/go/ph20-config-release/project/internal/release"
	"tenetlang/go/ph20-config-release/project/internal/version"
)

func main() {
	os.Exit(run(os.Args[1:], os.Stdout))
}

// run 处理参数并写输出，返回退出码（逻辑与 os.Exit 分离便于测试）。
func run(args []string, out io.Writer) int {
	// 1. 解析 CLI：-profile 是环境选择器，其余参数转给 config.Load 的 flag 层。
	profile, rest, err := splitProfile(args)
	if err != nil {
		fmt.Fprintln(out, err)
		return 2
	}
	var asVersion string
	filtered := make([]string, 0, len(rest))
	for i := 0; i < len(rest); i++ {
		if rest[i] == "-as-version" && i+1 < len(rest) {
			asVersion = rest[i+1]
			i++
			continue
		}
		filtered = append(filtered, rest[i])
	}

	// 2. 多环境配置加载（默认 → config.<profile>.json → env → flag）。
	cfg, src, err := config.Load(config.Options{Profile: profile, Dir: "./configs", Args: filtered})
	if err != nil {
		fmt.Fprintf(out, "配置加载失败：%v\n", err)
		return 1
	}
	fmt.Fprintf(out, "== 配置（profile=%s）==\n", profile)
	fmt.Fprintf(out, "   port=%d name=%q debug=%v region=%q logLevel=%q\n",
		cfg.Port, cfg.Name, cfg.Debug, cfg.Region, cfg.LogLevel)
	fmt.Fprintf(out, "   dbDsn=%s（已脱敏）\n", maskDSN(cfg.DBDSN))
	fmt.Fprintf(out, "   ← 字段来源：port=%s name=%s dbDsn=%s（发布排障定位）\n",
		src["port"], src["name"], src["dbDsn"])

	// 3. 版本自报：优先用注入值；-as-version 只用于离线演示"注入后的样子"。
	v := version.Gather()
	if asVersion != "" {
		v.Version = asVersion
	}
	fmt.Fprintln(out, "\n== 版本自报 ==")
	fmt.Fprintln(out, "   "+v.Summary())

	// 4. 灰度裁决：同一规则，多用户各得其所（realtime-map 50% + 白名单）。
	fmt.Fprintln(out, "\n== 灰度裁决（realtime-map：白名单 + 50% 放量）==")
	internal := func(u string) bool { return strings.HasPrefix(u, "user-000") }
	f := feature.Feature{Name: "realtime-map", Allow: internal, Percent: 50}
	if err := f.Validate(); err != nil {
		fmt.Fprintln(out, "   feature 规则非法：", err)
		return 1
	}
	for _, u := range []string{"user-0000", "user-0000", "user-0042", "user-0099", "user-0077"} {
		fmt.Fprintf(out, "   %-10s → %-5v（跨实例一致：同一 user 恒同判定）\n", u, feature.Evaluate(f, u))
	}

	// 5. 发布预检：候选 = 配置全文 + 版本 + 迁移计划 + 回滚预案。
	//    未注入版本（version=dev）会被 version-injected 拦住——这正是预检的目的；
	//    加 -as-version 模拟注入后走全绿路径（坏候选的拦截用例见 e2e_test.go）。
	fmt.Fprintln(out, "\n== 发布预检 ==")
	cand := release.Candidate{
		Version:      v.Version,
		ConfigText:   cfgTextFor(profile),
		RollbackPlan: "rollout undo --to v1.9.0",
		Flags: []release.FlagState{
			{Name: "old-dark", MustBeOff: true, IsOff: true},
		},
		Migrations: []release.Migration{
			{ID: 1, Breaking: false, Note: "add speed_kmh (expand)"},
			{ID: 2, Breaking: true, ExpandIn: "v1.9.0", Note: "drop legacy speed (contract)"},
		},
		Released: []string{"v1.9.0"},
	}
	fmt.Fprint(out, release.Render(release.StandardChecks().Run(cand)))
	return 0
}

// splitProfile 抽出 -profile（选择器），返回环境名与剩余参数。
func splitProfile(args []string) (string, []string, error) {
	profile := "dev"
	var rest []string
	for i := 0; i < len(args); i++ {
		if args[i] == "-profile" && i+1 < len(args) {
			profile = args[i+1]
			i++
			continue
		}
		if v, ok := strings.CutPrefix(args[i], "-profile="); ok {
			profile = v
			continue
		}
		rest = append(rest, args[i])
	}
	return profile, rest, nil
}

// cfgTextFor 读回 profile 配置文件原文当候选配置（真实工程用合并后全文）。
func cfgTextFor(profile string) string {
	data, err := os.ReadFile("./configs/config." + profile + ".json")
	if err != nil {
		return "" // 预检的明文密钥检查对缺失文件宽松处理（加载层已把关）
	}
	return string(data)
}

// maskDSN 打印脱敏后的连接串。
func maskDSN(dsn string) string {
	if dsn == "" {
		return "(空)"
	}
	return "postgres://user:***@host:5432/app"
}
