# ph18 阶段项目：设备管理 API 规范（spec-first + v1/v2 兼容）

## 需求

把 roadmap §18 推荐项目「设备管理 API 规范」落地为一个 **spec-first 的版本化设备 API**：
`internal/spec/openapi.json` 是唯一权威规范（同时描述 /v1 与 /v2 两代接口），实现严格照规范挂载路由、裁剪字段、返回错误；根目录 `contract_test.go` 是契约测试——把规范与实现逐条对账，任何漂移（实现多一条路由、响应多一个字段、错误结构不一致）都在 CI 立刻变红。承接 ph17 project（分层单体设备管理服务）的扩展方向："把 handler 直接序列化 domain 升级为 DTO 隔离 + 对外契约稳定化"——本项目的 v1/v2 DTO 裁剪与错误码注册表正是兑现那条方向。

## 功能清单

- [x] `/v1/devices` GET：列表（status/offset/limit 过滤分页，固定按 id 排序）；POST：注册设备（201 + Location，v1/v2 共用）
- [x] `/v1/devices/{id}` GET / DELETE：单查（带 Deprecation/Sunset 弃用通告头）与幂等注销（204）
- [x] `/v2/devices` GET：v1 超集——列表新增 `sort` 参数（白名单 id/name + id 决胜）
- [x] `/v2/devices/{id}` GET：v2 视图（新增 `model`、`lastSeen` 字段），不带弃用头
- [x] **统一错误结构**：全 API 只有 `{code,message}` 一种错误形态，code 来自 `internal/apierr` 注册表（v1.0 三个 code：BAD_REQUEST / DEVICE_NOT_FOUND / INTERNAL），`apierr_test.go` 钉住"历史 code 永不可删"
- [x] **版本演进通过 DTO 裁剪落地**：领域模型无 json tag 不属于任何版本；v1 响应绝不泄漏 v2 字段（handler_test 断言），v2 是 v1 的超集
- [x] **契约测试五连**（contract_test.go）：路由双向对齐、Error schema 必填 code/message 且全错误响应引用共享组件、v2 schema ⊇ v1 schema、2xx 响应全部带 example、query 参数声明与实现解析集合一致

## 目录结构

```
project/
├── go.mod                    # go 1.25.0（全仓语言版本档）
├── doc.go                    # module 根包（供根契约测试挂载）
├── contract_test.go          # spec-first 契约测试（规范 ↔ 实现双向对账）
├── cmd/deviceapi/            # 组装点：store → handler → mux
└── internal/
    ├── apierr/               # 错误码注册表（集中、只增不删、带 since/语义）+ 测试
    ├── devices/              # 领域模型 + v1/v2 DTO 裁剪 + store + 版本化 handler + 集成测试
    └── spec/
        ├── openapi.json      # 唯一权威规范（v1+v2 双版本，含 example/枚举/错误 schema）
        └── spec.go           # OpenAPI 最小解析器（go:embed 打包规范）
```

依赖方向（单向向内，无环）：

```text
contract_test.go（根）──▶ internal/spec（读规范）──▶ internal/devices（Routes/QueryKeys/响应字段）
cmd/deviceapi（组装）──▶ internal/devices ──▶ internal/apierr
```

## 验证环境与命令

- 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（只用标准库）；go 命令需带仓库统一重定位环境
  （`GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache GOPROXY=https://goproxy.cn,direct GOSUMDB=off`）
- 构建/测试/静态检查：`go build ./... && go test ./... && go vet ./...`
- 起服务：`go run ./cmd/deviceapi -addr 127.0.0.1:18110`
- 冒烟（另开终端）：

```bash
# 1. v1 单查：只有 v1 三字段 + Deprecation 头
curl -s -D - http://127.0.0.1:18110/v1/devices/dev-001
# 2. v2 单查：v1 超集（model/lastSeen），无弃用头
curl -s http://127.0.0.1:18110/v2/devices/dev-001
# 3. 列表（v2 sort 能力）
curl -s 'http://127.0.0.1:18110/v2/devices?sort=name&offset=0&limit=10'
# 4. 统一错误：未知设备 / 非法状态参数
curl -s http://127.0.0.1:18110/v1/devices/nope
curl -s 'http://127.0.0.1:18110/v2/devices?status=bogus'
# 5. 幂等注销：重复 DELETE 两次均 204
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE http://127.0.0.1:18110/v1/devices/dev-002
```

## 验收标准

- [ ] `go build ./... && go test ./... && go vet ./...` 通过（根契约测试 + apierr + devices 集成测试全绿；go1.25.6 本机实测通过（已验证））
- [ ] 能说清 spec-first 的工作流：规范先于实现、实现只认规范、契约测试保证两者永不漂移
- [ ] 能指认"字段只增不删"的三重保险各在哪：v2 schema ⊇ v1 schema（spec 层 contract_test）、v1 响应不泄漏 v2 字段（handler_test）、错误码注册表只增不删（apierr_test）
- [ ] 冒烟验证 v1 带 Deprecation 头而 v2 不带；v1 响应不含 model/lastSeen
- [ ] 做一个"破坏实验"：给 DeviceV1 加一个 json 字段 → `go test ./...` 中 handler_test 的红（响应字段越界），还原后变绿——能解释为什么这条防线存在

## 扩展方向

- 把手工 OpenAPI 解析换成真实工具链：用 `oapi-codegen` 从 YAML 生成 server/client 桩，用 spec 校验器做 schema 级验证（本实现为演示契约思想而零第三方手写）
- 规范与实现的 version 演进（v3）：在 openapi.json 中追加 /v3 路径并写迁移说明，观察 v1→v3 期间三层保险如何约束你
- v1 下线流程：Sunset 到期后从 spec 与 Routes() 同时移除 v1 路径——契约测试会提醒你哪些客户端契约一并消失
- 把错误结构升级为带 `requestId`/`details` 的 v2 错误体（字段只增不删的又一次演练，参考 examples/ex02）
- 项目与 ph11/ph19 衔接：本 API 一旦被多个服务调用，接口版本与错误语义就成了跨服务的契约——消息事件里的 schema 版本管理属 [ph19 消息队列与事件驱动深入阶段](../../ph19-mq-event-driven/19-mq-event-driven.md)
