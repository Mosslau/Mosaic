# examples —— 湖仓与数据编排方向阶段完整示例

> 每个示例对应主文档 `23-lakehouse-orchestration.md` 相关小节（3.1~3.8）的完整可运行版。全部**纯 Java 17 标准库、零第三方依赖、默认包**，数据在代码内确定性自造，可离线复现。运行方式统一为「`javac` 编译到 /tmp + `java` 跑 Demo」，产物不落仓库。

| 文件（目录） | 说明（对应主文档小节） | 验证命令（进入各自目录） | 实测 |
|------|------|------------|------|
| `ex01-warehouse-layers/` | 四层建模与依赖方向纪律（反向依赖被拒）、口径唯一源校验、确定性拓扑序（3.1） | `javac -encoding UTF-8 -d /tmp/ph23-ex01 *.java && java -cp /tmp/ph23-ex01 WarehouseLayersDemo` | **7/7 PASS** |
| `ex02-table-snapshots/` | 快照链与 CAS 原子提交、时间旅行、增量读、schema 演进兼容性（3.2 / 4.1） | `javac -encoding UTF-8 -d /tmp/ph23-ex02 *.java && java -cp /tmp/ph23-ex02 TableSnapshotsDemo` | **8/8 PASS** |
| `ex03-partition-layout/` | 分区布局与裁剪、扫描字节估算、小文件分区检测（3.3） | `javac -encoding UTF-8 -d /tmp/ph23-ex03 *.java && java -cp /tmp/ph23-ex03 PartitionLayoutDemo` | **7/7 PASS** |
| `ex04-compaction/` | 小文件合并决策与读写放大测算、幂等 apply（3.4 / 4.2） | `javac -encoding UTF-8 -d /tmp/ph23-ex04 *.java && java -cp /tmp/ph23-ex04 CompactionDemo` | **7/7 PASS** |
| `ex05-batch-stream-unified/` | 同一口径批/流两种执行：水位线、迟到侧输出与补偿、幂等窗口覆盖（3.5 / 4.3） | `javac -encoding UTF-8 -d /tmp/ph23-ex05 *.java && java -cp /tmp/ph23-ex05 UnifiedPipelineDemo` | **7/7 PASS** |
| `ex06-orchestration-dag/` | DAG 确定性拓扑序、就绪判断、重试上限、失败阻塞下游、并发度（3.6） | `javac -encoding UTF-8 -d /tmp/ph23-ex06 *.java && java -cp /tmp/ph23-ex06 OrchestrationDemo` | **8/8 PASS** |
| `ex07-backfill-idempotent/` | 分区幂等回填、下游重算闭包、断点续跑、原因留痕（3.7 / 4.4） | `javac -encoding UTF-8 -d /tmp/ph23-ex07 *.java && java -cp /tmp/ph23-ex07 BackfillDemo` | **8/8 PASS** |
| `ex08-quality-lineage-cost/` | 质量门禁（fail-closed）、列级血缘、扫描/存储成本与 Prometheus 文本（3.8） | `javac -encoding UTF-8 -d /tmp/ph23-ex08 *.java && java -cp /tmp/ph23-ex08 QualityLineageCostDemo` | **9/9 PASS** |

## 验证说明

- **验证环境**：OpenJDK 17.0.18（Homebrew），无第三方依赖、无外部数据文件；每个 Demo 末尾打印 `ALL PASS: N/N`，出现 FAIL 时以非 0 退出码结束。
- **验证状态：已验证**（本机实测）：8 个示例全部 `javac` 编译通过 + `java` 运行全绿（断言数见上表，合计 **61 项**）；每份源码文件头的「验证状态」行与上表一致。
- **确定性**：全部示例不读系统时间与外部文件；需要时钟的地方显式传参（如 ex08 的 `nowMillis`）；窗口键用自实现日期换算，避免时区导致跨机差异；ex01 的拓扑序与 ex06 的调度顺序显式断言「两次运行相同」。
- **产物纪律**：编译产物一律写 `/tmp/ph23-exNN`，仓库内无 `.class`。
- **闭环式断言**：示例不只断言「函数返回值」，还断言**端到端事实**——如 ex04 的 `readSavedRatio`、ex05 的「批算 == 流算」、ex07 的「重算后下游值 == 按新上游重算的值」。

## 关键口径与简化（如实标注）

| 位置 | 主文档写的是 | 代码实际是 | 原因 |
|------|------------|-----------|------|
| ex02 时间旅行的「历史行数」 | 快照只记 `filesByPartition` | 用 `ROWS_PER_FILE = 1000` 把文件数换算为行数 | 元数据层只关心文件清单；行数是为了让断言可读，换算口径写在注释里 |
| ex03 `pruningRatio()` | 未规定入参 | 主口径 `pruningRatio(partition)`，另有按「最新分区」的无参重载 | 「裁剪比例」必须绑定一个查询谓词，否则含义不清 |
| ex04 `readSavedRatio` | 4.2 的「读代价 ≈ 打开文件数 + 扫描字节」 | `readCost = Σbytes + 打开文件数 × 4096B`，因此**字节不变也可能有正收益** | 小文件的主要代价是**打开次数**（元数据 + IO），不是字节量 |
| ex05 迟到数据 | 「丢弃或写入侧输出（补偿）」 | `stream()` 只计数 + 写侧输出；`compensate()` 才按同一份 `recomputeWindows` 整体覆盖并入 | 让「补偿」可重放、幂等；另附 `applyIncrementally` 对照，证明追加语义会重复计数 |
| ex06 编排器 | 「就绪 = 上游全部成功」 | 编排器在 `Dag.ready()` 之上再按本地状态过滤出 `PENDING` | 否则失败任务每轮都「就绪」→ 活锁（开发中实测到并修复） |
| ex07 回填任务顺序 | 未规定 | 闭包按**表拓扑序**输出（上游先于下游） | 按字典序会先跑 ADS 读到旧 DWS——顺序是正确性要求 |
| ex08 门禁短路 | 未规定 | 五类检查全部跑完**不短路**，任一类 FAIL 即拒绝提交 | 值班需要一次看到全部问题；fail-closed 保证坏数据不进表 |

## 与真实引擎的差距

示例用**确定性内存模型**表达湖仓语义（表格式 = 快照 + 清单 + 原子指针；执行 = 内存分区文件；编排 = 内存 DAG），**未接入**真实 Iceberg/Delta 目录布局、Spark/Flink 执行引擎、对象存储（S3/HDFS）与 Airflow/Dagster 部署——这些属基础设施工程，相关命令与形态见主文档第 5 章分工与 project/README 的「与真实生产形态的差距」清单。
