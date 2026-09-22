# ph15 阶段项目：Go 工具链检查脚本（toolcheck）

## 需求

对应 roadmap §15「推荐项目」之「Go 工具链检查脚本」。本阶段学的核心是版本与工具链管理，但"项目要求的 Go 版本到底是多少、当前工具链够不够"在团队里往往只存在于口头约定——本项目把它变成**机器可读的检查**：`toolcheck` 读一个 go.mod（从 -dir 向上查找或 -mod 直指），解析 `module / go / toolchain` 三行，与编译它自己的工具链（`runtime.Version()`）对比，输出三态结论与退出码，支持 `-json` 供 CI 消费、`-want` 施加团队策略门槛。语义与 go 命令实测行为对齐（主文档 3.6 节）：

- **go 行 = 硬门槛**：当前工具链低于 go 行时构建必失败（GOTOOLCHAIN=auto 会尝试下载、=local 直接报错）→ `fail`
- **toolchain 行 = 首选**：高于当前时 auto 会下载切换、local 会忽略 → `warn`（版本不统一风险）
- 两者都满足 → `ok`；`-want` 额外抬高门槛 → 不满足即 `fail`

## 功能清单

- [x] `cmd/toolcheck` CLI：`-dir`（向上找 go.mod）、`-mod`（直指文件）、`-want`（策略门槛）、`-json`（结构化输出）
- [x] 三态结论与退出码：ok/warn = 0，fail = 1，用法/解析错误 = 2
- [x] `internal/gomodfile`：go.mod 定位（FindUp）+ module/go/toolchain 三行解析（容忍注释与未知指令）
- [x] `internal/vercmp`：Go 版本数字段比较（go 前缀容错、缺段补 0）
- [x] `internal/check`：三态判定（纯函数，注入 current 便于测试）
- [x] 全量验证：`go test ./...`、`go vet ./...`、`go test -race ./...` 通过

## 运行方式（已在 go1.25.6 / darwin / arm64 验证，零第三方依赖）

```bash
cd languages/studies/go/ph15-version-toolchain/project
go test ./... && go vet ./... && go test -race ./...   # 验证：测试 + 竞态检测
go run ./cmd/toolcheck                                 # 检查 project 自身（OK, exit 0）
go run ./cmd/toolcheck -json                           # JSON 输出
go run ./cmd/toolcheck -want go1.26.0                  # 团队策略门槛：当前 1.25.6 不满足 → fail
go run ./cmd/toolcheck -mod ../exercises/sol-03-goreq/testdata/gohigh.mod   # 检查任意 go.mod
```

## 验收标准

- [ ] **三态判定与 go 命令实测一致**：go 行 1.99.0 的 fixture → fail（exit 1）；toolchain go1.26.0 的 fixture → warn；自身 go.mod（go 1.25.0）→ ok
- [ ] **`-want` 策略门槛生效**：`-want go1.26.0` 把"自身 go.mod 满足"升级为 fail；`-want go1.24.0` 不改变 ok
- [ ] **`-json` 输出可被机器消费**：status/message/module/go_line/toolchain/current 字段齐全
- [ ] **测试断言语义而非巧合**：vercmp 覆盖前缀/缺段/大小比较；gomodfile 覆盖注释、无 go 行、未知指令；check 覆盖三态 + want 策略
- [ ] **`go test -race ./...` 通过**

## 实测记录（go1.25.6，Apple M4 Pro，2026-09-02）

**`go run ./cmd/toolcheck`（自身 go.mod）**：

```
go.mod    : …/project/go.mod
module    : tenetlang/go/ph15-version-toolchain/project
go 行     : 1.25.0
toolchain : -（未声明）
当前工具链: go1.25.6（编译本程序的 go）
结论 [ok]: 当前 go1.25.6 ≥ go.mod 要求（go 1.25.0）
exit=0
```

**`go run ./cmd/toolcheck -mod ../exercises/sol-03-goreq/testdata/gohigh.mod`（go 行 1.99.0）**：

```
结论 [fail]: 当前 go1.25.6 < go 行 1.99.0（硬门槛）
   GOTOOLCHAIN=auto 会尝试下载更新工具链；=local 会直接报错
exit=1
```

**`go run ./cmd/toolcheck -json -want go1.26.0`**：

```json
{
  "mod_file": "…/project/go.mod",
  "module": "tenetlang/go/ph15-version-toolchain/project",
  "go_line": "1.25.0",
  "toolchain": "",
  "current": "go1.25.6",
  "want": "go1.26.0",
  "status": "fail",
  "message": "当前 go1.25.6 \u003c 策略要求 go1.26.0"
}
exit=1
```

**测试结果**：`go test ./...` 全绿（internal/check：TestRun 5 组 + TestRunWantPolicy 2 组；internal/gomodfile：TestParse 5 组 + TestParseInvalid + TestFindUp；internal/vercmp：TestCompare 8 组 + TestLess），`go vet ./...` 零输出，`go test -race ./...` 零数据竞争。

**结论解读**（对应主文档 3.6 节）：检查器的三态语义不是拍脑袋——它复刻了 go 命令实测行为：go 行 1.99.0 时 go 命令自己会拒绝构建（GOTOOLCHAIN=local 报 `go.mod requires go >= 1.99.0 (running go 1.25.6; GOTOOLCHAIN=local)`）；toolchain 行 go1.26.0 时 go 命令在 auto 模式尝试下载 go1.26.0、local 模式则忽略该行继续构建——所以前者是 fail（硬错）、后者是 warn（版本可能不统一）。toolcheck 把"当前工具链 vs go.mod 要求"变成一个 pre-flight 检查，任何人在任何机器上 `toolcheck` 一下就知道构建会不会被工具链坑。

## 扩展方向（可选）

- 扫 go.work：读 workspace 的 use 列表，对每个模块各跑一次检查（衔接主文档 3.5 节 workspace）
- 接 CI：`toolcheck -json` 输出与 GitHub Actions/GitLab CI 的退出码联动（衔接 ph12 云原生阶段的 CI/CD）
- 加 `-mode publish`：把 `go list -m -json` 的 module 版本一并纳入报告（衔接 ph20 配置与发布策略的版本号注入）
- 加 Windows/旧版 Go 兼容：vercmp 处理 rc/beta 后缀（当前只覆盖发布版，见 internal/vercmp 包注释）
