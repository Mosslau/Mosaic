# 阶段项目：标准 Go 项目模板

对应 roadmap ph05 推荐项目第一个「标准 Go 项目模板」。用 `cmd/` + `internal/` + `pkg/` 三层标准布局搭一个开箱即用的项目骨架，内置可运行的「设备状态管理 CLI」示例命令——拿到手就能当新 Go 项目的起点。

## 需求

- `cmd/device-cli` 程序入口：`add` / `list` / `status` / `delete` / `config` 五个子命令 + `-selfcheck` 内置自检
- `internal/config` 配置加载：默认值 → JSON 文件 → 环境变量覆盖 → 集中校验（fail fast）
- `internal/device` 设备管理业务：增删改查 + 状态校验 + JSON 文件持久化（跨进程数据不丢）
- `pkg/status` 公共库：状态常量与合法性校验，被 internal 引用（体现「pkg 可被模块内任意包引用」）

## 功能清单

| 功能 | 说明 |
|------|------|
| 标准布局 | cmd/ 入口 + internal/ 业务包 + pkg/ 公共库，`go build ./...` 一键构建 |
| 子命令 | add / list / status / delete / config，`flag.NewFlagSet` 子命令解析 |
| 配置加载 | 默认值 → JSON 文件 → 环境变量覆盖 → 集中校验，错误 `%w` 包装 |
| 文件持久化 | 设备数据存 JSON 文件，重开进程数据仍在 |
| 状态校验 | pkg/status 命名常量 + `Valid()`，非法状态启动期拒绝 |
| 内置自检 | `-selfcheck` 跑通 配置加载 / 增删改查 / 状态校验 / 持久化重载 |
| 单元测试 | internal/device 表格驱动测试，`go test ./...` 通过 |

## 验收标准

- [ ] `gofmt -l .` 零差异、`go vet ./...` 零报告、`go test ./...` 全部通过
- [ ] `go run ./cmd/device-cli -config config.example.json add -id D01 -name 温度传感器` 添加成功，随后 `go run ./cmd/device-cli list` 能看到该设备（文件持久化生效）
- [ ] `go run ./cmd/device-cli status -id D01 -state online` 更新成功；`-state bogus` 被拒绝并以非零码退出
- [ ] `go run ./cmd/device-cli -selfcheck` 输出「自检通过」，退出码 0
- [ ] 代码符合 ph05 要点：internal 编译器级隔离、显式 error、库代码（internal/）不打日志

## 扩展方向

- 设备数据改用 MySQL / Redis（ph10 数据库阶段）——把 `internal/device` 的存储面接口化即可替换
- 加入 `go test -race` 与 benchmark（ph08 测试阶段深入 testing 生态）
- 用 `go.work` 把本项目与共享库拆成多模块联调（ph05 示例 3）
- 接入 `log/slog` 结构化日志（ph07 标准库阶段）
- Docker 化部署 + 健康检查（ph12 云原生与部署阶段）

## 验证环境

- Go 1.22.2（darwin/arm64），无第三方依赖
- 运行命令：
  - `go run ./cmd/device-cli -config config.example.json add -id D01 -name "温度传感器"`
  - `go run ./cmd/device-cli list`
  - `go run ./cmd/device-cli status -id D01 -state online`
  - `go run ./cmd/device-cli config`
  - `go run ./cmd/device-cli -selfcheck`
  - `go test ./...`
- 验证状态：已验证（Go 1.22.2）
