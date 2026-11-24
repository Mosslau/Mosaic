# 共享基础设施（D0 底座）

> 定位：AI 平台与数据平台**共用**的 D0 底座。两个平台的 D0 不各建一套 compose——Kafka / PG / Redis / RustFS / Vault / 观测只起一次。
> 状态：🚧（7 个组件已实测；12 项烟测全部通过；K8s / Loki 未验证，见「未验证项」）
> 对应验收：数据平台 `V0-1`–`V0-3`；AI 平台 `A0-1`–`A0-3`（仅 D0，D1 起未开始）

## 组件与端口

本机已有另一套栈占用 5432 / 6379 / 9090 / 3000，本底座全部换端口：

| 组件 | 镜像 | 宿主端口 | 用途 |
|---|---|---|---|
| Kafka（KRaft 单节点） | `apache/kafka:4.4.0` | **19092** | 事件总线；D3 接入 / D4 流计算 |
| PostgreSQL 16 | `postgres:16-alpine` | **15432** | 账本、注册表、元数据 |
| Redis 7 | `redis:7.4-alpine` | **16379** | 缓存 / 状态（孪生、限流） |
| Prometheus | `prom/prometheus:v2.55.1` | **19090** | 指标抓取（当前仅抓自身） |
| Grafana | `grafana/grafana:11.3.1` | **13000** | 看板；已预置 Prometheus 数据源 |
| RustFS（对象存储） | `rustfs/rustfs:1.0.6` | 19000 / 19001 | Iceberg 湖 / 语料 / Skill 包 / 归档；S3 兼容、Apache-2.0 |
| Vault（凭据） | `hashicorp/vault:1.18` | 18200 | 凭据唯一来源（dev 模式） |

默认账号：Grafana `admin / mosaic`；PG 库/用户/密码 `mosaic / mosaic / mosaic`；RustFS `mosaic / mosaic123`；Vault dev root token `root`。

**7 个组件全部必选**：`./up.sh` 默认全起，并用 `--wait` 等 healthcheck 通过。

> **RustFS 镜像说明**：MinIO 自 2025-10 起停止发布社区版镜像（Docker Hub 下架、Quay 401），底座已改用 **RustFS**（Apache-2.0、S3 兼容，2026-09 GA）。本机直连 Docker Hub 不通，实际拉取走 `docker.1panel.live/rustfs/rustfs` 后 tag 为 `rustfs/rustfs:1.0.6`；正式环境应改为固定 digest 并同步到内部 registry。云上对应形态是 S3 / OSS（同一套 S3 API，见[数据平台 D2](../data-platform/通用数据平台建设路线.md)）。

## 一键起停

```bash
cd engineering/compose
./up.sh                          # 起 7 个组件，等 healthcheck 通过
./up.sh kafka postgres           # 只起指定服务（调试用）
./down.sh                        # 停服务，保留数据卷
./down.sh --volumes              # 连卷一起删
```

## 验收：`./smoke.sh`

实测输出（2026-11-24，macOS arm64 / Docker 29.5.3 / Compose v5.3.1；`smoke.sh` 需本机 `curl` 支持 `--aws-sigv4`，即 7.75+）：

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
== 6. RustFS：健康 + 建桶/写读对象 ==
  ✅ RustFS :19000 health=200
  ✅ bucket mosaic-smoke 可创建（HTTP 200）
  ✅ mosaic-smoke/d0.txt 可写可读（hello-rustfs）
== 7. Vault：状态 + 写读一个 secret ==
  ✅ vault status 可读（dev 模式 unsealed）
  ✅ secret/d0 smoke=ok 可写可读
== 汇总 ==
  通过 12 项，失败 0 项
  结论：D0 通过（7 个组件全部健康）
```

对应关系：

| 验收 | 证据 |
|---|---|
| `V0-1` / `A0-1` 一条命令起停 | `./up.sh` 一次起 7 个服务，全部 healthy |
| `V0-2` / `A0-2` 健康 / 指标 / 日志 | 7 个服务均带 healthcheck；Prometheus `/-/healthy` 与查询 API 通过；Grafana `/api/health` 通过；`docker compose logs kafka` 可读 |
| `V0-3` / `A0-3` dummy 链路 | 同一次 smoke 内完成：Kafka 生产/消费 + PG 建表写查 + Redis 读写 + RustFS 建桶写读对象 + Vault 写读 secret |

## 未验证项（不装作通过）

| 项 | 原因 | 补验证方式 |
|---|---|---|
| RustFS 对象锁 / 版本（WORM） | D0 只验证了基础 S3 读写；WORM 是车联网 Raw 层增量需求 | D2 前做对象锁 POC（`PutObjectLockConfiguration` + 合规保留） |
| K8s / kind | 本机未安装 kind / kubectl 集群 | AI D6 前补；当前用 compose 替代 |
| Loki / OTel Collector | 镜像未缓存；先用 Prometheus + docker logs 顶替 | D9 控制面前补 |

## 边界

- 只做**共享底座**；D1 契约内核尚未建立（原 P1 demo 已移除），不在本目录；D2 起的 Polaris Catalog / Doris 等平台组件也不在本目录（归数据平台 D2/D3）。
- 不引入 K8s 编排；生产化（HA、备份、TLS）属 D12/D10，不在 D0 范围。
- Vault 是 **dev 模式**（内存态、root token、无持久化），只用于本地开发；生产化接 KMS / 正式 Vault 集群。
- Prometheus 当前只抓自身；D1 契约库/注册服务落地后再恢复 `mosaic-dummy` target。
