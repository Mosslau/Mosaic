# Go 微服务与 RPC 阶段

> 面向后端服务、云原生和车联网数据平台方向，本阶段把 ph09/ph10 的"单体服务"拆成"可扩展的多服务系统"——掌握 RPC 模式、JSON-RPC 编解码、服务注册与发现、负载均衡/熔断/超时与微服务拆分原则，以标准库 net/rpc 起步理解 RPC 本质，再以 gRPC/protobuf 完成生态选型。

## 1. 概述

Go 微服务与 RPC 阶段的目标是（引用 Roadmap）：**能写可扩展的服务系统**——掌握微服务拆分、服务注册与发现、RPC 通信（JSON-RPC 编解码、请求/响应与流式模式）、负载均衡/熔断/超时/限流等可靠性原语，并为 gRPC/protobuf 生态选型建立判断力。ph09 的"单体 HTTP 服务 + 内存 map 数据"与 ph10 的"单体 + 单库 + 单缓存"在本阶段拆分为多个进程：用户服务、订单服务、设备管理服务各自独立部署，服务间通信从 HTTP JSON 升级为 RPC；ph10 的数据层能力（连接池、事务、索引）将下沉为各服务的独立存储。

| 核心维度 | 覆盖内容 |
|----------|---------|
| RPC 模式 | 请求/响应、服务端流、客户端流、双向流的概念与落地形态 |
| RPC 实现 | 标准库 net/rpc + net/rpc/jsonrpc（零依赖，可离线实测） |
| JSON-RPC 编解码 | wire 格式、id 配对、通知（notification）、与 Gob 二进制对比 |
| 服务注册与发现 | 概念（登记/心跳/摘除/发现）+ 本地注册表演示 |
| 可靠性原语 | 负载均衡（轮询）、超时、熔断、限流——概念 + 简单实现演示 |
| 微服务拆分 | 单体到微服务、拆分原则与常见陷阱 |
| 生态选型 | gRPC + protobuf：IDL、代码生成、四种模式、拦截器 |

本阶段的核心信念来自四条必会概念：**微服务解决组织和扩展问题，也引入复杂度**——拆分换来独立演进与水平扩展，代价是网络失败、数据一致性与排查困难；**RPC 必须有超时**——网络调用随时会慢会断，没有 deadline 的调用会层层拖垮系统；**重试要考虑幂等**——一次调用可能"成功但响应丢失"，只有幂等接口才能安全重试；**可观测性是分布式系统的必需品**——请求跨多个服务，必须靠日志、指标、追踪才能定位问题。

这个阶段只涉及微服务起步与 RPC 通信本身（承接 ph09 Web 后端阶段的单体 HTTP、ph10 数据库阶段的数据层拆分），**不涉及云原生与容器部署（Docker、Kubernetes、服务网格属 ph12 云原生与部署阶段，roadmap 第 12 节，目录待建）、消息队列与异步解耦（Kafka/MQTT 属 ph19 消息队列与事件驱动深入阶段，roadmap 第 19 节，目录待建）、分布式事务与强一致（两阶段提交、Saga 属后续阶段，roadmap 未单列）、API 网关与可观测性的完整部署（Prometheus/OpenTelemetry 工具链接入属 ph12）** — 本阶段是"单体拆分 + RPC 通信"起步。

## 2. 来源与演变

**RPC 是"让跨进程调用像本地调用"的古老命题**：1980 年代 Sun RPC 提出"stub + 序列化 + 传输"骨架；1990 年代的 CORBA/DCOM 因复杂而衰败；2000 年代 XML 系（SOAP/XML-RPC）过重，JSON-RPC（2005 年 1.0、2010 年 2.0）以"JSON 报文 + 方法名 + id 配对"成为轻量事实标准——**net/rpc/jsonrpc 的 wire 格式正是 JSON-RPC 风格**（params 数组、id 回显、无 id 即通知）。微服务（Microservices）在 2014 年由 Martin Fowler 与 James Lewis 的文章定名，强调"服务小而自治、独立部署、围绕业务能力组织"，配合容器与 CI/CD 才真正落地。

**Go 侧的演进**：net/rpc 与 net/rpc/jsonrpc 随 Go 1.0（2012）进入标准库，是"标准库哲学"的产物——零依赖、API 极简，但官方声明**冻结**（"The net/rpc package is frozen and is not accepting new features"），生态转向 gRPC；protobuf（Protocol Buffers）2008 年由 Google 开源（v2），2015 年 gRPC 开源并同步发布 protobuf v3——基于 HTTP/2 与 protobuf，以"接口定义（IDL）+ 代码生成 + 多语言"为核心，2016 年捐给 CNCF；**grpc-go（google.golang.org/grpc）是官方 Go 实现**，纯 Go、无 CGO，天然适合"小型静态二进制"（ph12 的部署理念由此而来）。注册发现与配置中心从 **etcd（2013，CoreOS）**、**Consul（2014，HashiCorp）** 演进到 **Nacos（2018，阿里巴巴）**；可观测性在 2017-2019 年整合成标准——**Prometheus**（2012 诞生于 SoundCloud，2016 入 CNCF）、**Grafana**（2014）、**Jaeger**（2017 年 Uber 开源）、**OpenTelemetry**（2019 年由 OpenTracing 与 OpenCensus 合并成立）。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Sun RPC | 1980s | 提出 stub/序列化/传输骨架，RPC 思想源头 |
| JSON-RPC 1.0 | 2005 | 轻量 JSON 报文协议（方法名 + params + id） |
| protobuf v2 | 2008 | Google 开源二进制序列化（内部标准） |
| JSON-RPC 2.0 | 2010 | 规范化 request/response/notification/batch |
| net/rpc | 2012 | 随 Go 1.0 进入标准库（Gob/JSON 编解码）；此后官方声明冻结 |
| etcd | 2013 | CoreOS 发布（服务发现/配置中心） |
| 微服务定名 | 2014 | Fowler/Lewis 文章；Consul、Grafana 发布 |
| gRPC + protobuf v3 | 2015 | Google 开源 gRPC（HTTP/2 + protobuf + 代码生成） |
| gRPC 入 CNCF | 2016 | gRPC、Prometheus 进入 CNCF；Envoy 发布 |
| Nacos | 2018 | 阿里巴巴开源（注册发现 + 配置中心） |
| OpenTelemetry | 2019 | OpenTracing 与 OpenCensus 合并成立 |

本文示例以 **go1.25.6** 为基线（本环境实际跑通——标准库 net/rpc + net/rpc/jsonrpc **零第三方依赖**，可离线构建运行，是全部可运行示例的验证基础；net/rpc 的 API 自 Go 1.0 至今未变，是最稳定的部分——把"注册对象方法 → 序列化 → 传输 → 路由"的机制学透后，换 gRPC 只是换协议栈），验证工具链 protoc 29.3 + protoc-gen-go v1.36.6 + protoc-gen-go-grpc v1.5.1 + grpc-go v1.72.0（gRPC 生态示例本环境实际生成 pb 代码并跑通，未在本环境验证的项会单独标注）。

## 3. 语法与参数

### 3.1 RPC 模式：请求/响应与流式（概念）

RPC 调用按"消息流方向"分四种模式（gRPC 的命名）：

| RPC 模式 | 语义 | 典型场景 |
|----------|------|---------|
| 一元（Unary） | 一个请求 → 一个响应 | 普通查询/命令（GetUser） |
| 服务端流（Server Streaming） | 一个请求 → 连续多条响应 | 批量推送、订阅（ListUsers、设备遥测） |
| 客户端流（Client Streaming） | 连续多个请求 → 一个响应 | 上传、批量上报 |
| 双向流（Bidirectional） | 两端各自连续收发、互不阻塞 | 实时通信、遥测双向推送 |

要点：**流 = 同一 RPC 上连续的多条消息**，消息仍是完整报文（不互相切割），流的结束由业务决定（服务端推完即返回 / 客户端收够即断）；**net/rpc 只支持一元模式**——流式概念在标准库侧的落地形态是"持久连接上的 JSON-RPC 通知流"（示例 5：服务端连续推送无 id 的通知，客户端读到 EOF 即流结束）；gRPC 原生支持全部四种模式（示例 6 演示一元 + 服务端流）。

> 双向流在车联网实时推送场景深入展开，属 ph21 IoT/车联网相关 Go 阶段（roadmap 第 21 节，目录待建），这里只需理解"流 = 连续消息 + 消息边界 + 生命周期由业务决定"。

### 3.2 net/rpc 基础（注册 · 调用 · 方法签名约束）

net/rpc 的使用是三步：**服务端注册对象 → 每连接 ServeConn（编解码）→ 客户端 Dial + Call/Go**。

```go
// 完整可运行版见 examples/ex01-rpc-basic/main.go
// 验证环境：go1.25.6（已验证），零第三方依赖
server := rpc.NewServer()                    // 独立 server 实例（rpc.Register 是全局注册）
if err := server.Register(svc); err != nil { // 默认服务名 = 类型名 "UserService"
	log.Fatal(err)
}
// 每来一个连接，起 goroutine 用 Gob 编码服务（二进制、不可读）
go server.ServeConn(conn)                    // 换 JSON 编码：server.ServeCodec(jsonrpc.NewServerCodec(conn))

client, err := rpc.Dial("tcp", addr)         // 客户端：Dial 建连接（Gob）
var reply GetUserReply
err = client.Call("UserService.GetUser", &GetUserArgs{ID: 1}, &reply) // 同步调用
client.Go("UserService.ListUsers", &ListUsersArgs{}, &ListUsersReply{}, done) // 异步：done 收 *rpc.Call
```

要点：**方法签名约束是 net/rpc 的"编译期契约"**——方法必须满足 `func (t *T) MethodName(arg T1, reply *T2) error`：方法名与类型可导出、参数两个、第二个是结构体指针、返回 error；不满足的方法不会注册（`Register` 返回错误），这是"注册时校验"而非"编译时报错"。**错误约定**：方法返回非 nil error 即调用失败，错误**只以字符串透传**回客户端——没有 gRPC 那种状态码，判断错误只能按字符串/自定义类型，`errors.Is` 不适用（示例 1 有专门用例）。**并发**：一个连接一个 goroutine、多个连接并发处理，服务端共享状态必须自己加锁（`sync.Mutex`）。

### 3.3 JSON-RPC 编解码（net/rpc/jsonrpc）

`net/rpc/jsonrpc` 把 wire 格式换成 **JSON 文本**（可读、可跨语言、可用 curl 手测），协议骨架与 JSON-RPC 2.0 兼容：请求 `{"method":..., "params":[{...}], "id":N}`（params 为数组、id 由客户端定），响应回显 id 并带 `result` 或 `error`；**id 缺失即通知（notification）**——服务端处理但不回包（这是示例 5 流式推送的基础）。实测 wire 输出（示例 2）：

```text
wire 请求   : {"method":"UserService.GetUser","params":[{"ID":1}],"id":7}
wire 响应   : {"id":7,"result":{"User":{"ID":1,"Name":"alice","Email":"","Status":1}},"error":null}
错误响应    : {"id":7,"result":null,"error":"user not found"}
```

要点：**JSON-RPC 的 params 是数组**（net/rpc 单参数包进 `[{...}]`），手写服务端解析时要先解包再反序列化；**id 配对是"请求-响应关联"的机制**——一个连接上并发多个请求靠 id 区分（net/rpc 内部串行发送，流式推送场景要自己处理并发）；**JSON 可读但体积大、无强类型**，Gob 二进制紧凑但不可读——两者的取舍正是"文本协议 vs 二进制协议"的经典选择题（对比见 4.2）。

### 3.4 服务注册与发现（概念 + 本地注册表）

**注册与发现解决"地址写死"**：服务实例启动时向注册中心登记"服务名 → 实例地址"，周期心跳续约；注册中心对超过 TTL 未心跳的实例执行摘除；消费方不再写死 IP，而是按服务名 Discover 得到存活实例列表再调用。本地注册表演示（示例 3 / project/internal/registry）：

```go
// 完整可运行版见 examples/ex03-registry-discovery/main.go
// 验证环境：go1.25.6（已验证），零第三方依赖
type Registry struct {
	mu        sync.Mutex
	instances map[string]map[string]time.Time // service → addr → 最后心跳时间
	ttl       time.Duration
}

func (r *Registry) Register(service, addr string) { /* 登记（重复登记 = 续约） */ }
func (r *Registry) Heartbeat(service, addr string) { r.Register(service, addr) } // 刷新最后心跳时间
func (r *Registry) Deregister(service, addr string) { /* 优雅下线主动注销 */ }
func (r *Registry) Discover(service string) []string { /* 惰性剔除超 TTL 的实例后返回存活列表 */ }
```

要点：**心跳 + TTL 是"被动摘除"**（实例崩溃没机会 Deregister，靠 TTL 兜底），**Deregister 是"主动摘除"**（优雅下线立即生效）；**Discover 要返回稳定顺序**（轮询负载均衡依赖它可预期）。生产对照：

| 组件 | 作用 | 代表实现 |
|------|------|---------|
| 注册中心 | 服务名 → 地址、心跳摘除、供消费方发现 | etcd、Consul、Nacos |
| 配置中心 | 配置集中管理、动态下发（改配置不重启） | etcd、Consul、Nacos、Apollo |
| API Gateway | 统一入口：路由、鉴权、限流、协议转换 | Kong、APISIX、Envoy |

> 配置中心与 API Gateway 的完整落地属 ph20 配置管理与发布策略阶段（roadmap 第 20 节，目录待建）/ ph12，本阶段只理解注册发现的机制本身。

### 3.5 负载均衡 · 超时 · 熔断 · 限流（概念 + 简单实现）

四个可靠性原语是本阶段必会概念的落地载体，各自"概念 + 简单实现"：

**负载均衡（Load Balancing）**——把请求分摊到多个实例，避免单点打爆。轮询（RoundRobin）是最简策略：按顺序轮流返回实例地址（project/internal/lb 30 行实现）；生产还有加权轮询、最少连接、一致性哈希。**超时（Timeout）**——"RPC 必须有超时"的落地：**net/rpc 没有原生 deadline**，调用方必须用 goroutine + select 自定时长：

```go
// 完整可运行版见 examples/ex04-lb-timeout-breaker/main.go 的 callWithTimeout
func callWithTimeout(d time.Duration, fn func() error) error {
	done := make(chan error, 1) // 缓冲 1：超时后 fn 返回时不阻塞在通道上
	go func() { done <- fn() }()
	select {
	case err := <-done:
		return err
	case <-time.After(d):
		return ErrTimeout // ⚠️ 超时后 fn 的 goroutine 无法取消，会继续跑完（net/rpc 无取消机制）
	}
}
```

**熔断（Circuit Breaking）**——连续失败后快速失败（不发网络调用），给下游喘息、防雪崩连锁。状态机 **closed → open → half-open**：closed 连续 N 次失败 → open（冷却期内拒绝放行）；冷却结束 → half-open 放行一个探针：成功复位 closed、失败回到 open（project/internal/breaker 的 `Allow/Success/Failure` 三方法就是全部）。**限流（Rate Limiting）**——保护服务不被突发流量打爆：令牌桶（每周期补满 N 个令牌，`atomic.Int64` + `CompareAndSwap` 原子扣减），无令牌返回 429 语义（gRPC 对应 `codes.ResourceExhausted`）。

```go
// 完整可运行版见 examples/ex04-lb-timeout-breaker/main.go 的 tokenBucket
func (b *tokenBucket) allow() bool {
	for {
		t := b.tokens.Load()
		if t <= 0 {
			return false
		}
		if b.tokens.CompareAndSwap(t, t-1) {
			return true // CAS 原子扣减：并发安全
		}
	}
}
```

要点：**熔断只记"服务不可达"**（超时/连接失败），服务正常响应但限流是"忙"不是"故障"——不触发熔断，重试换实例即可（project 的 `TestRateLimitedRetriesAnotherInstance` 专门验证）；**重试只对幂等接口安全**（见 3.5 下一条与练习 2）。生产对照：限流用 `golang.org/x/time/rate`（增量令牌桶）、熔断用 `sony/gobreaker`、重试用 grpc-go 的 retryPolicy——**三件套组合拳 = 服务稳定性底线**（ph09"超时和限流是服务稳定性的基础"的服务间版本）。

**重试与幂等（Retry & Idempotency）**——重试的前提是幂等：**读操作天然幂等，写操作要设计成幂等**（"设置状态"而非"累加计数"，或用幂等键去重），否则重试造成重复扣款/重复下单。落地：服务端按幂等键（IdempotencyKey）去重——同一 key 重复提交返回第一次的结果（练习 2 的订单服务）；客户端只对瞬时错误（超时、连接失败、限流）重试，业务错误不重试（project 的 `isTransient`）。

### 3.6 微服务拆分原则

**单体到微服务是"组织与扩展问题"的解法**：单体把所有功能打包在一个进程，简单直接，但"组织越大越难改、单点部署即整体发布"；微服务按**业务能力**拆分为小而自治的服务，独立演进、独立部署、水平扩展。拆分的三个参考维度：

| 拆分维度 | 判断问题 |
|----------|---------|
| 业务能力 | 这个功能是不是一个完整业务闭环？（用户/订单/设备各自成服务） |
| 数据边界 | 能不能各管各的数据？（共享一张表 → 拆不动；独立数据层 → 可拆） |
| 变更频率 | 两块的发布节奏是否不同？（高频变更独立发布，低频稳定可合并） |

要点：**拆分是有代价的**——网络失败（RPC 必须有超时）、数据一致性（跨服务无事务，靠幂等与最终一致）、排查困难（可观测性必需）；**三大陷阱**：过度拆分（几十个服务互相调，成本 > 收益）、共享数据库（两个服务写同一张表 = 还是单体）、分布式事务（跨服务强一致成本极高，roadmap 未单列阶段，本阶段靠幂等设计规避）。roadmap 的示例链"protobuf → 定义 service → 生成 Go 代码 → server → client → interceptor"正是"单体拆分 + 服务间通信"的最小闭环。

### 3.7 gRPC 与 protobuf（生态选型）

生产级 RPC 生态的首选是 **gRPC + protobuf**（本环境实测可用，完整工程见 examples/ex06-grpc-ecosystem）。

**protobuf 是接口契约（IDL）**：`.proto` 文件里 `message` 定义数据结构，字段是"类型 + 名称 + **编号**"，编号是 wire format 的寻址依据（见 4.5），**一旦发布不可修改含义**；`service` 定义 RPC 接口、`rpc` 声明方法；`option go_package = "导入路径;包名"` 决定生成代码的 Go 包。

```proto
// 完整可运行版见 examples/ex06-grpc-ecosystem/proto/user.proto
syntax = "proto3";
package user;
option go_package = "tenetlang/go/ph11-microservice-rpc/examples/ex06-grpc-ecosystem/proto;pb";

service UserService {
  rpc GetUser(GetUserRequest) returns (GetUserResponse); // 一元 RPC
  rpc ListUsers(ListUsersRequest) returns (stream User); // 服务端流式 RPC
}
message User {
  int64  id = 1;
  string name = 2;
  string email = 3;
  int32  status = 4; // 1=在线 2=离线
}
```

**protoc 生成 Go 代码**（示例 6 的 pb 文件已提交，无 protoc 环境可直接构建）：

```bash
# 1. 安装插件（本机已验证：protoc-gen-go v1.36.6 + protoc-gen-go-grpc v1.5.1）
go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.6
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1
# 2. 生成：protoc 只解析 .proto，真正产出 Go 代码的是两个插件
protoc --go_out=. --go_opt=paths=source_relative \
       --go-grpc_out=. --go-grpc_opt=paths=source_relative \
       proto/user.proto
# 产出: proto/user.pb.go（message 序列化）与 proto/user_grpc.pb.go（service 骨架）
```

要点：**生成代码是"一次性契约"**——重新生成会覆盖、手改无效，改接口只改 .proto；**实现接口必须嵌入 `pb.UnimplementedUserServiceServer`**——proto 后续新增方法时旧实现不会编译失败；**server 三步：net.Listen → grpc.NewServer + RegisterUserServiceServer → Serve**；**client 三步：`grpc.NewClient`（取代已弃用的 `grpc.Dial`）→ `pb.NewUserServiceClient(conn)` → 带 ctx 调用**；本地调试用 `insecure.NewCredentials()`、生产必须 TLS（ph12）；**"RPC 必须有超时"落地为 `context.WithTimeout`**——超时后返回 `codes.DeadlineExceeded`（示例 6 有确定性用例：服务端对 id=100 睡 150ms、客户端 20ms deadline）；**错误用 `status.Code(err)` 取 gRPC 错误码**（如 `codes.NotFound`），据此决策重试/降级/报错——这是 net/rpc"错误只传字符串"的升级版。

**四种 RPC 模式在 proto 中的写法**：一元 `rpc GetUser(Req) returns (Resp)`；服务端流 `rpc ListUsers(Req) returns (stream Resp)`；客户端流 `rpc Upload(stream Req) returns (Resp)`；双向流 `rpc Chat(stream Req) returns (stream Resp)`——**四种模式只影响传输方式，不影响接口契约**；本阶段掌握一元 + 服务端流（示例 6），双向流在 ph21 车联网实时推送中深入。

**拦截器（Interceptor）是 gRPC 的"中间件"**：在 RPC 进入 handler 前/返回后插入横切逻辑（日志、鉴权、限流、tracing），与 ph09 的 HTTP middleware 同构；服务端签名 `func(ctx, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error)`，调 `handler(ctx, req)` 即"放行到下一层"；`grpc.ChainUnaryInterceptor(a, b)` 按传入顺序包裹；客户端拦截器通过 `invoker` 发起真实调用（示例 6 有日志 + 超时两个拦截器的可运行版）。**可观测性三支柱**（日志看细节、指标看趋势、追踪看链路）与 OpenTelemetry 的接入点见 4.6，工具链完整部署属 ph12。

## 4. 底层原理

### 4.1 RPC 的本质：stub → 序列化 → 传输 → 路由 → 反序列化

所有 RPC（net/rpc、JSON-RPC、gRPC、CORBA……）都是同一个骨架——**客户端 stub 把方法调用变成报文，服务端把报文路由回对象方法**：

```text
客户端对象 ──stub──▶ 序列化(Gob/JSON/protobuf) ──TCP/HTTP2──▶ 反序列化 ──路由: 服务名.方法名──▶ 服务端对象方法
   ▲                                                                                                    │
   └──────────────────────────── 序列化回传（reply 指针回填） ◀────────────────────────────────────────┘
```

net/rpc 的路由规则：报文带 `ServiceMethod`（"UserService.GetUser"），服务端拆成 服务名.方法名 查表（`Register` 时构建的 method map），用反射把参数解进 `arg` 指针、调用后把 `reply` 序列化回传——**反射是 net/rpc 的实现基石**，这也是为什么方法签名约束必须在运行时校验（3.2）；gRPC 的路由在 HTTP/2 上按 `/user.UserService/GetUser` 的路径分发（见 4.6）。

### 4.2 JSON-RPC wire 格式与消息边界

- **报文即 JSON 值**：请求 `{"method","params","id"}`、响应 `{"id","result","error"}`；`params` 必须是数组（单参数包进 `[{...}]`，net/rpc 与 JSON-RPC 2.0 一致）；`id` 是任意 JSON 值，响应**必须原样回显**——并发请求靠它配对
- **通知**：请求缺 `id` 即通知（notification），服务端处理但不回包——示例 5 的服务端流推送正是"持续发通知"（客户端以 EOF 判流结束）
- **消息边界（framing）**：TCP 是字节流，报文之间必须有边界——net/rpc/jsonrpc 用 `json.Decoder/Encoder`（隐式按 JSON 值分隔）；手写服务端可用**换行分隔**（示例 5/练习 3）或**长度前缀**；gRPC 用 5 字节前缀（1 字节标志 + 4 字节长度）——**流式 RPC 的消息边界靠 framing 保证，流不切割消息**
- **Gob vs JSON 对比**：Gob 二进制紧凑（无 key 名）、解码快但不可读；JSON 可读、可跨语言、可 curl 手测但体积大——教学上"先 JSON 看懂 wire，再上 protobuf 压体积"

### 4.3 熔断状态机与负载均衡算法

- **熔断状态机**：closed（放行，计数连续失败）→ 达阈值 open（快速失败）→ 冷却期后 half-open（放行一个探针）→ 探针成功回 closed / 失败回 open；`openedAt` 记录打开时刻，`Allow()` 里 `time.Since(openedAt) > cooldown` 即到半开——**状态转换全部在锁内原子完成**，探针并发由"half-open 只放行一次"约束（project/internal/breaker 的测试覆盖三态全路径，覆盖率 96.4%）
- **负载均衡算法**：轮询（RoundRobin）`next % len(addrs)`，零状态、实现最简，但**不感知实例负载**；加权轮询按权重分配比例；最少连接感知实时负载；一致性哈希保证"同一 key 落到同一实例"（有状态场景）；生产 gRPC 的 balancer 默认 pick_first/round_robin，且会把熔断中的子连接移出调度（project 的 `Allow()` 快速失败即等价行为）
- **LB 与熔断协作**：project 的弹性客户端里"每个实例一个熔断器"——实例故障只熔断自己，LB 继续把请求分给健康实例；熔断器状态按地址保留（Refresh 重建列表不丢状态）

### 4.4 心跳与 TTL 摘除（服务发现的实现机制）

- **心跳**：实例周期性向注册中心上报"我还活着"（刷新 lastSeen）；生产间隔 5~10s、TTL 取 3 倍间隔左右，本演示 500ms~1s 便于观察
- **TTL 惰性摘除**：Discover 时顺带检查 `now - lastSeen > ttl` 即删除——**不需要后台清扫协程**，查询路径自愈（project 的 registry 即此实现）；代价是"摘除延迟最长一个 TTL"，故障转移靠客户端重试兜底
- **主动下线 vs 被动摘除**：优雅退出先 Deregister（立即生效、不占 TTL 窗口）再关监听；崩溃只能靠 TTL——两种摘除路径都要测试（project 的 `TestTTLExpiry` 与 `TestDeregister`）
- **生产一致性**：etcd/Consul 用租约（lease）+ 分布式共识保证注册表强一致、多副本高可用；本演示的进程内 map 是单点模型，机制相同、可靠性不同

### 4.5 protobuf 编码：varint 与 wire format（gRPC 生态）

- **Tag = `(字段编号 << 3) | wire_type`**：编号 1-15 的 tag 只有 1 字节——**常用字段放小编号省空间**
- **varint**：小整数 1 字节（最高位是"是否还有下一字节"），`1 → 0x01`、`300 → 0xAC 0x02`；**int32 负数按 64 位补码编码占 10 字节**，负数值建议用 `sint32`（ZigZag 编码）
- **wire type**：0=varint、1=64-bit、2=length-delimited（string/bytes/repeated）、5=32-bit
- **对比 JSON**：protobuf 二进制 + 强类型 + 编号寻址——体积小（无 key 名）、解析快（按编号跳转）；代价是不可读、必须经 IDL 与代码生成——与 4.2 的 Gob/JSON 取舍同构

### 4.6 gRPC 基于 HTTP/2（生态）

- **HTTP/2 三大特性**：二进制分帧（frame 是传输单元）、多路复用（一条连接并发多个 stream，解决 HTTP/1.1 队头阻塞）、HPACK 头压缩
- **gRPC 把 RPC 映射到 HTTP/2**：每个调用一条 stream，请求是 HEADERS + DATA 帧——**一条 TCP 连接承载大量并发 RPC**，长连接高并发下复用收益显著；帧级别流量控制让每个 stream 独立流控，防止慢消费者拖垮连接
- **拦截器链与 tracing 的上下文传播**：client interceptor → 网络 → server 拦截器链 → handler → 原路返回；trace 由 span 组成、按 parent-child 串成 trace，客户端把 `traceparent`（W3C 标准）头随请求发出、服务端解析后把新 span 挂到同一 trace——otelgrpc 拦截器自动完成"生成 span + 传播 context"，业务代码只在关键点加 span（三支柱完整接入属 ph12）

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 用户服务 | net/rpc/gRPC 服务定义、JSON-RPC 编解码、错误透传/错误码 |
| 订单服务 | 幂等设计（幂等键去重）、超时、重试 |
| 设备管理服务 | 服务端流式上报/推送、令牌桶限流 |
| 服务间查询（订单服务查用户） | gRPC client、context 超时、错误码透传（练习 4） |
| 多实例服务发现与调度 | 注册中心 + 负载均衡 + 熔断（project） |
| 单体拆分决策 | 微服务拆分原则（业务能力/数据边界/变更频率） |

**不适合**此阶段的事项：

- **云原生与容器部署**（Docker、Kubernetes、服务网格、Prometheus/OpenTelemetry 完整接入）：属 ph12 云原生与部署阶段（roadmap 第 12 节，目录待建）——本阶段多服务在本机多进程运行
- **消息队列与异步解耦**（Kafka/RabbitMQ/MQTT）：属 ph19 消息队列与事件驱动深入阶段（roadmap 第 19 节，目录待建）——本阶段通信全部同步 RPC
- **分布式事务与多库一致性**（两阶段提交、Saga）：属后续阶段（roadmap 未单列）——本阶段服务各自管数据，跨服务一致性靠接口幂等设计规避
- **配置中心与 API Gateway 的完整落地**：属 ph20/ph12——本阶段只理解注册发现机制

**选型参考：net/rpc vs gRPC**

| 维度 | net/rpc + jsonrpc | gRPC + protobuf |
|------|-------------------|-----------------|
| 依赖 | 标准库，零依赖 | protoc + grpc-go（第三方） |
| 接口契约 | 方法签名反射校验（运行时） | .proto IDL + 代码生成（编译期） |
| wire | Gob（二进制）/ JSON | protobuf（二进制，编号寻址） |
| 流式 | 仅一元（通知流是变通） | 四种模式原生支持 |
| 超时 | 调用方自定时长 | context.WithTimeout（可取消） |
| 错误 | 字符串透传 | 状态码 codes.*（可编程语义） |
| 生态 | 冻结（官方声明） | 拦截器、重试策略、多语言、云原生标准 |
| 定位 | 理解 RPC 本质的教材 | 生产首选 |

## 6. 代码示例

> 以下示例均为完整可运行 Go module，位于 [`examples/`](./examples/) 目录（每个示例一个子目录，先进入对应目录再运行）。验证环境：go1.25.6（darwin/arm64）；示例 1~5 **零第三方依赖**（标准库），示例 6 需要 grpc-go + protobuf（经 GOPROXY=goproxy.cn 拉取，本环境实测跑通）。全部示例已通过 `go vet ./...`、`go test ./...` 与 `go test -race ./...`，覆盖率实测见下表（数据表与运行命令见 examples/README.md）。

| 示例 | 一句话说明 | go test -cover |
|------|-----------|----------------|
| ex01-rpc-basic | net/rpc 基础：Register + Gob 编码，同步 Call 与异步 Go，签名约束与错误透传 | 56.1% |
| ex02-jsonrpc-codec | JSON-RPC 编解码：裸 TCP 手写报文看 wire 格式 + Go client，与 Gob 对比 | 49.4% |
| ex03-registry-discovery | 服务注册与发现：注册表登记/心跳/TTL 摘除/发现 + 多实例 + 优雅下线 | 70.2% |
| ex04-lb-timeout-breaker | 负载均衡（轮询）/ 超时 / 熔断状态机三原语 + 真实实例组合演示 | 67.9% |
| ex05-streaming | 流式概念：JSON-RPC 通知在持久连接上的服务端流推送（消息边界 + EOF） | 60.8% |
| ex06-grpc-ecosystem | gRPC/protobuf 生态：.proto → protoc 生成 → 一元 + 服务端流 + 日志/超时拦截器 | 46.6%（proto 生成代码不计量） |

### 示例 1：net/rpc 基础（ex01-rpc-basic）

```go
// examples/ex01-rpc-basic/main.go —— 服务端注册 + Gob 编码，客户端同步/异步调用
// 验证环境：go1.25.6，零第三方依赖，命令：go test -v ./...；go run .
server := rpc.NewServer()
if err := server.Register(svc); err != nil { /* 服务名 = 类型名 "UserService" */ }
go func() {
	for {
		conn, err := lis.Accept()
		if err != nil { return }
		go server.ServeConn(conn) // 默认 Gob 编码（二进制、不可读）
	}
}()
```

### 示例 2：JSON-RPC 编解码（ex02-jsonrpc-codec）

```text
// examples/ex02-jsonrpc-codec/main.go 实测输出（wire 即 JSON 文本，可 curl 手测）
wire 请求   : {"method":"UserService.GetUser","params":[{"ID":1}],"id":7}
wire 响应   : {"id":7,"result":{"User":{"ID":1,"Name":"alice","Email":"","Status":1}},"error":null}
错误响应    : {"id":7,"result":null,"error":"user not found"}
```

### 示例 3：服务注册与发现（ex03-registry-discovery）

```go
// examples/ex03-registry-discovery/main.go —— 实例上线注册 + 心跳续约，客户端按服务名发现
reg.Register("user.Service", addr)   // 实例启动登记
reg.Heartbeat("user.Service", addr)  // 周期续约（间隔 << TTL）
reg.Deregister("user.Service", addr) // 优雅下线主动注销
reg.Discover("user.Service")         // 客户端发现存活实例（惰性剔除超 TTL 的失联实例）
```

### 示例 4：负载均衡 / 超时 / 熔断（ex04-lb-timeout-breaker）

```go
// examples/ex04-lb-timeout-breaker/main.go —— 熔断状态机核心（closed → open → half-open）
func (b *Breaker) Allow() bool {
	switch b.state {
	case "open":
		if time.Since(b.openedAt) > b.cooldown {
			b.state = "half-open" // 冷却结束：放行一个探针
			return true
		}
		return false // 冷却中：快速失败，不发网络调用
	case "half-open":
		return true
	default:
		return true
	}
}
```

### 示例 5：流式概念（ex05-streaming）

```go
// examples/ex05-streaming/main.go —— 服务端流：先回 ack，再连续推送无 id 的通知，推完关闭
if req.ID != nil {
	_ = enc.Encode(response{ID: *req.ID, Result: map[string]bool{"ok": true}, Error: nil}) // ack
}
for i := 1; i <= 5; i++ {
	_ = enc.Encode(notification{Method: "device.push", Params: DeviceStatus{DeviceID: p.DeviceID, Speed: float64(60 + i*7)}})
	time.Sleep(150 * time.Millisecond) // 模拟实时遥测节奏
}
return // 流结束：关闭连接 → 客户端读到 EOF
```

### 示例 6：gRPC / protobuf 生态（ex06-grpc-ecosystem）

```go
// examples/ex06-grpc-ecosystem/main.go —— server 三步 + 拦截器链（日志在外、超时在内）
s := grpc.NewServer(grpc.ChainUnaryInterceptor(loggingUnary, timeoutUnary(2*time.Second)))
pb.RegisterUserServiceServer(s, newUserServer())
go func() { _ = s.Serve(lis) }()
// 客户端：grpc.NewClient（取代已弃用的 grpc.Dial）+ context.WithTimeout 调用级超时
conn, _ := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
client := pb.NewUserServiceClient(conn)
ctx, cancel := context.WithTimeout(context.Background(), time.Second)
u, err := client.GetUser(ctx, &pb.GetUserRequest{Id: 1}) // 错误用 status.Code(err) 决策
```

## 7. 总结

### 关键要点

1. **微服务解决组织和扩展问题，也引入复杂度**（必会概念）：独立演进、水平扩展 vs 网络失败、数据一致性、排查困难——复杂度靠规范与工具对冲；拆分看业务能力/数据边界/变更频率，警惕过度拆分与共享数据库
2. **RPC 必须有超时**（必会概念）：net/rpc 无原生 deadline，调用方 goroutine + select 自定时长；gRPC 用 context.WithTimeout（可真正取消，返回 codes.DeadlineExceeded）
3. **重试要考虑幂等**（必会概念）：重试只对幂等接口安全；读天然幂等，写用"设置状态"或幂等键去重；只对瞬时错误重试
4. **可观测性是分布式系统的必需品**（必会概念）：日志看细节、指标看趋势、追踪看链路（traceparent 上下文传播），完整接入属 ph12
5. **net/rpc 是理解 RPC 本质的教材**：注册对象方法 → 序列化 → 传输 → 路由，三步 API 自 Go 1.0 未变、官方冻结；错误只传字符串、无状态码
6. **JSON-RPC 的 wire 是"方法名 + params 数组 + id 配对"**：id 回显关联请求响应，缺 id 即通知（流式推送的基础）；消息边界靠 framing（换行/长度前缀）
7. **服务注册与发现解决"地址写死"**：登记 + 心跳续约 + TTL 被动摘除 + Deregister 主动摘除；生产用 etcd/Consul/Nacos
8. **三件套保护稳定性**：负载均衡分摊（轮询起步）、熔断防雪崩（closed→open→half-open，只记"服务不可达"）、限流防打爆（令牌桶，429 语义）——project 里组合成一个弹性客户端
9. **gRPC = HTTP/2 + protobuf + 代码生成**：.proto 是唯一事实来源、生成代码不可手改；四种 RPC 模式覆盖查询到实时推送；拦截器是中间件；status.Code 是跨服务可编程错误语义

### 跨语言对比：微服务与 RPC

| 维度 | Go net/rpc | Go gRPC | Java gRPC / Spring Cloud | Python gRPC |
|------|------------|---------|--------------------------|-------------|
| RPC 框架 | net/rpc（标准库，冻结） | google.golang.org/grpc（官方） | grpc-java / Dubbo | grpcio（官方） |
| 接口定义 | 方法签名反射校验 | protobuf（.proto） | protobuf / Feign 接口 | protobuf |
| 代码生成 | 无（运行时校验） | protoc-gen-go / -go-grpc | protoc / Maven 插件 | grpcio-tools |
| 服务发现 | 自实现（本地注册表） | etcd/Consul 自定义 resolver | Nacos/Eureka（Spring Cloud） | 自研/Consul |
| 治理能力 | 自实现（lb/breaker/超时） | 拦截器 + sony/gobreaker | Spring Cloud 全家桶（Hystrix/Sentinel） | 装饰器/拦截器 |
| 特点 | 零依赖、理解本质 | 简洁、纯 Go、静态二进制 | 生态全、治理内置、重 | 胶水语言、生态一般 |

### 阶段验收清单

- [ ] **能写 RPC 服务与客户端**：net/rpc 的方法签名约束、RegisterName、Call/Go，错误透传语义（示例 1）
- [ ] **能看懂并手写 JSON-RPC 报文**：params 数组、id 配对、通知与消息边界（示例 2/5）
- [ ] **能实现并解释服务注册与发现**：登记/心跳/TTL 摘除/发现，主动注销与被动摘除的区别（示例 3）
- [ ] **能实现并解释可靠性原语**：轮询负载均衡、调用超时、熔断三态、令牌桶限流的取舍（示例 4）
- [ ] **能设计幂等接口**：幂等键去重 + 瞬时错误重试，说出"为什么只有幂等接口能安全重试"（练习 2）
- [ ] **能定义 protobuf 服务并生成代码**：.proto 的 message/service、字段编号与 go_package 语义、四种 RPC 模式（示例 6）
- [ ] **能实现 gRPC server/client**：server 三步注册 + client 带 ctx 超时调用，一元与服务端流跑通，status.Code 决策（示例 6/练习 4）
- [ ] **能按拆分原则做单体拆分决策**：业务能力/数据边界/变更频率三问，说清拆分代价与陷阱（3.6）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续。四题与 roadmap「练习」小节一一对应：

1. **用户服务**（★）：net/rpc 用户服务——GetUser/ListUsers/AddUser + JSON-RPC 编解码（提示：示例 1/2）
2. **订单服务**（★★）：幂等下单（幂等键去重）+ 客户端超时重试（提示：示例 4 的 callWithTimeout）
3. **设备管理服务**（★★）：服务端令牌桶限流上报 + JSON-RPC 通知流推送（提示：示例 5 + 令牌桶）
4. **gRPC 通信 demo**（★★★）：订单服务 A 调用户服务 B 组装响应，NotFound 错误码透传（提示：示例 6 工程结构）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**设备数据采集微服务**——注册中心（JSON-RPC 暴露登记/心跳/发现）+ 设备管理服务（限流上报与查询，可多实例，优雅下线）+ 采集网关（发现 → 轮询负载均衡 → 每实例熔断 → 超时重试 → 跨实例汇总查询），全部标准库、零第三方依赖。它是本阶段全部知识点的合体：注册发现（示例 3）+ 可靠性三原语（示例 4）+ 多服务协作（示例 2/5），也是 roadmap「设备数据采集微服务」推荐项目的落地。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（go build / go test / go vet / -race / 冒烟与故障演练）

roadmap 另一个推荐项目「gRPC 服务框架 demo」（把"发现 → LB → 熔断 → 超时重试"沉淀为可复用框架，新服务只注册 handler）可在完成后作为扩展：把 project 的 internal/device 客户端抽象成接口即可，也为 ph17 架构设计与代码分层阶段打底。

### 下一阶段

本阶段是当前 Go Roadmap 最后一个已展开的阶段（ph01~ph11 目录齐备，ph12 起尚未建目录）。**ph12+（云原生与部署阶段，roadmap 第 12 节，目录待建）：后续可深入 Docker、Kubernetes、CI/CD 与监控告警**——本阶段的多服务将打包成镜像部署到集群，Prometheus 抓取指标、健康检查与优雅退出上线，注册发现与配置中心从"本机进程"升级为"集群内服务"；在此之前可先按推荐学习顺序巩固 ph10 数据层与 ph11 本阶段的练习与项目。
