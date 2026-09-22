# ph23 阶段项目：最小湖仓与编排平台（lakeplat，Java 路线收官项目）

> 对应 roadmap §23 与主文档 [`23-lakehouse-orchestration.md`](../23-lakehouse-orchestration.md) 第 7 章「阶段项目」。
> 本项目是 Java 学习路线的**最后一个阶段项目**（roadmap 第 23 节即最后一节，无 ph24）：把 ph01~ph22 的机制
> （record / sealed 语义、枚举纪律、Map 幂等覆盖、确定性拓扑排序、纯函数算子、文本指标）
> 组织成**一个纯 Java、可 `javac` 编译、可离线自检的模块集**。
>
> 主文档的三条边界在这里被严格遵守：**不碰真实引擎的分布式执行**（Spark/Flink 的 shuffle、反压、调度器内核——
> 本项目用**确定性内存模型**模拟「一次执行产出哪些分区文件」）、**不碰对象存储与集群运维**（S3/HDFS、K8s、
> Iceberg/Delta 的真实目录布局——只把表格式的**心智**建模清楚）、**不碰数据建模方法论**（维度建模与指标业务定义）。
> 所有数据在代码内确定性自造（固定逻辑时钟 `T0 = 2024-06-01T00:00:00Z`），无第三方依赖、无外部文件、无外部进程。

## 需求

主文档第 7 章给出的闭环是：**四层建表与口径校验 → 写入产生快照（原子提交）→ 分区布局与裁剪成本估算
→ 小文件检测与 compaction 决策 → 批/流同口径执行（水位线 + 迟到侧输出）→ DAG 编排与失败传播
→ 幂等回填与下游重算 → 质量门禁 + 列级血缘 + 成本一屏**。本项目把它落成一条端到端流水线，
每个模块 = 一个限界上下文：

```text
                     ┌──────────────────────── LakePlatform（湖仓门面，固定逻辑时钟）────────────────────────┐
  建表 + 声明依赖     │ WarehouseModel：ODS/DWD/DWS/ADS 层级纪律（反向依赖抛错）+ 指标口径唯一源（只在 DWS）    │
  ─────────────────▶ │  分层：ods_event_raw → dwd_trip_detail → dws_metrics_* → ads_dashboard_daily          │
                     │                                                                                     │
  写入（分区整体覆盖）│ TableFormat：不可变 Snapshot（清单 + parent 链）──CAS 提交──▶ current 指针原子前进       │
  ─────────────────▶ │   ├─ timeTravel(ts)      沿父链回溯 → 读历史行数（不需要副本）                        │
                     │   ├─ incremental(since)  比较清单差异 → 只返回变化分区（元数据判据，不是时间戳）       │
                     │   └─ SchemaEvolution     加列兼容；删列/改类型在**提交阶段**被拒（fail-fast）          │
                     │                                                                                     │
  查询（带分区谓词）  │ PartitionLayout：分区裁剪 → ScanCost（打开文件数 / 扫描字节 / 裁剪比例）              │
  ─────────────────▶ │ Compaction：小文件检测（文件数 > 阈值 且 平均 < 目标）→ Plan（读收益 / 写放大）        │
                     │   └─ apply 幂等：`part-<序号>` 规范命名整体重建分区，重复 apply 产出同一份清单        │
                     │                                                                                     │
  批 / 流同一口径     │ Pipeline：同一份过滤 + 聚合，两种执行                                                 │
  ─────────────────▶ │   ├─ batch(events)          按窗口整体覆盖（幂等写 = exactly-once 效果）               │
                     │   ├─ stream(events, 水位线) watermark = max(evTs) - allowedLateness                    │
                     │   │     evTs <= watermark → 迟到：写**侧输出**（补偿任务按更宽水位线重算），不丢       │
                     │   └─ assertParity           批算与流算同一窗口必须同值（运行时校验，不是口头承诺）    │
                     │                                                                                     │
  编排 DAG           │ Dag：确定性拓扑序（同层按 id）+ 就绪 = 上游**全部**成功                              │
  ─────────────────▶ │ Orchestrator：并发度限制真正的槽位；重试上限内先失败后成功；耗尽 → FAILED 并阻塞下游   │
                     │   └─ 下游被 BLOCKED（不是 SUCCEEDED「跳过」）——静默缺口比显式失败贵得多              │
                     │                                                                                     │
  幂等回填           │ Backfill：plan = 依赖图闭包 + 分区粒度对齐（ODS 月分区不会被 DWD 天分区带动）         │
  ─────────────────▶ │   ├─ 分区整体覆盖（不追加、不 upsert）→ 重复执行结果逐字节一致                        │
                     │   ├─ 下游 DWS/ADS 同分区重算（否则新旧口径混用且无人能发现）                          │
                     │   ├─ resume：已成功分区跳过（断点续跑只补缺口）                                       │
                     │   └─ ReasonLog：每次回填留痕「重算了哪些分区、跳过哪些、为什么」                      │
                     │                                                                                     │
  治理               │ QualityGate：非空/唯一/量程/行数波动/鲜度五类；任一 FAIL → **不提交**（fail-closed）   │
  ─────────────────▶ │ Lineage：列级血缘，sourcesOf 回溯到 ODS、impactOf 给出变更影响闭包                     │
                     │ OpsConsole：表/快照/成本/编排/治理五块一屏 + `lake_` 前缀 Prometheus 文本（同源一致）  │
                     └─────────────────────────────────────────────────────────────────────────────────────┘
```

图中箭头即「控制面只做决策与台账，执行体只做计算」这条契约：**表的当前状态由元数据决定，而不是目录**。
把门的 `CommitResult`、窗口的 `WindowResult`、编排的 `Round`、回填的 `RunResult` 都是纯数据 record，
换成真实引擎后控制面语义不变。

## 模块清单

| 类 | 职责 | 对应主文档小节 |
|----|------|----------------|
| `Layer` | 四层枚举：层级序号即依赖方向纪律（`canReadFrom`）+ 每层允许的数据形态 | 3.1 |
| `TableRef` | 表的不可变引用（表名 + 层）+ 层前缀解析；天然有序，保证各处遍历确定性 | 3.1 |
| `WarehouseModel` | 建表、依赖方向校验（反向依赖抛可读异常）、指标口径唯一源（只在 DWS）、下游重算闭包 | 3.1 / 3.7 |
| `Schema` | 列式 schema（有序 map）+ 加列/删列/改类型操作（供兼容性校验） | 3.2 |
| `Snapshot` | 不可变快照：id / parentId / ts / operation / schema / 清单（分区 → 文件） | 3.2 / 4.1 |
| `SchemaEvolution` | 兼容性规则：加列安全；删列/改类型列出「哪列、什么变更、为什么不兼容」并拒绝 | 3.2 |
| `TableFormat` | 表格式：CAS 原子提交、时间旅行、增量读、分区覆盖清单构造、文件路径确定性生成 | 3.2 / 4.1 |
| `DataFile` | 数据文件（路径 / 分区 / 行数 / 字节）——扫描成本的最小单位 | 3.3 |
| `PartitionLayout` | 分区裁剪、扫描字节估算 `ScanCost`、小文件检测阈值 `SmallFileFlag` | 3.3 |
| `Compaction` | 合并到目标大小、收益测算（`readSavedRatio` / `writeAmplification`）、幂等 apply | 3.4 / 4.2 |
| `Event` / `Window` | 事件（事件时间 + 维度）与定长窗口；窗口键用 `civil_from_days` 确定性生成，无时区依赖 | 3.5 |
| `Pipeline` | 批流一体：同一聚合逻辑两种执行、水位线推进、迟到写侧输出、窗口幂等覆盖、`assertParity` | 3.5 / 4.3 |
| `TaskNode` | DAG 节点：依赖 + 重试上限 + 产出的表 | 3.6 |
| `Dag` | 确定性拓扑序（Kahn + 同层按 id）、就绪判断（上游全部成功）、失败传递闭包与「被谁阻塞」 | 3.6 |
| `Orchestrator` | 按轮推进：并发度槽位、重试上限、耗尽后 FAILED 并**阻塞**下游、执行日志 | 3.6 |
| `BackfillTask` | 回填工作项（表 + 分区 + 原因）+ 状态枚举（原因留痕是硬要求） | 3.7 |
| `Backfill` | 计划 = 依赖闭包 + 分区粒度对齐；分区整体覆盖；纯函数口径；断点续跑；`ReasonLog` | 3.7 / 4.4 |
| `QualityGate` | 五类门禁（非空/唯一/量程/行数波动/鲜度）+ `Verdict`（fail-closed，失败不放行） | 3.8 |
| `Lineage` | 列级血缘推导、`sourcesOf` 回溯到 ODS、`impactOf` 影响闭包、孤儿列自检 | 3.8 |
| `CostReport` | 成本快照：扫描量 / 存储量 / 文件数 / 小文件分区数 / compaction 收益（不发明数字，只汇总） | 3.8 |
| `OpsConsole` | 运维一屏（表/快照/成本/编排/治理）+ Prometheus 文本（`lake_` 前缀，与一屏同源） | 3.8 |
| `LakePlatform` | 门面：持有各域、转发调用、把状态投影成只读读数，并提供 `invariantsHold()` 自检 | 第 7 章「阶段项目」 |
| `LakePlatformDemo` | 端到端演示 + 14 项验收断言（输出即验收报告） | 阶段验收清单 |

## 目录结构

```text
project/
├── README.md
├── Makefile                       # 可选：make / make run / make clean（产物只落 /tmp）
└── src/lakeplat/
    ├── LakePlatformDemo.java      # 端到端闭环 + 14 项断言（14 行 PASS）
    ├── LakePlatform.java          # 湖仓门面 + 固定逻辑时钟 + 全平台读数
    ├── Layer.java                 # 四层枚举（序号即依赖纪律）
    ├── TableRef.java              # 表引用（表名 + 层）
    ├── WarehouseModel.java        # 分层依赖 + 口径唯一源 + 下游闭包
    ├── Schema.java                # 列式 schema
    ├── SchemaEvolution.java       # schema 兼容性校验（fail-fast）
    ├── Snapshot.java              # 不可变快照（清单 + 父链）
    ├── TableFormat.java           # CAS 提交 / 时间旅行 / 增量读
    ├── DataFile.java              # 数据文件
    ├── PartitionLayout.java       # 分区裁剪 + 扫描成本 + 小文件检测
    ├── Compaction.java            # 合并决策 + 收益测算 + 幂等 apply
    ├── Event.java                 # 事件（事件时间）
    ├── Window.java                # 定长窗口 + 确定性日期键
    ├── Pipeline.java              # 批流一体 + 水位线 + 迟到侧输出
    ├── TaskNode.java              # DAG 节点
    ├── Dag.java                   # 拓扑序 + 就绪 + 失败传播
    ├── Orchestrator.java          # 编排器（并发度 / 重试 / 阻塞下游）
    ├── BackfillTask.java          # 回填工作项 + 原因
    ├── Backfill.java              # 幂等回填 + 下游传播 + 断点续跑 + 留痕
    ├── QualityGate.java           # 五类门禁（fail-closed）
    ├── Lineage.java               # 列级血缘
    ├── CostReport.java            # 成本快照
    └── OpsConsole.java            # 运维一屏 + Prometheus 文本
```

## 构建与运行（已验证）

验证环境：**OpenJDK 17.0.18（Homebrew）**；零第三方依赖；构建产物只写到 `/tmp`。

```bash
# 在 languages/java/ph23-lakehouse-orchestration/project/ 目录执行
javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java     # 1. 编译
java -cp /tmp/ph23-proj lakeplat.LakePlatformDemo               # 2. 运行（输出即验收报告）
rm -rf /tmp/ph23-proj                                           # 3. 清理
```

## 验收标准

### 命令与实测结果

```console
$ javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java && java -cp /tmp/ph23-proj lakeplat.LakePlatformDemo
== 最小湖仓与编排平台（lakeplat）闭环演示：分层→快照→布局→治理→批流→编排→回填→门禁 ==
PASS 四层依赖：5 张表 / 3 条合法依赖（ODS→DWD→DWS→ADS），DWD 下游闭包含 DWS+ADS；DWD 读 ADS 被拒 → 反向依赖被拒：dwd_trip_detail[DWD] 读 ads_dashboard_daily[ADS] 违反分层纪律（ADS.ordinal=3 > DWD.ordinal=1，数据只能从上游流向下游）
PASS 口径唯一源：instances_daily_active 归属 dws_metrics_instance_day；DWD 声明被拒（口径唯一源被破坏：指标 instances_daily_active 声明在 dwd_trip_detail[DWD]，但只允许声明在 DWS 层（下游 ADS 只做展示态加工，上游 DWD 不做业务解释））；ADS 声明被拒（口径唯一源被破坏：指标 instances_daily_active 声明在 ads_dashboard_daily[ADS]，但只允许声明在 DWS 层（下游 ADS 只做展示态加工，上游 DWD 不做业务解释））
PASS 快照链：CREATE #1000 → #1001 → #1002 父链连续，current 前进到 #1002；用过期父快照 #1000 提交被拒（CAS 冲突：期望父快照 #1000 但当前已是 #1002（乐观提交失败，表保持原快照，请重读后重试）），3 次提交尝试后指针仍指向 #1002
PASS 时间旅行：在 ts=T0+2500ms 读到快照 #1001（11600 行），而 current #1002 已是 13500 行——读旧数据只沿父链回溯，不需要副本
PASS 增量读：自快照 #1001 以来变化分区 = [event_date=2024-06-02, event_date=2024-06-03]（06-01 未变化 + 后续 schema 变更不含数据 → 下游不必重扫，判据是快照元数据而不是时间戳）
PASS schema 演进：删列 instance_id 在提交阶段被拒（schema 变更不兼容，提交被拒：[列 instance_id 删除：删列后历史文件读不出该列，下游类型断言会崩（DROP COLUMN 需显式确认）]（兼容变更只有「加列」；删列/改类型需显式确认）），快照停在 #1002；加列 device_model 兼容并提交成功 → #1003（旧快照仍能读出 instance_id）
PASS 分区裁剪：扫描 8/13 个文件、3328000/5616000 字节（裁剪 40.7%）——只命中 06-01 的 8 个文件（全表 13 个），扫描量下降 40.7%（分区键匹配查询谓词才有收益，scanBytes 就是这次查询要付的钱）
PASS 小文件治理：检出 event_date=2024-06-01 文件 8 个 / 平均 416000B（文件数 8 > 4 且平均 416000B < 目标 524288B）；合并方案 event_date=2024-06-01 文件 8→4，读收益 50.0%，写放大 1.00x（字节守恒 5616000B）；重复 apply 幂等——第二次产出 0 个新文件，清单仍 4 个文件，重规划已无可合并分区（读多写少才值得合）
PASS 批流同口径：窗口 2024-06-01 同口径批算 7 行/sum=221，流算 7 行/sum=221（assertParity 通过）；含迟到事件的历史全量批算是 8 行/sum=320，另一窗口 2024-06-02 为 4 行——同一份过滤+聚合逻辑、同一事件时间、同一幂等写，批与流得出同一组数
PASS 迟到侧输出：水位线 1717368900000，接受 11 条，迟到 1 条 → 侧输出 [evt-0009（窗口 2024-06-01，迟到 123900000ms）]（迟到 123900000ms）；整条流重放后结果与侧输出逐字节一致，窗口内事件 11 条不重复计数（批流一体的最后一块拼图）
PASS 编排拓扑与重试：两次构造拓扑序相同 [ods_ingest, dwd_clean, dwd_dedup, dwd_dim, dws_metrics, ads_dashboard, ads_export]；dwd_dedup 已成功而 dwd_dim 未成功时 dws_metrics 不就绪（上游必须全部成功），就绪集 = [dwd_dim]；dws_metrics 尝试记录 [1:FAILED, 2:SUCCEEDED] → 整图 成功 7/7，永久失败 []，阻塞 []
PASS 失败传播：ads_dashboard 尝试记录 [1:FAILED, 2:FAILED, 3:FAILED]（重试上限 2 次）→ 永久失败；下游 [ads_export] 被**阻塞**而非跳过（重试 2 次耗尽（共 3 次尝试），任务失败并阻塞下游），显式暴露缺口，成功 5/7 个节点
PASS 幂等回填：重算 [dwd_trip_detail/2024-06-01, dws_metrics_instance_day/2024-06-01, ads_dashboard_daily/2024-06-01]（下游 [ads_dashboard_daily, dws_metrics_instance_day]，不含粒度不对齐的 ODS 月分区）；第二次执行 0 个新分区且全量状态摘要与第一次逐字节相同；ADS 读数 9586 → 10800 证明闭包被真正重算；断点续跑跳过已成功的 3 个分区；原因留痕 4 条（@1717200005000 dwd_trip_detail/2024-06-01 —— 上游修数：源系统补回 1214 条被隐藏的记录（重算 3 个分区，跳过 0） … @1717200005400 dwd_trip_detail/2024-06-02 —— 故障补偿：06-02 批次缺 3 个分区文件（重算 0 个分区，跳过 0））
     （fail-closed：门禁拒绝 → 跳过提交，表保持快照 #1004）
+---------------------------- 湖仓与编排运维一屏 ----------------------------+
  [表] 5 张表 / 5 个分区 / 12 个文件 / 存储 13712000B
  [快照] current=#1001 / 共 2 个快照 / CAS 提交尝试 6 次 | 最近增量读 2 个分区 / 时间旅行 11600 行
  [成本] 扫描 3328000/5616000 字节（裁剪 40.7%）| 小文件分区 0 个 | compaction 方案 0 个（读收益 0.0%）
  [编排] DAG 7 节点：成功 5 / 失败 1 / 阻塞 1 | 回填 6 个分区（跳过 6）/ 留痕 4 条
  [治理] 门禁 拒绝（3/5 项失败） | 列级血缘 11 列（ODS 源列 4）
        ods_event_raw [ODS] 分区 1 / 文件 1 / 存储 7680000B / 小文件分区 0
        dwd_trip_detail [DWD] 分区 4 / 文件 11 / 存储 6032000B / 小文件分区 0
        dws_metrics_instance_day [DWS] 分区 0 / 文件 0 / 存储 0B / 小文件分区 0
        dws_metrics_instance_week [DWS] 分区 0 / 文件 0 / 存储 0B / 小文件分区 0
        ads_dashboard_daily [ADS] 分区 0 / 文件 0 / 存储 0B / 小文件分区 0
+---------------------------------------------------------------------------+
PASS 门禁/血缘/成本：坏批次 [NOT_NULL, UNIQUE, RANGE] 项失败 → 门禁失败 3 项 → fail-closed：本次提交被拒，表保持上一个快照，表停在快照 #1004（行数与 schema 原样，坏数据根本没进表），门禁通过的那批才提交 → #1005；ADS.value 可回溯到 ODS 列 [ods_event_raw.event_id]，改 ODS.region 的影响闭包是 [dwd_trip_detail.region, ods_event_raw.region]（变更评审的最小单位）；一屏 [表/快照/成本/编排/治理] 五块齐全，Prometheus 文本与快照逐项一致（storage=13712000B / files=12 / scan=3328000B）
ALL PASS: 14/14
```

- **14 行 `PASS`、0 行 `FAIL`，末行 `ALL PASS: 14/14`**；任何一项失败都会打印 `FAIL` 并以 `System.exit(1)` 结束（可直接接 CI）。
- 输出**逐字节可复现**：连续两次运行 `diff` 为空（固定逻辑时钟 `T0`，窗口键用 `civil_from_days` 自算而不经过系统时区，
  指标里的浮点比值统一按三位小数输出，不读系统时间、不读外部文件、不依赖 HashMap 迭代序）。
- 「一屏」里 `[快照] current=#1001` 指向的是**第一张表**（ODS）的快照，所以是 #1001/2 个快照；
  断言使用的 DWD 表当前是 #1005（可在 `/tmp` 之外用 `LakePlatform.snapshots()` 查看全部表的父链）。

### 14 项断言覆盖的语义

| # | 断言 | 覆盖语义（主文档小节） |
|---|------|------------------------|
| 1 | 四层依赖合法、下游闭包正确；DWD 读 ADS 的反向依赖被拒 | 依赖方向即纪律（3.1） |
| 2 | 口径只有写在 DWS 才被接受，DWD/ADS 声明同一指标均被拒 | 口径唯一源（3.1） |
| 3 | 快照父链连续、CAS 提交后 current 前进、过期父快照提交被拒 | 快照 + 清单 + 原子指针替换（3.2/4.1） |
| 4 | 时间旅行按 ts 读到历史快照与历史行数 | 时间旅行免费（3.2） |
| 5 | 增量读只返回变化分区（未变化分区不进结果） | 增量读靠元数据序列（3.2） |
| 6 | 删列在提交阶段被拒且指针不动；加列兼容并成功提交 | schema 演进 fail-fast（3.2） |
| 7 | 分区裁剪使扫描字节从 5616000 降到 3328000（−40.7%） | 分区裁剪与扫描成本（3.3） |
| 8 | 小文件分区被检出；合并 8→4 文件、读收益 50%、写放大 1.00x；重复 apply 幂等且字节守恒 | compaction 读写放大权衡（3.4/4.2） |
| 9 | 批算与流算同一窗口同值（`assertParity` 通过），另一窗口同样一致 | 批流一体 = 语义一致（3.5/4.3） |
| 10 | 迟到事件进侧输出（不丢、不错算），整条流重放后结果与侧输出逐字节一致 | 水位线 + 侧输出 + 幂等窗口覆盖（3.5） |
| 11 | 拓扑序两次构造相同；上游未全部成功时下游不就绪；重试第 1 次失败、第 2 次成功 | 确定性拓扑 + 就绪条件 + 重试上限（3.6） |
| 12 | 重试耗尽后 FAILED，下游被 BLOCKED（不是跳过），失败原因可读 | 失败传播：阻塞而非跳过（3.6） |
| 13 | 重复回填结果逐字节一致、下游闭包被真正重算、断点续跑只补缺口、原因留痕 | 幂等回填 + 下游传播 + 断点 + 留痕（3.7/4.4） |
| 14 | 门禁失败不提交（快照/行数/schema 原样）；血缘回溯到 ODS；一屏与 Prometheus 文本同源一致 | 门禁 fail-closed + 列级血缘 + 成本一屏（3.8） |

## 运行手册

1. **看闭环是否健康**：`java -cp /tmp/ph23-proj lakeplat.LakePlatformDemo`，只看末行 `ALL PASS: 14/14`；
   `LakePlatform.invariantsHold()` 会在每次断言里被调用，它同时校验「所有表父链连续」与「所有依赖都满足分层方向」。
2. **看某次查询要付多少钱**：拿 `PartitionLayout.ScanCost`——`files()/fullFiles()` 是打开文件数，
   `bytes()/fullBytes()` 是扫描字节，`pruneRatio()` 是裁剪收益。这就是按扫描量计费引擎的账单口径（3.3）。
3. **看某个分区该不该合并**：`PartitionLayout.detectSmallFilePartitions(files)` 给阈值命中原因，
   `Compaction.plan(partition, files)` 给 `readSavedRatio`（读收益）与 `writeAmplification`（写代价）。
   **判据是未来的读次数，不是文件多不多**（4.2）。
4. **看一次提交为什么被拒**：`TableFormat.CommitResult.message()`（CAS 冲突）与
   `SchemaEvolution.check` 抛出的异常文本（哪个列、什么变更、为什么不兼容）都可直接展示给变更评审。
5. **看某个窗口批流为什么对不上**：`Pipeline.assertParity(batchResults)` 抛出时会同时打印批算与流算的
   `count/sum`；`Pipeline.sideOutput()` 是迟到事件清单，`Pipeline.windowEvents()` 是窗口内事件日志
   （同一个 `eventId` 只占一个槽位，这就是重放不重复计数的证据）。
6. **看任务为什么阻塞**：`Orchestrator.blockedTasks()` / `blockedBy(taskId)` / `failureReason(taskId)`，
   以及 `Orchestrator.executionLog()` 里逐次 `(taskId, attempt, outcome)` —— 编排决策可完整复盘（3.6）。
7. **看回填做了/跳过了什么**：`Backfill.reasonLog()` 每次回填一条，含 `recalculated` 与 `skipped` 两份清单与
   `reason`（上游修数/规则变更/故障补偿）；`Backfill.appliedKeys()` 是断点续跑的依据（3.7）。
8. **接指标系统**：`OpsConsole.prometheusText()` 输出 `lake_tables_total` / `lake_partitions_total` /
   `lake_files_total` / `lake_storage_bytes` / `lake_snapshot_current_id` / `lake_snapshots_total` /
   `lake_commit_attempts_total` / `lake_incremental_partitions` / `lake_scan_bytes` / `lake_scan_bytes_full` /
   `lake_scan_saved_ratio` / `lake_small_file_partitions` / `lake_compaction_plans` /
   `lake_compaction_read_saved_ratio` / `lake_quality_gate_failed_checks` / `lake_dag_nodes` /
   `lake_dag_tasks{state}` / `lake_backfill_partitions_total{result}` / `lake_backfill_reason_logs` /
   `lake_lineage_columns` / `lake_lineage_ods_source_columns` / `lake_table_{storage_bytes,files,partitions}{table,layer}`，
   把它挂到一个 HTTP `/metrics` 即可被 Prometheus 抓取。

## 与真实生产形态的差距（诚实清单）

| 本项目 | 生产形态 | 说明 |
|--------|----------|------|
| `TableFormat` 是单 JVM 内存对象，CAS 是进程内乐观检查 | Iceberg/Delta/Hudi + 对象存储（元数据目录 + 原子 rename/条件 PUT） | 复刻「快照 + 清单 + 原子指针替换」的**语义**；真实并发提交需要 catalog 层的锁或条件写，本项目只做单写者模型 |
| 清单里 `DataFile` 只有 (路径, 分区, 行数, 字节) | Parquet/ORC 文件 + 列级统计（min/max/null 计数）| 真实裁剪还有「块级跳过」（3.3 表格最后一行）；本项目只演示分区级裁剪，字节数是估算值而非实测 |
| `Compaction` 只按大小贪心合并 | 按文件血缘做增量合并、按查询频率决定优先级、与写入并发协调 | 语义复刻（决策 + 收益测算 + 幂等）；真实 compaction 还要处理快照过期与元数据膨胀（4.1） |
| 批流是同一个进程里的两次调用 | Spark Structured Streaming / Flink 作业 + 检查点存储 + 状态后端 | 复刻「同口径 + 水位线 + 幂等覆盖」；真实执行的反压、shuffle、checkpoint 属引擎内核（主文档「不涉及」） |
| 侧输出只是内存里的迟到清单 | 侧输出表 + 补偿作业（按更宽水位线重算窗口） | 复刻「迟到不丢」的路径；补偿作业的调度仍是 DAG，可直接复用本项目 `Dag`/`Orchestrator` |
| `Orchestrator` 单轮同步推进，无持久化 | Airflow/Dagster 的调度器 + 元数据库 + 分布式 worker | 复刻就绪/重试/失败传播/并发度四项语义；选主、任务队列、SLA 告警属基础设施 |
| 回填状态在内存 map 里 | 回填任务表 + 分区级状态持久化 | 复刻「幂等 + 传播闭包 + 断点 + 留痕」；真实断点需要把 `appliedKeys` 落库 |
| 门禁读的是内存 `Row` | Great Expectations 类框架 + SQL 校验 + 采样 | 复刻五类检查与 fail-closed 裁决；真实规则库、异常基线与告警通道属治理平台 |
| `Lineage` 由调用方显式登记边 | SQL 解析（`sqlglot` 类）自动推导列级血缘 | 本项目证明了「列级回溯与影响闭包」的算法与价值，没有做 SQL 解析 |
| 服务发现 / 权限 / 审计未涉及 | DataHub/OpenMetadata + 列级权限 + DLP | 主文档 3.8 第四行「目录与权限」只给形态，本项目只做门禁/血缘/成本三件事 |
| 逻辑时钟（`T0` 常量）| 真实 UTC 时钟与事件时间 | 为了让输出逐字节可复现；生产要注意时钟漂移与事件时间/处理时间之分（3.5） |

## 扩展方向

- **接真实表格式（Iceberg/Delta）**：把 `TableFormat` 换成 Iceberg `Catalog` + `Snapshot`/`ManifestFile` API，
  `Snapshot.manifest` 映射成 manifest 列表；`SchemaEvolution` 映射成 Iceberg 的 `UpdateSchema` 兼容性检查
  （加列安全、删列需 `allowIncompatibleChanges`）。控制面其余部分（`WarehouseModel`/`Compaction`/`Backfill`）不用改。
- **接真实引擎（Spark/Flink）**：`Pipeline.batch/stream` 换成 Spark Structured Streaming 的
  `foreachBatch` + `checkpointLocation`；`Pipeline` 的口径（过滤 + 窗口聚合）落成一段共享 SQL/DataFrame 逻辑，
  `assertParity` 变成每日批流对账任务（同一窗口比 count/sum）。
- **接真实调度器（Airflow/Dagster）**：`Dag` 导出成 DAG 定义（任务 id → `dependencies`），
  `Orchestrator` 的 `Round`/`TaskRun` 映射成 task instance 状态；失败阻塞下游即 `trigger_rule=all_success`（默认），
  不要改成 `all_done` 或 `none_failed_min_one_success`——那正是「跳过下游」的静默缺口来源（3.6）。
- **接对象存储**：`TableFormat.filePath` 换成真实对象键，`Compaction` 用多线程/分布式重写分区文件，
  并补上快照过期清理（保留 N 个快照 / N 天）——这是 4.1 明确的元数据膨胀代价。
- **接血缘推导**：用 SQL 解析器从 DWD/DWS/ADS 的建表语句自动生成 `Lineage.Edge`，替换 `demo` 里的显式登记；
  再把 `impactOf` 接进 CI（改上游列 → 自动列出受影响的下游列与看板），这就是变更评审的最小单位。
- **接治理平台**：`QualityGate` 的规则从 `Policy` record 换成规则库（按表/按列配置），
  `Lineage` 与 `CostReport` 推给 DataHub/OpenMetadata 类目录，`lake_` 指标接 Grafana 做「成本一屏」。
- **更丰富的分区建模**：`WarehouseModel` 目前一个表一个分区键；生产常见「实体 + 日期」二级分区，
  可把 `partitionKey` 换成有序列表，`PartitionLayout` 的裁剪谓词变成多列组合，并补上「分区爆炸」的元数据压力度量（3.3）。
- **多写者并发提交**：把 `TableFormat.commit` 的进程内 CAS 换成 catalog 层的条件提交
  （真实 Iceberg 用 `commit.retry.num-retries` + 元数据指针条件写），并补上「提交冲突率」指标，
  这会让断言 3 从「内存乐观检查」升级为「跨进程真实并发」。
