# ph20 配置管理与发布策略示例

> 六个示例覆盖本阶段"可运行"的知识点主干：三来源配置读取（ex01）→ 分层合并语义（ex02）→ feature flag 灰度语义（ex03）→ 版本号注入与构建信息（ex04）→ 发布决策与回滚（ex05）→ 热更新边界与原子热替换（ex06）。每个示例是自包含的独立 Go module，零第三方依赖，在 go1.25.6 上按文件头命令可复现（`go vet ./...`、`go build ./...`、`go test ./...`）。

| 示例 | 一句话说明 | 对应主文档 | 运行/测试命令（进入各自子目录） |
|------|-----------|-----------|------------------------------|
| ex01-env-file-flag | 同一份 Config 被 env/file/flag 三来源独立提供，LookupEnv 区分"未设置 vs 空串" | 3.1 | `go run . -port 9000 -name demo`；`go test ./...`（5 个加载测试） |
| ex02-config-layering-merge | 分层合并：default→file→env→flag 逐层叠加、map 递归合并、数组整替换、env 扁平键类型感知覆盖、来源可追溯 | 3.2 | `go run . -port 6060`；`go test ./...`（7 个合并语义测试） |
| ex03-feature-flag | feature flag：关/开/按用户百分比三种策略、一致性分桶哈希、灰度放量单调、生命周期、故障兜底 | 3.3 | `go run .`；`go test ./...`（8 个灰度测试） |
| ex04-version-injection | 版本注入：ldflags -X 语义版本 + runtime/debug.ReadBuildInfo 的 VCS/Go 信息，运行期版本自报 | 3.5 | `go build -ldflags "-X main.version=v1.2.3 -X main.commit=9f1a2b3 -X main.date=2026-09-03T00:00:00Z" -o /tmp/ph20-ex04 . && /tmp/ph20-ex04`；`go test ./...`（3 个版本测试） |
| ex05-rollout-decision | 发布决策状态机：健康曲线驱动 hold/advance/rollback/complete，确定性回放发布与回滚演练 | 3.4 | `go run .`；`go test ./...`（5 个决策测试） |
| ex06-hot-reload-boundary | 热更新边界分类 + 原子快照热替换：运行中推送新 log.level，后续请求无锁即用新值 | 3.7 | `go run .`；`go test ./...`（含 `go test -race ./...`，5 个边界/并发测试） |

## 验证说明

- 全部示例 go.mod 为 `go 1.25.0`，与仓库语言版本档一致；`go vet ./...`、`go build ./...`、`go test ./...` 三条命令在每个子目录内执行。
- 验证环境：go1.25.6（darwin/arm64）；GOCACHE/GOMODCACHE 重定位到 /tmp 临时目录（`GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache GOPROXY=off GOSUMDB=off`）；零第三方依赖，可离线复现。
- **验证状态：已验证**——go1.25.6 本机实测：6 个模块 `go vet ./... && go build ./... && go test ./...` 全绿、gofmt 合规（`gofmt -l .` 无输出）；ex06 另跑 `go test -race ./...` 全绿；ex04 另实测 ldflags 注入构建并运行验证注入生效。
- **产物纪律**：ex04 的 `go build` 产物示例写 /tmp（`-o /tmp/ph20-ex04`），不在仓库落二进制；若在任何示例目录内执行 `go build` 生成了二进制，请删除或同样改用 `-o /tmp/<名字>`。
- 正确性自证设计：6 个示例全部带单元测试，单测通过即证明三来源语义、覆盖优先级、灰度一致性、版本注入、发布决策、热更原子性各自符合预期。
- 真配置中心（etcd/consul 客户端、Viper 深度接入、Apollo）本机无服务可连，未落地为示例模块——相关安装/运行命令见主文档 3.2 与 4.4，均标注「未在本环境验证」。
