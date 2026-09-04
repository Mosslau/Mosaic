# ph17 阶段项目：车联网设备管理服务

## 需求

把 roadmap §17 推荐项目「车联网设备管理服务」落地为一个**分层单体**：设备注册、状态查询、心跳上报、固件升级、指令受理走 HTTP 管理面（`cmd/deviceapi`），内部按 handler（HTTP 翻译）/ service（业务规则）/ store（内存与 JSON 文件两种存储实现，repository 角色）/ domain（领域模型）/ errs（业务错误码）/ config（配置）分层，构造函数注入组装，service 与 handler 各带单元测试。管理面只做"设备的注册与状态管理"，**不做设备协议接入**（MQTT/WebSocket 遥测上行属 [ph21 IoT / 车联网 / 嵌入式相关 Go 阶段](../../ph21-iot-vehicle-edge/21-iot-vehicle-edge.md)），也不做对外 API 契约设计（属 [ph18 API 设计与兼容性阶段](../../ph18-api-design-compat/18-api-design-compat.md)，roadmap 第 18 节）。

## 功能清单

- [x] `POST /api/devices`：注册设备（id/name 非空、id 唯一、固件可选但必须是 `major.minor.patch`），新设备默认 offline
- [x] `GET /api/devices` / `GET /api/devices/{id}`：列表（按 ID 排序）与单个查询
- [x] `DELETE /api/devices/{id}`：注销设备（不存在 → 404）
- [x] `POST /api/devices/{id}/heartbeat`：心跳上报——设备上线（status=online）并刷新 lastSeen
- [x] `POST /api/devices/{id}/firmware`：固件升级——**禁止版本回退**（冲突 → 409 CONFLICT），同版本幂等
- [x] `POST /api/devices/{id}/commands`：指令受理——**离线设备拒收**（409 DEVICE_OFFLINE），在线设备受理（202）
- [x] `GET /healthz`：探活
- [x] 存储实现可切换：`-store mem`（重启即空）| `-store file`（JSON 文件持久化，重启仍在），service/handler 零改动
- [x] 统一错误结构 `{"code":"DEVICE_...","message":"..."}`，唯一的错误码 → HTTP 状态映射点在 handler.fail
- [x] JSON 结构化日志（slog）+ 访问日志中间件（method/path/duration）
- [x] service 层单测（stub 替身 + 注入时钟）与 handler 层集成单测（httptest + 内存存储）

## 目录结构

```
project/
├── go.mod                      # go 1.25.0（全仓语言版本档）
├── cmd/
│   └── deviceapi/
│       └── main.go             # 组装点 + 启动：配置 → 存储 → service → handler → 中间件
└── internal/
    ├── config/                 # 配置解析（flag > 环境变量 > 默认值）
    ├── domain/                 # 领域模型：Device/Status/ErrNotFound（依赖图最内层）
    ├── errs/                   # 业务错误码：Code + Error{Code,Msg,Err}（可 errors.Is/As）
    ├── service/                # 业务层：注册/心跳/固件/指令规则（定义 DeviceStore 接口）
    │   └── service_test.go     # 白盒单测：stub 替身 + 注入时钟
    ├── store/                  # repository：mem.go（内存）/ file.go（JSON 文件）
    └── handler/                # 接入层：路由 + 请求/响应翻译 + fail() 唯一错误映射
        └── device_test.go      # httptest 集成单测
```

依赖方向（单向向内，无环）：

```text
cmd/deviceapi（组装）──▶ handler ──▶ service ──▶ domain ◀── store（实现，不 import service）
                               └──────▶ errs ◀── service  /  handler（只认 Code）
```

## 验证环境与命令

- 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（只用标准库）；go 命令需带仓库统一重定位环境
  （`GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache GOPROXY=https://goproxy.cn,direct GOSUMDB=off`）
- 构建/测试/静态检查：`go build ./... && go test ./... && go vet ./...`
- 起服务（内存存储）：`go run ./cmd/deviceapi -addr 127.0.0.1:18084 -store mem`
- 起服务（文件存储，重启数据仍在）：`go run ./cmd/deviceapi -addr 127.0.0.1:18084 -store file -store-file /tmp/ph17-devices.json`
- 冒烟（另开终端，以文件存储为例）：

```bash
# 1. 注册设备（新设备默认 offline）
curl -s -X POST http://127.0.0.1:18084/api/devices \
  -d '{"id":"car-0001","name":"车队A-1号车","firmware":"1.2.3"}'
# 2. 离线设备下发命令 → 409 {"code":"DEVICE_OFFLINE",...}
curl -s -X POST http://127.0.0.1:18084/api/devices/car-0001/commands -d '{"command":"restart"}'
# 3. 心跳上线 → 200 status=online、lastSeen 刷新
curl -s -X POST http://127.0.0.1:18084/api/devices/car-0001/heartbeat
# 4. 固件回退 → 409 {"code":"CONFLICT",...}（禁止回退）
curl -s -X POST http://127.0.0.1:18084/api/devices/car-0001/firmware -d '{"version":"1.0.0"}'
# 5. 在线设备下发命令 → 202 {"status":"accepted"}
curl -s -X POST http://127.0.0.1:18084/api/devices/car-0001/commands -d '{"command":"restart"}'
```

## 验收标准

- [ ] `go build ./... && go test ./... && go vet ./...` 通过（service_test 与 handler_test 全绿；go1.25.6 本机实测通过（已验证））
- [ ] 能画出 import 依赖图并说清：为什么 store 不 import service、为什么 domain 谁也不 import、为什么接口断言写在 cmd/deviceapi
- [ ] 用 `-store mem` 与 `-store file` 各跑一遍冒烟：文件存储下重启进程后数据仍在、内存存储下重启即空——证明 repository 隔离了存储细节
- [ ] 能指认每个规则（唯一性/默认离线/禁止回退/离线拒命令）在 service 层的哪一行，并说明对应的单测用例
- [ ] 用 `curl` 打一个未知设备与一次固件回退，确认响应都是统一的 `{"code","message"}` 结构且 code 稳定

## 扩展方向

- 把「handler 直接序列化 domain.Device」升级为 DTO 隔离：请求/响应结构与领域模型解耦，字段可独立演进（对外契约稳定化的完整纪律属 [ph18 API 设计与兼容性阶段](../../ph18-api-design-compat/18-api-design-compat.md)）
- 给 `store/file.go` 加写时临时文件 + rename 原子替换，避免进程被杀留下半截文件（本实现为教学简化）
- 把 service 的"心跳决定在线"换成**租约过期**模型（超时未上报自动 offline），为 ph21 真实设备生命周期打底
- 把"指令受理"扩展为异步命令队列 + ACK 追踪，管理面与投递链分离（投递链实现属 ph21 IoT / 车联网 / 嵌入式相关 Go 阶段）
- 单体内部边界即未来服务边界：本项目的 service 接口一旦变厚（多域、独立伸缩诉求），按 ph11 微服务与 RPC 阶段的技术形态抽取为独立服务——拆的时机判断见主文档 3.8
