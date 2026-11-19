# 共享基础设施（D0 底座）

> 定位：AI 平台与数据平台**共用**的 D0 底座。两个平台的 D0 不各建一套 compose——Kafka / PG / Redis / 观测只起一次。
> 状态：🚧（5 个组件已实测；MinIO / Vault 镜像未缓存、K8s 未验证，见「未验证项」）
> 对应验收：数据平台 `V0-1`–`V0-3`；AI 平台 `A0-1`–`A0-3`

## 组件与端口

本机已有另一套栈占用 5432 / 6379 / 9090 / 3000，本底座全部换端口：

| 组件 | 镜像 | 宿主端口 | 用途 |
|---|---|---|---|
| Kafka（KRaft 单节点） | `apache/kafka:4.4.0` | **19092** | 事件总线；D3 接入 / D4 流计算 |
| PostgreSQL 16 | `postgres:16-alpine` | **15432** | 账本、注册表、元数据 |
| Redis 7 | `redis:7.4-alpine` | **16379** | 缓存 / 状态（孪生、限流） |
| Prometheus | `prom/prometheus:v2.55.1` | **19090** | 指标抓取；抓 `mosaic-dummy`（18180/18181） |
| Grafana | `grafana/grafana:11.3.1` | **13000** | 看板；已预置 Prometheus 数据源 |
| MinIO（可选） | `minio/minio` | 19000 / 19001 | 对象存储；`--profile objectstore` |
| Vault（可选） | `hashicorp/vault:1.18` | 18200 | 凭据；`--profile vault` |

Grafana 默认账号 `admin / mosaic`；PG 默认库/用户/密码 `mosaic / mosaic / mosaic`。

## 一键起停

```bash
cd engineering/infra/compose
./up.sh                          # 起 5 个默认组件，等健康检查通过
./up.sh --profile objectstore    # 追加 MinIO（需联网拉镜像）
./up.sh --profile vault          # 追加 Vault（需联网拉镜像）
./down.sh                        # 停服务，保留数据卷
./down.sh --volumes              # 连卷一起删
```

## 验收：`./smoke.sh`

实测输出（2026-11-11，macOS / Docker 29.6.2 / Compose v5.3.1）：

```text
== 2. Kafka：建 topic + 生产/消费一条 ==
  ✅ topic mosaic.smoke 可写可读（hello-mosaic）
== 3. Postgres：建表 / 写入 / 查询 ==
  ✅ d0_smoke 写入并查到 1 行
== 4. Redis：set / get ==
  ✅ redis d0:smoke=ok
== 5. Prometheus / Grafana ==
  ✅ Prometheus :19090 healthy
  ✅ Prometheus 查询 API 返回 success
  ✅ Grafana :13000 health=ok
  ✅ 容器日志可查（docker compose logs kafka）
== 6. 可选组件 ==
  ➖ MinIO 未启动（镜像未缓存；需要时 ./up.sh --profile objectstore）
  ➖ Vault 未启动（镜像未缓存；需要时 ./up.sh --profile vault）
  通过 7 项，失败 0 项
```

对应关系：

| 验收 | 证据 |
|---|---|
| `V0-1` / `A0-1` 一条命令起停 | `./up.sh` 一次起 5 个服务，全部 healthy |
| `V0-2` / `A0-2` 健康 / 指标 / 日志 | 5 个服务均带 healthcheck；Prometheus `/-/healthy` 与查询 API 通过；Grafana `/api/health` 通过；`docker compose logs kafka` 可读 |
| `V0-3` / `A0-3` dummy 链路 | Kafka 生产/消费一条消息 + PG 写入/查询 + Redis 读写（同一次 smoke 内完成） |

## 未验证项（不装作通过）

| 项 | 原因 | 补验证方式 |
|---|---|---|
| MinIO | 镜像未缓存；本次拉取 `minio/minio` 时 registry 连接中断 | 网络恢复后 `./up.sh --profile objectstore`，再跑 `mc` 冒烟 |
| Vault | 同上 | `./up.sh --profile vault` 后用 `vault status` 验证 |
| K8s / kind | 本机未安装 kind / kubectl 集群 | AI D6 前补；当前用 compose 替代 |
| Loki / OTel Collector | 镜像未缓存；先用 Prometheus + docker logs 顶替 | D9 控制面前补 |

## 边界

- 只做**共享底座**；D1 契约内核在各平台的 `P1-contract-kernel/`，不在本目录。
- 不引入 K8s 编排；生产化（HA、备份、TLS）属 D12/D10，不在 D0 范围。
- Prometheus 的 `mosaic-dummy` target 指向宿主 `18180/18181`，dummy 服务未启动时 target 为 down，不影响 D0 判定。
