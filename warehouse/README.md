# warehouse 数仓层 —— 建模与加工

> 对应《OceanVerse 架构总览》§1.1 的计算层（实时 / 离线）与湖仓层（Lakehouse）。
> **本层职责**：把接进来的数据**加工成数仓分层表**（ODS→DWD→DWS→ADS），并定义这些表的口径。
>
> **边界（重要）**：**基础设施配置不在本层** —— ClickHouse 的内存上限、MinIO、Kafka、Flink 集群的编排都在 `deploy/`。
> 本层只放"建模与加工代码"：作业 SQL、结果表 DDL、口径说明。改名沿革：本层原为 `realtime/`，2026-09-20 更名（原因见下）。 <!-- check-docs:allow -->
>
> **为什么叫 warehouse 而不是 lakehouse**：《架构总览》里 **湖仓层 (Lakehouse) 已被定义为存储层**（Iceberg/Hudi + ClickHouse + MinIO + Metastore），
> 拿它命名"加工代码"会让人按层名对应错位；而 `warehouse/` 与今天的实际产出（`ads_*` 数仓分层表 + 建仓作业）匹配，
> 第 2 阶段的 Iceberg 双写与批处理分层照样装得下 —— 湖仓本就是这套数仓的实现形态。

---

## 1. 模块

| 模块 | 内容 | 状态 |
|---|---|---|
| `streaming/` | **流处理作业**（Flink SQL：在线数 / 故障数 / 高温电池）—— 口径唯一源在 `streaming/README.md` §2 | ✅ 第 1 阶段第 3 步 |
| `batch/` | **批处理分层**（ODS→DWD→DWS 转换、Iceberg 双写、CDC 落地） | ⏳ 第 2 阶段新增；现有内容**不需要迁移** |

## 2. 分层规约（第 2 阶段落地；当前只有 ADS 一层）

```
ODS   原始落地（第 2 阶段：Iceberg，真相源）
DWD   明细（清洗/规范化后的车辆·电池·故障事件）
DWS   汇总（车辆日健康、电池风险日）
ADS   应用（看板与 API 直接消费）        ← 今天的 ads_* 三张表就在这一层
DIM   维度（vehicle / user / battery / model / store / region）
```

- **命名**：`<层>_<主题>_<粒度>`，如 `ads_vehicle_online_1m`、`dwd_battery_status_event`。
- **湖仓定位**（能力域②）：**Iceberg/MinIO 是底座与真相源，ClickHouse 是 serving 加速层**。
  验收点：任何服务层的表都应能**从湖仓重建**（第 2 阶段的硬判据）。
- **口径纪律**：新指标先登记口径（第 2 阶段落到口径字典），再写作业 —— 当前的口径唯一源是 `streaming/README.md` §2。

## 3. 延伸阅读

- `streaming/README.md` —— 流处理作业手册：口径（唯一源）/ 四步跑起来 / 实测证据 / 运维 / 已知边界
- `../deploy/README.md` —— 基础设施：Flink profile、ClickHouse 内存上限、两个 runbook（Q17~Q19）
- `../roadmap/项目进度.md` —— 阶段进度与待收口项
