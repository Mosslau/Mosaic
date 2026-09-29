# 选型验证 PoC（P0）

> 状态：⬜ 未开始
> 所属平台与单元：data-platform · P0 选型验证（类别：期）
> 对应文档：../通用数据平台建设路线.md（工程路线：§6 P0 排期、§7 V1–V8 通过标准）；../../roadmap/智能通用大数据平台工程师.md（职业路线）

## 目标

证明所选开源能**拼起来**、关键连接器可用、资源预算算得清——**不做业务**（业务链路从 P1 起）。

本单元是**探针型**（形态：探针）：它不交付业务链路，交付的是一次性付清、全平台受益的**兼容矩阵 + 资源预算 + 版本锁定**，后续六期直接引用（§2.6 的 PoC 档由此回填）。

## 范围与不做

- **范围**：12 个组件在本机 Docker Compose 起栈；跑通 8 条连接性 / 兼容性验证（V1–V8）；出《选型验证报告》；锁定各组件版本并建立兼容矩阵；完成一项非技术评估（Dinky）与一项预研 spike（Calcite 语义层）。
- **不做**：不做业务链路与调度编排（P1 起）、不做元数据治理 / 服务化 / AI；**不引入 K8s**（单机 Compose）。

## 技术栈

一台 **8C32G** 起步（16G 在 DataHub + ES + Doris + DS 同启时余量不足，先算后起——见 V6 与 §2.6）：

| 组件 | 版本 | 用途 |
|---|---|---|
| Kafka（KRaft） | 3.7+ | 总线 |
| MinIO | latest（P0 实测后锁定 tag 并写入兼容矩阵） | 对象存储 |
| SeaTunnel（Zeta） | 2.3.x | 集成引擎 |
| Apache Flink | 1.20 | 长驻流作业运行时（StreamPark 托管的**作业本体**；V8 需要有作业可启停） |
| Apache Doris | 2.1.x | OLAP 仓 |
| ClickHouse | 24.x+ | Doris 的选型对照（与 V3 同数据量、同规模跑写入 / 查询，决策见 §9 风险 9） |
| DolphinScheduler | 3.2.x | 编排 / 调度 |
| StreamPark | 2.1.x（P0 实测后锁定，写入兼容矩阵） | 实时作业托管（只验其 OpenAPI 能否被外部幂等启停，见 V8） |
| DataHub | 1.0.x（P0 实测后锁定，写入兼容矩阵） | 元数据（元数据库**复用平台 PostgreSQL，不引入 MySQL**，V5 一并验证；若与平台 PG 不兼容，回退 0.14.x 并记录） |
| Elasticsearch | 8.x | DataHub 索引依赖 |
| PostgreSQL / Redis | 16 / 7 | 平台元数据（DataHub 元数据库、Iceberg JdbcCatalog、DS 元数据库、平台配置库复用；schema / 账号 / 连接上限见 §2.5 约定 3）/ 缓存 |

## 系统架构

**验证环境拓扑**（单机 Compose，全部容器同宿主；箭头 = 待验证的连接）：

```text
业务库(MySQL) ──V1──▶ Kafka(KRaft) ──V2──▶ SeaTunnel(Zeta) ──▶ Iceberg(MinIO)
                                                        │
                                                        └──V3──▶ Doris 2.1
                                                        └──V3(对照)──▶ ClickHouse 24

DolphinScheduler ──V4──▶ 批作业（Shell / SQL / SeaTunnel）
StreamPark ──V8──▶ Flink 入门作业（验 OpenAPI 幂等启停）
DataHub(GMS + 前端) ──V5──▶ 平台 PostgreSQL（元数据库复用）+ Elasticsearch（索引）
横切：Prometheus + Grafana（V6 资源预算的观测面）
```

**连通矩阵**（V1–V8 的验证对象与依赖）：

| 验证 | 链路 / 对象 | 依赖组件 | 前置 |
|---|---|---|---|
| V1 | MySQL-CDC → Kafka | SeaTunnel CDC 连接器、Kafka | —— |
| V2 | Kafka → Iceberg | SeaTunnel、Iceberg、MinIO | V1 |
| V3 | JDBC 分片 → Doris（+ ClickHouse 对照） | Doris、ClickHouse | —— |
| V4 | DS 调度批作业 | DolphinScheduler | —— |
| V5 | DataHub 采集 | DataHub、PostgreSQL、Elasticsearch | —— |
| V6 | 资源预算 | 全部容器 | 起栈后 |
| V7 | Iceberg / SeaTunnel 版本兼容 | Iceberg、SeaTunnel | V2 |
| V8 | StreamPark OpenAPI 幂等启停 | StreamPark、Flink | —— |

## 前置与复用

- **前置单元**：无（P0 是平台起点）。
- **前置条件**：8C32G 宿主；镜像与驱动 jar 可离线获取；ClickHouse 对照的数据量口径。
- **复用**：不复用 `algorithms/` 的实验。
- **产出被谁引用**：§2.6 的 PoC 档（实测回填）、§3 各组件的版本号与兼容矩阵、P1 的门禁（V6）与环境拓扑。

## 验收标准

- [ ] **V1** SeaTunnel: MySQL-CDC → Kafka —— 改一行 5 秒内可见，信封完整
- [ ] **V2** SeaTunnel: Kafka → Iceberg —— 湖表可查；重放两次不变
- [ ] **V3** SeaTunnel: JDBC 分片 → Doris（ClickHouse 对照）—— 并行生效，无 load 错误；同数据量的写入吞吐 / 查询 P95 对照结论写入报告（决策见 §9 风险 9）
- [ ] **V4** DolphinScheduler 调度批作业 —— 定时成功，可重跑
- [ ] **V5** DataHub 采集元数据（元数据库复用平台 PG）—— 表字段可见；DataHub 元数据库运行于平台 PostgreSQL；各复用方（DataHub / Iceberg Catalog / DS / 配置库 / 审计）的 schema、账号与连接上限已划分并记录（§2.5 约定 3）
- [ ] **V6** 资源预算（§2.6 PoC 档）—— 逐服务稳态 RSS 记录 + `mem_limit` 加总 < 宿主 80% + 冒烟链路通过
- [ ] **V7** Iceberg / SeaTunnel 版本兼容 —— sink 写入成功
- [ ] **V8** StreamPark OpenAPI 鉴权与幂等 —— 连续两次启动不产生第二个作业实例；鉴权方式确认

**交付物**：`选型验证报告.md`（含兼容矩阵、§2.6 PoC 档实测、ClickHouse / Doris 对照、语义层 spike 与 Dinky 评估结论）+ 可复跑的 `docker-compose.yml` + 8 条 V 的实测记录。

**两项不占 V 编号的产出**（同属本单元）：

1. **Dinky 社区治理与发版节奏审查**（§3⑤）——结论写入报告后再决定是否引入；
2. **语义层 spike**——用 Calcite 原型翻译 3 个代表性指标（含派生指标与时间粒度），对照评估 dbt MetricFlow；结论（自研 Calcite / 引入 MetricFlow / 限定 MQL 为受约束 JSON DSL）写入报告，**P2 开工前评审**。

## 实施笔记

- **开工前置条件**（2026-09 拟定，开工前逐项确认）：① 宿主 8C32G 与磁盘余量；② 镜像与驱动 jar 的离线获取路径；③ ClickHouse 对照的数据量与"同规模"口径；④ 语义层 spike 的人力与评审时点（P2 开工前）。
- **已知风险与对策**（开工前逐项盯）：

| 风险 | 对策 |
|---|---|
| 驱动 jar 目录官方文档三处不一致 | 实测确认，写进部署规范 |
| Iceberg 与 SeaTunnel 版本不兼容 | 锁 SeaTunnel 支持的 Iceberg 版本（1.6.1） |
| 内存打穿（旧项目踩过：6 容器 + 1 万长连接打穿 6GB） | V6 门禁卡住，先算预算再起容器 |
| DataHub 组件多（GMS + 前端 + ES + 元数据库） | 元数据库复用平台 PG（不引入 MySQL）；PoC 阶段可先只用其采集能力，完整部署放 P3 |
