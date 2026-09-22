# ph15 Go 版本、工具链示例

> 四个示例覆盖本阶段全部"可运行"知识点：构建信息与版本印章（ex01-buildinfo）→ 语义化版本比较（ex02-semver）→ go env 语义探测（ex03-goenv-probe）→ 多模块 workspace（ex04-workspace，内含 service-a 与 sharedlib 两个 module）。全部为完整可运行 Go module（ex04 是 workspace 形态），零第三方依赖，在 go1.25.6（darwin/arm64）实测通过（`go vet`、`go test`、`go test -race` 全绿）。

| 示例 | 一句话说明 | 运行命令（进入各自子目录） |
|------|-----------|--------------------------|
| ex01-buildinfo | 二进制内嵌的版本画像：runtime.Version()（工具链版本）、debug.ReadBuildInfo()（模块路径/模块版本/go 版本/VCS 印章）、`-ldflags -X` 注入 | `go test -v ./...`；`go run .`；`go build -ldflags "-X main.version=v1.2.3" -o /tmp/ex01 . && /tmp/ex01`；`go version -m /tmp/ex01` |
| ex02-semver | 模块版本排序规则：数字段比较（v1.9 < v1.10）、缺段补 0、预发布排序、+build 元数据忽略 | `go test -v ./...`；`go run .` |
| ex03-goenv-probe | 调用 `go env -json` 拉取关键键并逐条注解语义（GOROOT/GOPATH/GOMODCACHE/GOCACHE 四类路径的区别） | `go test -v ./...`；`go run .` |
| ex04-workspace | 多模块 workspace：go.work use ./service-a ./sharedlib，本地未发布模块互相依赖、改源码即生效 | 在 ex04-workspace 目录：`go run ./service-a`；`go test ./service-a/... ./sharedlib/...`；`go env GOWORK` |

## 实测记录（go1.25.6 darwin/arm64，2026-09-02）

数字随机器与 Go 版本波动，以本机重跑为准；本表全部为本环境实测输出。

### ex01：构建信息实测（go run .，位于 TenetLang git 仓库内）

```
runtime.Version(): go1.25.6
version var      : dev
main module      : tenetlang/go/ph15-version-toolchain/examples/ex01-buildinfo (devel)
go version(build): go1.25.6
```

**`go build -ldflags "-X main.version=v1.2.3"` 后**：`version var: v1.2.3`，并多出三行 VCS 印章：

```
setting vcs.revision : 10e66b40db098e05bff467ac10914d464dda792e
setting vcs.time     : 2026-09-01T12:07:06Z
setting vcs.modified : true   ← 本仓库工作区未提交（含本阶段新增文件）
```

**结论**：① `runtime.Version()` = 编译该二进制的工具链版本（本环境 go1.25.6）；② 模块版本来自 `debug.ReadBuildInfo()`——仓库打了 tag 才是 vX.Y.Z，否则 `(devel)`（实测：在 /tmp 建 git 仓库打 v1.0.0 tag 后构建，`mod` 字段显示 v1.0.0、`vcs.modified=false`，见主文档 3.3/6 节）；③ `-ldflags "-X main.version=..."` 是构建期注入业务版本号的标准手法，`go version -m <二进制>` 读出全部构建信息——"这二进制是谁、用什么版本、哪个 commit 编出来的"从此可回答。

### ex02：语义化版本比较实测（go test -v ./...：16 个子测试全 PASS）

```
Compare("v1.9.0", "v1.10.0") = -1   ← 数字段比较：9 < 10（字典序会给出相反结论）
Compare("v1.10.0", "v1.9.0") = 1
Compare("v1.2.3", "v2.0.0") = -1    ← major 优先
Compare("v1.2", "v1.2.1") = -1      ← 缺段补 0：1.2 == 1.2.0 < 1.2.1
Compare("v1.2.3-rc.1", "v1.2.3") = -1   ← 预发布 < 正式版
Compare("v1.2.3-alpha", "v1.2.3-beta") = -1   ← 字母标识按字典序
Compare("v1.2.3-1", "v1.2.3-alpha") = -1      ← 数值标识 < 字母标识
Compare("v1.2.3+incompatible", "v1.2.3") = 0  ← 构建元数据不参与排序
```

**结论**：go 工具给模块版本排序用的是语义化版本规则，核心三点——① 数字段**数值**比较（v1.9 < v1.10）；② 预发布版本（-alpha/-beta/-rc）排在正式版之前；③ `+xxx` 元数据（含 Go 大版本标记 `+incompatible`）不参与排序。生产代码请用官方扩展包 `golang.org/x/mod/semver`，本示例是规则一致的教学子集（不引第三方依赖）。

### ex03：go env 关键项实测（go run .，缓存已重定位到 /tmp 的环境）

```
GOROOT       = /opt/homebrew/Cellar/go/1.25.6/libexec  ← 工具链安装目录
GOPATH       = /tmp/gopath                             ← 工作区根（默认 ~/go）
GOMODCACHE   = /tmp/gomodcache                         ← 模块缓存（默认 $GOPATH/pkg/mod）
GOCACHE      = /tmp/gocache                            ← 构建缓存（可随时删）
GOBIN        = (空)                                     ← go install 安装目录（默认 $GOPATH/bin）
GOTOOLCHAIN  = auto                                    ← auto / local / path / goX.Y.Z
GOVERSION    = go1.25.6                                ← go version 的机器可读形式
GOPROXY      = https://proxy.golang.org,direct         ← 模块代理
GOSUMDB      = sum.golang.org                          ← 校验和数据库
GOWORK       = (空)                                     ← 非空 = 处于 workspace 中
```

**结论**：`go env` 输出的是"go 命令实际看到的环境"（默认值 + GOENV 配置文件 + 环境变量覆盖后）。四条路径最容易混——**GOROOT** 是工具链安装目录、**GOPATH** 是工作区根、**GOMODCACHE** 是模块源码缓存（`go mod download` 落点）、**GOCACHE** 是编译产物缓存（内容寻址，删了也只是下次重编）。本仓库验证环境把三者重定位到 /tmp（沙箱限制 + 顺便演示"缓存位置可迁移"），默认值见主文档 3.2 节。

### ex04：workspace 实测（cd examples/ex04-workspace）

```
$ go env GOWORK
…/languages/go/ph15-version-toolchain/examples/ex04-workspace/go.work
$ go run ./service-a
Hello from sharedlib, service-a!
$ go test ./service-a/... ./sharedlib/...
ok  	tenetlang/go/ph15-version-toolchain/examples/ex04-workspace/service-a	0.005s
ok  	tenetlang/go/ph15-version-toolchain/examples/ex04-workspace/sharedlib	0.005s
$ go list -m -json tenetlang/go/ph15-version-toolchain/examples/ex04-workspace/sharedlib | head -3
{ "Path": "…/ex04-workspace/sharedlib",
  "Main": true,
  "Dir": "…/ex04-workspace/sharedlib" }
```

**结论**：service-a/go.mod 只写 `require sharedlib v0.0.0`（v0.0.0 = 占位，无发布版本），go.work 的 use 列表让该模块路径解析到本地目录（`go list -m` 输出 Main:true）——`go run ./service-a` 直接用本地 sharedlib 源码。**两个实测边界**：① workspace 根目录的 `./...` pattern 报 `does not contain modules listed in go.work`（多模块场景要按模块给 pattern：`./service-a/... ./sharedlib/...`）；② `go mod tidy` / `go list -m all` 这类需要**版本元数据**的命令仍会去 proxy 找 v0.0.0（workspace 只覆盖构建期解析，不替代"发布版本"）——完整会话输出见主文档 3.5 节。

## 验证说明

- 全部示例 `go vet ./...`、`go test ./...`、`go test -race ./...` 通过（ex04 为 `go vet/test/-race ./service-a/... ./sharedlib/...`；race 零数据竞争）
- 实测环境：go1.25.6 darwin/arm64，Apple M4 Pro；GOCACHE/GOMODCACHE/GOPATH 重定位到 /tmp；零第三方依赖，可离线复现
- ex01 在 TenetLang 仓库内构建时 VCS 印章取 TenetLang 的 HEAD（vcs.modified=true 因为本阶段文件尚未提交）；打 tag 场景的干净输出见主文档 6 节示例 1
