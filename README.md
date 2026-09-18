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
| 亲手验证一条数据流 | `ingest/docs/接入层示例集-v1.md`（命令 → 期望输出 → 判定） |
| 看**指标面板** | http://localhost:3000（`admin`/`admin`）→ Dashboards：`device-gateway` / `device-codec` |
| 读**设计** | 《ingest/docs/接入层与车端接入网关设计-v1.md》（权威）/《ingest/docs/GB32960-二进制协议与字段映射-v1.md》（协议） |
| 排障 | 《deploy/README.md》Q1~Q13 +《ingest/docs/接入层示例集-v1.md》§7 判定清单 |
| 看**全局蓝图** | `roadmap/OceanVerse架构总览.md`（八大能力域 + 24 月五阶段） |

## CI 管什么

`.github/workflows/ci.yml` 三个作业，挡住三类曾真实发生的回归：

| 作业 | 内容 | 挡住什么 |
|---|---|---|
| `go`（矩阵 ×4 模块） | `build` / `vet` / `test -cover` | 代码回归 |
| `docker` | 两镜像**根上下文**构建 + 冒烟跑 `/health` | 契约拆分后 Dockerfile 静默失效 |
| `docs` | `scripts/check-docs.sh`（事实校验）+ `scripts/check-mermaid.sh`（渲染校验） | 文档漂移：旧路径/裸引用/数字对不上/围栏嵌套/图渲染失败 |

本地等价执行：`bash scripts/check-docs.sh && bash scripts/check-mermaid.sh`（后者需 Docker）。

## Why "OceanVerse"?

In Greek mythology, all rivers and springs eventually flow into Oceanus,
the great river encircling the world. Data follows the same journey —
from scattered streams into one ocean of insight.

## License

MIT
