# Go 包管理与工程结构阶段

> go mod 是 Go 的依赖管理方案，internal 是编译器级可见性控制，标准布局是社区共识——三者共同构成 Go 项目的工程骨架。

## 1. 概述

Go 包管理与工程结构阶段的目标是：**掌握 go mod 依赖管理、internal 包可见性、标准项目布局与多模块 workspace**。ph01-ph04 全部以单文件 `go run main.go` 运行，本阶段正式进入多文件、多包、多模块的工程化开发——从"能跑"到"可维护"的转折点。

| 核心维度  | 覆盖内容                                                 |
| ----- | ---------------------------------------------------- |
| 模块管理  | go mod init/tidy、go.mod 指令、go.sum 校验、replace/exclude |
| 包可见性  | 大写公开、小写私有、internal 编译器级强制                            |
| 工程布局  | cmd/internal/pkg 目录约定、单模块与多模块项目组织                    |
| 多模块协作 | go.work、workspace 本地开发、多模块联调策略                       |

Go 包管理哲学是"最小满足"——MVS 算法不选最新版本而选满足所有约束的最小版本，与 npm（最左选择最新）根本不同。工程布局上，Go 不强制但强烈暗示：`cmd/` 放入口、`internal/` 放内部包、`pkg/` 放可复用库——不是目录仪式，是可测试可替换的工程解耦。

范围边界：不涉及 goroutine/channel（ph06）、`testing` 深入（ph08）、CI/CD；wire/Makefile 仅示例中点到即止。

## 2. 来源与演变

Go 依赖管理经历了从"无方案"到"默认方案"的 10 年演进：

| 阶段 | 版本 | 机制 | 核心问题 |
|------|------|------|---------|
| GOPATH | < 1.11 | 所有代码放 `$GOPATH/src`，`go get` 拉最新 | 无法指定版本、多项目冲突 |
| Vendor | 1.5 | `vendor/` 目录存放依赖副本 | 版本锁定靠人工、仓库膨胀 |
| Dep 实验 | 1.8~1.10 | 官方实验工具 `dep`，`Gopkg.toml` | 过渡方案，未纳入 go 命令 |
| Go Modules | 1.11 | `go.mod` + `go.sum`，`GO111MODULE=on` | 生态迁移期，与 GOPATH 并存 |
| 默认开启 | 1.16 | `GO111MODULE=on` 成为默认值 | GOPATH 模式退出历史 |
| Workspace | 1.18 | `go.work` 多模块本地开发 | 免频繁 replace 联调 |

关键转折：Go 1.16 后 `go mod init` 是所有项目的起点，项目可放在文件系统任意位置。MVS 来自 Go 团队对 npm/rust 生态的反思：不选"最新兼容版本"而选"满足所有人需求的最小版本"，避免依赖膨胀和不可复现构建。

本文示例以 **Go 1.21+** 为基线（`go.work` workspace 需 1.18+），验证工具链 Go 1.22.2 darwin/arm64。

## 3. 语法与参数

### 3.1 模块操作与 go.mod

模块生命周期从 `go mod init` 开始，`go mod tidy` 是高频日常操作：

| 命令 | 作用 |
|------|------|
| `go mod init <path>` | 初始化模块，创建 go.mod |
| `go mod tidy` | 添加缺失依赖、移除未使用依赖 |
| `go mod download` | 下载依赖到本地缓存 |
| `go mod vendor` | 复制依赖到 `vendor/` 目录 |
| `go mod why <pkg>` | 解释为什么需要某依赖 |
| `go get <pkg>@<v>` | 升级/降级/添加指定版本依赖 |
| `go work init [dirs...]` | 初始化 workspace |

go.mod 核心指令：

```text
module github.com/example/vehicle-server  // 模块路径——全局唯一标识
go 1.21                                   // 最低 Go 版本，影响语言特性与标准库行为
require github.com/gin-gonic/gin v1.9.1  // 直接依赖
require github.com/cespare/xxhash/v2 v2.2.0 // indirect  // 间接依赖
replace github.com/old/lib => github.com/new/lib v1.0.0  // 替换依赖路径
exclude github.com/buggy/lib v1.2.0                       // 排除特定版本
retract v1.0.0                                            // 声明撤回版本
```

`go mod tidy` 自动维护 `// indirect` 标记。`replace` 用于本地多模块开发，Go 1.18+ 配合 `go.work` 可省去频繁 replace。

### 3.2 go.sum —— 锁定依赖内容而非 lockfile

`go.sum` 每行格式为 `<module> <version> <hash>` 或 `<module> <version>/go.mod <hash>`。每行记录模块源码（`h1:` 前缀）或其 `go.mod` 文件的哈希。**go.sum 不是 lockfile**：Go 没有独立 lock 文件，版本约束在 `go.mod`，go.sum 确保下载内容与首次获取时一致。团队协作时 go.sum 必须提交到版本控制。

### 3.3 包可见性与 internal

可见性两级：大写公开（exported）、小写私有（unexported，仅同一 package 内）。`internal` 是编译器级第三级——**包含 `internal` 路径元素的包，只能被其父级目录树内的代码导入**：

```text
cmd/vehicle-server/main.go → import "example.com/proj/internal/vehicle" ✅ 父级是 proj/
pkg/codec/decoder.go       → import "example.com/proj/internal/vehicle" ❌ 不在父链上
// compiler error: "use of internal package ... not allowed"
```

外部模块无论如何都无法导入——编译期拒绝，非运行时检查。

### 3.4 标准目录布局

标准布局（非强制，多数知名项目遵循）：

```text
myproject/
├── go.mod
├── cmd/                    # 程序入口——每个子目录一个 main 包
│   ├── server/main.go
│   └── cli/main.go
├── internal/               # 内部包——编译器强制外部不可引用
│   ├── service/            #   业务逻辑
│   ├── repository/         #   数据访问
│   └── config/             #   配置加载
├── pkg/                    # 可复用公共库（允许外部引用）
│   └── codec/
└── api/ configs/ scripts/  # 其他辅助目录
```

核心原则：**不要为了目录而过度分层**。5 个文件的 CLI 工具放在根目录即可；代码量增长到需要按职责拆包时再引入 `cmd/internal`。分层的目的是可测试、可替换——不是目录仪式。

### 3.5 多模块 Workspace（Go 1.18+）

多模块本地开发时频繁 `replace` 很痛苦，`go.work` 解决：

```bash
go work init ./lib/shared ./services/collector ./services/reporter
# 生成 go.work：
# go 1.21
# use ( ./lib/shared  ./services/collector  ./services/reporter )
```

工作区内模块可直接 import 彼此，无需 replace。**go.work 只用于本地开发，不应提交到版本控制**。

### 3.6 配置加载与日志规范（internal/config + log）

`internal/config` 包的实际职责：从环境变量/JSON 文件读配置，集中校验，向上返回一个不可变的 Config 结构体。

```go
// internal/config/config.go
package config

import (
    "encoding/json"
    "fmt"
    "os"
)

type Config struct {
    Port    int    `json:"port"`
    DataDir string `json:"data_dir"`
}

func Load(path string) (*Config, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, fmt.Errorf("read config %s: %w", path, err)
    }
    var cfg Config
    if err := json.Unmarshal(data, &cfg); err != nil {
        return nil, fmt.Errorf("parse config %s: %w", path, err)
    }
    // 集中校验：宁可启动时失败，不要运行到一半才暴露配置错误
    if cfg.Port <= 0 || cfg.Port > 65535 {
        return nil, fmt.Errorf("invalid port: %d", cfg.Port)
    }
    return &cfg, nil
}
```

| 约定 | 做法 | 理由 |
|------|------|------|
| 错误用 `%w` 包装 | `fmt.Errorf("...: %w", err)` | 保留错误链，上层可 `errors.Is/As` |
| 配置结构体不可变 | 返回 `*Config` 后不再改 | 多 goroutine 读无竞态 |
| 启动时校验 | Load 内检查合法性 | fail fast，错误前置 |
| 环境变量覆盖 | 先读文件再读 env 覆盖（可选） | 12-factor 惯例，容器化部署友好 |

日志方面，标准库 `log` 包的工程约定：

```go
import "log"

func main() {
    log.SetFlags(log.LstdFlags | log.Lshortfile)   // 时间戳 + 文件名:行号

    cfg, err := config.Load("config.json")
    if err != nil {
        log.Fatalf("load config: %v", err)          // 打印后 os.Exit(1)，仅用于 main 启动期
    }
    log.Printf("server starting on :%d", cfg.Port)  // 常规运行日志
}
```

| 函数 | 行为 | 适用位置 |
|------|------|---------|
| `log.Print/Printf` | 打印后继续运行 | 业务运行日志 |
| `log.Fatal/Fatalf` | 打印后 `os.Exit(1)` | **仅限 main 启动失败**——库代码里 Fatal 会让调用方无法优雅处理 |
| `log.Panic` | 打印后 panic | 几乎不用 |

**约定**：库代码（internal/ 下的包）返回 `error` 不打印日志——打日志是 main 层（cmd/）的职责，否则同一错误在每一层被重复打印。结构化日志（`log/slog`，Go 1.21+）在 ph07 标准库展开。

## 4. 底层原理

### 4.1 最小版本选择算法（MVS）

MVS 是 Go 模块系统的核心算法，与 npm/pip 截然不同：

| 对比维度 | npm（最左选择） | Go MVS（最小版本选择） |
|----------|----------------|----------------------|
| 选版策略 | 选满足约束的最新版本 | 选满足所有约束的最小版本 |
| 依赖膨胀 | `node_modules` 黑洞 | 精确、最小、可复现 |
| 升级方向 | 被动：自动拉最新 | 主动：开发者显式 `go get` |
| 构建可复现 | 依赖 package-lock.json | go.mod 约束 + go.sum 校验 |

MVS 四步：构建需求图 → 确定最小版本（需求中最高，非所有可用中最高） → 用户显式 `go get` 才升级 → A 要 `v1.2`、B 要 `v1.3`，选 `v1.3`。项目只 require 了 `lib v1.0.0`，即使 `v2.0.0` 已发布，`go build` 仍下载 `v1.0.0`——**依赖不会在你不知情的情况下升级**。

### 4.2 go.sum 与 internal 的底层实现

`go.sum` 通过 `GOSUMDB`（sum.golang.org）全局透明日志防止篡改：本地已有 → 对比哈希不匹配则拒绝；本地无记录 → 查询 GOSUMDB 获取公证哈希。`GONOSUMDB`/`GOPRIVATE` 跳过私有模块校验。

`internal` 是 `go/build` 和 `cmd/compile` 中的硬编码逻辑——导入路径解析时发现 `internal` 元素则检查当前包路径是否以 `internal` 父目录为前缀，不满足即编译错误。外部模块无论如何构造 import 语句都无法绕过。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 新建 Go 项目 | go mod init、模块路径命名（仓库 URL） |
| 添加/升级依赖 | go get、go mod tidy、语义化版本 |
| 多程序入口 | `cmd/` 下多个 main 包，各自编译独立二进制 |
| 隐藏内部实现 | `internal/` 目录——编译器强制外部不可引用 |
| 本地多模块联调 | go.work、replace 指令 |
| 私有模块/企业仓库 | `GOPRIVATE`、`GONOSUMDB`、`GOPROXY` 配置 |
| 依赖审计 | go mod why、go mod graph、go mod verify |
| vendor 模式 | 离线构建、CI 加速、代码审计 |

不适合 `internal/` 的场景：单包项目不超过 5 个文件；实验/学习项目（过度分层增加理解成本）。

## 6. 代码示例

> 本节每个示例的完整可运行文件在 [`examples/`](./examples/) 目录，验证环境 Go 1.22.2（darwin/arm64），每个示例是独立 module，运行命令见 examples/README.md。

### 示例 1：Todo CLI —— 标准布局的最小项目

```text
todo-cli/
├── go.mod                          (module github.com/example/todo-cli, go 1.21)
├── cmd/todo/main.go
└── internal/todo/todo.go
```

```go
// cmd/todo/main.go
package main

import (
    "fmt"
    "os"
    "strconv"
    "github.com/example/todo-cli/internal/todo"
)

func main() {
    if len(os.Args) < 2 { fmt.Println("用法: todo <add|done|list> [args...]"); os.Exit(1) }
    store := todo.NewStore()
    switch os.Args[1] {
    case "add":
        if len(os.Args) < 3 { fmt.Println("用法: todo add <任务描述>"); return }
        fmt.Printf("已添加 #%d: %s\n", store.Add(os.Args[2]), os.Args[2])
    case "done":
        if len(os.Args) < 3 { fmt.Println("用法: todo done <任务ID>"); return }
        id, _ := strconv.Atoi(os.Args[2])
        store.Done(id)
        fmt.Printf("已完成 #%d\n", id)
    case "list":
        items := store.List()
        if len(items) == 0 { fmt.Println("暂无待办事项"); return }
        for _, item := range items {
            status := "[ ]"
            if item.Done { status = "[✓]" }
            fmt.Printf("%s #%d %s\n", status, item.ID, item.Title)
        }
    default: fmt.Printf("未知命令: %s\n", os.Args[1])
    }
}
```

```go
// internal/todo/todo.go
package todo

type Item struct {
    ID    int
    Title string
    Done  bool
}

type Store struct {
    items  []Item
    nextID int
}

func NewStore() *Store           { return &Store{nextID: 1} }
func (s *Store) Add(title string) int {
    id := s.nextID
    s.items = append(s.items, Item{ID: id, Title: title})
    s.nextID++
    return id
}
func (s *Store) Done(id int) {
    for i := range s.items {
        if s.items[i].ID == id { s.items[i].Done = true; return }
    }
}
func (s *Store) List() []Item    { return s.items }
```

外部模块无法 `import ".../internal/todo"`——编译器直接拒绝，这就是 internal 的工程价值。

完整文件：`examples/ex01-todo-cli/`（cmd/todo/main.go + internal/todo/todo.go）

### 示例 2：车辆数据服务 —— 车联网语义的标准布局

```text
vehicle-server/
├── go.mod                          (module github.com/example/vehicle-server, go 1.21)
├── cmd/vehicle-server/main.go
├── internal/vehicle/service.go
├── internal/canbus/frame.go
└── internal/config/config.go
```

```go
// cmd/vehicle-server/main.go
package main

import (
    "fmt"
    "log"
    "github.com/example/vehicle-server/internal/canbus"
    "github.com/example/vehicle-server/internal/config"
    "github.com/example/vehicle-server/internal/vehicle"
)

func main() {
    cfg := config.Load()
    fmt.Printf("车辆数据服务启动 [端口:%d 协议:%s]\n", cfg.Port, cfg.Protocol)
    svc := vehicle.NewService()
    frames := []canbus.Frame{
        {ID: 0x18F, Data: [8]byte{0x00, 0xFA, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00}},
        {ID: 0x7E8, Data: [8]byte{0x04, 0x41, 0x0C, 0x1A, 0xF4, 0x00, 0x00, 0x00}},
    }
    for _, f := range frames {
        fmt.Printf("  [0x%X] → %s\n", f.ID, svc.Process(f))
    }
    if err := svc.Shutdown(); err != nil { log.Fatal(err) }
}
```

```go
// internal/vehicle/service.go
package vehicle

import (
    "errors"
    "fmt"
    "sync"
    "github.com/example/vehicle-server/internal/canbus"
)

type Service struct { mu sync.Mutex; running bool }
func NewService() *Service { return &Service{running: true} }

func (s *Service) Process(frame canbus.Frame) string {
    switch frame.ID {
    case canbus.SpeedID:
        return fmt.Sprintf("车速: %.1f km/h", canbus.ParseSpeed(frame))
    case canbus.EngineRPM:
        return fmt.Sprintf("转速: %.0f rpm", canbus.ParseRPM(frame))
    }
    return "未知帧类型"
}

func (s *Service) Shutdown() error {
    s.mu.Lock(); defer s.mu.Unlock()
    if !s.running { return errors.New("服务已关闭") }
    s.running = false
    fmt.Println("车辆数据服务已安全关闭")
    return nil
}
```

```go
// internal/canbus/frame.go
package canbus

type Frame struct { ID uint32; Data [8]byte } // CAN 2.0A 标准帧
const ( SpeedID uint32 = 0x18F; EngineRPM uint32 = 0x7E8 )

func ParseSpeed(f Frame) float64 {
    if f.ID != SpeedID || len(f.Data) < 4 { return 0 }
    return float64(uint16(f.Data[2])<<8|uint16(f.Data[3])) * 0.01
}
func ParseRPM(f Frame) float64 {
    if f.ID != EngineRPM || len(f.Data) < 4 || f.Data[0] < 3 { return 0 }
    return (float64(f.Data[3])*256 + float64(f.Data[4])) / 4.0
}
```

```go
// internal/config/config.go
package config
type Config struct { Port int; Protocol string }
func Load() Config { return Config{Port: 8080, Protocol: "CAN"} }
```

三个 internal 包在模块内互引无障碍，对外部不可见——Go 工程化的标准姿势。

完整文件：`examples/ex02-vehicle-server/`（cmd/vehicle-server/main.go + internal/vehicle/service.go + internal/canbus/frame.go + internal/config/config.go）

### 示例 3：多模块 Workspace —— 共享库 + 多服务

```text
vehicle-platform/
├── go.work
├── lib/shared/          (module: ../shared, go 1.21)
│   └── vin.go
├── services/collector/  (module: ../collector + replace→../../lib/shared)
│   ├── go.mod
│   └── main.go
└── services/reporter/   (module: ../reporter + replace→../../lib/shared)
    ├── go.mod
    └── main.go
```

```text
// go.work
go 1.21
use ( ./lib/shared  ./services/collector  ./services/reporter )
```

```go
// lib/shared/vin.go —— 跨模块共享的 VIN 校验库
package shared

import "fmt"

func ValidateVIN(vin string) error {
    if len(vin) != 17 {
        return fmt.Errorf("VIN 长度 %d 不符合 17 位标准", len(vin))
    }
    for _, ch := range vin {
        if ch == 'I' || ch == 'O' || ch == 'Q' { // OBD-II: VIN 不含 I/O/Q 防混淆
            return fmt.Errorf("VIN 包含非法字符 '%c'", ch)
        }
    }
    return nil
}
```

```go
// services/collector/go.mod
module github.com/example/vehicle-platform/collector
go 1.21
require github.com/example/vehicle-platform/shared v0.0.0
replace github.com/example/vehicle-platform/shared v0.0.0 => ../../lib/shared
```

```go
// services/collector/main.go
package main

import (
    "fmt"
    "github.com/example/vehicle-platform/shared"
)

func main() {
    for _, vin := range []string{"LSVAA4184ES000001", "WVWZZZ3CZ8E123456", "INVALID"} {
        if err := shared.ValidateVIN(vin); err != nil {
            fmt.Printf("[拒绝] %s: %v\n", vin, err)
        } else {
            fmt.Printf("[接受] %s\n", vin)
        }
    }
}
```

```go
// services/reporter/main.go
package main

import (
    "fmt"
    "github.com/example/vehicle-platform/shared"
)

func main() {
    vin := "LSVAA4184ES000001"
    if err := shared.ValidateVIN(vin); err != nil {
        fmt.Printf("报告生成失败: %v\n", err)
        return
    }
    fmt.Printf("为 VIN=%s 生成日报 [模拟]\n  采集点: 120 组\n  异常: 无\n", vin)
}
```

`go.work` 使 workspace 内模块可直接 import 彼此无需 replace；示例同时展示 replace 是为说明两种路径的完整性。

完整文件：`examples/ex03-workspace/`（go.work + lib/shared/vin.go + services/collector/main.go + services/reporter/main.go）

## 7. 总结

### 关键要点

1. **go mod init 是所有项目的起点**：模块路径应为全局唯一仓库路径（如 `github.com/user/repo`）
2. **go mod tidy 是高频操作**：添加缺失依赖、移除未使用依赖——提交前必须执行
3. **go.sum 锁定依赖内容**：不是 lockfile，是校验和——保证团队复现同一构建
4. **internal 是编译器级防线**：外部模块 import internal 包直接编译错误，非 lint 警告
5. **大写公开、小写私有**：没有 public/private 关键字，首字母大小写决定可见性
6. **标准布局是建议不是规范**：小项目不必强行拆分 `cmd/internal/pkg`
7. **MVS 不选最新选最小**：依赖不会在 CI 中"悄悄升级"——与 npm 的根本差异
8. **go.work 用于本地多模块联调**：不应提交版本控制，是开发辅助工具

### 跨语言对比：包与模块

| 概念 | Go | Java | Python | Rust | C++ |
|------|-----|------|--------|------|-----|
| 依赖管理 | go.mod / go.sum | pom.xml / build.gradle | requirements.txt / pyproject.toml | Cargo.toml / Cargo.lock | CMakeLists.txt / vcpkg.json |
| 版本选择 | MVS（最小版本） | 最近版本（Maven） | pip 解析器回溯 | Cargo 语义化解析 | 无统一机制 |
| 可见性 | 大小写 + internal | public/protected/private | `_`前缀约定（无强制） | `pub` / `pub(crate)` | public/protected/private |
| 包/模块 | package + module | package + JPMS | package + venv | crate + mod | namespace + 头文件 |
| workspace | go.work | Maven reactor | pip workspace / poetry | Cargo workspace | add_subdirectory |
| lock 文件 | go.sum（校验和） | 无内置 | 无内置 | Cargo.lock | 无内置 |
| 构建工具 | `go build` | Maven/Gradle | pip/setuptools/poetry | `cargo build` | CMake/Make/Bazel |

### 阶段验收清单

- [ ] 能使用 `go mod init/tidy` 管理依赖，解释 `go.mod` 与 `go.sum` 的区别
- [ ] 能使用 `internal` 包并理解编译器强制机制
- [ ] 能组织 `cmd/internal/pkg` 标准布局，创建 `go.work` 管理多模块本地开发
- [ ] 能把单文件程序拆分为 cmd+internal 多包结构
- [ ] 能写带配置加载模块的 CLI 工具（读 JSON/环境变量，fail fast）

### 动手练习

本阶段练习见 [exercises/](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：拆分单文件程序、写 CLI 工具、写配置加载模块、建立标准项目结构共 4 题。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [project/](./project/)：**标准 Go 项目模板**（cmd/ 入口 + internal/ 业务包 + pkg/ 公共库的标准布局骨架，内置可运行的设备状态管理示例命令，可作为新项目起点）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[并发编程 Goroutine 与 Channel 阶段](../ph06-concurrency/06-concurrency.md) —— goroutine 调度、channel 通信、select 多路复用、WaitGroup/Mutex 同步、context 取消传播、worker pool 模式。
