# Go 语言学习 Roadmap

> 面向后端服务、云原生、车联网和 IoT 数据平台，重点建立简洁工程化、并发和服务交付能力。

## 1. Go 基础语法阶段

> 📖 详细展开版见 [ph01-basic-syntax/01-basic-syntax.md](./ph01-basic-syntax/01-basic-syntax.md)

### 目标

能写简单 Go 程序，理解 Go 的简洁语法和工程风格。

### 学习内容

- package main、import、func main
- 变量、常量、基本类型
- if、switch、for
- 数组、slice、map、string、pointer

### 必会概念

- Go 没有 while，for 是唯一循环语句
- 短变量声明适合局部变量
- 零值是 Go 设计的重要部分
- 代码格式由 gofmt 统一

### 示例

```go
package main

import "fmt"

func main() {
    fmt.Println("Hello, Go")
}
```

### 练习

- 计算器
- 判断素数
- 字符串反转
- map 统计词频

### 阶段验收

- 能独立运行 go run
- 能写出基础控制流和函数
- 能使用 gofmt 格式化代码

### 推荐项目

- Todo CLI
- 简单通讯录

## 2. 函数与错误处理阶段

> 📖 详细展开版见 [ph02-func-error/02-func-error.md](./ph02-func-error/02-func-error.md)

### 目标

掌握 Go 的函数设计和显式错误处理习惯。

### 学习内容

- 函数、多返回值、命名返回值
- 可变参数、匿名函数、闭包
- defer、panic、recover
- error、errors.New、fmt.Errorf

### 必会概念

- 普通错误用 error 返回
- panic 只用于不可恢复错误
- defer 适合释放资源
- 错误信息要携带上下文

### 示例

```go
func divide(a, b int) (int, error) {
    if b == 0 {
        return 0, errors.New("divide by zero")
    }
    return a / b, nil
}
```

### 练习

- 安全除法
- 文件读取错误处理
- 配置解析错误处理
- 自定义业务错误

### 阶段验收

- 能写清晰错误返回路径
- 能正确使用 defer
- 能避免用 panic 控制业务流程

### 推荐项目

- 配置加载器
- 命令行参数校验工具

## 3. Slice、Map、Struct 阶段

> 📖 详细展开版见 [ph03-slice-map-struct/03-slice-map-struct.md](./ph03-slice-map-struct/03-slice-map-struct.md)

### 目标

掌握 Go 最常用的数据组织方式。

### 学习内容

- slice 与 array
- len、cap、append、切片共享底层数组
- map 查询、删除、遍历
- struct 定义和组合

### 必会概念

- slice 是描述符，不是数组本体
- map 遍历顺序不稳定
- map 不是并发安全的
- struct 组合优先于继承式思维

### 示例

```go
type Motor struct {
    ID      int
    Speed   int
    Enabled bool
}
```

### 练习

- 学生管理系统
- 设备状态表
- map + struct 管理车辆数据
- slice 扩容实验

### 阶段验收

- 能解释 slice 的 len/cap
- 能正确判断 map key 是否存在
- 能用 struct 表达业务数据

### 推荐项目

- 设备状态管理 CLI
- 车辆数据缓存结构

## 4. 方法与接口阶段

> 📖 详细展开版见 [ph04-method-interface/04-method-interface.md](./ph04-method-interface/04-method-interface.md)

### 目标

理解 Go 的面向接口编程，用小接口降低耦合。

### 学习内容

- 方法、值接收者、指针接收者
- interface、隐式实现
- 组合与嵌入
- 空接口与类型断言

### 必会概念

- 接口由使用方定义通常更灵活
- 小接口比大接口更可维护
- 指针接收者可修改对象状态
- nil 接口和持有 nil 指针的接口不同

### 示例

```go
type Sensor interface {
    Read() float64
}
```

### 练习

- Sensor 接口
- Storage 接口
- Logger 接口
- 用接口模拟 CAN/UART 数据读取

### 阶段验收

- 能设计小而清晰的接口
- 能解释隐式实现
- 能通过接口 mock 依赖

### 推荐项目

- 可替换存储层的 Todo 服务
- 设备采集抽象层

## 5. 包管理与工程结构阶段

> 📖 详细展开版见 [ph05-pkg-structure/05-pkg-structure.md](./ph05-pkg-structure/05-pkg-structure.md)

### 目标

能组织真实 Go 工程项目。

### 学习内容

- go mod、go.mod、go.sum
- package、module、internal
- cmd、internal、pkg 目录约定
- 配置、日志、测试

### 必会概念

- module 是依赖版本边界
- internal 包限制外部引用
- cmd 放程序入口，internal 放内部业务
- 不要为了目录而过度分层

### 示例

```text
myapp/
├── go.mod
├── cmd/server/main.go
├── internal/service/
├── internal/repository/
└── README.md
```

### 练习

- 拆分单文件程序
- 写 CLI 工具
- 写配置加载模块
- 建立标准项目结构

### 阶段验收

- 能使用 go mod tidy
- 能解释包可见性
- 能构建多包项目

### 推荐项目

- 标准 Go 项目模板
- 命令行工具集合

## 6. 并发编程 Goroutine 与 Channel 阶段

> 📖 详细展开版见 [ph06-concurrency/06-concurrency.md](./ph06-concurrency/06-concurrency.md)

### 目标

掌握 Go 的核心并发模型。

### 学习内容

- goroutine、channel
- buffered/unbuffered channel
- select、WaitGroup、Mutex、RWMutex
- context、timeout、cancellation
- worker pool、fan-in、fan-out

### 必会概念

- goroutine 不是无限便宜，需要生命周期管理
- channel 用于通信，mutex 用于保护共享状态
- context 用于取消和超时传播
- 关闭 channel 应由发送方负责

### 示例

```go
var wg sync.WaitGroup
wg.Add(1)
go func() {
    defer wg.Done()
    fmt.Println("worker")
}()
wg.Wait()
```

### 练习

- worker pool
- 并发爬虫
- 任务超时控制
- 数据采集并发处理

### 阶段验收

- 能避免 goroutine 泄漏
- 能使用 context 控制生命周期
- 能用 race detector 检查并发代码

### 推荐项目

- 并发日志处理器
- 数据采集任务池

## 7. 标准库阶段

> 📖 详细展开版见 [ph07-stdlib/07-stdlib.md](./ph07-stdlib/07-stdlib.md)

### 目标

熟悉 Go 标准库，优先用标准库完成常见任务。

### 学习内容

- fmt、os、io、bufio、strings、strconv
- time、context、sync
- net、net/http、encoding/json
- errors、log、flag、testing

### 必会概念

- 标准库覆盖大量后端基础能力
- io.Reader/io.Writer 是核心抽象
- net/http 可直接构建生产级基础服务
- JSON tag 是接口协议的一部分

### 示例

```go
http.HandleFunc("/hello", func(w http.ResponseWriter, r *http.Request) {
    fmt.Fprintln(w, "hello")
})
http.ListenAndServe(":8080", nil)
```

### 练习

- 文件统计工具
- JSON 配置解析器
- HTTP API server
- 命令行 Todo 工具

### 阶段验收

- 能用标准库读写文件和处理 JSON
- 能写基础 HTTP 服务
- 能使用 testing 写单元测试

### 推荐项目

- HTTP health check 工具
- 日志分析小工具

## 8. 测试与工程质量阶段

> 📖 详细展开版见 [ph08-testing/08-testing.md](./ph08-testing/08-testing.md)

### 目标

写可维护、可测试的 Go 代码。

### 学习内容

- testing、表格驱动测试
- benchmark、mock、fuzz testing
- race detector、coverage
- go test、go fmt、go vet、golangci-lint

### 必会概念

- 表格驱动测试是 Go 常用风格
- benchmark 要结合 benchmem 看分配
- race detector 可发现数据竞争
- 接口有助于隔离测试依赖

### 示例

```go
func TestAdd(t *testing.T) {
    got := Add(1, 2)
    if got != 3 {
        t.Fatalf("got %d", got)
    }
}
```

### 练习

- 给业务函数写表格驱动测试
- 给 handler 写测试
- 给并发代码跑 race
- 给核心模块写 benchmark

### 阶段验收

- 能一键运行测试
- 能解释覆盖率和 benchmark 结果
- 能用 mock 隔离外部依赖

### 推荐项目

- 带测试的 HTTP API
- 并发模块 benchmark

## 9. Web 后端开发阶段

> 📖 详细展开版见 [ph09-web-backend/09-web-backend.md](./ph09-web-backend/09-web-backend.md)

### 目标

能用 Go 写后端 API 服务。

### 学习内容

- HTTP、REST API、路由
- middleware、JSON 请求响应
- 参数校验、JWT、Cookie/Session、CORS
- 文件上传、日志、错误码、API 文档、限流
- Gin、Echo、Fiber、Chi

### 必会概念

- handler 要清晰分离解析、校验、业务和响应
- 中间件适合横切逻辑
- API 错误结构要统一
- 超时和限流是服务稳定性的基础

### 示例

```go
mux := http.NewServeMux()
mux.HandleFunc("GET /ping", func(w http.ResponseWriter, r *http.Request) {
    w.Write([]byte("pong"))
})
http.ListenAndServe(":8080", mux)
```

本阶段示例全部用标准库 net/http（Go 1.22 方法路由）；Gin / Echo / Fiber / Chi 的选型背景与对比见阶段笔记第 2 章。

### 练习

- Todo API
- 登录注册
- 文件上传服务
- 设备状态查询 API

### 阶段验收

- 能设计 REST 接口
- 能处理参数校验和统一错误
- 能写出基础认证流程

### 推荐项目

- 车辆数据上报 API
- 后台管理服务

## 10. 数据库阶段

> 📖 详细展开版见 [ph10-database/10-database.md](./ph10-database/10-database.md)

### 目标

掌握 Go 操作数据库和缓存。

### 学习内容

- SQL、MySQL、PostgreSQL
- database/sql、sqlx、gorm、ent、bun
- Redis、go-redis
- 连接池、事务、索引、慢查询、迁移

### 必会概念

- 先理解 database/sql，再选择 ORM
- 事务边界要由业务定义
- SQL 注入必须通过参数化避免
- Redis 适合缓存、锁和热点数据

### 示例

```go
db, err := sql.Open("mysql", dsn)
if err != nil {
    return err
}
defer db.Close()
```

### 练习

- 用户表 CRUD
- 设备状态存储
- Redis 缓存用户信息
- 数据库事务处理

### 阶段验收

- 能写参数化 SQL
- 能处理事务提交和回滚
- 能设计基础缓存策略

### 推荐项目

- MySQL + Redis 的 Todo 服务
- 车辆轨迹存储服务

## 11. 微服务与 RPC 阶段

> 📖 详细展开版见 [ph11-microservice-rpc/11-microservice-rpc.md](./ph11-microservice-rpc/11-microservice-rpc.md)

### 目标

能写可扩展的服务系统。

### 学习内容

- 微服务基础、服务注册发现、配置中心
- RPC、gRPC、Protocol Buffers
- timeout、retry、熔断、限流
- 可观测性三支柱概念（日志/指标/追踪；工具链接入属 ph12）

### 必会概念

- 微服务解决组织和扩展问题，也引入复杂度
- RPC 必须有超时
- 重试要考虑幂等
- 可观测性是分布式系统的必需品

### 示例

```text
protobuf → 定义 service → 生成 Go 代码 → server → client → interceptor
```

### 练习

- 用户服务
- 订单服务
- 设备管理服务
- gRPC 通信 demo

### 阶段验收

- 能定义 protobuf 服务
- 能实现 gRPC server/client
- 能解释可观测性三支柱与 traceparent 上下文传播（工具链接入属 ph12）

### 推荐项目

- 设备数据采集微服务
- gRPC 服务框架 demo

## 12. 云原生与部署阶段

> 📖 详细展开版见 [ph12-cloud-native/12-cloud-native.md](./ph12-cloud-native/12-cloud-native.md)

### 目标

能把 Go 服务部署到真实环境。

### 学习内容

- Linux、Docker、Dockerfile、Docker Compose
- Kubernetes、Helm
- CI/CD、GitHub Actions/GitLab CI
- 健康检查、日志采集、监控告警
- 可观测性工具链接入：Prometheus、Grafana、Jaeger、OpenTelemetry
- API Gateway 与流量入口治理
- 灰度发布、滚动升级

### 必会概念

- Go 适合构建小型静态二进制
- 容器镜像应尽量小且可复现
- 健康检查和优雅退出很重要
- 配置不应写死在镜像里

### 示例

```dockerfile
FROM golang:1.22 AS builder
WORKDIR /app
COPY . .
RUN go build -o server ./cmd/server
```

### 练习

- 写 Dockerfile
- 用 Compose 启动 Go + MySQL + Redis
- 部署到 Kubernetes
- 接入 Prometheus

### 阶段验收

- 能构建镜像并启动服务
- 能配置环境变量和健康检查
- 能查看日志和指标
- 能接入 Prometheus 指标与 OpenTelemetry 追踪

### 推荐项目

- 可部署 API 服务模板
- Kubernetes 部署示例

## 13. 性能优化阶段

> 📖 详细展开版见 [ph13-perf-optimization/13-perf-optimization.md](./ph13-perf-optimization/13-perf-optimization.md)

### 目标

能分析和优化 Go 程序性能。

### 学习内容

- benchmark、pprof、trace
- GC 基础、内存分配分析
- CPU/goroutine/mutex/block profile
- escape analysis、sync.Pool
- 减少锁竞争和不必要分配

### 必会概念

- 先 profile，再优化
- 分配次数会影响 GC 压力
- goroutine 泄漏也是性能问题
- sync.Pool 只适合可复用临时对象

### 示例

```bash
go test -bench=. -benchmem
go tool pprof
```

### 练习

- 优化 JSON 解析
- 分析高并发接口
- 查 goroutine 泄漏
- 优化锁竞争

### 阶段验收

- 能生成并阅读 pprof
- 能解释逃逸分析输出
- 能用 benchmark 验证优化效果

### 推荐项目

- 高并发接口压测与优化
- 日志解析性能优化

## 14. 高级 Go 阶段

> 📖 详细展开版见 [ph14-advanced-go/14-advanced-go.md](./ph14-advanced-go/14-advanced-go.md)

### 目标

理解 Go 底层机制和高级工程能力。

### 学习内容

- Generics
- Go 内存模型、GMP、GC
- channel、map、slice、interface 底层机制
- defer、panic/recover 原理
- reflection、unsafe、cgo

### 必会概念

- reflect、unsafe、cgo 是高级工具，业务代码慎用
- interface 动态分发有成本
- map 并发写会出问题
- GMP 决定 goroutine 调度行为

### 示例

```go
func Max[T ~int | ~float64](a, b T) T {
    if a > b { return a }
    return b
}
```

### 练习

- 泛型工具库（Map/Filter/Reduce + 类型集约束）
- 观察 slice 扩容（扩容序列观察器 + 结构性规则测试）
- defer / panic-recover 语义实验（六语义断言 + SafeCall 模式）
- 写反射版配置加载器（JSON 默认值 + env 覆盖）

「用 cgo 调 C 库」由 ph14 示例 6（examples/ex06-cgo）覆盖，未单列为练习；「用 pprof 分析高 CPU」属 ph13 性能优化阶段，此处不重复。

### 阶段验收

- 能解释 GMP/GC 大致机制
- 能谨慎使用泛型和反射
- 能定位底层性能问题

### 推荐项目

- 泛型工具库
- Go runtime 机制实验笔记

## 15. Go 版本、工具链阶段

> 📖 详细展开版见 [ph15-version-toolchain/15-version-toolchain.md](./ph15-version-toolchain/15-version-toolchain.md)

### 目标

理解 Go 版本演进、工具链和模块兼容策略。

### 学习内容

- Go release 节奏
- go env、go version、go install
- go work、workspace
- toolchain 指令
- 模块版本、语义化版本

### 必会概念

- go.mod 中的 go 版本影响语言和标准库行为
- 工具链版本应在团队中统一
- go work 适合多模块本地开发
- 依赖升级需要测试验证

### 示例

```bash
go version
go env
go work init ./service-a ./service-b
```

### 练习

- 创建多模块 workspace
- 升级一个依赖版本
- 记录项目 Go 版本要求

### 阶段验收

- 能解释 go.mod 的 go 版本
- 能管理多模块开发
- 能稳定复现构建环境

### 推荐项目

- 多服务 workspace 示例
- Go 工具链检查脚本

## 16. PGO 与高级性能优化阶段

> 📖 详细展开版见 [ph16-pgo-advanced-perf/16-pgo-advanced-perf.md](./ph16-pgo-advanced-perf/16-pgo-advanced-perf.md)

### 目标

了解生产流量指导优化和更高级的性能调优方法。

### 学习内容

- Profile Guided Optimization
- CPU profile 采集
- 热点路径识别
- 内存布局和分配优化
- 性能回归基线

### 必会概念

- PGO 需要代表性 profile
- 性能优化要有基线和回归检查
- 热点代码更值得优化
- 不要为低频路径牺牲可读性

### 示例

```bash
go build -pgo=cpu.pprof ./cmd/server
```

### 练习

- 采集压测 profile
- 用 PGO 构建服务
- 对比优化前后延迟和吞吐

### 阶段验收

- 能说明 PGO 适用条件
- 能产出性能对比报告
- 能避免无证据优化

### 推荐项目

- API 服务 PGO 实验
- 性能回归测试脚本

## 17. 架构设计与代码分层阶段

> 📖 详细展开版见 [ph17-architecture-layering/17-architecture-layering.md](./ph17-architecture-layering/17-architecture-layering.md)

### 目标

能组织中大型 Go 服务代码，避免业务逻辑混乱。

### 学习内容

- handler/service/repository 分层
- 领域模型和 DTO
- 依赖注入
- 配置、日志、错误码、接口边界
- 单体到服务化演进

### 必会概念

- 分层为可测试和可演进服务，不是目录仪式
- handler 不应承载复杂业务
- repository 隔离存储细节
- 接口应定义在使用方附近

### 示例

```text
handler → service → repository → database
```

### 练习

- 重构 Todo API 分层
- 抽象存储接口
- 给 service 层写单元测试

### 阶段验收

- 能说明每层职责
- 能通过接口替换依赖
- 能控制循环依赖

### 推荐项目

- 分层 Web API 模板
- 车联网设备管理服务

## 18. API 设计与兼容性阶段

> 📖 详细展开版见 [ph18-api-design-compat/18-api-design-compat.md](./ph18-api-design-compat/18-api-design-compat.md)

### 目标

设计稳定、清晰、可演进的 API。

### 学习内容

- REST/gRPC 接口设计
- 版本管理
- 错误码、分页、过滤、排序
- 向后兼容
- OpenAPI / protobuf 兼容规则

### 必会概念

- 字段只增不删更利于兼容
- 错误结构要稳定
- 幂等接口更适合重试
- API 文档应和实现同步

### 示例

```json
{
  "code": "DEVICE_NOT_FOUND",
  "message": "device not found"
}
```

### 练习

- 设计设备查询 API
- 设计统一错误结构
- 为接口补 OpenAPI 文档

### 阶段验收

- 能说明接口兼容策略
- 能处理分页和过滤
- 能给 API 写示例和错误说明

### 推荐项目

- 设备管理 API 规范
- gRPC 兼容性实验

## 19. 消息队列与事件驱动深入阶段

> 📖 详细展开版见 [ph19-mq-event-driven/19-mq-event-driven.md](./ph19-mq-event-driven/19-mq-event-driven.md)

### 目标

掌握异步解耦和高吞吐数据处理设计。

### 学习内容

- Kafka、NATS、RabbitMQ
- 生产者、消费者、消费者组
- 顺序性、重复消费、幂等
- 重试、死信队列、积压处理
- 事件驱动架构

### 必会概念

- 消息至少一次投递意味着消费者要幂等
- 分区影响顺序性和并行度
- 积压需要监控和降级策略
- 事件 schema 需要版本管理

### 示例

```text
采集服务 → Kafka topic → 清洗服务 → 存储服务
```

### 练习

- Kafka 消费车辆数据
- NATS 发布订阅 demo
- 实现幂等消费
- 处理重试和死信

### 阶段验收

- 能解释消息可靠性取舍
- 能设计事件格式
- 能监控消费延迟

### 推荐项目

- 车辆遥测消费服务
- 日志采集流水线

## 20. 配置管理与发布策略阶段

> 📖 详细展开版见 [ph20-config-release/20-config-release.md](./ph20-config-release/20-config-release.md)

### 目标

让服务在多环境中安全发布和运行。

### 学习内容

- 环境变量、配置文件、配置中心
- feature flag
- 灰度发布、滚动发布、回滚
- 版本号、构建信息、迁移脚本
- 运行时配置热更新边界

### 必会概念

- 配置和代码要分离
- 敏感信息不能进仓库
- 发布要可回滚
- 数据库变更要兼容旧版本服务

### 示例

```bash
APP_ENV=prod ./server
```

### 练习

- 写配置加载模块
- 注入构建版本信息
- 设计灰度开关
- 写发布检查清单

### 阶段验收

- 能在 dev/test/prod 使用不同配置
- 能快速定位运行版本
- 能安全回滚服务

### 推荐项目

- 多环境配置模块
- 服务发布 checklist

## 21. IoT / 车联网 / 嵌入式相关 Go 阶段

### 目标

用 Go 构建车联网后端、边缘网关和数据平台。

### 学习内容

- MQTT、WebSocket、TCP/UDP、HTTP API、gRPC
- Kafka、NATS、RabbitMQ
- Redis、时序数据库、Prometheus
- OTA、设备影子、设备认证、数据上报、指令下发

### 必会概念

- Go 适合设备接入、数据采集、边缘网关和云端服务
- 设备协议要处理断线重连、幂等和鉴权
- 遥测数据要考虑吞吐、存储和查询模式

### 示例

```text
设备 → MQTT 接入 → Go 清洗服务 → Kafka → 存储/告警/可视化
```

### 练习

- MQTT 设备接入服务
- 车辆遥测数据接收服务
- OTA 升级服务
- WebSocket 实时监控面板

### 阶段验收

- 能接入设备数据并落库
- 能处理断线重连和认证
- 能监控服务吞吐和错误率

### 推荐项目

- 车联网数据平台
- 边缘网关转发服务

## 附录：阶段性项目验收标准

### 目标

用项目验证 Go 学习成果。

### 学习内容

- 功能验收、测试验收、部署验收
- README、Makefile、Dockerfile
- 单元测试、集成测试、压测
- 日志、指标、追踪

### 必会概念

- Go 项目交付不仅是 go run 成功
- 服务需要可观测和可部署
- 测试和 CI 是质量底线

### 示例

```text
验收项：
- go test ./... 通过
- go test -race ./... 通过
- Docker 镜像可启动
- /healthz 可用
```

### 练习

- 给项目补测试
- 给项目补 Dockerfile
- 给项目补 health check
- 接入基础指标

### 阶段验收

- 能交付可运行可测试的 CLI 工具（初级）
- 能交付可测试可部署的 HTTP API（中级）
- 能交付可观测可压测可回滚的服务（高级）

### 推荐项目

- Go 服务模板
- 车联网数据接入服务

## 推荐学习顺序

```text
Go 基础语法
→ 函数 / error / defer
→ slice / map / struct
→ method / interface
→ go mod / package
→ goroutine / channel
→ context / sync
→ 标准库
→ 测试
→ HTTP API
→ 数据库 / Redis
→ 微服务 / gRPC
→ Docker / Kubernetes
→ pprof / 性能优化
→ Go 底层原理
→ 车联网 / IoT / 云原生项目
```

## Go 和 C / C++ / Rust 的区别

| 方向 | C | C++ | Rust | Go |
| --- | --- | --- | --- | --- |
| 内存管理 | 手动 | RAII | 所有权 | GC |
| 学习曲线 | 中等 | 高 | 高 | 中低 |
| 并发模型 | pthread | thread/async | thread/async | goroutine + channel |
| 工程效率 | 中等 | 中等 | 中等 | 高 |
| 适合方向 | 系统/底层 | 系统/高性能 | 系统/安全 | 后端/云原生/工具 |

## 项目路线

### 初级项目

- 计算器
- Todo CLI
- 通讯录
- 文件统计工具
- JSON 格式化工具

### 中级项目

- HTTP API 服务
- 用户登录注册系统
- Redis 缓存服务
- MySQL CRUD 系统
- Worker Pool 任务系统

### 高级项目

- 微服务电商 demo
- gRPC 服务框架
- API Gateway
- 日志采集系统
- Prometheus 监控服务

### 车联网 / IoT 项目

- MQTT 设备接入平台
- 车辆数据上报服务
- OTA 升级管理服务
- CAN 数据解析后端
- 边缘网关数据转发服务

## 对你最推荐的 Go 路线

```text
Go 基础
→ slice / map / struct
→ interface
→ goroutine / channel
→ context
→ net/http
→ Gin / Chi
→ MySQL / PostgreSQL
→ Redis
→ MQTT
→ WebSocket
→ gRPC
→ Kafka / NATS
→ Docker
→ Kubernetes
→ Prometheus / Grafana
→ 车联网数据平台
```

重点掌握：struct、interface、error、defer、goroutine、channel、context、sync、net/http、encoding/json、database/sql、Redis、MQTT、gRPC、Docker、Kubernetes、pprof。
