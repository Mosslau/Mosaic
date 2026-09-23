# ph11 阶段项目：设备数据采集微服务

> 对应 Roadmap「微服务与 RPC 阶段」推荐项目之一——**设备数据采集微服务**（另一个「gRPC 服务框架 demo」见扩展方向）。把本阶段的知识点拼成三个可独立运行的服务：
> **注册中心（服务注册与发现）+ 设备管理服务（限流上报与查询，可多实例）+ 采集网关（发现 → 负载均衡 → 超时/熔断/重试）**。
> 与 ph09 的「设备数据上报 API」（单体 HTTP）一脉相承：本阶段把"服务"拆成多个进程，通信从 HTTP JSON 升级为 RPC。

## 需求

设备端端设备持续上报状态（device_id、speed、ts），采集网关负责把上报可靠地送达设备管理服务：

- **注册中心**（独立进程）：服务实例启动时登记"服务名 → 地址"、周期心跳续约、TTL 过期摘除失联实例，消费方按服务名发现——对应生产 etcd/Consul/Nacos 的最小模型
- **设备管理服务**（可多实例）：JSON-RPC 提供状态上报（令牌桶限流，超限拒绝）+ 按设备查询最新状态；启动时注册、退出时优雅下线
- **采集网关**：发现全部实例 → 轮询负载均衡（每实例一个熔断器）→ 带超时与重试的上报 → 跨实例汇总查询（演示"无共享存储时状态分散在各实例"）

## 目录结构

```text
project/
├── cmd/
│   ├── registry/              # 注册中心进程（JSON-RPC 暴露 Register/Heartbeat/Deregister/Discover）
│   ├── device-service/        # 设备管理服务进程（注册 + 心跳 + 限流上报 + 查询 + 优雅下线）
│   └── gateway/               # 采集网关进程（发现 → LB → 超时/熔断/重试 → 汇总查询）
└── internal/
    ├── registry/              # 注册表：Register/Heartbeat/Deregister/Discover + TTL 摘除 + RPC 服务/客户端
    ├── lb/                    # 轮询负载均衡（RoundRobin）
    ├── breaker/               # 熔断器状态机（closed → open → half-open）
    └── device/                # 设备服务契约 + 服务端（限流）+ 弹性客户端（三原语组合）
```

## 功能清单

- [x] 注册中心：登记/心跳/注销/发现（经 JSON-RPC），TTL 惰性摘除失联实例
- [x] 设备服务：限流上报（令牌桶，超限返回 rate limited）、按设备查询、多实例各自独立状态
- [x] 网关：发现 → 轮询 → 熔断（每实例一个，open 快速失败不发网络调用）→ 超时（1s）→ 瞬时失败换实例重试
- [x] 限流是"忙"不是"故障"：被限流实例不计入熔断失败，重试换实例可成功
- [x] 故障自愈：实例宕机 → 熔断打开 → 重启后冷却期过半开探针成功 → 恢复 closed
- [x] 跨实例汇总查询 GetAll（演示无共享存储的状态分散问题，生产落 ph10 数据库）
- [x] 三个进程均支持 SIGINT/SIGTERM 优雅退出（设备服务先 Deregister 再关监听）

## 验收标准

- `go build ./...`、`go vet ./...` 零告警、`go test ./...` 全部通过、`go test -race ./...` 无数据竞争
- `go test -cover ./internal/...` 实测覆盖率（go1.25.6）：**internal/lb 100.0%、internal/breaker 96.4%、internal/registry 93.4%、internal/device 85.6%**（cmd 为入口，不计量）
- 冒烟（本环境实测通过，测完已 kill 干净、无残留进程与端口）：

```text
轮次 1：发现 2 个设备服务实例 [127.0.0.1:53051 127.0.0.1:53052]
  上报 car-001 -> ok   （9 次上报全部成功，轮询分摊到两个实例）
查询 car-001 -> 127.0.0.1:53051 上最新状态: speed=75 ts=...
kill -TERM 设备服务 → "收到退出信号，注销服务并关闭监听" → "设备服务已退出"
```

- 故障演练（可选，人工验证）：起 1 个设备服务后 kill 掉（不注销）→ 网关连续上报 2 次失败 → 熔断打开 → 后续上报"熔断开启: 快速失败"（不发网络调用）→ 同端口重启设备服务 → 500ms 冷却后半开探针成功 → 上报恢复

## 验证环境

go1.25.6（darwin/arm64），依赖：**零第三方**（全部标准库 net/rpc + net/rpc/jsonrpc，可离线构建运行）。依赖拉取环境仅当需要 go.sum 时才涉及网络（本项目无第三方依赖，无 go.sum）。

```bash
# 1. 构建与测试
go build ./...
go vet ./...
go test ./... && go test -race ./... && go test -cover ./internal/...

# 2. 起注册中心（TTL 5s）
go run ./cmd/registry -addr 127.0.0.1:54001

# 3. 起两个设备服务实例（另开终端）
go run ./cmd/device-service -addr 127.0.0.1:53051 -registry 127.0.0.1:54001
go run ./cmd/device-service -addr 127.0.0.1:53052 -registry 127.0.0.1:54001

# 4. 起采集网关（3 轮演示）
go run ./cmd/gateway -registry 127.0.0.1:54001 -rounds 3

# 5. 停止（优雅退出）
kill -TERM <各进程 pid>
```

> ⚠️ 网关的 `GetAll` 查询演示了"无共享存储时，同一设备状态可能只存在于部分实例"——本演示各实例用内存 map 独立存状态（教学简化）；生产应把状态落到共享存储（ph10 数据库阶段）或做数据同步，跨实例查询只是兜底手段。

## 扩展方向（可选）

- **gRPC 改造**：把 JSON-RPC 换成 gRPC + protobuf（参考 examples/ex06），服务间错误用 status.Code 传递
- **服务框架化**：把"发现 → LB → 熔断 → 超时重试"沉淀为可复用框架（roadmap 另一个推荐项目「gRPC 服务框架 demo」），新服务只注册 handler
- **真实注册中心**：把 internal/registry 换成 etcd/Consul 的 Go client（本环境未装 etcd/Consul，未验证）
- **共享存储**：设备状态落到 SQLite/MySQL（ph10 的连接池与事务），多实例读写同一份数据
- **设备遥测推送**：状态实时推送（服务端流，参考 examples/ex05 的通知流）——属 ph21 通用数据采集与接入网关深入阶段
