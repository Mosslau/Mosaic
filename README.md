# 🌊 OceanVerse

> **百川汇洋，数据纳乾坤**
>
> *From a thousand streams, one ocean.*

**A big data platform: Ingestion · Processing · Serving.**

[![CI](https://github.com/Mosslau/OceanVerse/actions/workflows/ci.yml/badge.svg)](https://github.com/Mosslau/OceanVerse/actions/workflows/ci.yml)

智能电动车数据智能平台——从车端数据采集接入、实时流处理，到分析服务化输出与可视化监控，构建完整的数据水利工程。

## 🚀 从这里开始

| 我想… | 去哪 |
|---|---|
| 看**现在走到哪**、下一步做什么 | `roadmap/项目进度.md` |
| 把环境跑起来 | 《deploy/README.md》§4（首次先 `bash emqx/gen-certs.sh`） |
| 亲手验证一条数据流 | `ingest/docs/03-验收示例集-v1.md`（命令 → 期望输出 → 判定） |
| 看**指标面板** | http://localhost:3000（`admin`/`admin`）→ Dashboards：`device-gateway` / `device-codec` / `realtime-metrics` |
| 跑**实时作业**（Flink SQL：在线数/故障数/高温电池） | `warehouse/streaming/README.md`（四步：起 Flink → 建表 → 提交 → 看结果） |
| 查**指标准确定义**（口径唯一源） | `warehouse/streaming/README.md` §2 |
| 读**设计** | 《ingest/docs/01-接入层设计-v1.md》（权威）/《ingest/docs/02-GB32960协议规格-v1.md》（协议） |
| 排障 | 《deploy/README.md》Q1~Q13 +《ingest/docs/03-验收示例集-v1.md》§7 判定清单 |
| 看**全局蓝图** | `roadmap/OceanVerse架构总览.md`（八大能力域 + 24 月五阶段） |

## CI 管什么

`.github/workflows/ci.yml` **8 个作业**（5 类），挡住曾真实发生过的回归：

| 作业 | 内容 | 挡住什么 |
|---|---|---|
| `go`（矩阵 ×4 模块） | `gofmt` / `build` / `vet` / `test` / `test -race` | 代码回归 |
| `docker` | 三个镜像构建（gateway / codec / **flink**）+ 冒烟跑 `/health` + Flink 连接器 jar 在位断言 | 契约拆分后 Dockerfile 静默失效；自建 Flink 镜像漏 jar |
| `pipeline-health` | `scripts/check-pipeline-health.sh`（6 组判据，含 Q11 僵尸消费组） | "消费组被孤儿进程占着"这类常规检查看不出的故障 |
| `compose` | 真起**八容器** + 逐容器 healthcheck + 内存预算门禁 + 预算门禁体检 + **Flink profile 起来并断言集群** + Prometheus 规则新鲜度 | 结构校验冒充运行验证；账面内存超配；编排断裂 |
| `docs` | `scripts/check-docs.sh`（⑨ 组事实校验，含实时层口径三处一致）+ `scripts/check-mermaid.sh`（渲染校验） | 文档漂移：旧路径/裸引用/数字对不上/围栏嵌套/图渲染失败/口径三处不同步 |

本地等价执行：`bash scripts/check-docs.sh && bash scripts/check-compose-budget.sh && bash scripts/test-compose-budget.sh`（Mermaid 渲染校验另需 Docker）。

环境约定：`runs-on: ubuntu-24.04`（显式钉 LTS，避开 `ubuntu-latest` 于 2026-10-19 迁往 Ubuntu 26）；`actions/checkout@v7` + `actions/setup-go@v7`（Node 24 运行时）；Go 版本来自各模块 `go.mod` 的 `go` 指令，升级 Go 无需改 workflow。

## Why "OceanVerse"?

In Greek mythology, all rivers and springs eventually flow into Oceanus,
the great river encircling the world. Data follows the same journey —
from scattered streams into one ocean of insight.

## License

MIT
