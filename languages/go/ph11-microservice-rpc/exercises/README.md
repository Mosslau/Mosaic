# ph11 微服务与 RPC 阶段练习

> 先自己做，再对照 `sol-*` 参考实现。每题标注难度（★~★★★），四题与 roadmap 本阶段「练习」小节一一对应（用户服务 / 订单服务 / 设备管理服务 / gRPC 通信 demo）。按 roadmap 顺序 1 → 2 → 3 → 4 即可，按难度递进建议 1 → 2 → 3 → 4。

运行方式：每个参考实现是**独立的 Go module**（目录内自带 go.mod），先进入对应目录再运行（如 `cd sol-01-user-service && go test -v`）。请勿在 exercises/ 根目录执行 `go test ./...`——根目录没有 go.mod。

依赖：sol-01~03 **零第三方依赖**（标准库 net/rpc + net/rpc/jsonrpc，可离线运行）；sol-04 是 gRPC demo，需要 `google.golang.org/grpc` + protobuf（与 examples/ex06 相同，GOPROXY 配置见下）。参考实现文件头都写了验证环境与命令（已验证：go1.25.6，darwin/arm64）；**sol 文件头的覆盖率数字均为本机实测后写入**（ph08/ph10 教训：不许先写后编）。

依赖拉取环境（仅 sol-04 需要）：`GOPROXY=https://goproxy.cn,direct GOSUMDB=off GOCACHE=/tmp/gocache`（本机默认 proxy.golang.org 不可达，goproxy.cn 可达）。

## 练习 1：用户服务（★）

**目标**：用标准库 net/rpc 定义并调用一个用户服务（GetUser / ListUsers / AddUser），理解 RPC 方法签名约束与错误透传。

**要求**：

- 服务对象方法满足签名约束：`func (t *T) MethodName(arg T1, reply *T2) error`；方法名、参数/返回值类型、字段全部可导出
- 用 `RegisterName("UserService", ...)` 显式指定服务名；编码用 `net/rpc/jsonrpc`（JSON-RPC wire）
- GetUser 查无此用户返回错误（错误以字符串透传）；AddUser 对空 name 报错
- 服务端状态用 `sync.Mutex` 保护（RPC 是并发的）

**验收**：`go test -v` 覆盖：AddUser 返回自增 ID、GetUser 命中/未命中、ListUsers 按 ID 升序、空 name 校验、未注册服务名调用失败；`go vet ./...` 零报告。

> 提示：参考 examples/ex01-rpc-basic 与 examples/ex02-jsonrpc-codec；先自己写再对照。

## 练习 2：订单服务（★★）

**目标**：实现**幂等下单**接口 + 客户端**超时重试**，落地必会概念"重试要考虑幂等"。

**要求**：

- `CreateOrder(UserID, Amount, IdempotencyKey)`：同一幂等键重复提交返回**第一次创建的同一订单**、不重复入库（服务端 `map[key]*Order` 去重）
- 金额非正 / 幂等键为空 → 报错
- 客户端 `callWithTimeout`（net/rpc 无原生 deadline，用 goroutine + select 自定时长）与 `callWithRetry`（瞬时失败退避重试 N 次）
- 说明：为什么"幂等键"让"重试"与"重复提交"等价（只对幂等接口安全）

**验收**：`go test -v` 覆盖：下单成功、同 key 两次返回同一订单、不同 key 不同订单、非法金额/缺 key 报错、首次失败重试成功、重试耗尽报错、慢调用超时返回 ErrTimeout；`go vet ./...` 零报告。

> 提示：参考 examples/ex04 的 callWithTimeout；幂等键在真实系统是"请求方生成的唯一标识"（如 UUID），服务端按它去重。

## 练习 3：设备管理服务（★★）

**目标**：实现服务端**令牌桶限流**的上报接口 + 基于 JSON-RPC 通知的**服务端流**推送，理解"限流保护服务"与"流式 = 同一连接上连续的多条消息"。

**要求**：

- `DeviceService.ReportStatus`：令牌桶限流（`atomic.Int64` + CompareAndSwap 扣令牌），超限返回 "rate limited"（429 语义）
- `DeviceService.Subscribe`：先回 ack（带 id），再连续推送 N 条设备状态通知（无 id 的 notification），推完关闭连接（客户端读到 EOF = 流结束）
- wire 报文手写 JSON-RPC 2.0 简化版（请求 `{"method","params","id"}`，params 为数组），消息边界用换行分隔

**验收**：`go test -v` 覆盖：限流内前 3 次成功、第 4 次被拒、补桶后恢复、订阅收到 5 条推送（device_id 正确）、上报与订阅共存、未知方法报错；`go vet ./...` 零报告。

> 提示：参考 examples/ex05-streaming 的报文结构与订阅循环；令牌桶参考 examples/ex04 或 sol-03 参考实现。

## 练习 4：gRPC 通信 demo（★★★）

**目标**：用 gRPC + protobuf 起**两个服务互相调用**——订单服务（A）的 GetOrder 内部调用用户服务（B）拿用户名组装响应，用 `status.Code` 处理 B 的 NotFound。

**要求**：

- 一个 .proto 定义两个 service：`UserService.GetUser`（B）与 `OrderService.GetOrder`（A）；`option go_package` 指向本 module 的 proto 包
- protoc 生成代码（命令见 generate.sh；本机 protoc 29.3 + protoc-gen-go v1.36.6 + protoc-gen-go-grpc v1.5.1 实测可用）；生成产物提交进仓库
- A 的服务对象注入 `pb.UserServiceClient`（依赖注入，便于测试替换）；GetOrder 内部 `context.WithTimeout` 调用 B（"RPC 必须有超时"）
- B 的 NotFound 错误码**原样透传**给上层客户端

**验收**：`go test -v` 覆盖：GetOrder 返回组装后的 user_name、订单不存在 NotFound、**用户已删时 B 的 NotFound 透传且错误信息是 "user not found"**、重复查询一致；`go vet ./...` 零报告。

> 提示：参考 examples/ex06-grpc-ecosystem 的工程结构（proto + generate.sh + server/client + 拦截器）；本练习不需要拦截器，聚焦"两服务协作 + 错误码透传"。

---

四道练习与 `sol-*` 参考实现一一对应（sol-01 ~ sol-04），全部做完再对照复盘。
