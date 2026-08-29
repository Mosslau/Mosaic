# Go 微服务与 RPC 阶段
> 面向后端服务、云原生和车联网数据平台方向，本阶段掌握微服务与 RPC——protobuf、gRPC、超时/重试/熔断/限流、可观测性与 API 网关，把"单体 HTTP 服务"升级为"可扩展的多服务系统"。

## 1. 概述
Go 微服务与 RPC 阶段的目标是：**能写可扩展的服务系统**——掌握微服务拆分、服务注册发现与配置中心、protobuf 定义接口、gRPC server/client 与拦截器、超时/重试/熔断/限流，并接入日志、指标与 tracing。ph10 的"单体 + 单库 + 单 Redis"在本阶段拆分为用户服务、订单服务、设备管理服务等多个进程，服务间通信从 HTTP JSON 升级为 gRPC 二进制协议，数据库访问下沉为各服务独立的存储层。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 微服务基础 | 单体到微服务拆分、服务注册发现、配置中心 |
| RPC 与 gRPC | Protocol Buffers、protoc 代码生成、四种 RPC 模式 |
| 可靠性 | timeout、retry、幂等、熔断（Circuit Breaking）、限流 |
| 可观测性 | OpenTelemetry、Prometheus、Grafana、Jaeger |
| API Gateway | 统一入口、路由、鉴权、限流、协议转换 |
| 工程化 | interceptor、连接管理、多服务协作 |

本阶段的核心信念来自四条必会概念：**微服务解决组织和扩展问题，也引入复杂度**——拆分换来独立演进与水平扩展，代价是网络失败、数据一致性与排查困难；**RPC 必须有超时**——网络调用随时会慢会断，没有 deadline 的调用会层层拖垮系统；**重试要考虑幂等**——一次调用可能"成功但响应丢失"，只有幂等接口才能安全重试；**可观测性是分布式系统的必需品**——请求跨多个服务，必须靠日志、指标、追踪才能定位问题。

范围边界：承接 ph10 数据库（各服务独立数据层、共享 MySQL/Redis 基础设施）；**不涉及** 云原生与容器部署（ph12）、消息队列（ph13 及之后）、分布式事务（ph16）；本阶段是"单体拆分 + gRPC 通信"起步。

## 2. 来源与演变
**架构从单体到微服务的演进**：单体应用（Monolith）把 Web、业务、存储打包在一个进程，简单直接，但"组织越大越难改"；SOA（面向服务架构）把功能拆成可复用服务，靠 ESB 总线集成，重而复杂；**微服务（Microservices）** 在 2014 年前后由 Martin Fowler 与 James Lewis 的文章定名，强调"服务小而自治、独立部署、围绕业务能力组织"，配合容器与 CI/CD 才真正落地。

**gRPC 与 protobuf 的诞生**：protobuf（Protocol Buffers）2008 年由 Google 开源（v2），是 Google 内部的二进制序列化标准；2015 年 Google 开源 **gRPC** 并同步发布 protobuf v3——基于 HTTP/2 与 protobuf，以"接口定义（IDL）+ 代码生成 + 多语言"为核心，2016 年捐给 CNCF；**grpc-go（google.golang.org/grpc）是官方 Go 实现**，纯 Go、无 CGO 依赖，天然适合"小型静态二进制"（ph12 的部署理念由此而来）。

**配套生态的演进**：注册发现与配置中心从 **etcd（2013，CoreOS）**、**Consul（2014，HashiCorp）** 演进到 **Nacos（2018，阿里巴巴）**；可观测性在 2017-2019 年整合成标准——**Prometheus**（2012 诞生于 SoundCloud，2016 入 CNCF）、**Grafana**（2014）、**Jaeger**（2017 年 Uber 开源）、**OpenTelemetry**（2019 年由 OpenTracing 与 OpenCensus 合并成立）；**API 网关**从 Kong（2015）、Envoy（2016，Lyft）到 APISIX（2019）；2017 年出现的服务网格（Istio）把流量治理下沉到数据面代理。

| 时间 | 事件 |
|------|------|
| 2008 | Google 开源 protobuf（v2） |
| 2012 | Prometheus 诞生于 SoundCloud |
| 2013 | etcd 发布（服务发现/配置中心） |
| 2014 | Consul、Grafana 发布；微服务概念流行 |
| 2015 | Google 开源 gRPC；protobuf v3 发布 |
| 2016 | Envoy 发布（Lyft）；gRPC 与 Prometheus 进入 CNCF |
| 2017 | Jaeger（Uber）、Istio（服务网格）发布 |
| 2018 | Nacos 开源（阿里巴巴） |
| 2019 | OpenTelemetry 成立；APISIX 开源 |

## 3. 语法与参数
### 3.1 protobuf 语法（.proto 文件）
要点：**.proto 是接口契约（IDL）**——`message` 定义数据结构，字段是"类型 + 名称 + **编号**"，编号是 wire format 的寻址依据（见 4.2），**一旦发布不可修改含义**；类型映射：`int64→int64`、`string→string`、`int32→int32`、`bool→bool`、`double→float64`、`bytes→[]byte`；`repeated` 是数组；`service` 定义 RPC 接口、`rpc` 声明方法；`option go_package = "导入路径;包名"` 决定生成代码的 Go 包。完整语法见示例 1 的 `user.proto`。

### 3.2 用 protoc 生成 Go 代码
```bash
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest      # 消息代码插件
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest    # 服务代码插件
protoc --go_out=. --go_opt=paths=source_relative \
       --go-grpc_out=. --go-grpc_opt=paths=source_relative \
       proto/user.proto
# 产出: proto/user.pb.go（message 序列化）与 proto/user_grpc.pb.go（service 骨架）
```

要点：**protoc 只解析 .proto，真正产出 Go 代码的是两个插件**——protoc-gen-go 生成 message、protoc-gen-go-grpc 生成 service；`--go_opt=paths=source_relative` 让输出与 .proto 同目录；生成的代码配合 `go get google.golang.org/grpc google.golang.org/protobuf` 使用；**生成代码是"一次性契约"**——重新生成会覆盖，手改无效，改接口只改 .proto。本机无 protoc 时，示例 2-5 已基于生成后的代码编写，安装插件后运行上述命令即可复现。

### 3.3 gRPC service 定义与四种 RPC 模式
| RPC 模式 | proto 写法 | 典型场景 |
|----------|-----------|---------|
| 一元（Unary） | `rpc GetUser(Req) returns (Resp)` | 普通请求/响应 |
| 服务端流（Server Streaming） | `rpc ListUsers(Req) returns (stream Resp)` | 批量推送、订阅 |
| 客户端流（Client Streaming） | `rpc Upload(stream Req) returns (Resp)` | 上传、批量上报 |
| 双向流（Bidirectional） | `rpc Chat(stream Req) returns (stream Resp)` | 实时通信、遥测推送 |

要点：**proto3 的字段都是可选语义**（无 required/optional 关键字），缺省即零值；**四种模式只影响传输方式，不影响接口契约**；本阶段掌握一元 + 服务端流（示例 2/3），双向流在 ph22 车联网实时推送中深入。

### 3.4 gRPC server 与 client（Go 侧用法）
要点：**server 侧三步：net.Listen → grpc.NewServer + RegisterUserServiceServer → Serve**（完整见示例 2）；**client 侧三步：`grpc.NewClient` → `pb.NewUserServiceClient(conn)` → 带 ctx 调用**（完整见示例 3）；**实现接口必须嵌入 `pb.UnimplementedUserServiceServer`**——proto 后续新增方法时旧实现不会编译失败；**`grpc.NewClient` 取代已弃用的 `grpc.Dial`**，本地调试用 `insecure.NewCredentials()`、生产必须 TLS（ph12）；**必会概念"RPC 必须有超时"落地为 context.WithTimeout**——旧 API `grpc.WithTimeout` 只控制拨号超时，调用超时必须走 context；错误统一用 `status.Code(err)` 取 gRPC 错误码（如 `codes.NotFound`），据此决策重试/降级/报错。

### 3.5 超时·重试·幂等·熔断·限流（必会概念）
- **超时（Timeout）**：调用必须带 deadline；实现：客户端 `context.WithTimeout` + 服务端拦截器强制 deadline（示例 4）
- **重试（Retry）**：只对瞬时错误（`codes.Unavailable`）自动重试；实现：grpc-go 内置重试策略（service config 的 retryPolicy）
- **幂等（Idempotency）**：重试的前提——**读操作天然幂等，写操作要设计成幂等**（"设置状态"而非"累加计数"），否则重试造成重复扣款/重复下单
- **熔断（Circuit Breaking）**：连续失败后快速失败，给下游喘息、防雪崩连锁；实现：简易计数器熔断器（示例 5），生产用 `github.com/sony/gobreaker`
- **限流（Rate Limiting）**：保护服务不被突发流量打爆；实现：`golang.org/x/time/rate`（令牌桶）或 hand-written 令牌桶（示例 5），超限返回 `codes.ResourceExhausted`（429 语义）

```go
// grpc-go 客户端内置重试：连续失败自动退避重试（只对幂等接口安全！）
serviceConfig := `{"methodConfig":[{"name":[{"service":"user.UserService"}],
  "retryPolicy":{"maxAttempts":3,"initialBackoff":"0.1s","maxBackoff":"1s",
  "backoffMultiplier":2,"retryableStatusCodes":["UNAVAILABLE"]}}]}`
conn, _ := grpc.NewClient("127.0.0.1:50051",
	grpc.WithTransportCredentials(insecure.NewCredentials()),
	grpc.WithDefaultServiceConfig(serviceConfig))
```

### 3.6 服务注册发现·配置中心·API Gateway
| 组件 | 作用 | 代表实现 |
|------|------|---------|
| 服务注册发现 | 服务启动时登记"服务名→实例地址"，消费方按名字解析，心跳摘除 + 负载均衡 | etcd、Consul、Nacos |
| 配置中心 | 配置集中管理、动态下发（改配置不重启） | etcd、Consul、Nacos、Apollo |
| API Gateway | 统一入口：路由、鉴权、限流、灰度、协议转换（REST→gRPC） | Kong、APISIX、Envoy |

要点：**注册发现解决"地址写死"**——本阶段 client 直连 `127.0.0.1:50051` 是简化形态，生产用服务名解析（grpc 的 name resolver + 负载均衡策略）；**配置中心解决"配置散落"**——服务只读环境变量/本地文件，生产配置集中下发（ph20 深入）；**Gateway 是"前端统一入口"**——浏览器/App 只进网关，网关把 HTTP 请求转成内部 gRPC 调用。

### 3.7 可观测性：日志·指标·追踪
| 支柱 | 回答的问题 | Go 接入 |
|------|-----------|--------|
| 日志（Logs） | 某个请求发生了什么 | log/slog（Go 1.21 标准库） |
| 指标（Metrics） | 系统整体健康度（QPS、延迟、错误率） | prometheus/client_golang（Counter/Gauge/Histogram） |
| 追踪（Tracing） | 一个请求跨了哪些服务、每段耗时 | go.opentelemetry.io/otel（OpenTelemetry SDK） |

要点：**三支柱缺一不可**——日志看细节、指标看趋势、追踪看链路；**OpenTelemetry 是事实标准**——gRPC 官方提供 otelgrpc 拦截器自动埋点与上下文传播（见 4.5）；**Prometheus 是拉取模式**——服务暴露 `/metrics` 端点，Prometheus 定期抓取，Grafana 画图，Jaeger 展示追踪；本阶段验收"能接入日志、指标和 tracing"= 在示例 4 的拦截器里加 slog 结构化日志 + otel 埋点，完整部署在 ph12。

## 4. 底层原理
### 4.1 gRPC 基于 HTTP/2
- **HTTP/2 三大特性**：二进制分帧（frame 是传输单元）、多路复用（一条连接并发多个 stream，解决 HTTP/1.1 队头阻塞）、HPACK 头压缩
- **gRPC 把 RPC 映射到 HTTP/2**：每个调用一条 stream，请求是 HEADERS + DATA 帧——**一条 TCP 连接承载大量并发 RPC**，长连接高并发下复用收益显著；帧级别流量控制让每个 stream 独立流控，防止慢消费者拖垮连接

### 4.2 protobuf 编码：varint 与 wire format
- **Tag = `(字段编号 << 3) | wire_type`**：编号 1-15 的 tag 只有 1 字节——**常用字段放小编号省空间**
- **varint**：小整数 1 字节（最高位是"是否还有下一字节"），`1 → 0x01`、`300 → 0xAC 0x02`；**int32 负数按 64 位补码编码占 10 字节**，负数值建议用 `sint32`（ZigZag 编码）
- **wire type**：0=varint、1=64-bit、2=length-delimited（string/bytes/repeated）、5=32-bit
- **对比 JSON**：protobuf 二进制 + 强类型 + 编号寻址——体积小（无 key 名）、解析快（按编号跳转）；代价是不可读、必须经 IDL 与代码生成

### 4.3 流式 RPC 与消息边界
- **流 = 同一 RPC 上连续的多条消息**；每条消息仍是完整 protobuf（length-delimited 前缀长度），流不切割消息
- 服务端流：服务端 `stream.Send` 逐条推，客户端 `stream.Recv` 循环读到 `io.EOF` 表示流结束（示例 3）
- 双向流：两端各自收发、全双工互不阻塞；**流的生命周期由业务决定**——遥测推送用长流，批量查询用短流

### 4.4 interceptor 机制
- **interceptor 是 gRPC 的"中间件"**：在 RPC 进入 handler 前/返回后插入横切逻辑（日志、鉴权、限流、tracing），与 ph09 的 HTTP middleware 同构
- **调用链**：client interceptor → 网络 → server 拦截器链 → handler → 原路返回；`grpc.ChainUnaryInterceptor(a, b)` 按传入顺序包裹（a 在外、b 在内）
- 签名模式：服务端 `func(ctx, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error)`，调用 `handler(ctx, req)` 即"放行到下一层"（示例 4）；流式 RPC 用 StreamInterceptor
- **context 是拦截器间传值的通道**：`context.WithValue` 放 traceID/用户信息，下游拦截器与 handler 都能读

### 4.5 分布式追踪的上下文传播
- **trace 由 span 组成**：一次外部调用 = 一个 span（名称、起止时间、属性），span 按 parent-child 关系串成 trace
- **上下文传播**：客户端把 `traceparent`（W3C 标准）头随请求发出，服务端解析后把新 span 挂到同一 trace——跨服务链路由此串起
- **otelgrpc 拦截器自动完成"生成 span + 传播 context"**，业务代码只在关键点加 span；采样（sampling）控制存储成本

## 5. 使用场景
| 场景 | 涉及知识点 |
|------|-----------|
| 用户服务 | protobuf 定义、gRPC server、状态码 |
| 订单服务 | 幂等设计、重试、超时 |
| 设备管理服务 | 服务端流式上报、限流 |
| 服务间查询（订单服务查用户） | gRPC client、context 超时 |
| 网关入口（App/浏览器） | API Gateway、REST→gRPC 转换 |
| 全链路排障 | 日志、指标、追踪三支柱 |

**不适合**此阶段的事项：

- **分布式事务与多库一致性**（两阶段提交、Saga）：属 ph16——本阶段服务各自管库，跨服务一致性靠接口幂等设计规避
- **消息队列与异步解耦**（Kafka/RabbitMQ/MQTT）：属 ph19——本阶段通信全部同步 gRPC
- **服务网格与 Kubernetes 部署**（Istio、容器编排）：属 ph12——本阶段治理靠拦截器手动实现、本机多进程运行

## 6. 代码示例
五个示例共享一个 demo 工程，对应目录：`proto/`（示例 1，含 protoc 生成的 pb 包）、`server/`（示例 2）、`client/`（示例 3）、`interceptor/`（示例 4）、`ratelimit/`（示例 5）；这正是 roadmap 示例链"protobuf → 定义 service → 生成 Go 代码 → server → client → interceptor"。

### 示例 1：定义 .proto 并用 protoc 生成 Go 代码
```proto
// 依赖与生成命令见 3.2；产出 proto/user.pb.go 与 proto/user_grpc.pb.go
syntax = "proto3";
package user;
option go_package = "demo/proto;pb"; // 导入路径;包名

// 用户服务：roadmap 练习"用户服务"的 protobuf 定义
service UserService {
  rpc GetUser(GetUserRequest) returns (GetUserResponse); // 一元 RPC
  rpc ListUsers(ListUsersRequest) returns (stream User); // 服务端流式 RPC
}
message GetUserRequest { int64 id = 1; }
message GetUserResponse { User user = 1; }
message ListUsersRequest { repeated int64 ids = 1; }
message User {
  int64  id = 1;
  string name = 2;
  string email = 3;
  int32  status = 4; // 1=在线 2=离线
}
```

要点：生成 `proto/user.pb.go`（message 序列化）与 `proto/user_grpc.pb.go`（service 接口与骨架）；**生成代码直接可用、但不可手改**——接口变更只改 .proto 再重新生成；示例 2-5 均基于该 pb 包，先跑本例再 `go run` 其余示例。

### 示例 2：gRPC server（实现用户服务）
```go
// 运行: go run ./server（先执行示例 1 的 protoc 命令生成 proto 包）
package main
import (
	"context"
	"log"
	"net"

	pb "demo/proto"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type userServer struct{ pb.UnimplementedUserServiceServer } // 必须嵌入：proto 新增方法不破坏编译

var users = map[int64]*pb.User{
	1: {Id: 1, Name: "alice", Email: "alice@tenet.dev", Status: 1},
	2: {Id: 2, Name: "bob", Email: "bob@tenet.dev", Status: 2},
}

func (s *userServer) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.GetUserResponse, error) {
	u, ok := users[req.Id]
	if !ok {
		return nil, status.Error(codes.NotFound, "user not found") // gRPC 标准错误码
	}
	return &pb.GetUserResponse{User: u}, nil
}

func (s *userServer) ListUsers(req *pb.ListUsersRequest, stream pb.UserService_ListUsersServer) error {
	for _, id := range req.Ids {
		if u, ok := users[id]; ok {
			if err := stream.Send(u); err != nil { // 服务端流：逐条 Send
				return err
			}
		}
	}
	return nil
}

func main() {
	lis, err := net.Listen("tcp", "127.0.0.1:50051")
	if err != nil {
		log.Fatal(err)
	}
	s := grpc.NewServer() // 拦截器版见示例 4
	pb.RegisterUserServiceServer(s, &userServer{})
	log.Println("gRPC server listening on 127.0.0.1:50051")
	log.Fatal(s.Serve(lis))
}
```

要点：**server 三步走：net.Listen → grpc.NewServer + RegisterUserServiceServer → Serve**；实现接口必须嵌入 `pb.UnimplementedUserServiceServer`；错误用 `status.Error(codes.NotFound, ...)` 返回——**gRPC 用标准错误码跨服务通信**，client 侧 `status.Code(err)` 取出；服务端流用 `stream.Send` 逐条发送，遍历完 `return nil` 即正常结束。

### 示例 3：gRPC client（含 context 超时设置）
```go
// 运行前提：先启动示例 2 的 server（监听 127.0.0.1:50051）
package main
import (
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"time"

	pb "demo/proto"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

func main() {
	// grpc.NewClient 取代已弃用的 grpc.Dial；生产环境用 TLS（ph12）
	conn, err := grpc.NewClient("127.0.0.1:50051", grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()

	client := pb.NewUserServiceClient(conn) // 生成的客户端工厂
	// RPC 必须有超时（必会概念）：调用级超时用 context.WithTimeout
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	u, err := client.GetUser(ctx, &pb.GetUserRequest{Id: 1})
	if err != nil {
		log.Fatalf("GetUser 失败: code=%v err=%v", status.Code(err), err)
	}
	fmt.Printf("GetUser: id=%d name=%s status=%d\n", u.User.Id, u.User.Name, u.User.Status)

	// 服务端流式 RPC：stream.Recv 循环读到 io.EOF 即流结束
	stream, err := client.ListUsers(ctx, &pb.ListUsersRequest{Ids: []int64{1, 2, 3}})
	if err != nil {
		log.Fatal(err)
	}
	for {
		u, err := stream.Recv()
		if errors.Is(err, io.EOF) {
			break // 流正常结束
		}
		if err != nil {
			log.Fatal(err)
		}
		fmt.Printf("ListUsers: %s\n", u.Name)
	}
}
```

要点：**`grpc.NewClient` 取代已弃用的 `grpc.Dial`**；本地调试用 `insecure.NewCredentials()`，生产必须 TLS（ph12）；**调用级超时 = context.WithTimeout**——超时后返回 `codes.DeadlineExceeded`；`stream.Recv` 返回 `io.EOF` 表示流正常结束（区别于真实错误）；`status.Code(err)` 取错误码做决策。运行输出：`GetUser: id=1 name=alice status=1`、`ListUsers: alice`、`ListUsers: bob`。

### 示例 4：服务端/客户端 interceptor（日志 + 超时中间件）
```go
// 单文件自包含：程序内起 server（两个服务端拦截器），再以带拦截器的 client 调用
package main
import (
	"context"
	"fmt"
	"log"
	"net"
	"time"

	pb "demo/proto"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

type userServer struct{ pb.UnimplementedUserServiceServer }

func (s *userServer) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.GetUserResponse, error) {
	time.Sleep(50 * time.Millisecond) // 模拟业务耗时
	if req.Id == 0 {
		return nil, status.Error(codes.InvalidArgument, "id 必须大于 0")
	}
	return &pb.GetUserResponse{User: &pb.User{Id: req.Id, Name: fmt.Sprintf("user-%d", req.Id), Status: 1}}, nil
}

// 服务端拦截器 1：日志（方法名 + 耗时 + 错误）
func loggingUnary(ctx context.Context, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error) {
	start := time.Now()
	resp, err := handler(ctx, req) // 放行到下一层（下一个拦截器 / 真正的 handler）
	log.Printf("[server] %s 耗时 %v err=%v", info.FullMethod, time.Since(start), err)
	return resp, err
}

// 服务端拦截器 2：超时（给请求 context 强加 deadline）
func timeoutUnary(d time.Duration) grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error) {
		ctx, cancel := context.WithTimeout(ctx, d)
		defer cancel()
		return handler(ctx, req)
	}
}

// 客户端拦截器：记录每次调用的耗时与错误
func clientLogging(ctx context.Context, method string, req, reply any, cc *grpc.ClientConn,
	invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
	start := time.Now()
	err := invoker(ctx, method, req, reply, cc, opts...)
	log.Printf("[client] %s 耗时 %v err=%v", method, time.Since(start), err)
	return err
}

func main() {
	lis, err := net.Listen("tcp", "127.0.0.1:50052")
	if err != nil {
		log.Fatal(err)
	}
	// ChainUnaryInterceptor：按传入顺序包裹，logging 在外、timeout 在内
	s := grpc.NewServer(grpc.ChainUnaryInterceptor(loggingUnary, timeoutUnary(200*time.Millisecond)))
	pb.RegisterUserServiceServer(s, &userServer{})
	go s.Serve(lis)
	defer s.Stop()
	time.Sleep(100 * time.Millisecond) // 等服务就绪

	conn, err := grpc.NewClient("127.0.0.1:50052",
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithUnaryInterceptor(clientLogging))
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()

	client := pb.NewUserServiceClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	u, err := client.GetUser(ctx, &pb.GetUserRequest{Id: 7})
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("GetUser ok: %s\n", u.User.Name)
}
```

要点：**服务端拦截器签名** `func(ctx, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error)`，调 `handler(ctx, req)` 放行、返回前补横切逻辑；**`grpc.ChainUnaryInterceptor` 按传入顺序包裹**（logging 在外、timeout 在内）；**客户端拦截器**通过 `invoker` 发起真实调用；运行输出可见两端日志 `[server] /user.UserService/GetUser 耗时 ...` 与 `[client] ...`。扩展：把日志换成 slog 结构化日志、把鉴权（从 metadata 读 token）加进链里，就是生产拦截器的雏形。

### 示例 5：限流 + 熔断简化实现
```go
// 服务端令牌桶限流（超限返回 ResourceExhausted）；客户端简易熔断器
// （连续 3 次失败打开 2 秒，打开期间快速失败、不发网络调用）
package main
import (
	"context"
	"fmt"
	"log"
	"net"
	"sync/atomic"
	"time"

	pb "demo/proto"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

type userServer struct{ pb.UnimplementedUserServiceServer }

func (s *userServer) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.GetUserResponse, error) {
	time.Sleep(10 * time.Millisecond)
	return &pb.GetUserResponse{User: &pb.User{Id: req.Id, Name: "ok", Status: 1}}, nil
}

// ---- 服务端：令牌桶限流（每秒补满一次桶，CAS 原子扣令牌）----
type tokenBucket struct {
	capacity int64
	tokens   atomic.Int64
}

func newTokenBucket(rate int64) *tokenBucket {
	b := &tokenBucket{capacity: rate}
	b.tokens.Store(rate)
	go func() {
		for range time.Tick(time.Second) {
			b.tokens.Store(b.capacity) // 生产用 golang.org/x/time/rate
		}
	}()
	return b
}

func (b *tokenBucket) allow() bool {
	for {
		t := b.tokens.Load()
		if t <= 0 {
			return false
		}
		if b.tokens.CompareAndSwap(t, t-1) {
			return true
		}
	}
}

func rateLimitUnary(b *tokenBucket) grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error) {
		if !b.allow() {
			return nil, status.Error(codes.ResourceExhausted, "rate limited") // 429 语义
		}
		return handler(ctx, req)
	}
}

// ---- 客户端：简易熔断器 ----
type breaker struct {
	failures atomic.Int64
	open     atomic.Bool
}

func (b *breaker) trip() {
	b.open.Store(true)
	go func() {
		time.Sleep(2 * time.Second) // 打开 2 秒后自动恢复（简化演示）
		b.open.Store(false)
	}()
}

func (b *breaker) call(ctx context.Context, fn func() error) error {
	if b.open.Load() {
		return fmt.Errorf("熔断开启：快速失败，不发起网络调用")
	}
	err := fn()
	code := status.Code(err)
	if code == codes.ResourceExhausted || code == codes.Unavailable { // 可重试类错误才计数
		if b.failures.Add(1) >= 3 {
			b.trip()
			fmt.Println(">>> 连续 3 次失败，熔断器打开")
			b.failures.Store(0)
		}
	} else if err == nil {
		b.failures.Store(0)
	}
	return err
}

func main() {
	lis, err := net.Listen("tcp", "127.0.0.1:50053")
	if err != nil {
		log.Fatal(err)
	}
	s := grpc.NewServer(grpc.UnaryInterceptor(rateLimitUnary(newTokenBucket(3)))) // 每秒最多 3 个请求
	pb.RegisterUserServiceServer(s, &userServer{})
	go s.Serve(lis)
	defer s.Stop()
	time.Sleep(100 * time.Millisecond)

	conn, err := grpc.NewClient("127.0.0.1:50053", grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()
	client := pb.NewUserServiceClient(conn)

	cb := &breaker{}
	for i := 0; i < 10; i++ { // 3 个令牌耗尽 → 连续失败 → 熔断打开 → 快速失败
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)
		err := cb.call(ctx, func() error {
			_, err := client.GetUser(ctx, &pb.GetUserRequest{Id: 1})
			return err
		})
		cancel()
		if err != nil {
			log.Printf("第 %d 次: 失败 %v", i+1, err)
		} else {
			log.Printf("第 %d 次: 成功", i+1)
		}
		time.Sleep(50 * time.Millisecond)
	}
}
```

要点：**令牌桶限流**——每秒补满 N 个令牌，`CompareAndSwap` 原子扣减（并发安全），无令牌返回 `codes.ResourceExhausted`（429 语义）；**简易熔断器**——只对"可重试类错误"（ResourceExhausted/Unavailable）计数，连续 3 次失败打开 2 秒，打开期间快速失败、不发网络调用；运行输出为"前 3 次成功 → 4-6 次被限流 → 熔断打开 → 7-10 次快速失败"；生产限流用 `golang.org/x/time/rate`、熔断用 `sony/gobreaker`、重试用 3.5 的 retryPolicy——**三件套组合拳 = 服务稳定性底线**（ph09"超时和限流是服务稳定性的基础"的服务间版本）。

## 7. 总结
### 关键要点
1. **微服务解决组织和扩展问题，也引入复杂度**（必会概念）：独立演进、水平扩展 vs 网络失败、排查困难——复杂度靠规范与工具对冲
2. **RPC 必须有超时**（必会概念）：调用级 context.WithTimeout + 服务端拦截器强制 deadline，无超时的调用会层层拖垮系统
3. **重试要考虑幂等**（必会概念）：重试只对幂等接口安全；读操作天然幂等，写操作设计成"设置"而非"累加"
4. **可观测性是分布式系统的必需品**（必会概念）：日志看细节、指标看趋势、追踪看链路，三支柱缺一不可
5. **protobuf 是接口契约**：.proto 是唯一事实来源，生成代码不可手改；字段编号一旦发布不可变
6. **gRPC = HTTP/2 + protobuf + 代码生成**：多路复用、二进制高效、强类型；四种 RPC 模式覆盖查询到实时推送
7. **拦截器是 gRPC 的中间件**：日志、鉴权、限流、tracing 都挂在这里，与 HTTP middleware 同构
8. **熔断限流保护下游与自己**：限流防打爆、熔断防雪崩连锁，超限返回 ResourceExhausted；**注册发现与网关解决"地址与入口"**：服务名解析替代 IP 写死、网关统一外部入口
9. **错误码是跨服务的语义**：status.Code 传递可编程错误，client 按码决策（重试/降级/报错）

### 跨语言对比：微服务与 RPC
| 维度 | Go gRPC | C++ gRPC | Java gRPC / Spring Cloud | Python gRPC |
|------|---------|----------|--------------------------|-------------|
| RPC 框架 | google.golang.org/grpc（官方） | grpc（官方 C++） | grpc-java / Dubbo | grpcio（官方） |
| 接口定义 | protobuf（.proto） | protobuf | protobuf / Feign 接口 | protobuf |
| 代码生成 | protoc-gen-go / -go-grpc | protoc 内置 | protoc / Maven 插件 | grpcio-tools |
| 服务发现 | etcd/Consul 自定义 resolver | 自研/Envoy | Nacos/Eureka（Spring Cloud） | 自研/Consul |
| 治理能力 | 拦截器手写或 sony/gobreaker | 拦截器 | Spring Cloud 全家桶（Hystrix/Sentinel） | 装饰器/拦截器 |
| 特点 | 简洁、纯 Go、静态二进制 | 性能极致、上手重 | 生态全、治理内置、重 | 胶水语言、生态一般 |

### 阶段验收标准
- **能定义 protobuf 服务**：写 .proto 的 message/service、跑 protoc 生成代码、理解字段编号与 go_package 的语义
- **能实现 gRPC server/client**：server 三步注册 + client 带超时调用，一元与服务端流都能跑通（示例 2/3）
- **能接入日志、指标和 tracing**：拦截器里打结构化日志，能说出 otelgrpc/Prometheus 的接入点（3.7、4.5）
- **能说清超时/重试/幂等/熔断/限流的取舍**：每条必会概念都能给出"为什么 + 怎么做"（3.5）

### 进入下一阶段前
确保能完成以下练习（均来自 roadmap，对应示例编号）：

- **用户服务**：protobuf 定义 + gRPC server（提示：示例 1/2；扩展加"注册用户"方法，密码字段存哈希）
- **订单服务**：幂等下单接口 + 客户端重试（提示：3.5 的 retryPolicy；用幂等键验证重复请求只生效一次）
- **设备管理服务**：服务端流式批量上报 + 限流（提示：示例 2 的 ListUsers + 示例 5 的令牌桶）
- **gRPC 通信 demo**：起两个服务互相调用，A 调 B 拿数据组装响应（提示：示例 2+3；用 status.Code 处理 B 的 NotFound）

### 推荐项目
- **设备数据采集微服务**：设备管理服务（gRPC server，服务端流接收设备批量状态）+ 采集网关（gRPC client 带超时/重试/熔断）+ 限流拦截器——把示例 2/3/5 拼成"设备上报 → 采集服务"链路；验收：client 压测可见限流生效、停掉 server 再启动可见重试恢复、模拟下游故障可见熔断打开
- **gRPC 服务框架 demo**：把示例 4 的拦截器沉淀为可复用框架——统一日志、超时、鉴权（metadata 传 token）、tracing 埋点，新服务接入只需注册 handler——正是 roadmap 推荐项目形态，也为 ph17 架构分层打底

### 下一阶段
**云原生与部署阶段**（`ph12-cloud-native`，文档规划中）——Docker、Kubernetes、CI/CD、监控告警；本阶段的多服务将打包成镜像部署到集群，Prometheus 抓取指标、健康检查与优雅退出上线，注册发现与配置中心从"本机进程"升级为"集群内服务"。
