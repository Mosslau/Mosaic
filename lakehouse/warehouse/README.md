# warehouse 数仓 —— 建模与加工

> 上位：`../README.md`（湖仓层：定位与边界）。
> **本部分职责**：定义**分层与命名规约**，并索引各加工模块（今天只有流处理）。

---

## 1. 分层规约（第 2 阶段落地；当前只有 ADS 一层在产）

```
ODS   原始落地（第 2 阶段：Iceberg，真相源）
DWD   明细（清洗 / 规范化后的车辆·电池·故障事件）
DWS   汇总（车辆日健康、电池风险日）
ADS   应用（看板与 API 直接消费）      ← 今天的 ads_* 三张表就在这一层
DIM   维度（vehicle / user / battery / model / store / region）
```

- **命名**：`<层>_<主题>_<粒度>` —— 如 `ads_vehicle_online_1m`、`dwd_battery_status_event`。
- **粒度后缀**：`_1m` 表示 1 分钟窗口；`_day` 表示日粒度。
- **真相源纪律**：ADS/DWS 都是**派生**的，必须能从 ODS（第 2 阶段 = Iceberg）重建；不允许只有 serving 层才有数据。

## 2. 模块

| 模块 | 内容 | 状态 |
|---|---|---|
| `streaming/` | **流处理**：Flink SQL 三作业（在线数 / 故障数 / 高温电池）→ ClickHouse ADS 表 | ✅ 第 1 阶段第 3 步 |
| `batch/` | **批处理分层**：ODS→DWD→DWS 转换、Iceberg 双写、CDC 落地 | ⏳ 第 2 阶段新增；现有内容**不需要迁移** |

## 3. 口径纪律

- **新指标先登记口径，再写作业**（第 2 阶段落到"指标口径字典"；今天的最小子集就是 §2 那张表）。
- **口径唯一源**：当前在 `streaming/README.md` §2（三个指标各一段精确表述 + 三条全局口径）。
  口径与实现分处三处（README / `streaming/sql/00-common.sql` / `streaming/clickhouse/init.sql`），
  改一处必须同步另两处 —— `scripts/check-docs.sh` 的检查⑨ 会核对表名与 topic 是否三处一致。
