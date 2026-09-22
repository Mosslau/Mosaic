# ph23 湖仓与数据编排方向 Java 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> **与主文档「动手练习」的对应**：四题一一对应 [`23-lakehouse-orchestration.md`](../23-lakehouse-orchestration.md) 第 7 章列出的四个练习——练习 1 = 分层建模与口径对账（3.1）、练习 2 = 快照与增量读（3.2）、练习 3 = DAG 编排与幂等回填（3.6/3.7）、练习 4 = 质量门禁与列级血缘（3.8）。
> **验证纪律**：四题均为纯 Java 17（标准库、零依赖、默认包、无 lint 配置），用本机 OpenJDK 17.0.18 实测，四题入口全部 `ALL PASS`。

## 依赖与验证方式

- **依赖**：仅 JDK 17 标准库（record / sealed interface / switch 表达式 / 并发集合 / `AtomicReference`），无 Maven/Gradle 依赖，无第三方 jar，无 Spark/Flink/Iceberg/Kafka/S3。全部为**确定性内存模型**（无随机、无网络；唯一的并发出现在 sol-02 的 CAS 提交，且其断言不依赖线程调度顺序）。
- **编译运行命令**（每题独立 `javac *.java`，输出目录用 `/tmp`，不产生仓库内构建产物）：

```bash
JAVAC=javac   # 本机：OpenJDK 17.0.18 (Homebrew)
JAVA=java
OUT=/tmp/ph23-sol01 && mkdir -p $OUT
cd sol-01-warehouse-layers && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT Sol01Demo && cd ..
# 其余三题同理：sol-02-snapshot-incremental → /tmp/ph23-sol02 → Sol02Demo
#               sol-03-dag-backfill        → /tmp/ph23-sol03 → Sol03Demo
#               sol-04-quality-lineage     → /tmp/ph23-sol04 → Sol04Demo
```

- **lint**：无。这四题不引入 checkstyle/spotless 等配置，判定标准是「`javac` 零警告编译 + 入口打印 `ALL PASS: N/N`」。
- **验证状态**：四题均已在本机 OpenJDK 17.0.18 实测通过（每题入口末尾打印 `ALL PASS: N/N`，任一断言失败即打印 `FAIL` 并以 `System.exit(1)` 结束）。各题文件头第三行写有真实实测数字。

| 练习 | 难度 | 参考实现 | 入口类 | 主文档小节 | 实测断言 |
|------|------|---------|--------|-----------|---------|
| 1 分层建模与口径对账 | ★★ | `sol-01-warehouse-layers/` | `Sol01Demo` | 3.1 | 12/12 PASS |
| 2 快照与增量读 | ★★★ | `sol-02-snapshot-incremental/` | `Sol02Demo` | 3.2 / 4.1 | 12/12 PASS |
| 3 DAG 编排与幂等回填 | ★★★ | `sol-03-dag-backfill/` | `Sol03Demo` | 3.6 / 3.7 / 4.4 | 14/14 PASS |
| 4 质量门禁与列级血缘 | ★★★ | `sol-04-quality-lineage/` | `Sol04Demo` | 3.8 | 14/14 PASS |

## 练习 1：分层建模与口径对账（★★）

**目标**：把「数据只能从上游流向下游」与「口径只有一个源」固化成建模阶段就能拒绝错误的约束，并用一个对账函数把「两张表的同一个数」按分区比出来——口径漂移要在建模或对账时暴露，而不是等业务发现两个数对不上。

**要求**：
- 分层 `ODS(0) < DWD(1) < DWS(2) < ADS(3)`，依赖校验规则是**上游层级 ≤ 下游层级**；反向依赖（如 DWD 直接读 ADS）与自依赖一律抛 `IllegalStateException`，且失败不改变已成功校验的计数
- **口径唯一源**：同一指标只允许在 DWS 定义一次；第二次登记（无论写在哪一层）抛异常并给出「已定义在哪张表、什么表达式」；非 DWS 层登记口径同样被拒
- 口径表达式一致性可跨目录比对（`count(distinct instance_id)` 与 `count(instance_id)` 判为冲突并给出冲突明细）
- **口径对账**：给定两张表与同一指标，按同一分区逐分区比对数值；一致返回 `PASS` 与已比对分区数；不一致返回 `FAIL` 并逐个给出**差异分区 + 两侧数值**；某侧缺分区时显式报「无法对账」而不是静默跳过

**验收**：四层层级有序；5 条合法依赖全部通过且反向依赖不计入校验数；自依赖被拒；口径在 DWS 登记成功、重复定义被拒（指标数不变）、写进 ADS 被拒；跨目录表达式冲突可检出；对账一致 3 分区 `PASS`；对账不一致能报出 `partition=20240602` 与两侧 1000/880；缺分区时抛异常并在信息里带上分区号。参考实现见 `sol-01-warehouse-layers/`（12 项断言）。

## 练习 2：快照与增量读（★★★）

**目标**：用「不可变快照 + parent 链 + CAS 指针替换」实现表的 ACID 语义——时间旅行沿链回溯、增量读比较清单差异、按快照差异算出「哪些分区需要重算」，并说清为什么快照 id 比时间戳可靠。

**要求**：
- `Snapshot(snapshotId, parentId, tsMillis, operation, filesByPartition)` 不可变；首次提交 `parentId = -1`，此后每次提交的 parent 指向提交时的当前快照；快照 id 单调递增
- **CAS 提交**：`commit(expected, ...)` 仅当当前指针仍是 `expected` 时替换，返回 `false` 表示「有人先提交了」，调用者必须重读后重试（不能盲写覆盖）
- `timeTravel(ts)`：回溯到「ts 之前最近的一次提交」；早于全部快照给最早快照；晚于全部快照给当前快照（边界不能少判 HEAD 本身）
- `incremental(sinceId)`：给出自该快照以来**新增/变更/删除**的分区；`since` 等于当前快照时为空增量
- `affectedPartitions(fromId, toId)`：按快照差异给出确定有序的「受影响分区」列表
- 并发场景可**确定性**断言：两个写者争抢同一个 base 只有一个提交成功，被拒者重读当前指针后落地；链上无分叉、无「两份当前快照」

**验收**：parent 连续（`s1(-1) → s2(1) → s3(2)`）且 id 严格递增；时间旅行命中区间内最近快照、早于/晚于全部快照两侧边界正确；增量读只含变化分区（含新增与删除）、`since` 等于当前快照时为空；分区差异与受影响分区列表确定有序；CAS 并发提交恰好一个赢家、恰好一个被拒后重试、两条提交串成链；重放同一覆盖操作分区布局不变且与上一快照差异为空；用过期 base 提交被拒且指针不动。参考实现见 `sol-02-snapshot-incremental/`（12 项断言）。

## 练习 3：DAG 编排与幂等回填（★★★）

**目标**：把「依赖图 + 就绪条件 + 失败传播」与「回填 = 依赖闭包 + 分区整体覆盖 + 断点续跑」两件事写成一个确定性内存编排器——顺序可复盘、缺口显式暴露、重跑结果一致。

**要求**：
- `TaskNode(id, deps, retries)`；`topoOrder()` 用 Kahn 算法 + **同层按 id 排序**，两次运行逐项相同；有环 DAG 抛异常（信息里带已完成/总任务数）
- `ready(successSet)`：自身未跑且**所有上游都成功**才就绪；部分上游成功不算（不跑「半份数据」）
- 失败传播：重试次数 = `retries + 1`（首次 + 重试），耗尽后标记 `FAILED`，其下游保持 `BLOCKED`（**不是 `SUCCESS`**）；与本链无关的任务照常成功
- **幂等回填**：`plan(startTable, partitions)` 沿依赖图向下游传播**闭包**，每张下游表重算同一组分区，且不含无关表；分区列表必须严格升序、无重复、非空，否则抛 `IllegalArgumentException`
- 执行是**按分区整体覆盖**（不是追加、也不是 upsert），每次写入记录 `reason`；`run(store, alreadyCovered)` 跳过已覆盖分区，实现**断点续跑只补缺口**

**验收**：拓扑序确定且依赖先行（`[ods_dim, ods_load, dwd_fact, dws_dau, ads_board]`）；有环 DAG 被拒；就绪判断在部分上游成功时不放行；失败任务恰好尝试 3 次、下游一次都没跑且状态是 `BLOCKED`；回填闭包覆盖 `dwd_fact → dws_dau → ads_board` 且不含 `ods_load/ods_dim`；非法范围（降序/空）被拒；重复回填 0 次执行、全部跳过、覆盖集合与内容一致；断点续跑已覆盖 5 个跳过、补跑 7 个，合计等于计划 12，且回填后 12/12 个分区都有内容。参考实现见 `sol-03-dag-backfill/`（14 项断言）。

## 练习 4：质量门禁与列级血缘（★★★）

**目标**：把「坏数据不进表」与「改上游列前知道谁受影响」两件事写成可执行的兜底——门禁失败一律 fail-closed（不发布快照），血缘细到列级并可回溯到 ODS。

**要求**：
- **五类门禁**：非空（报出空列与行数）、唯一（报出重复键值与总行数）、量程（报出越界列、实际范围与允许范围）、行数波动（实际行数相对基线偏离超阈值即失败）、鲜度（最新数据滞后超过 SLA 即失败）
- **fail-closed 提交**：任一门禁 `FAIL` → 拒绝提交，表停在**上一个成功版本**（version 不变、当前快照不变、不产生新快照历史）；全部门禁通过才提交成功并推进 version
- 一次检查跑完全部门禁（不短路），失败明细逐条可读（含门禁名、具体列/数值/阈值）并**原样成为拒绝原因**
- **列级血缘**：记录「输出列 ← 输入列」，`upstreamClosure(table, column)` 一路追到没有上游为止（通常就是 ODS）；`downstream(table, column)` 给出改这一列会波及的**下游列集合**（跨表传递）

**验收**：`dws_daily_active.dau` 的上游闭包可追到 ODS 的 `instance_id/event_type`；`ads_instance_dashboard.active_cnt` 跨三层闭包完整；改 `ODS.instance_id` 影响 3 列、改 `ODS.event_time` 影响 4 列（含 `dwd.ds` 退化列）；一份坏数据被非空/唯一/量程/行数四类门禁同时拦下；五类门禁各自在自己的坏数据上失败并给出可读原因；门禁失败时 version 停在 0、坏数据一行没进去；全部通过时 version 0 → 1 且当前快照 3 行；门禁明细含失败原因并驱动拒绝；提交历史只留成功版本。参考实现见 `sol-04-quality-lineage/`（14 项断言）。

## 验证命令（纯 Java，无第三方依赖）

```bash
JAVAC=javac && JAVA=java
mkdir -p /tmp/ph23-sol01 /tmp/ph23-sol02 /tmp/ph23-sol03 /tmp/ph23-sol04
(cd sol-01-warehouse-layers    && $JAVAC -encoding UTF-8 -d /tmp/ph23-sol01 *.java && $JAVA -cp /tmp/ph23-sol01 Sol01Demo)
(cd sol-02-snapshot-incremental && $JAVAC -encoding UTF-8 -d /tmp/ph23-sol02 *.java && $JAVA -cp /tmp/ph23-sol02 Sol02Demo)
(cd sol-03-dag-backfill        && $JAVAC -encoding UTF-8 -d /tmp/ph23-sol03 *.java && $JAVA -cp /tmp/ph23-sol03 Sol03Demo)
(cd sol-04-quality-lineage     && $JAVAC -encoding UTF-8 -d /tmp/ph23-sol04 *.java && $JAVA -cp /tmp/ph23-sol04 Sol04Demo)
# 本机实测：12/12、12/12、14/14、14/14，四题全部 ALL PASS
```

四题全部 `ALL PASS` 后继续到 [`examples/`](../examples/) 与 [`project/`](../project/)：最小湖仓与编排平台（lakeplat）。
