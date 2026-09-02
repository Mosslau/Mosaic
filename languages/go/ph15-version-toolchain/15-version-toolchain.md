# Go 版本、工具链阶段

> 面向"版本与工具链是工程资产"——本阶段把 ph01~ph14 一直在用却从没系统讲过的"go 命令与版本管理"拆开：Go 的发布节奏与支持窗口、go env 的路径语义（GOROOT/GOPATH/GOMODCACHE/GOCACHE）、go version / go install 的版本后缀、go work 多模块 workspace、go.mod 的 go 行与 toolchain 指令（版本要求到底由谁说了算）、模块版本与语义化版本规则。全部结论都有本环境实测背书（go env 各项输出、语言版本门禁报错、工具链自动下载失败消息、workspace 会话、file:// proxy 安装、依赖升级的测试拦截），且全程离线可复现。

## 1. 概述

Go 版本、工具链阶段的目标是（引用 Roadmap）：**理解 Go 版本演进、工具链和模块兼容策略**。前 14 个阶段里，`go run`/`go test`/`go mod tidy` 是"想都不想就用"的黑盒——本阶段把它们变成**可解释、可检查、可复现**的环节：为什么 go.mod 里那行 `go 1.25.0` 能决定"我的代码能不能用某个语法"；为什么同一个项目在不同机器上构建结果可能不同（工具链版本没统一）；monorepo 里多个模块怎么在本地互相依赖而不发布；升级依赖时为什么必须跑测试；CI 里怎么让"用的 go 版本"成为被记录的、可检查的事实。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 发布节奏 | 双版本年更（2 月 / 8 月 minor）+ 补丁节奏 + 官方支持窗口（最近两个 major），版本命名 go1.N.M |
| 环境与缓存 | go env 语义：GOROOT / GOPATH / GOMODCACHE / GOCACHE / GOBIN 四类路径的区别与实测值、GOENV 配置文件、-w/-u 持久化 |
| 版本读取 | go version / go env GOVERSION / runtime.Version() / go version -m / debug.ReadBuildInfo()（VCS 印章、-ldflags 注入） |
| 工具安装 | go install 的 @version 后缀（proxy 协议、同名覆盖、版本写进二进制）、与 go get 的分工 |
| 多模块开发 | go work workspace（init/use/edit、GOWORK、目录覆盖版本解析）、与 replace 的对比 |
| 工具链要求 | go.mod 的 go 行（语言版本门槛 + 最小工具链）与 toolchain 行（首选工具链）、GOTOOLCHAIN=auto/local/版本 |
| 模块版本 | 语义化版本 v1.2.3（数字段比较、预发布、+build）、大版本 /vN 路径规则、伪版本、依赖升级与测试验证 |

这个阶段只涉及版本管理与工具链的使用和机制，**不涉及 Go 语言底层机制本身（GMP/GC/interface 分派等属 [ph14 高级 Go 阶段](../ph14-advanced-go/14-advanced-go.md)）、性能剖析与优化的工具用法（pprof/benchmark/逃逸分析属 ph13 性能优化阶段）、PGO 与用生产 profile 指导编译（属 ph16 PGO 与高级性能优化阶段，roadmap 第 16 节，目录待建）、容器与 CI/CD 里的工具链编排（多阶段 Dockerfile、CI 矩阵属 ph12 云原生与部署阶段）、多环境发布里的版本号与构建信息策略（灰度/回滚属 ph20 配置管理与发布策略阶段，roadmap 第 20 节，目录待建）** — 本阶段把"版本"固定在 go 命令与 go.mod 这一层；发布层怎么用这些版本是 ph20 的事。

## 2. 来源与演变

**Go 的版本管理形态是被"工具链演进速度"逼出来的**：语言本身追求"向后兼容的稳定"，但编译器/工具/标准库每半年就向前走一步——于是"你的项目锁定在哪个 Go 版本"从技术问题变成了**工程治理问题**。三个关键转折：2018 年 modules 取代 GOPATH（依赖开始有版本）；2021 年 Go 1.16 让 modules 成为默认（go.mod 成为项目身份证）；2023 年 Go 1.21 收紧 go 行语义并引入 toolchain 指令与 GOTOOLCHAIN（"项目要求哪个工具链"第一次被机器强制）。**设计哲学：把"版本兼容"从约定变成 go.mod 里的机器可读声明，让工具自动保证**——这也是本阶段"go 行 / toolchain 行 / go.sum 提交 / 检查脚本"一系列动作的共同出发点。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Go 1.0 | 2012 | 首发；GOPATH 模式，无依赖版本概念（go get 永远最新） |
| Go 1.6 / 1.7 | 2016 | 每年 2 月 / 8 月各一个 minor 的发布节奏固定（1.6 于 2016-02、1.7 于 2016-08） |
| Go 1.11 | 2018 | modules 以实验姿态引入（go.mod / go.sum），GOPATH 模式开始退场 |
| Go 1.13 | 2019 | module proxy（GOPROXY）与校验和数据库（GOSUMDB）成为默认 |
| Go 1.16 | 2021 | modules 成为默认模式；GO111MODULE 不再需要显式开启 |
| Go 1.17 | 2021 | 模块图剪枝（pruning）：go.mod 只记直接依赖，构建图变小 |
| Go 1.18 | 2022 | 泛型落地（ph14 详述）；`go work` 子命令登场（workspace 实验） |
| Go 1.21 | 2023 | **工具链管理转折**：go 行语义收紧为"最低要求"；新增 toolchain 行与 GOTOOLCHAIN 环境变量；workspace 正式可用 |
| Go 1.22 | 2024 | 语言默认行为切换（for 循环变量每次迭代独立等）依赖 go 行门禁 |
| Go 1.24 | 2025 | map 换 Swiss map 实现（ph14 的版本敏感点之一） |
| Go 1.25 | 2025 | 1.25.0 于 2025-08-12 发布；1.25.6（本环境工具链）于 2026-01-15 发布 |
| Go 1.26 / 1.27 | 2026 | 1.26.0（2026-02-10）、1.27.0（2026-08-19）发布；1.25 线随 1.27 发布停止支持 |

本文示例以 **go1.25.6** 为基线（本环境实际跑通——本阶段全部 go env 输出、语言门禁报错、工具链切换失败消息、workspace 会话、file:// proxy 安装与依赖升级演练均为 go1.25.6 / darwin / arm64 / Apple M4 Pro 上零第三方依赖的实测结果，可离线复现；依赖演示用本地 replace 目录与自建 file:// module proxy，不依赖网络），验证工具链 go1.25.6（`go version`、`go env`、`go vet`、`go test -race`、`go work`、`go list`、`go install`、`go mod edit/tidy` 全部可用）。需要说明三点版本背景：① **1.25 线已过官方支持窗口**（按"每个 major 支持到出现两个更新的 major"的规则，1.25 随 1.27.0 于 2026-08-19 停止支持，最后补丁 1.25.14 与 1.27.0 同日发布）——本环境固定用 1.25.6 是因为它是本仓库已装工具链，恰好演示"工具链不更新的状态"，生产环境请跟随受支持窗口；② 本仓库验证环境（沙箱）默认 GOPATH 指向 /Users/ninebot/go 但禁止写入，因此全部实测把 GOCACHE、GOMODCACHE、GOPATH 重定位到 /tmp（这本身就是"缓存可迁移"的演示，见 3.2）；③ 涉及语言/标准库行为的版本门禁（3.6）在别的 Go 版本上结论相同，报错措辞可能随版本微调。

## 3. 语法与参数

### 3.1 发布节奏：双版本年更 + 补丁 + 支持窗口

**Go 的 minor 版本（1.N）每年发两个：2 月与 8 月**；每个 minor 发布后，官方以"补丁版本（1.N.M）"的形式持续修复关键 bug 与安全问题，约每 1~2 个月一发（1.25 线实测发了 14 个补丁：1.25.1 于 2025-09-03、…、1.25.6 于 2026-01-15、…、1.25.14 于 2026-08-19），直到该 minor 线停止支持。停止支持的时刻由官方规则决定（[Go Release History](https://golang.google.cn/doc/devel/release) 原文）：**每个 major 发布被支持到出现两个更新的 major 为止**。用近年实测数据说话：

| minor | 发布日期 | 停止支持（规则：出现两个更新的 major 时） |
|-------|---------|-----------------------------------------|
| 1.22 | 2024-02-06 | 1.24 发布（2025-02-11）时 |
| 1.23 | 2024-08-13 | 1.25 发布（2025-08-12）时 |
| 1.24 | 2025-02-11 | 1.26 发布（2026-02-10）时（末补丁 1.24.13，2026-02-04） |
| 1.25 | 2025-08-12 | 1.27 发布（2026-08-19）时（末补丁 1.25.14，2026-08-19 同日） |
| 1.26 | 2026-02-10 | 1.28 发布时（未到） |
| 1.27 | 2026-08-19 | —（当前最新） |

**版本命名 go1.N.M**：N 是 minor（语言/工具/标准库的演进，每半年一次），M 是 patch（修复，无新功能）。**语言与标准库的新特性只进 minor，补丁只修不增**——这是"升级到 1.26 要谨慎、升级到 1.26.3 只需看安全公告"的根据。安全修复只发给还在支持窗口内的版本，这也是"必须跟上 minor"的硬理由。

> 先给一个本阶段的结论：**生产项目应把 go.mod 的 go 行定在"语言功能够用"的最低版本（见 3.6），并用 CI 锁一个受支持的 minor**；跟不跟最新 minor 是团队节奏，但停在已 EOL 的线 = 没有安全修复。

### 3.2 go env：环境变量与四类路径

**`go env` 输出"go 命令实际看到的环境"**——它把默认值、GOENV 配置文件（`go env -w` 的落点）与进程环境变量合并成最终值。运行 `go env`（或 `go env <键>...`、`go env -json`）即可查询；`go env -w KEY=value` 持久化到 GOENV 文件、`go env -u KEY` 撤销。本环境实测（重定位后）：

```text
$ go env GO111MODULE GOPATH GOMODCACHE GOCACHE GOROOT GOPROXY GOSUMDB GOTOOLCHAIN GOFLAGS GOWORK GOOS GOARCH GOVERSION
（每键一行；本环境为沙箱，GOCACHE/GOMODCACHE/GOPATH 已重定位到 /tmp）
```

| 键 | 默认（未覆盖时） | 本环境实测（重定位到 /tmp） | 语义 |
|----|----------------|---------------------------|------|
| GOROOT | 工具链安装目录 | /opt/homebrew/Cellar/go/1.25.6/libexec | go 命令、编译器、标准库源码所在；`runtime.GOROOT()` 等价 |
| GOPATH | ~/go | /tmp/gopath | 工作区根；module 模式下是 GOMODCACHE/GOBIN 的宿主 |
| GOMODCACHE | $GOPATH/pkg/mod | /tmp/gomodcache | **模块源码缓存**：`go mod download` 的 zip 与解压源码落点 |
| GOCACHE | ~/Library/Caches/go-build（darwin） | /tmp/gocache | **编译产物缓存**：内容寻址中间产物，可随时删（`go clean -cache`） |
| GOBIN | $GOPATH/bin | 空 = 用默认 | `go install` 的二进制安装目录（3.4 会设置它） |
| GOVERSION | — | go1.25.6 | 当前 go 命令版本（`go version` 的机器可读形式） |
| GOTOOLCHAIN | auto | auto | 工具链选择策略（3.6 详解） |
| GOPROXY | proxy.golang.org,direct | 同上 | 模块代理；可 file:// 指向本地离线代理（3.4/4.3） |
| GOSUMDB | sum.golang.org | 同上 | 模块校验和数据库（go.sum 的信任根） |
| GOWORK | 空 | 空 | 当前生效的 go.work 路径；非空 = 处于 workspace（3.5） |

**实测口径（脚注）**：本机未重定位时的默认值实测为 `GOPATH=/Users/ninebot/go`、`GOMODCACHE=/Users/ninebot/go/pkg/mod`、`GOCACHE=/Users/ninebot/Library/Caches/go-build`（darwin）——但本仓库验证沙箱对以上默认位置只读（`go` 命令实际写入时报 `operation not permitted`），故全部实测在 `GOPATH=/tmp/gopath GOMODCACHE=/tmp/gomodcache GOCACHE=/tmp/gocache` 的**会话级环境变量重定位**下进行（非 `go env -w` 持久化），上表「本环境实测」列即该会话的真实输出，与 examples/ex03-goenv-probe 及 examples/README.md 的实测记录一致；「默认」列给出的是未重定位的符号默认。GOCACHE/GOMODCACHE/GOPATH 三键之外的键在两种环境下取值相同。

**四类路径是最容易混的一组，务必分清**：

| 路径 | 装什么 | 删了会怎样 |
|------|--------|-----------|
| GOROOT | 工具链本体（go/编译器/标准库） | 不能删（重装工具链） |
| GOPATH | 工作区根 + 派生目录的宿主 | module 模式下作用减弱 |
| GOMODCACHE | 第三方模块的 zip 与解压源码 | 重新下载（`go clean -modcache`） |
| GOCACHE | 自己代码的编译中间产物 | 下次编译变慢而已（内容寻址，可安全删） |

> 本环境把 GOMODCACHE 与 GOCACHE 指到 /tmp 后照常构建——**缓存目录天然可迁移**：CI 里挂共享缓存、离线环境指到只读的预填充目录，都是常见操作；GOCACHE 内容寻址、跨机器内容一致，甚至可以多人共享同一份构建缓存。

### 3.3 go version：工具链版本怎么读

**`go version` 回答"当前 go 命令是什么版本"**：`go version go1.25.6 darwin/arm64`（版本 + GOOS/GOARCH）。程序里用 `runtime.Version()` 拿同一个值；`go env GOVERSION` 是它的机器可读形式。但"运行期工具链版本"只是版本画像的一角——**二进制里还埋着模块版本与构建信息**，用 `go version -m <二进制>` 或 `debug.ReadBuildInfo()` 读：

```go
// 完整可运行版见 examples/ex01-buildinfo/main.go（report() 节选，行与文件一致）
s := "runtime.Version(): " + runtime.Version() + "\n"
// s += "version var      : " + version + "\n"  ← 业务版本号（-ldflags 注入，见 6 节示例 1）
bi, ok := debug.ReadBuildInfo()
if !ok {
	return s + "build info: unavailable\n"
}
s += fmt.Sprintf("main module      : %s %s\n", bi.Main.Path, bi.Main.Version)
s += "go version(build): " + bi.GoVersion + "\n"
// for _, kv := range bi.Settings { … vcs.revision / vcs.time / vcs.modified … }
```

**实测（ex01，go1.25.6，TenetLang 仓库内构建）**：`go build -ldflags "-X main.version=v1.2.3"` 后运行，输出 `runtime.Version(): go1.25.6`、`version var: v1.2.3`、`main module: …ex01-buildinfo (devel)`、`go version(build): go1.25.6`、`setting vcs.revision : 10e66b4…`。三个要点：① **模块版本来自 VCS tag**——仓库打了 v1.2.3 的 tag 才显示 v1.2.3，没打 tag 一律 `(devel)`（伪版本机制见 3.7）；② **`-ldflags "-X main.version=…"` 是构建期注入业务版本号的官方手法**（`-X` 写的是包级变量的值），配合 VCS 印章（vcs.revision / vcs.time / vcs.modified，默认在有 .git 的目录构建时自动盖）就构成"这个二进制是谁、哪个 commit、什么 go 版本编出来的"的完整答案——线上排障第一件事 `go version -m`；③ 业务发布层怎么编排这些版本号（灰度对照、回滚判断）属 ph20（roadmap 第 20 节，目录待建），本阶段只讲"信息怎么进二进制"。

### 3.4 go install：@version 后缀与模块代理

**`go install` 的两种形态**：`go install ./cmd/x`（模块内，装当前代码，版本记 `(devel)`）与 **`go install 模块路径@版本`**（从 module proxy 取指定版本安装，Go 1.16 起支持命令形态）。`@` 后缀让"装哪个版本"显式化，这正是工具链治理的一环：`go install golang.org/x/tools/gopls@latest` 或锁死 `@v0.20.0`。

**实测（file:// proxy，离线可复现，完整会话见下）**：本环境无外网，我们在 /tmp 自建了一个 module proxy（目录结构与真实 proxy 协议完全一致：`<module>/@v/list`、`v1.0.0.info/.mod/.zip`——这正是 4.3 要讲的 proxy 协议）。会话里 GOBIN 指到 /tmp/ph15x/bin，GOPROXY=file:///tmp/ph15x/goproxy，GOSUMDB=off（离线无 sumdb 可查）：

```text
$ go install example.com/greeter-cli@v1.0.0
go: downloading example.com/greeter-cli v1.0.0
$ go install example.com/greeter-cli@v1.1.0   ← 同名覆盖：后装的 v1.1.0 覆盖 v1.0.0
$ ./bin/greeter-cli
greeter-cli v1.1.0: Hello from v1.1.0 …
$ go version -m bin/greeter-cli                ← 版本写在二进制里
bin/greeter-cli: go1.25.6
	path	example.com/greeter-cli
	mod	example.com/greeter-cli	v1.1.0	h1:Qzn7awB3qm3Su0TAEwr/…
$ go install example.com/greeter-cli@v1.0.0    ← 再装 v1.0.0，二进制变回 v1.0.0
```

**三个必记点**：① **同名覆盖**——`@version` 选的是"装哪个版本"，不是"装成不同名字"；二进制名 = 模块路径最后一段，两版不能并存（想要并存自己复制/改名）；② **版本靠 `go version -m` 验证**，别信"我刚装的"；③ **`go install m@v` 的解析走 module proxy**（GOPROXY 协议，4.3 详述）——离线/内网环境可以像上面一样指 file:// proxy 或共享 GOMODCACHE。另外 `go run m@version`（Go 1.21+ 起支持：`@` 版本后缀从 Go 1.21 起对 go run 生效，go1.20 及更早只支持 go install）用同一机制"跑某个版本而不安装"，临时试工具版本很好用。

### 3.5 go work：多模块 workspace 实测

**workspace（go.work）解决"多个模块在本地互相依赖而不发布"**：monorepo、把大模块拆成多个模块的过渡期、跨模块改代码联调，都是它的主场。机制一句话：**go.work 的 use 列表把模块路径映射到本地目录**，主模块 go.mod 里对它们的 require 直接由本地目录满足——不需要发布、不需要 replace。

实测（/tmp/ph15x/ws 完整会话，go1.25.6；仓库内等价镜像见 examples/ex04-workspace）：

```text
$ go work init ./app ./lib          # 以两个模块目录建 workspace
$ cat go.work
go 1.25.6                           # ← go work init 写入当前 go 版本

use (
	./app
	./lib
)
$ go env GOWORK                     # 在 workspace 树内：GOWORK 指向 go.work
/tmp/ph15x/ws/go.work
$ go run ./app                      # app import example.com/greeter（require v0.0.0）
Hello, workspace!                   # ← 解析到本地 lib 目录，无需发布
$ go work use ./extra               # 追加模块（go work edit -dropuse 移除）
$ go list -m -json example.com/greeter
{ "Path": "example.com/greeter", "Main": true, "Dir": "/tmp/ph15x/ws/lib", … }
```

**实测的两个边界**（都是"workspace 只覆盖构建期解析"的体现）：① workspace 根目录的 `go test ./...` 报 `pattern ./...: directory prefix . does not contain modules listed in go.work`——`./...` 不会跨进 use 目录，要按模块给 pattern（`./app/... ./lib/...`）或用模块路径；② `go mod tidy` 与 `go list -m all` 这类要**版本元数据**的命令仍会去 proxy 找 require 里写的 v0.0.0（离线即报 `module lookup disabled by GOPROXY=off`）——本地目录没有"版本号"，tidy 无从记录；所以发布前的版本校核还是要 tag + proxy。

**go work 与 replace 的取舍**：

| 维度 | go work（go.work） | replace => 本地目录（go.mod 内） |
|------|-------------------|-------------------------------|
| 管多少个模块 | 一个 workspace 管一批（use 列表） | 一个 go.mod 管一个依赖 |
| 依赖方是否知情 | 主模块 go.mod 不用动（require 照写） | 每个依赖方 go.mod 都要写 replace 行 |
| 团队共享 | go.work 可提交（use 用相对路径） | replace 行提交即污染发布 |
| 对本地目录跑 go mod tidy | 仍要版本元数据（会查 proxy） | 直接读目录，tidy 可离线完成 |
| 何时摘除 | 合并/发布前删 go.work | 发版前删 replace 行并验证真版本可解析 |

> 本阶段只用 workspace 的最小形态（use 列表 + 目录覆盖）；**依赖解析与发布的深入（模块代理协议、校验和、MVS 全貌）是 ph05 包管理阶段的知识延伸，这里只需理解"workspace 覆盖 = 开发期本地替换"这一条**，发布形态见 4.3。

### 3.6 go.mod 的 go 行与 toolchain 指令（实测）

**go.mod 顶部两行是项目对工具链的"声明"**，语义（Go 1.21 起收紧）：

| go.mod 行 | 形式 | 语义 | 不满足时（实测） |
|-----------|------|------|-----------------|
| `go` | `go 1.25.0` | **最低要求**：① 语言版本门槛（低于它的语法报错）；② 工具链最低版本 | 编译器报语言错误，或工具链报版本错误（见下） |
| `toolchain` | `toolchain go1.25.6` | **首选工具链**：高于当前时，auto 模式下载并切换；local 模式忽略 | auto 尝试下载；local 安静忽略（两者不同！） |

**实测 1——语言版本门槛**（go 行决定"这行语法允不允许"，与运行的工具链无关）。同一份用 range-over-int（Go 1.22 特性）的源码，go 行不同结论不同——先写 `go 1.21.0` 构建报错，改成 `go 1.22.0` 后编译通过：

```text
$ go build ./...                 # go.mod 写 go 1.21.0
./main.go:4:17: cannot range over 3 (untyped int constant): requires go1.22 or later (-lang was set to go1.21; check go.mod)
$ go build ./...                 # go.mod 改成 go 1.22.0
（编译通过）
```

**实测 2——go 行高于当前工具链**（go.mod 写 `go 1.99.0`，本机 go1.25.6）：

```text
$ go build ./...                                    # GOTOOLCHAIN=auto（默认）：尝试下载
go: downloading go1.99.0 (darwin/arm64)
go: download go1.99.0: golang.org/toolchain@v0.0.1-go1.99.0.darwin-arm64: Get "https://proxy.golang.org/…": i/o timeout
$ GOTOOLCHAIN=local go build ./...                  # =local：不下载，直接拒绝
go: go.mod requires go >= 1.99.0 (running go 1.25.6; GOTOOLCHAIN=local)
```

**实测 3——toolchain 行高于当前工具链**（go.mod 写 `go 1.25.0` + `toolchain go1.26.0`）：

```text
$ go build ./...                                    # auto：尝试下载 go1.26.0（同样超时失败）
go: downloading go1.26.0 (darwin/arm64)
…
$ GOTOOLCHAIN=local go build ./...                  # local：忽略 toolchain 行，构建通过（exit 0）
```

**结论**（这三组实测是"版本要求由谁说了算"的完整答案）：**go 行是硬门槛**——低于它，auto 想下载、local 直接报错，构建必失败；**toolchain 行是首选**——auto 会切过去（团队里装了更新版本就自动用），local 直接无视（版本可能不统一）。所以"工具链版本应在团队中统一"的正确落地是：go 行定**最低可用版本**（写你真正用到的语言特性所需的最低 minor），toolchain 行定**首选精确版本**（要团队都用 go1.25.6 就写 toolchain go1.25.6），CI/本地用 GOTOOLCHAIN=auto 让工具自动对齐；`go mod init` 会把当前工具链完整版本写进 go 行（go1.25.6 实测：`go mod init` 生成 `go 1.25.6`）。注意对照：本仓库示例/练习/项目的 go.mod 统一写的是 `go 1.25.0`——那是把 go 行定在"语言版本档"的工程写法：go 行只表达**最低要求**（`go 1.25.0` ≤ 当前工具链 1.25.6 即满足），与 `go mod init` 默认写当前工具链完整版本并不矛盾——init 是"所见即所用"的默认，发布前通常再按团队最低版本显式调低（`go mod edit -go=…`），两种写法都合法。

> go 行对语言/标准库行为的完整门禁（含 GODEBUG 默认行为切换）见 4.2；**GOTOOLCHAIN=path（让 go 命令跟随 PATH 里的版本）与自动下载的细节属于工具链选择机制，本节只给实测结论**。

### 3.7 模块版本与语义化版本：v1.2.3 与兼容规则

**Go 的依赖版本就是语义化版本（semver）：vMAJOR.MINOR.PATCH**，兼容规则是模块生态的契约：

| 段 | 何时递增 | 兼容承诺 | 例子 |
|----|---------|---------|------|
| PATCH | 修复 bug | 向后兼容（行为修复可能改变可观察结果！见实测） | v1.2.3 → v1.2.4 |
| MINOR | 加功能（向后兼容） | 旧代码应能继续编译运行 | v1.2.3 → v1.3.0 |
| MAJOR | 不兼容变更 | **没有**向后兼容承诺 | v1.9.0 → v2.0.0 |

**排序规则（实测，见 ex02）**：数字段按**数值**比较（`v1.9.0 < v1.10.0`，字典序会判反）、缺段补 0（`v1.2 == v1.2.0`）、预发布排正式版之前（`v1.2.3-rc.1 < v1.2.3`）、`+xxx` 元数据不参与排序（`v1.2.3+incompatible == v1.2.3`）。生产代码用官方扩展 `golang.org/x/mod/semver`，示例 ex02 是规则一致的自实现教学子集。

**三个 Go 特有的版本形态**（遇到要认识）：

- **大版本路径规则（/vN）**：MAJOR ≥ 2 的模块，路径必须带 `/vN` 后缀（`example.com/kit/v2`），因为 v1 与 v2 是**两个不同模块**、可以同时被依赖（MVS 见 4.3）。v0 与 v1 不带后缀。
- **`+incompatible`**：老模块没按 /vN 规则发布 v2+ 时的兼容标记（如 `v2.0.0+incompatible`），go 工具允许但不鼓励。
- **伪版本（pseudo-version）**：`v0.0.0-20260901000000-3e124a7…`——本地目录没有 tag 时，go 用 VCS 的时间与 commit 哈希合成可排序的版本号（3.3 里 ex01 的 `(devel)` 是"还没编进版本"的构建态，tag 了就显示 tag）。

**依赖升级必须测试验证（实测演示，完整输出见练习 sol-02）**：v1.1.0 只改了问候语措辞（`"Hello, X!"` → `"Hey, X!"`），签名没变、按 semver 完全"合法"——但消费者的契约测试在升级后当场失败：

```text
$ go test ./...            # 升级后（require 已改 v1.1.0、replace 已切到 ../greet-v1.1.0）
--- FAIL: TestGreetContract (0.00s)
    greet_test.go:16: greet.Greet() = "Hey, service-a!", want prefix "Hello, "
FAIL
```

**教学点**：semver 承诺的是 **API 兼容，不是行为不变**——改输出、改默认值、修"bug"都可能破坏下游的可观察行为。所以升级的正确姿势永远是：读 changelog → 升 go.mod（`go get m@新版本` 或编辑 require）→ **跑测试** → 适配或回滚（sol-02 两条路都实测全绿）。这也正是 roadmap 必会概念「依赖升级需要测试验证」的落点：测试是依赖升级的安全网，没有它，v1.1.0 的"小改动"会在生产里变成事故。

## 4. 底层原理

### 4.1 go 命令如何选择工具链

**go 命令本身是"版本选择器"**：每次执行先读当前模块（或 workspace）的版本要求，再决定用哪个工具链跑剩下的活：

```text
运行 go 子命令（build/test/run/install…）
   │
   ▼
读 go.mod（或 go.work）的 go 行 与 toolchain 行
   │
   ├─ 当前工具链 ≥ go 行？─────────── 否 ──▶ 版本不满足
   │                                        ├─ GOTOOLCHAIN=auto  → 下载/取缓存
   │                                        │    golang.org/toolchain@v0.0.1-goX.Y.Z.<GOOS>-<GOARCH>
   │                                        │    （toolchain 本身就是个模块，走 GOPROXY）
   │                                        └─ GOTOOLCHAIN=local → 报错退出（实测消息见 3.6）
   ▼
toolchain 行 > 当前（且 GOTOOLCHAIN=auto）？── 是 ──▶ 切到 toolchain 行指定版本
   │
   └─ 否 ──▶ 用当前工具链执行构建（语言版本按 go 行门禁，见 4.2）
```

**两个机制要点**（都有 3.6 的实测消息背书）：① **新工具链 = 一个普通模块**：`golang.org/toolchain@v0.0.1-go1.99.0.darwin-arm64`——所以"自动切换工具链"在实现上就是一次 GOPROXY 下载，离线/内网会像实测那样失败在 `Get "https://proxy.golang.org/…": i/o timeout`；② **local 模式是"无视 toolchain 行、仍执行 go 行"**：实测里 toolchain go1.26.0 + local 构建成功（exit 0），go 1.99.0 + local 直接报错——两个门槛的执行路径不同，这也是 sol-03 与 project 里三态判定（fail/warn/ok）的设计依据。

### 4.2 语言版本门槛：go 行怎么变成编译行为

**go 行不是注释，它决定编译器的 `-lang` 参数与标准库/运行时的默认行为**。语言侧：编译器按 go 行设置语言版本，分两种门禁——**语法门禁**：低于 go 行的语法直接报错，3.6 实测的报错文本里那句 `(-lang was set to go1.21; check go.mod)` 就是证据：**报错的是编译器（-lang），提示查的是 go.mod**；**语义门禁**：同一份代码按 go 行取对应语言档——Go 1.22 起 for 循环变量每次迭代独立、range-over-int 可用，而 go 行 < 1.22 的模块仍按旧语义编译（3.6 实测 1 里 range-over-int 在 `go 1.21.0` 下报错、`go 1.22.0` 下通过，就是 -lang 在起作用）。**语言侧的这两类门禁都走 -lang，不是 GODEBUG**。标准库/运行时侧：Go 用 GODEBUG 机制管理"行为默认值随版本演进"的兼容开关——go.mod 的 go 行决定这批开关取新默认还是旧默认（如 Go 1.22 起 net/http ServeMux 新路由语法的 httpmuxgo121 开关：go 行 ≥ 1.22 的模块默认启用新行为，旧模块保持 Go 1.21 行为；此类开关也可用 GODEBUG 环境变量临时覆盖），升 go 行 = 一次性切到新默认（此机制属官方 [go.dev/doc/godebug](https://golang.google.cn/doc/godebug) 文档内容，本环境未逐项实测，标注以官方文档为准）。

**工程含义**：go 行往高调（如 1.21 → 1.22）不只是"换个编译器版本"，还意味着**一批标准库行为默认值跟着变**——所以"升级 go 行"也要跑全量测试（与 3.7 的依赖升级同理）；反过来，`go 1.21` + 用 1.25.6 工具链编译 = 语言与行为都锁在 1.21 的兼容档（实测 range-over-int 被拒），这是"老项目渐进升级"的官方路径：先升工具链、go 行原地不动，逐个版本解锁。

### 4.3 模块解析：MVS、go.sum 与缓存布局

**go 命令如何决定"example.com/greet 用哪个版本"**：MVS（minimal version selection，最小版本选择）——读主模块的 require 与每个依赖的 require，对**每个模块路径取被要求的最大版本**；主模块（及 workspace use 的模块）不参与 MVS，永远用本地代码（3.5 的 Main:true 就是这个意思）。版本元数据从 GOPROXY 拉：proxy 协议就是 `GOPROXY/<module>/@v/` 下的一组文件：

```text
GOMODCACHE/cache/download/example.com/greet/@v/     ← 与 proxy 同构的本地缓存
├── list                  # 有哪些版本
├── v1.0.0.info           # {"Version":"v1.0.0","Time":…}
├── v1.0.0.mod            # go.mod 内容（决定它的依赖，供 MVS 用）
└── v1.0.0.zip            # 模块源码（解压到 GOMODCACHE/example.com/greet@v1.0.0/）
```

**本阶段动手自建过 file:// proxy（3.4 实测）**，所以这条路是"亲手走过"的：proxy 协议 = GOMODCACHE 里 cache/download 目录的镜像；`go mod download` 就是把 proxy 文件搬进 cache；校验与 go.sum 由 GOSUMDB（sum.golang.org）背书——go.sum 记录每个版本的 zip/mod 哈希，保证"下载过的东西不被换"（`go mod verify` 复核）。**发布态四件套**：提交 go.mod + go.sum、go 行写明最低版本、依赖版本写进 go.mod（`go get`/`go mod tidy` 维护）、GOFLAGS=-mod=readonly 防止构建时偷偷改 go.mod。离线/内网团队按同样的结构搭 file:// proxy 或共享 GOMODCACHE，就能复现本阶段的全部实验。

## 5. 使用场景

| 场景 | 用什么 | 对应小节 |
|------|--------|---------|
| 新机器/CI 上先确认"用什么 go、目录在哪" | go version、go env | 3.2 / 3.3 |
| 装一个指定版本的工具（gopls@v0.20.0、自研 CLI@tag） | go install 模块@版本 | 3.4 |
| 线上二进制"是谁、哪个 commit、什么 go 编的" | go version -m（debug.ReadBuildInfo） | 3.3 |
| monorepo / 大模块拆分期多模块本地联调 | go work（workspace） | 3.5 |
| 某个依赖想先用本地未发布版本验证 | replace => 本地目录 | 3.5 |
| 团队统一工具链、构建可复现 | go.mod 的 go/toolchain 行 + 检查脚本 | 3.6 + project |
| 升级依赖（含安全补丁） | go get @新版本 + 契约测试 | 3.7 |
| 离线/内网构建 | GOPROXY=file:// + 共享 GOMODCACHE | 3.4 / 4.3 |

**不适合**此阶段的事项：

- **容器里的工具链编排**（多阶段 Dockerfile、CI 版本矩阵、镜像内 go 版本）：属 ph12——本阶段讲"go 命令怎么选版本"，ph12 讲"镜像/流水线怎么管版本"
- **性能剖析工具**（pprof/benchmark 怎么用）：属 ph13——版本与工具链不是性能话题
- **PGO**（用生产 profile 指导编译，`go build -pgo=…`）：属 ph16（roadmap 第 16 节，目录待建）——它与本阶段的 toolchain 行同属"构建期配置"，但流程属 ph16
- **发布侧版本策略**（灰度对照、回滚判断、多环境版本号注入）：属 ph20（roadmap 第 20 节，目录待建）——本阶段只保证"版本信息进得去、查得出"

## 6. 代码示例

> 以下示例均为完整可运行 Go module，位于 [`examples/`](./examples/) 目录（每个示例一个子目录，先进入对应目录再运行；ex04 是 workspace，在 ex04-workspace 目录运行）。验证环境：go1.25.6（darwin/arm64，Apple M4 Pro），零第三方依赖，GOCACHE/GOMODCACHE 重定位 /tmp；四个示例均通过 `go vet ./...`、`go test ./...`、`go test -race ./...`（ex04 按模块 pattern 跑）。实测数字见 examples/README.md（下表"实测"列为本环境输出节选）。

| 示例 | 一句话说明 | 实测（节选） |
|------|-----------|-------------|
| ex01-buildinfo | 二进制版本画像：runtime.Version / ReadBuildInfo / -ldflags 注入 / VCS 印章 | `go run .` → `go1.25.6` + `(devel)`；`-ldflags -X` 后 version var=v1.2.3，vcs.revision 10e66b4… |
| ex02-semver | 语义化版本排序规则（数字段比较、缺段补 0、预发布、+build 忽略） | `Compare("v1.9.0","v1.10.0")=-1`；16 个测试全 PASS |
| ex03-goenv-probe | `go env -json` 关键键 + 语义注解（GOROOT/GOPATH/GOMODCACHE/GOCACHE） | GOROOT=…/Cellar/go/1.25.6/libexec、GOMODCACHE=/tmp/gomodcache（重定位） |
| ex04-workspace | go.work 多模块：service-a + sharedlib，require v0.0.0 由 workspace 目录满足 | `go run ./service-a` → `Hello from sharedlib, service-a!`；`go list -m -json` Main:true |

### 示例 1：构建信息（ex01-buildinfo）

```go
// examples/ex01-buildinfo/main.go —— report() 打印版本画像（节选，行与文件一致）
// version 是构建期可注入的版本号：go build -ldflags "-X main.version=v1.2.3"
var version = "dev"

func report() string {
	s := "runtime.Version(): " + runtime.Version() + "\n"
	s += "version var      : " + version + "\n"
	bi, ok := debug.ReadBuildInfo()
	if !ok {
		return s + "build info: unavailable\n"
	}
	s += fmt.Sprintf("main module      : %s %s\n", bi.Main.Path, bi.Main.Version)
	s += "go version(build): " + bi.GoVersion + "\n"
	for _, kv := range bi.Settings {
		switch kv.Key {
		case "vcs.revision", "vcs.time", "vcs.modified":
			s += fmt.Sprintf("setting %-13s: %s\n", kv.Key, kv.Value)
		}
	}
	return s
}
```

运行：`go test -v ./...`；`go run .`；`go build -ldflags "-X main.version=v1.2.3" -o /tmp/ex01 . && /tmp/ex01`；`go version -m /tmp/ex01`。**教学点**：runtime.Version() 是工具链版本；模块版本来自 VCS tag（无 tag = `(devel)`）；`-X` 注入业务版本号；有 .git 的目录构建自动盖 VCS 印章（干净仓库 vcs.modified=false，实测见 examples/README.md 与 /tmp 打 tag 场景）。

### 示例 2：语义化版本比较（ex02-semver）

```go
// examples/ex02-semver/main.go —— Compare 主路径（节选，行与文件一致）
func Compare(a, b string) int {
	pa, pb := parse(a), parse(b)
	if pa.major != pb.major {
		return cmpInt(pa.major, pb.major)
	}
	if pa.minor != pb.minor {
		return cmpInt(pa.minor, pb.minor)
	}
	if pa.patch != pb.patch {
		return cmpInt(pa.patch, pb.patch)
	}
	return comparePre(pa, pb)
}
```

运行：`go test -v ./...`（16 个子测试覆盖全部规则）；`go run .` 打印 8 组对比。**教学点**：parse 先丢 `v` 前缀、再丢 `+build` 元数据、拆出 prerelease（见文件内 parse/comparePre 的逐行注释）；数字段数值比较（v1.9 < v1.10）是模块版本排序的地基；生产用 `golang.org/x/mod/semver`，本示例是规则一致的自实现。

### 示例 3：go env 语义探测（ex03-goenv-probe）

```go
// examples/ex03-goenv-probe/main.go —— probe 调用 go env -json（节选，行与文件一致）
func probe() (map[string]string, error) {
	args := append([]string{"env", "-json"}, keys...)
	out, err := exec.Command("go", args...).Output()
	if err != nil {
		return nil, fmt.Errorf("go env: %w", err)
	}
	m := map[string]string{}
	if err := json.Unmarshal(out, &m); err != nil {
		return nil, fmt.Errorf("解析 go env -json 输出: %w", err)
	}
	return m, nil
}
```

运行：`go test -v ./...`；`go run .` 输出带语义注解的关键键表。**教学点**：`go env` = "go 命令实际看到的环境"（默认值 + GOENV 配置文件 + 环境变量覆盖后的最终值）；四类路径（GOROOT/GOPATH/GOMODCACHE/GOCACHE）一表分清；GOCACHE 内容寻址可随时删、GOMODCACHE 可整目录迁移（本环境重定位到 /tmp 就是活例）。

### 示例 4：workspace（ex04-workspace）

```go
// examples/ex04-workspace/service-a/main.go —— 主模块（节选，行与文件一致）
import (
	"fmt"

	"tenetlang/go/ph15-version-toolchain/examples/ex04-workspace/sharedlib"
)

// run 组装问候语；抽出来便于 main_test 直接断言（无需子进程）。
func run() string {
	return sharedlib.Greet("service-a")
}
```

配套文件（与 main.go 同目录）：`service-a/go.mod` 只写 `require tenetlang/go/ph15-version-toolchain/examples/ex04-workspace/sharedlib v0.0.0`（无 replace）；`go.work` 的 use 列表把该模块路径解析到本地 sharedlib/ 目录（go.work 全文见 ex04-workspace/go.work）。运行（cd examples/ex04-workspace）：`go run ./service-a`；`go test ./service-a/... ./sharedlib/... && go vet ./service-a/... ./sharedlib/... && go test -race ./service-a/... ./sharedlib/...`；`go env GOWORK`。**教学点**：workspace 目录覆盖 require 的版本解析（`go list -m -json` 输出 Main:true）；根目录 `./...` pattern 不可用的实测边界；`go mod tidy`/`go list -m all` 仍需版本元数据——workspace 解决"本地联调"，发布仍要 tag + proxy。

## 7. 总结

### 关键要点

1. **发布节奏**：minor 每年两次（2 月/8 月），补丁约每 1~2 个月一发；**每个 major 支持到出现两个更新的 major**（官方 Release History 规则，1.25 线随 1.27.0 于 2026-08-19 停更）——EOL 的版本没有安全修复
2. **四类路径**（必会区分）：GOROOT = 工具链安装目录、GOPATH = 工作区根、GOMODCACHE = 模块源码缓存（可迁移）、GOCACHE = 编译产物缓存（可随时删）；`go env` 输出覆盖默认/GOENV/环境变量后的最终值
3. **go version 与版本画像**：runtime.Version() = 工具链版本；`go version -m` / debug.ReadBuildInfo() 读模块版本（VCS tag，无 tag = `(devel)`）、go 版本、VCS 印章；`-ldflags "-X main.version=…"` 注入业务版本号
4. **go install @version**：从 proxy 取指定版本安装，二进制名 = 路径末段（**同名覆盖**，版本靠 `go version -m` 验证）；`go run m@v` 同机制不落地
5. **go work = 多模块本地联调**（必会概念）：use 列表把模块路径映射到本地目录，require v0.0.0 也编译得过；边界——根目录 `./...` 不可用、tidy/`list -m all` 仍需版本元数据；与 replace 的取舍见 3.5 表
6. **go 行是硬门槛**（必会概念）：语言版本门禁（实测 `-lang was set to go1.21` 报错）+ 工具链最低版本（实测 auto 下载失败 / local 硬报错）；toolchain 行是首选（auto 切换、local 忽略）——两行语义不同，团队统一靠"go 行定最低、toolchain 行定精确"
7. **语义化版本 v1.2.3**：数字段数值比较（v1.9 < v1.10）、预发布 < 正式版、+build 忽略；MAJOR ≥ 2 带 /vN 路径；伪版本 = VCS 时间 + commit 合成的可排序版本号
8. **依赖升级需要测试验证**（必会概念）：semver 承诺 API 兼容不是行为不变——v1.1.0 改个问候语措辞就能让消费者契约测试失败（实测 `"Hey, service-a!"` vs `want prefix "Hello, "`）；升级三连：改 require → go mod tidy → 跑测试（适配或回滚）
9. **工具链选择机制**：新工具链就是 `golang.org/toolchain@v0.0.1-goX.Y.Z.darwin-arm64` 这个普通模块（走 GOPROXY），auto 模式的"自动切换"本质是一次模块下载
10. **发布态四件套**：提交 go.mod + go.sum、go 行写明最低版本、依赖版本进 go.mod、GOFLAGS=-mod=readonly；离线/内网用 file:// proxy 或共享 GOMODCACHE（本阶段全程离线实测）

### 阶段验收清单

- [ ] 能解释 go.mod 的 go 行：说清"语言版本门槛 + 工具链最低版本"双重语义，能复述 go 1.21 下 range-over-int 的报错（示例 go.mod + 实测 2/3）
- [ ] 能管理多模块开发：workspace 建/加/查模块（init/use/edit、GOWORK、go list -m Main:true），说清与 replace 的取舍（示例 4 / 练习 1）
- [ ] 能稳定复现构建环境：说清 go/toolchain 行与 GOTOOLCHAIN=auto/local 的行为差异，会用 sol-03 / project/toolcheck 检查 go.mod 要求是否被当前工具链满足
- [ ] 能执行一次"带测试验证"的依赖升级：升 require → tidy → 契约测试拦截或通过 → 适配/回滚（练习 2 实测输出）
- [ ] 能用 go version -m / debug.ReadBuildInfo 回答"这个二进制是谁编的"（示例 1）
- [ ] 能完成项目验收标准：toolcheck 三态判定与 go 命令实测行为一致、`go test -race ./...` 通过

### 跨语言对比

- Go 的版本治理 = "go.mod 声明 + 工具自动执行"：go 行锁语言版本、toolchain 行锁工具链、GOTOOLCHAIN=auto 自动切换——对比 Rust 的 edition（语言版本）与 rustup toolchain（工具链，`rust-toolchain.toml` 的 `channel` 行几乎就是 Go 的 toolchain 行）、对比 Java 的"JDK 版本靠构建工具管"（Maven toolchains）、对比 Python 的 venv + pip（解释器版本靠外部编排）。**Go 的差异化：版本要求进源码（go.mod），与代码同提交、同 review**——这是"版本治理左移"的明确设计样本
- 语义化版本：Go 模块（v1.2.3 + /vN 大版本路径）与 npm/crates.io 的 semver 同源，但 /vN 路径规则（v2 是独立模块）比 npm 的"包名内嵌 major"更机械也更严格——为 analysis/ 与 Tenet 合成积累素材

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。三题与 roadmap §15 对齐：练习 1 ↔「创建多模块 workspace」、练习 2 ↔「升级一个依赖版本」、练习 3 ↔「记录项目 Go 版本要求」。完成 3 题后继续。

1. **创建多模块 workspace**（★★）：app + lib 两模块 + go.work，不发布不 replace 互相关联（参考实现实测：`Hello, world! (lib v0.0.0-workspace)`）
2. **升级一个依赖版本**（★★★）：v1.0.0 → v1.1.0，契约测试拦截行为变化，适配/回滚收场（参考实现实测：`greet_test.go:16: …"Hey, service-a!" want prefix "Hello, "`）
3. **记录项目 Go 版本要求**（★★）：解析 go.mod 的 module/go/toolchain 三行 + 三态判定 + testdata 表格测试（参考实现实测：OK exit 0 / FAIL exit 1 / WARN exit 0）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**Go 工具链检查脚本（toolcheck）**（roadmap 推荐项目「Go 工具链检查脚本」）——cmd/toolcheck + internal/gomodfile、internal/vercmp、internal/check 三个包，三态判定语义复刻 go 命令实测行为（go 行 fail / toolchain 行 warn / -want 策略门槛），支持 `-json` 供 CI 消费。**实测**：自身 go.mod → ok（exit 0）；go 行 1.99.0 fixture → fail（exit 1）；`-want go1.26.0` → fail；`go test -race ./...` 通过。roadmap 另一个推荐项目「多服务 workspace 示例」已由 examples/ex04-workspace 与练习 1 覆盖。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部 3 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（三态判定与 go 命令实测一致、`go test -race ./...` 通过）

### 下一阶段

**ph16+（PGO 与高级性能优化阶段，roadmap 第 16 节，目录待建）——本阶段是当前已建目录（ph01~ph15）的最后一个阶段**，ph16~ph21 的阶段目录尚未建立（roadmap 见 [`languages/go/go.md`](../go.md)）。后续可深入 **PGO（Profile Guided Optimization）与高级性能调优**方向：`go build -pgo=cpu.pprof` 让生产 profile 指导编译优化、性能回归基线——本阶段打下的"go 行锁语言版本、toolchain 行锁工具链、构建可复现"基础，正是 ph16"用 profile 改变编译行为"的版本前提（PGO 结果依赖工具链版本，版本不统一则优化不可复现）。在此之前可先按推荐学习顺序巩固 ph13 性能优化与本阶段的练习与项目。

---

*本文全部"已验证"声明（go1.25.6 实测：go env 各键、语言门禁与工具链报错消息、go work 会话、file:// proxy 的 go install、依赖升级演练、示例 1~4 / 练习 1~3 / 项目 toolcheck 的命令与数字）均属实；GODEBUG 默认行为切换一节为官方文档机制描述（go.dev/doc/godebug），未在本环境逐项实测；版本发布日期与支持窗口以 [Go Release History](https://golang.google.cn/doc/devel/release.html) 为准；不虚构验证。*
