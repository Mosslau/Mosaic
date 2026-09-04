# ph21 阶段项目：边缘网关转发服务 + 云端接入验收（edge-platform）

> Go 学习路线的收官工程（roadmap §21 与附录）。roadmap §21 推荐项目二选一，本工程选了**边缘网关转发服务**，并按附录「阶段性项目验收标准」把云端接入侧做成可测试可部署的完整交付形态：一条"车辆样本 → 边缘网关（本地聚合/断网缓存/断点续传）→ 云端接入（鉴权/幂等/清洗/时序存储/告警/指标）→ 查询/监控端点"的收官链路，衔接 ph01~ph20 全部技能。

## 需求

设备世界由边缘网关代理接入云端（主文档 3.11 的工程形态）：

- **网关侧**（cmd/gateway）：模拟若干车辆产生遥测；本地聚合（攒满 N 条出一批，3.11）；上行走 HTTP 并携带网关级动态 token（3.2）；网络瞬时失败把批写进**有界断网缓存 spool**（3.11）；恢复后**按原批号断点续传**、云端 ack 水位推进（4.3）；鉴权失败不重试直接拒绝。
- **云端侧**（cmd/platform）：`POST /api/v1/batches` 接收上行——**连接态鉴权**（HMAC token，3.2）、**批级幂等**（网关断网重试原样重放不二次生效，3.3）、**清洗校验**（vin/seq/量程，坏批进死信计数，3.7）、**时序存储与实时状态**（3.8）、**告警规则**（超速 warn/critical，3.7）；暴露 `/healthz`、`/version`、`/metrics`（Prometheus 文本，3.9）、车辆/最新速度查询 API。
- 链路收口：ph19 project「车辆遥测消费服务」消费的 `fleet.telemetry.v1` 主题，其上游接入正是本工程网关所代表的采集侧——本工程把 ph19 消费链路的"上游写端"补全。

## 架构

```text
车辆 A ─┐
车辆 B ─┼──▶ cmd/gateway（边缘网关）           cmd/platform（云端接入）
车辆 C ─┘      │ local.Collector（聚合满批）       │ api.Handler（薄 HTTP 层）
               │ gateway.Gateway.HandleBatch ──▶  POST /api/v1/batches
               │    ├─ 上行成功 ───────────────────▶  auth.Verify（token）
               │    └─ 瞬时失败 → spool（有界缓存） │  platform.Core.HandleBatch
               │                                    │    ├─ 批级幂等(去重窗)
               │ gateway.Flush（恢复后按序补传）    │    ├─ model.Validate（清洗）
               │    └─ ack 水位 → 裁剪 spool        │    ├─ store（时序+状态+水位）
               │                                    │    ├─ 告警规则
               │                                    │    └─ Counters（指标）
               │                                    └─ /healthz /version /metrics
               │                                       /api/v1/vehicles|{vin}/speed
```

## 功能清单

- [x] 边缘网关：本地聚合（条数触发出批）、有界断网缓存、按原批号补传、ack 水位推进、鉴权失败拒绝不重试
- [x] 云端接入：网关 token 鉴权、批级幂等、模型校验（坏批死信计数）、样本换算入库（m/s→km/h）
- [x] 云端存储与查询：内存时序存储（样本/最新速度）、每网关 ack 水位、车辆列表、车辆最新速度端点
- [x] 告警：超速 warn/critical 规则，命中计数进指标
- [x] 可观测端点：`/healthz`、`/version`（ldflags 注入点）、`/metrics`（Prometheus 文本）
- [x] 交付物：README、Makefile、Dockerfile、优雅退出、`go test -race` 全绿
- [ ] 真 Docker 镜像构建与运行（本机无 Docker，见 Dockerfile，未在本环境验证）

## 目录结构

```
project/
├── go.mod                    # go 1.25.0（全仓语言版本档）
├── doc.go                    # module 根包（供根 e2e 测试挂载）
├── e2e_test.go               # 端到端验收：断网→缓存→恢复→补传→幂等→端点全链路
├── Makefile                  # build/test/vet/race/run-platform/run-gateway
├── Dockerfile                # 平台二进制多阶段镜像（未在本环境验证）
├── cmd/
│   ├── platform/main.go      # 云端进程：env 配置 + API + 优雅退出
│   └── gateway/main.go       # 网关进程：模拟车队采集 + 上行/补传循环（-once 演示）
└── internal/
    ├── api/                  # 薄 HTTP 层（方法路由、JSON、/metrics 文本）
    ├── auth/                 # 网关级 HMAC 动态 token（Sign/Verify + Registry）
    ├── config/               # env 加载（端口/密钥表/聚合与缓存参数）
    ├── gateway/              # Collector 聚合 + Spool 缓存 + Gateway/Flush + HTTPUplink
    ├── model/                # 线路模型 BatchUpload/Sample + Validate（两测共享）
    ├── platform/             # Core（鉴权/幂等/清洗/存储/告警/计数）+ Store
    └── version/              # -ldflags 注入点（Version/Commit/BuildTime）
```

依赖方向（单向向内，无环）：

```text
cmd/ ──▶ internal/{api,gateway} ──▶ internal/{platform,model,auth} ──▶ internal/{store...,config,version}
e2e_test.go ──▶ cmd 之外组装：api + gateway + platform（真 HTTP loopback）
```

## 验证环境与命令

- 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（只用标准库）；go 命令需带仓库统一重定位环境
  （`GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache GOPROXY=off GOSUMDB=off`）
- 构建/测试/静态检查：`go build ./... && go test ./... && go vet ./...`
- 竞态复核：`go test -race ./...`
- 格式化：`gofmt -l .`（应无输出）
- **验证状态：已验证**——go1.25.6 本机实测 vet/build/test 全绿、`go test -race ./...` 全绿、gofmt 合规；e2e 演练（含"断网→缓存→恢复→补传→批级幂等→端点断言"）在真 HTTP loopback 上跑通，输出摘要见下。

```text
== e2e（TestEdgePlatformEndToEnd）关键断言 ==
在线期 6 批 ×3 样本 → 入库 18（spool=0）
断网 3 批 → spool=3；恢复补传 → 水位 9、spool=0、入库 27
重放批 1 → 不二次生效（入库仍 27，dup+1）
坏密钥 → 401；/healthz 200；/metrics 含 fleet_samples_cleaned_total 27
/vehicles 3 台；veh-001 最新速度 = 205.2 km/h
```

## 本地运行演练（两条终端）

```bash
# 终端 A：起云端（默认密钥 edge-001=dev-secret-1）
PLATFORM_ADDR=127.0.0.1:8080 GATEWAY_SECRETS=edge-001=dev-secret-1 \
  go run ./cmd/platform

# 终端 B：网关跑一轮确定性采集（3 车 × 6 条，flushSize=3 → 6 批）
go run ./cmd/gateway -once -cloud http://127.0.0.1:8080 \
  -gateway-id edge-001 -secret dev-secret-1 -vehicles 3 -samples 6

# 观察端点（另开终端）
curl -s localhost:8080/healthz
curl -s localhost:8080/version
curl -s localhost:8080/metrics
curl -s localhost:8080/api/v1/vehicles
curl -s localhost:8080/api/v1/vehicles/veh-001/speed
```

## 验收标准

- [ ] `go build ./... && go test ./... && go vet ./...` 通过（go1.25.6 本机实测全绿（已验证））；`go test -race ./...` 通过
- [ ] e2e 全绿：断网缓存/恢复补传/水位收敛/批级幂等/鉴权拒绝/四个可观测端点断言全部通过
- [ ] 能指认收官链路各段代码位置：网关聚合（`internal/gateway/gateway.go: Collector.Add`）、断网缓存与水位（`Spool.Enqueue/AckUpTo`）、上行鉴权（`internal/auth` + `api.handleBatches`）、批级幂等（`platform.Core.HandleBatch` 的 markSeen）、清洗校验（`model.BatchUpload.Validate`）、存储与指标（`platform.Store`/`Counters`）
- [ ] 能运行本地演练：终端 A 平台起来、终端 B 网关 `-once` 跑完一轮，curl 四个端点有响应
- [ ] 能解释"换真 MQTT broker 只改哪一层"：`internal/gateway` 的 `Uplink` 接口（新增一个 MQTT 实现即可），平台侧模型/幂等/存储不动
- [ ] 能说明附录交付形态：README/Makefile/Dockerfile/healthz/metrics/优雅退出各自在哪、`/version` 用 `-ldflags` 如何注入

## 扩展方向

- **真 MQTT 接入**：给 `internal/gateway` 实现基于 paho 的 `Uplink`（读 3.1 真 paho 路径命令），上行从 HTTP 换 MQTT topic `veh/{vin}/telemetry`；平台侧可接 ex01 自研 broker 或真 Mosquitto
- **存储落真库**：`platform.Store` 换 InfluxDB/TDengine（内存模型与 Series/Point 同构，3.8）；实时状态换 Redis 并接影子（3.6）
- **OTA 接入平台**：把 exercises/sol-03 的灰度决策器作为"控制面"加进云端，与升级批次/回滚目标联动（3.10）
- **生产化**：告警写事件流推 ph19 topic（消费端即 ph19 project）、按 `-race` + e2e 的纪律扩展压测（附录"可观测可压测"）、多网关水平扩展与分区
