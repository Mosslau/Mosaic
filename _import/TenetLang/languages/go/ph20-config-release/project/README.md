# ph20 阶段项目：多环境配置模块（release-server）

## 需求

把 roadmap §20 推荐项目「多环境配置模块」落地为**离线可测的发布准备工程**：一个服务发布前要回答的四件事（roadmap 阶段验收 1~3 的载体）——**dev/test/prod 用不同配置（配置分层 + 来源可追溯）**、**快速定位运行版本（ldflags 注入 + VCS 兜底）**、**灰度开关裁决（kill switch/白名单/百分比）**、**发布预检清单（版本/密钥/开关/迁移/回滚自动检查）**——拧成一个可执行走查 CLI `release-server`。跑一遍 `release-server -profile prod`，等于看一份"该服务在这个环境能不能安全发布"的报告。

工程兑现的 ph20 主题线：
- **配置分层**：默认 → `config.<env>.json` → env → flag 逐层覆盖，每字段来源可追溯（examples/ex02、exercises/sol-01 工程化）
- **版本注入**：`-X internal/version.Version=...` + `ReadBuildInfo` 的 VCS 兜底，`-version`/启动日志自报（examples/ex04、sol-02）
- **灰度开关**：HardOff > 白名单 > 百分比分桶 > 兜底的确定性裁决，多实例一致（examples/ex03、sol-03）
- **发布预检**：把"发布要可回滚""数据库变更要兼容旧版本服务"固化成机器检查项，CI 可卡点（sol-04 的包形态）
- **迁移纪律**：破坏性迁移必须 expand-contract 两阶段——前置 expand 版本已发布（旧服务全部升级）才允许 contract（删字段）

## 功能清单

- [x] 多环境分层配置加载（default→file→env→flag），必填项 fail-fast（`*config.RequiredError` 可 errors.As 命中）
- [x] 字段来源表（port/name/dbDsn 等 ← default/file/env/flag），排障定位
- [x] 版本自报：ldflags 注入语义版本 + `runtime/debug.ReadBuildInfo` VCS/Go 信息；`-version` 与 JSON 输出
- [x] 灰度裁决：白名单 + 百分比 + HardOff 优先级，纯函数确定性（跨实例一致）
- [x] 发布预检：7 项自动检查（版本注入/明文密钥/摘除开关/迁移编号/expand-contract/回滚预案/semver），PASS/FAIL/WARN 报表
- [x] e2e 验收测试：多环境差异、覆盖顺序、必填报错、灰度确定性、好候选全绿、坏候选全拦
- [x] 真配置中心（etcd/consul）接入点保留（见下），离线形态用注入式 env/file

## 目录结构

```
project/
├── go.mod                    # module tenetlang/go/ph20-config-release/project（go 1.25.0）
├── doc.go                    # 根包文档（依赖方向图）
├── e2e_test.go               # 端到端验收（离线、零第三方、可 -race）
├── configs/                  # 多环境配置样例 config.{dev,test,prod}.json（演示值，无真实密钥）
├── cmd/release-server/       # 组装点：profile 选择 + 走查输出
└── internal/
    ├── config/               # 分层加载：Config/Defaults/Load + SourceMap + RequiredError
    ├── version/              # 注入变量（Version/Commit/BuildDate）+ Gather/Summary/JSON
    ├── feature/              # 灰度裁决：Feature/Validate/Evaluate/HashBucket
    └── release/              # 发布预检：Candidate/Check/Suite/StandardChecks/Render
```

依赖方向（单向向内，无环）：

```text
cmd/release-server ──▶ internal/config  internal/version
       └────────────▶ internal/feature  internal/release
e2e_test.go ────────▶ internal/{config,version,feature,release}
```

## 验证环境与命令

- 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（只用标准库）；go 命令带仓库统一重定位环境（`GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache GOPROXY=off GOSUMDB=off`），可离线复现
- 构建/测试/静态检查：`go build ./... && go test ./... && go vet ./...`（另推荐 `go test -race ./...`）
- 运行走查（在 project/ 目录内，需相对 configs/）：

```bash
# 1. dev 版本走查：version=dev 被预检拦下（教学：发布必须带注入版本）
go run ./cmd/release-server -profile test

# 2. 模拟注入后走查：全绿（-as-version 仅供离线演示；真实用 ldflags）
go run ./cmd/release-server -profile prod -as-version v2.1.0

# 3. 真实注入构建（-X 打到 internal/version 的导出变量）：
go build -ldflags "-X tenetlang/go/ph20-config-release/project/internal/version.Version=v2.1.0 \
    -X tenetlang/go/ph20-config-release/project/internal/version.Commit=abc1234 \
    -X tenetlang/go/ph20-config-release/project/internal/version.BuildDate=2026-09-03T00:00:00Z" \
    -o /tmp/ph20-server ./cmd/release-server
/tmp/ph20-server -profile prod
```

- **验证状态：已验证**——go1.25.6 本机实测 vet/build/test 全绿、`go test -race ./...` 全绿、gofmt 合规；三条运行/构建命令均有实测输出（走查 1 拦 dev 版本、走查 2 全绿、ldflags 注入后 `version=v2.1.0 commit=abc1234`）。

## 真配置中心切换

本仓库（macOS）无 Docker/etcd/consul，配置中心客户端不在工程内落地（离线形态用注入式 env/file 已覆盖可测语义）。在有配置中心的环境接入（主文档 3.2/4.4，均标注「未在本环境验证」）：

```bash
# etcd：把 file 层换成 etcd watch（配置键 → 值），env/flag 优先级不变
go get go.etcd.io/etcd/client/v3@latest
# 单机起 etcd（有 Docker 时）：
docker run -d -p 2379:2379 --name etcd quay.io/coreos/etcd:v3.5.16 \
  etcd --advertise-client-urls http://0.0.0.0:2379 --listen-client-urls http://0.0.0.0:2379
# 客户端：clientv3.New(cfg) → Get/Watch("/services/release-server/", clientv3.WithPrefix())

# consul：
go get github.com/hashicorp/consul/api@latest
docker run -d -p 8500:8500 --name consul hashicorp/consul:1.20
# 客户端：api.NewClient → KV().Get/Watch → 把热更新键 push 进 atomic.Snapshot（见 examples/ex06）
```

该路径「未在本环境验证」（本机无 Docker/etcd/consul）；命令可复现，验证以你机器上的实际服务为准。

## 验收标准

- [ ] `go build ./... && go test ./... && go vet ./...` 通过（go1.25.6 本机实测通过（已验证））；`go test -race ./...` 通过
- [ ] `go run ./cmd/release-server -profile dev/test/prod` 三次输出不同配置，且来源表标出 file 层键
- [ ] 不带 `-as-version` 时预检拦下 version=dev；带 `-as-version v2.1.0`（或真实 ldflags 注入）时预检全绿
- [ ] 能指认四件事各落在哪个包哪一行：分层覆盖（internal/config → Load/applyString/SourceMap）、版本注入（internal/version 导出变量 + Gather 的 ReadBuildInfo）、灰度裁决（internal/feature → Evaluate 优先级）、预检清单（internal/release → StandardChecks 的 7 个 Run）
- [ ] 破坏实验：把 configs/config.prod.json 的 dbDsn 改成 `postgres://app:Leak@db/fleet` → 预检 `no-plaintext-secret` FAIL（敏感信息不能进仓库）；改回后变绿——能解释这条防线
- [ ] 破坏实验：把 e2e 里 good 候选的 Migrations 换成 `{ID:2, Breaking:true, ExpandIn:""}` → `breaking-migration-expanded`/`migration-ids-monotonic` 变红——能解释 expand-contract 为什么是"旧服务升级"的栅栏

## 扩展方向

- 把 `internal/config` 的 file 层换成 etcd/consul KV + watch（见上），热更新键走 `atomic.Pointer[Snapshot]`（examples/ex06 语义），不重启生效；重启类键（port/dbDsn）继续走文件/env/flag
- 迁移真实化：接入 golang-migrate / goose 的迁移文件与顺序，预检直接从迁移目录读 ID/破坏性标记，而非手工构造
- 把 release 预检挂成 `cmd/release-server check` 子命令供 CI 调用，exit code 按有无 FAIL 返回（当前 Render 已区分文本）
- 配置加密：dbDsn 等 secret 用 KMS/age 加密落盘，加载时解密（对应 roadmap 必会概念「敏感信息不能进仓库」的再进一步）
- 与 ph21 衔接：release-server 作为服务骨架，接上 MQTT/指标消费即进入通用数据采集平台（roadmap 第 21 节）
