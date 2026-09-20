# lakehouse 湖仓层 —— 建模与加工的落点

> 对应《OceanVerse 架构总览》§1.1 的**湖仓层 (Lakehouse)** 与计算层。
> **本层职责**：把接进来的数据**按数仓分层建起来**（ODS→DWD→DWS→ADS），并定义这些表的口径。
>
> **边界（重要）**：**存储组件的配置不在这里** —— ClickHouse 的内存上限、MinIO、Kafka、Flink 集群的编排都在
> `deploy/`。本层只放"建模与加工代码"：作业 SQL、表 DDL、口径说明。
>
> **命名沿革**：`realtime/` → `warehouse/streaming/` → 现结构 `lakehouse/warehouse/streaming/`（2026-09-20 两次调整）。 <!-- check-docs:allow -->
> 旧名 `realtime` 描述的是"性质"、且第 2 阶段批处理进来后会名不副实；现在三层各司其职：
> **`lakehouse`=层 · `warehouse`=数仓建模与加工 · `streaming`=模块**。
> 旧路径 `realtime/` 已进 `check-docs.sh` 的禁用词（漏改当场变红）。 <!-- check-docs:allow -->

---

## 1. 湖仓定位（对应能力域②存储底座）

| 要素 | 本项目落点 | 说明 |
|---|---|---|
| 开放表格式 | **Iceberg**（第 2 阶段入链路） | 底座与**真相源**，防厂商锁定 |
| 对象存储 | **MinIO**（已就位） | 廉价、弹性；真相源的物理承载 |
| serving 加速层 | **ClickHouse**（第 1 阶段已在用） | 面向查询的高性能层，**不是**真相源 |

**关键认知**：湖（Iceberg）是底座与真相源，OLAP 引擎（ClickHouse）是 serving 加速层 —— 两者是分工，不是竞品。
**验收点（第 2 阶段硬判据）**：任何服务层的表都应能**从湖仓重建**。

> 今天的现实：只有 ClickHouse serving 层在产（三个 ADS 表），Iceberg 尚未入链路 —— 第 2 阶段做 Flink 双写。

## 2. 目录

```
lakehouse/                            ← 本层
├── README.md                         #   本文件：湖仓定位 / 与 deploy 的边界 / 索引
└── warehouse/                        #   数仓：建模与加工（手册见 warehouse/README.md：分层规约与命名）
    └── streaming/                    #     模块：流处理（Flink SQL 三作业）
        ├── README.md                 #       口径唯一源 + 跑 / 验 / 运维 / 已知边界
        ├── sql/                      #       源表 + 三个 sink + 三个作业
        ├── clickhouse/init.sql       #       结果表 DDL（Kafka 引擎表 + 物化视图 + ADS 表）
        ├── conf/                     #       提交容器客户端配置
        └── submit-jobs.sh            #       提交脚本
（第 2 阶段：warehouse/batch/ —— 批处理分层转换、Iceberg 双写、CDC）
```

## 3. 延伸阅读

- `warehouse/README.md` —— 数仓分层规约（ODS→DWD→DWS→ADS）与命名
- `warehouse/streaming/README.md` —— 流处理模块手册：口径 / 四步跑起来 / 实测证据 / 运维 / 6 条已知边界
- `../deploy/README.md` —— 基础设施：Flink profile、ClickHouse 内存上限、Q17~Q19 runbook
- `../roadmap/项目进度.md` —— 阶段进度与待收口项
