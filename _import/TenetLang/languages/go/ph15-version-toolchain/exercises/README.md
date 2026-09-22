# ph15 Go 版本、工具链练习

> 先自己做，再对照 `sol-*` 参考实现。每题标注难度（★~★★★）。三题与 roadmap §15 对齐：练习 1 ↔「创建多模块 workspace」、练习 2 ↔「升级一个依赖版本」、练习 3 ↔「记录项目 Go 版本要求」。roadmap 推荐项目「Go 工具链检查脚本」由阶段 project/ 落地，「多服务 workspace 示例」由练习 1（与 examples/ex04-workspace）覆盖。
> 全部参考实现已在 go1.25.6（darwin/arm64）验证（`go test`、`go vet`、`go test -race` 全绿），零第三方依赖；sol-01/sol-03 进入各自目录运行，sol-02 进入 consumer 子目录运行。

## 练习 1：创建多模块 workspace（★★）

**目标**：亲手建一个 go.work 多模块 workspace——一个 app 模块依赖一个本地 lib 模块，不发布、不加 replace 也能互相 import，理解「go work 适合多模块本地开发」。

**要求**：
- 建两个模块：`lib`（包名 lib，提供 `Hello(name string) string`）与 `app`（包名 main，import lib 并打印问候语）
- 用 `go work init ./app ./lib` 建立 workspace（也可先写代码再 `go work use` 添加）
- app/go.mod 的 require 行写 lib 模块路径 + `v0.0.0`（占位版本），**不加** replace
- 验收自证：`go env GOWORK` 输出 go.work 路径、`go run ./app` 能跑通、删掉 go.work 后同一命令报错

**验收**：`go run ./app` 输出含 lib 的问候语；`go test ./app/... ./lib/...` 通过；能说出为什么 workspace 根目录的 `./...` 不能用（go1.25.6 实测行为）

**提示**：sol-01-workspace 目录；先想清楚 v0.0.0 为什么"没有 replace 也能编译"——workspace 把模块路径映射到本地目录，这就是它与 replace 的机制差异（对比见主文档 3.5 节表格）

## 练习 2：升级一个依赖版本（★★★）

**目标**：体会「依赖升级需要测试验证」——一个依赖从 v1.0.0 升到 v1.1.0，签名没变但行为变了，契约测试当场拦截；随后用"适配"或"回滚"收场。

**要求**：
- 消费者模块依赖 `example.com/greet`（replace 指向本地 v1.0.0 目录），写一个**契约测试**：断言 `Greet("service-a")` 以 `"Hello, "` 开头
- 模拟升级：`go mod edit -require=example.com/greet@v1.1.0` + 把 replace 切到 v1.1.0 目录 + `go mod tidy`，跑测试观察失败输出
- 给出两条收场路径并各跑一遍：① 回滚（edit 回 v1.0.0）② 适配（把契约断言更新成 v1.1.0 的 `"Hey, "` 前缀）

**验收**：v1.0.0 锁定态 `go test ./... && go vet ./... && go test -race ./...` 全绿；升级后测试**必须**失败并打印 `greet.Greet() = "Hey, service-a!", want prefix "Hello, "` 这类信息；回滚或适配后重新全绿

**提示**：sol-02-upgrade 目录（consumer/ + greet-v1.0.0/ + greet-v1.1.0/）；升级演练别在仓库目录里改 go.mod——复制到 /tmp 再演练，避免污染提交内容（本仓库 sol 的验证块就是这么实测的）

## 练习 3：记录项目 Go 版本要求（★★）

**目标**：把「工具链版本应在团队中统一」落成可执行物——写一个检查器：解析 go.mod 的 `module / go / toolchain` 三行，与当前工具链（`runtime.Version()`）比较，输出结论与退出码。

**要求**：
- `parseGoMod([]byte)`：解析三行（容忍行首空白、`//` 注释、未知指令），缺 go 行不报错
- 版本比较按数字段、缺段补 0（`1.25` == `1.25.0`；`go1.25.6` 与 `1.25.6` 相等）
- 三态结论（语义对齐 go 命令实测行为）：当前 < **go 行** → FAIL（硬门槛，exit 1）；当前 ≥ go 行但 < **toolchain 行** → WARN（auto 会切换下载、local 会忽略）；否则 OK（exit 0）
- 用 testdata/*.mod 做表格驱动测试（含注释、无 go 行、toolchain 行高于当前等 fixture）

**验收**：`go test -v ./...` 通过；`go run . -mod <自身 go.mod>` 输出 OK 且 exit 0；对 go 行 1.99.0 的 fixture 输出 FAIL 且 exit 1；对 toolchain go1.26.0 的 fixture 输出 WARN

**提示**：sol-03-goreq 目录；先想清楚三态为什么这样设计——go 行是"低于它构建必失败"的硬门槛，toolchain 行只是"首选工具链"（主文档 3.6 节有两条实测错误消息佐证）
