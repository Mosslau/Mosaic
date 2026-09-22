# ph17 阶段项目：节点管理服务

## 项目定位

把 roadmap §17 推荐项目「节点管理服务」落地为一个**分层单体**：节点注册、状态查询、心跳上报、版本升级、指令受理走 HTTP 管理面（`cmd/deviceapi`），内部按 handler（HTTP 翻译）/ service（业务规则）/ store（内存与 JSON 文件两种存储实现，repository 角色）/ domain（领域模型）/ errs（业务错误码）/ config（配置）分层，构造函数注入组装，service 与 handler 各带单元测试。

**教学价值**：本阶段只练"单个服务内部的代码组织"——依赖方向单向向内、接口在消费方声明、构造函数注入、错误码在边界统一包装与翻译。不引入任何框架或第三方依赖（只用标准库），把"分层"本身讲透；目录名 `cmd/deviceapi` 沿用历史命名，它就是本服务的 HTTP 管理面入口。

**术语口径与 ph21 对齐**：本服务管理的领域对象是「被平台管理的**节点档案**」（node）——注册、状态查询、心跳上报、版本升级、指令受理这些语义与 ph21 采集接入网关一致（ph21 里 `SourceID` 是**数据源**标识、节点档案承载节点的生命周期、`Collector` 是**采集器**）。管理面只做"节点的注册与状态管理"，**不做协议接入**（MQTT/WebSocket 遥测数据上行属 [ph21 通用数据采集与接入网关方向 Go 阶段](../../ph21-data-ingest-gateway/21-data-ingest-gateway.md)），也不做对外 API 契约设计（属 [ph18 API 设计与兼容性阶段](../../ph18-api-design-compat/18-api-design-compat.md)，roadmap 第 18 节）。

## 功能清单

- [x] `POST /api/nodes`：注册节点（id/name 非空、id 唯一、版本可选但必须是 `major.minor.patch`），新节点默认 offline
- [x] `GET /api/nodes` / `GET /api/nodes/{id}`：列表（按 ID 排序）与单个查询
- [x] `DELETE /api/nodes/{id}`：注销节点（不存在 → 404）
- [x] `POST /api/nodes/{id}/heartbeat`：心跳上报——节点上线（status=online）并刷新 lastSeen
- [x] `POST /api/nodes/{id}/version`：版本升级——**禁止版本回退**（冲突 → 409 CONFLICT），同版本幂等
- [x] `POST /api/nodes/{id}/commands`：指令受理——**离线节点拒收**（409 NODE_OFFLINE），在线节点受理（202）
- [x] `GET /healthz`：探活
- [x] 存储实现可切换：`-store mem`（重启即空）| `-store file`（JSON 文件持久化，重启仍在），service/handler 零改动
- [x] 统一错误结构 `{"code":"NODE_...","message":"..."}`，唯一的错误码 → HTTP 状态映射点在 handler.fail
- [x] JSON 结构化日志（slog）+ 访问日志中间件（method/path/duration）
- [x] service 层单测（stub 替身 + 注入时钟）与 handler 层集成单测（httptest + 内存存储）

## HTTP 管理面接口清单

| 方法 | 路径 | 语义 | 成功 | 失败（业务码 → 状态） |
| --- | --- | --- | --- | --- |
| POST | `/api/nodes` | 注册节点档案 | 201 + Node | 参数非法 `BAD_REQUEST`→400；重复 `NODE_EXISTS`→409 |
| GET | `/api/nodes` | 节点列表（按 ID 排序） | 200 + Node[] | — |
| GET | `/api/nodes/{id}` | 查询单个节点 | 200 + Node | `NODE_NOT_FOUND`→404 |
| DELETE | `/api/nodes/{id}` | 注销节点 | 204 | `NODE_NOT_FOUND`→404 |
| POST | `/api/nodes/{id}/heartbeat` | 心跳上报（置在线、刷新 lastSeen） | 200 + Node | `NODE_NOT_FOUND`→404 |
| POST | `/api/nodes/{id}/version` | 版本升级（禁止回退） | 200 + Node | `BAD_REQUEST`→400；`CONFLICT`→409 |
| POST | `/api/nodes/{id}/commands` | 指令受理（离线拒收） | 202 + `{"status":"accepted"}` | `NODE_OFFLINE`→409 |
| GET | `/healthz` | 探活 | 200 + `{"status":"ok"}` | — |

节点档案字段：`id`、`name`、`status`（online/offline/maintenance）、`version`（语义化版本，空串 = 未安装）、`lastSeen`（最近一次心跳时间）。

## 目录结构

```
project/
├── go.mod                      # go 1.25.0（全仓语言版本档）
├── cmd/
│   └── deviceapi/
│       └── main.go             # 组装点 + 启动：配置 → 存储 → service → handler → 中间件（HTTP 管理面入口）
└── internal/
    ├── config/                 # 配置解析（flag > 环境变量 > 默认值）
    ├── domain/                 # 领域模型：Node/Status/ErrNotFound（依赖图最内层）
    ├── errs/                   # 业务错误码：Code + Error{Code,Msg,Err}（可 errors.Is/As）
    ├── service/                # 业务层：注册/心跳/版本/指令规则（定义 NodeStore 接口）
    │   └── service_test.go     # 白盒单测：stub 替身 + 注入时钟
    ├── store/                  # repository：mem.go（内存）/ file.go（JSON 文件）
    └── handler/                # 接入层：路由 + 请求/响应翻译 + fail() 唯一错误映射
        └── node_test.go        # httptest 集成单测
```

依赖方向（单向向内，无环）：

```text
cmd/deviceapi（组装）──▶ handler ──▶ service ──▶ domain ◀── store（实现，不 import service）
                               └──────▶ errs ◀── service  /  handler（只认 Code）
```

## 与 ph21 的分工边界

- **本项目（ph17，管理面）**：只维护节点档案本身——注册/注销、状态查询、心跳刷新、版本登记与升级、指令受理判定。它是"平台侧对节点的台账与生命周期入口"，不碰任何线路协议。
- **ph21（采集接入网关，数据面）**：数据源（source）↔ 采集端（agent）↔ 采集器（Collector）的协议接入、鉴权、聚合、断网缓存与补传、遥测上行与清洗存储；真实平台里心跳由采集器批量上报，本项目管理面的单台上报只是教学演示。
- 一句话：**遥测上行属 ph21，节点台账与状态管理属本项目**。二者共享"节点/数据源"的身份口径，但代码与进程互不依赖。

## 验证环境与命令

- 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（只用标准库）。
- 本机 go-build 缓存在沙箱外会被拒，因此本仓库统一把缓存重定位到 `/tmp`：

```bash
cd languages/studies/go/ph17-architecture-layering/project
GOCACHE=/tmp/gocache-goph17 GOPATH=/tmp/gopath-goph17 go build ./... && \
GOCACHE=/tmp/gocache-goph17 GOPATH=/tmp/gopath-goph17 go vet ./... && \
GOCACHE=/tmp/gocache-goph17 GOPATH=/tmp/gopath-goph17 go test ./... && \
gofmt -l .
```

- 起服务（内存存储）：`go run ./cmd/deviceapi -addr 127.0.0.1:18084 -store mem`
- 起服务（文件存储，重启数据仍在）：`go run ./cmd/deviceapi -addr 127.0.0.1:18084 -store file -store-file /tmp/ph17-nodes.json`
- 冒烟（另开终端，以文件存储为例）：

```bash
# 1. 注册节点（新节点默认 offline）
curl -s -X POST http://127.0.0.1:18084/api/nodes \
  -d '{"id":"node-0001","name":"节点组 A-1 号节点","version":"1.2.3"}'
# 2. 离线节点下发命令 → 409 {"code":"NODE_OFFLINE",...}
curl -s -X POST http://127.0.0.1:18084/api/nodes/node-0001/commands -d '{"command":"restart"}'
# 3. 心跳上线 → 200 status=online、lastSeen 刷新
curl -s -X POST http://127.0.0.1:18084/api/nodes/node-0001/heartbeat
# 4. 版本回退 → 409 {"code":"CONFLICT",...}（禁止回退）
curl -s -X POST http://127.0.0.1:18084/api/nodes/node-0001/version -d '{"version":"1.0.0"}'
# 5. 在线节点下发命令 → 202 {"status":"accepted"}
curl -s -X POST http://127.0.0.1:18084/api/nodes/node-0001/commands -d '{"command":"restart"}'
```

## 验收标准

- [x] `go build ./... && go vet ./... && go test ./...` 通过，`gofmt -l .` 无输出 —— **go1.25.6 本机实测通过（已验证）**
- [x] 能画出 import 依赖图并说清：为什么 store 不 import service、为什么 domain 谁也不 import、为什么接口断言写在 cmd/deviceapi
- [x] 用 `-store mem` 与 `-store file` 各跑一遍冒烟：文件存储下重启进程后数据仍在、内存存储下重启即空——证明 repository 隔离了存储细节
- [x] 能指认每个规则（唯一性/默认离线/禁止回退/离线拒命令）在 service 层的哪一行，并说明对应的单测用例
- [x] 用 `curl` 打一个未知节点与一次版本回退，确认响应都是统一的 `{"code","message"}` 结构且 code 稳定

### 实测结果（2026-09-22，go1.25.6 darwin/arm64）

```text
$ GOCACHE=/tmp/gocache-goph17 GOPATH=/tmp/gopath-goph17 go build ./...
（无输出，退出码 0）
$ GOCACHE=/tmp/gocache-goph17 GOPATH=/tmp/gopath-goph17 go vet ./...
（无输出，退出码 0）
$ GOCACHE=/tmp/gocache-goph17 GOPATH=/tmp/gopath-goph17 go test ./...
ok  	tenetlang/go/ph17-architecture-layering/project/internal/handler	0.008s
ok  	tenetlang/go/ph17-architecture-layering/project/internal/service	0.006s
（cmd/deviceapi、config、domain、errs、store 无测试文件）
$ gofmt -l .
（无输出）
```

`go run ./cmd/deviceapi -addr 127.0.0.1:18084 -store file -store-file /tmp/ph17-nodes.json` 冒烟观察（实测原文摘录）：

```text
GET  /healthz                                   -> 200
POST /api/nodes {"id":"node-0001",...}          -> 201 {"id":"node-0001","status":"offline","version":"1.2.3",...}
POST /api/nodes/node-0001/commands（离线）       -> 409 {"code":"NODE_OFFLINE","message":"节点 node-0001 当前状态 offline，命令无法下发"}
POST /api/nodes/node-0001/heartbeat             -> 200 {"status":"online","lastSeen":"2026-09-22T03:43:54Z",...}
POST /api/nodes/node-0001/version 1.0.0（回退）  -> 409 {"code":"CONFLICT","message":"版本不允许回退: 1.2.3 -> 1.0.0"}
POST /api/nodes/node-0001/commands（在线）       -> 202 {"status":"accepted"}
GET  /api/nodes/node-0001                       -> 200（重启进程后仍返回该节点，文件存储持久化生效）
GET  /api/nodes/ghost                           -> 404 {"code":"NODE_NOT_FOUND","message":"节点不存在"}
```

## 扩展方向

- 把「handler 直接序列化 domain.Node」升级为 DTO 隔离：请求/响应结构与领域模型解耦，字段可独立演进（对外契约稳定化的完整纪律属 [ph18 API 设计与兼容性阶段](../../ph18-api-design-compat/18-api-design-compat.md)）
- 给 `store/file.go` 加写时临时文件 + rename 原子替换，避免进程被杀留下半截文件（本实现为教学简化）
- 把 service 的"心跳决定在线"换成**租约过期**模型（超时未上报自动 offline），为 ph21 真实节点生命周期打底
- 把"指令受理"扩展为异步命令队列 + ACK 追踪，管理面与投递链分离（投递链实现属 ph21 通用数据采集与接入网关方向 Go 阶段）
- 节点档案若要与 ph21 的数据源（source）/采集器（Collector）对账，可增加 `sourceID` 字段并抽出"节点 ↔ 数据源"映射层——本阶段刻意不做，保持分层教学的最小面
- 单体内部边界即未来服务边界：本项目的 service 接口一旦变厚（多域、独立伸缩诉求），按 ph11 微服务与 RPC 阶段的技术形态抽取为独立服务——拆的时机判断见主文档 3.8
