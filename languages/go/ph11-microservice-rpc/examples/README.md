# examples —— 微服务与 RPC 阶段完整示例

验证环境：go1.25.6（darwin/arm64）。六个示例各自是**独立的 Go module**（目录内自带 go.mod），先进入示例目录再运行——请勿在 examples/ 根目录执行 `go test ./...`（根目录没有 go.mod）。

**RPC 实现策略**：示例 1~5 全部基于**标准库** `net/rpc` + `net/rpc/jsonrpc`（零第三方依赖，可离线构建运行）——net/rpc 自 Go 1.0 起进入标准库，官方声明**冻结**（不再接收新功能），但其"注册对象方法 → 序列化 → 传输 → 路由"的机制是理解一切 RPC 的教材；示例 6 是 gRPC/protobuf 生态（protobuf 接口契约 + protoc 代码生成 + HTTP/2 + 拦截器），本环境**实际生成并跑通**（工具链与版本见下表）。

| 目录 | 说明 | 运行 |
|------|------|------|
| `ex01-rpc-basic/` | net/rpc 基础：Register + Gob 二进制编码，客户端同步 Call 与异步 Go，方法签名约束与错误透传 | `cd ex01-rpc-basic && go test -v`；`go run .` |
| `ex02-jsonrpc-codec/` | JSON-RPC 编解码：net/rpc/jsonrpc 的 wire 格式（裸 TCP 手写报文演示 + Go client），与 Gob 对比 | `cd ex02-jsonrpc-codec && go test -v`；`go run .` |
| `ex03-registry-discovery/` | 服务注册与发现：本地注册表（登记/心跳/TTL 摘除/发现）+ 多实例注册 + 优雅下线 | `cd ex03-registry-discovery && go test -v`；`go run .` |
| `ex04-lb-timeout-breaker/` | 负载均衡 / 超时 / 熔断：轮询 LB、callWithTimeout（net/rpc 无原生 deadline）、熔断状态机 closed→open→half-open | `cd ex04-lb-timeout-breaker && go test -v`；`go run .` |
| `ex05-streaming/` | 流式概念：JSON-RPC 2.0 通知（无 id）在持久连接上的服务端流推送，消息边界与 EOF 语义 | `cd ex05-streaming && go test -v`；`go run .` |
| `ex06-grpc-ecosystem/` | gRPC/protobuf 生态：.proto 定义 → protoc 生成 → 一元 + 服务端流 + 拦截器（日志/超时） | `cd ex06-grpc-ecosystem && go test -v`；`go run .` |

## 实测数据（本环境跑出，如实记录）

全部示例通过 `gofmt -l`（零差异）、`go vet ./...`（零报告）、`go test ./...`（行为符合预期）、`go test -race ./...`（无数据竞争）；覆盖率为本机实际输出（`go test -cover`）：

| 示例 | go test -cover | 备注 |
|------|----------------|------|
| ex01-rpc-basic | 56.1% | 7 个用例全过（命中/未命中/排序/校验/异步/未知方法/errors.Is 不适用） |
| ex02-jsonrpc-codec | 49.4% | 5 个用例全过（wire 格式/id 回显/错误响应/手写报文/Go client 往返） |
| ex03-registry-discovery | 70.2% | 5 个用例全过（登记发现/TTL 摘除/心跳续约/注销/实例生命周期） |
| ex04-lb-timeout-breaker | 67.9% | 12 个用例全过（轮询序列/超时触发/熔断三态/慢实例超时/集成） |
| ex05-streaming | 60.8% | 5 个用例全过（订阅 5 条推送/通知无 id/连接复用/部分订阅/超时回归） |
| ex06-grpc-ecosystem | 46.6% | 5 个用例全过（一元/流式/NotFound 错误码/DeadlineExceeded/拦截器链）；proto 为生成代码不计量 |

## 验证环境与工具链

- **Go**：go1.25.6（darwin/arm64）；示例 1~5 零第三方依赖。
- **gRPC 生态（ex06）**：protoc 29.3（本机 `/opt/homebrew/anaconda3/bin/protoc`）+ `protoc-gen-go v1.36.6` + `protoc-gen-go-grpc v1.5.1`（`go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.6`、`go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1` 安装）+ `google.golang.org/grpc v1.72.0` + `google.golang.org/protobuf v1.36.6`——本环境**实际生成 pb 代码并跑通全部测试**（生成命令见 ex06/generate.sh，pb 文件已提交，无 protoc 环境可直接构建）。
- **依赖拉取环境**（仅 ex06 需要网络）：`GOPROXY=https://goproxy.cn,direct GOSUMDB=off GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache`（本机默认 proxy.golang.org 不可达，goproxy.cn 可达）。
- 六个示例的验证状态均为：**已验证**。

## 注意事项

- 示例均为**单进程自包含**（程序内起 server、client 调用后退出，无残留进程）；真实场景是多个进程，把 server/client 拆成两个入口即可——project/ 就是这么做的。
- 示例服务监听 `127.0.0.1:0`（内核分配随机端口，避免冲突）；ex06 的 `go run .` 固定用 127.0.0.1:52051，结束即释放。
- net/rpc 错误**只以字符串透传**、无状态码（对应 gRPC 的 codes.*），判断时用字符串/自定义类型，`errors.Is` 不适用（ex01 有专门用例）。
