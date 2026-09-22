# ph22 AI 平台 / 训练与推理调度方向 Java 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> **与主文档「动手练习」的对应**：四题一一对应 [`22-ai-platform.md`](../22-ai-platform.md) 第 7 章列出的四个练习——练习 1 = 训练任务提交与状态机、练习 2 = 资源池与配额、练习 3 = 调度策略、练习 4 = 模型灰度发布决策。
> **验证纪律**：四题均为纯 Java 17（标准库、零依赖、默认包、无 lint 配置），用本机 OpenJDK 17.0.18 实测，四题入口全部 `ALL PASS`。

## 依赖与验证方式

- **依赖**：仅 JDK 17 标准库（record / sealed interface / switch 表达式 / 并发集合），无 Maven/Gradle 依赖，无第三方 jar，无 Kafka/Redis/GPU/K8s。全部为**确定性内存模型**（无随机、无时钟依赖、无网络）。
- **编译运行命令**（每题独立 `javac *.java`，输出目录用 `/tmp`，不产生仓库内构建产物）：

```bash
JAVAC=javac   # 本机：OpenJDK 17.0.18 (Homebrew)
JAVA=java
OUT=/tmp/ph22-sol01 && mkdir -p $OUT
cd sol-01-job-lifecycle && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT Sol01Demo && cd ..
# 其余三题同理：sol-02-pool-quota → /tmp/ph22-sol02 → Sol02Demo
#               sol-03-scheduling → /tmp/ph22-sol03 → Sol03Demo
#               sol-04-release-decision → /tmp/ph22-sol04 → Sol04Demo
```

- **lint**：无。这四题不引入 checkstyle/spotless 等配置，判定标准是「`javac` 零警告编译 + 入口打印 `ALL PASS: N/N`」。
- **验证状态**：四题均已在本机 OpenJDK 17.0.18 实测通过（每题入口末尾打印 `ALL PASS: N/N`，任一断言失败即打印 `FAIL` 并以 `System.exit(1)` 结束）。各题文件头第三行写有真实实测数字。

| 练习 | 难度 | 参考实现 | 入口类 | 主文档小节 | 实测断言 |
|------|------|---------|--------|-----------|---------|
| 1 训练任务提交与状态机 | ★★ | `sol-01-job-lifecycle/` | `Sol01Demo` | 3.1 | 11/11 PASS |
| 2 资源池与配额 | ★★★ | `sol-02-pool-quota/` | `Sol02Demo` | 3.2 / 3.7 | 13/13 PASS |
| 3 调度策略 | ★★★ | `sol-03-scheduling/` | `Sol03Demo` | 3.3 / 4.1 | 14/14 PASS |
| 4 模型灰度发布决策 | ★★★ | `sol-04-release-decision/` | `Sol04Demo` | 3.4 / 3.5 / 4.3 | 13/13 PASS |

## 练习 1：训练任务提交与状态机（★★）

**目标**：实现训练任务聚合根的状态机——把「提交 → 排队 → 运行 → 成功/失败/取消」固化成可审计的对象，非法操作必须被挡在聚合内部。

**要求**：
- 状态机（sealed interface + 穷尽 switch）：`Queued → Running | Cancelled`，`Running → Succeeded | Failed | Cancelled`，`Failed → Queued`（重试）；`Succeeded`/`Cancelled` 为**终态不可变**
- 非法迁移一律抛 `IllegalStateException`，且**不写审计**（失败的尝试不能污染轨迹）
- 重试只对 `FAILED` 开放，`attempt` 单调递增、**上限 3**，超限抛异常
- 幂等提交：幂等键 = `tenant + name + specHash`，重复提交返回**同一个任务实例**（不是新任务）
- 审计轨迹：每次成功迁移写一条 `(seq, from, to, reason, operator)`
- 提供按幂等键查重、按 jobId 查询、任务总数统计

**验收**：重复提交返回同一任务且任务总数不变；不同 spec（同 name 不同 gpus）视为新任务；合法迁移链的审计条数与迁移次数一致；终态任务被拉回排队、跳过 RUNNING 直接成功均被拒；第 4 次重试被拒且 `attempt` 停在 3。参考实现见 `sol-01-job-lifecycle/`（11 项断言）。

## 练习 2：资源池与配额（★★★）

**目标**：实现「一张卡的账本」——GPU 台账（分配/回收/不变量）与租户配额（超限**拒绝而非排队**）。

**要求**：
- `GpuPool`：总量固定，`allocate(jobId, gpus)` / `release(jobId)` 必须过账，任何时刻 `allocated + free == total` 是硬不变量，提供 `checkInvariant()`
- 重复分配同一 jobId、释放不存在的分配、非法 GPU 数量一律抛异常；超量申请被拒时**不得部分占用**（账本要么全变要么不变）
- `Quota(maxGpus, maxQueuedJobs)` + `QuotaGuard`：超限返回**可读原因**（形如 `配额不足：GPU 8/6（已用 4，申请 4）`），并把它记入拒绝日志
- **拒绝而非排队**：被拒的请求不进入任何等待队列（排队数保持 0），因为配额不会因为等待而变大
- 回收后可复用：释放占用的 GPU / 排队额度后，之前的超限请求可以成功

**验收**：分配/回收全过程不变量恒成立；重复分配与释放不存在均抛异常；超量申请不改变账本；配额超限的拒绝原因可读且排队数为 0；回收后同一请求变为 granted。参考实现见 `sol-02-pool-quota/`（13 项断言）。

## 练习 3：调度策略（★★★）

**目标**：把调度策略写成**纯函数**——同一输入必须给出确定决策（否则「为什么排队 6 小时」无法复盘），并用同一组输入对比 FIFO 与「优先级 + 回填」。

**要求**：
- 策略接口 `select(queue, freeGpus, tenantUsed) -> List<String>`，队列按提交顺序给出，返回本轮可运行的任务 id
- `FifoPolicy`：严格按提交顺序，队头放不下就**停住**（可复现的队头阻塞）
- `PriorityPolicy`：优先级降序、同级 FIFO（低优先级可能饿死，这正是需要老化/配额兜底的原因）
- `BackfillPolicy`：队头被卡住时，允许**放得下且预估时长不超过队头等待窗口**的小任务插队；队头位置不变、不被改写成别的任务
- 三个策略都是纯函数：不修改入参队列、不使用随机与时钟、同输入两遍结果必须一致

**验收**：同输入跑两遍三策略结果逐项一致；FIFO 在队头阻塞场景返回空集（后队小任务全被卡住）；优先级场景中 FIFO 与 Priority 的决策顺序不同且 Priority 队首是最高优先级；回填场景实际用上空闲卡、排除了预估过长的任务、且被卡的队头既未入选也未从队列中被移除。参考实现见 `sol-03-scheduling/`（14 项断言）。

## 练习 4：模型灰度发布决策（★★★）

**目标**：实现灰度发布决策器——晋级门槛 + 灰度推进 + 失败回滚，把「副本 → 流量 → 版本」的收敛纪律固化成可直接断言的纯函数。

**要求**：
- 决策器签名：`decide(currentStage, candidateMetric, prodMetric, healthOk, currentPct)`
- 阶段：`STAGING → CANARY(10% → 50% → 100%) → STABLE`；动作：晋级 / 推进到 50% / 推进到 100% / 回滚 / 保持
- 晋级门槛：`candidateMetric < prodMetric` 时**不得晋级**（保持并给出可读原因）
- 健康检查：失败一律回滚（`STAGING` 取消本次发布、`CANARY` 退回 STAGING 且流量归零）
- 灰度期业务指标劣化同样回滚；健康且指标达标才按 10 → 50 → 100 推进；100% 观察通过后进入 `STABLE`
- 非法输入被拒：流量百分比不在 `{0,10,50,100}`、指标非法、阶段与流量不一致（`STAGING≠0`、`CANARY=0`、`STABLE≠100`）均抛 `IllegalArgumentException` 并给出可读信息

**验收**：门槛不达标不晋级；健康失败必回滚；健康则 10→50→100 逐步推进；100% 后进入稳定态且稳定态幂等保持；灰度期指标劣化回滚；百分比 37 与阶段-流量不一致的输入被拒；同输入重复决策结果相等（纯函数）。参考实现见 `sol-04-release-decision/`（13 项断言）。

## 验证命令（纯 Java，无第三方依赖）

```bash
JAVAC=javac && JAVA=java
mkdir -p /tmp/ph22-sol01 /tmp/ph22-sol02 /tmp/ph22-sol03 /tmp/ph22-sol04
(cd sol-01-job-lifecycle   && $JAVAC -encoding UTF-8 -d /tmp/ph22-sol01 *.java && $JAVA -cp /tmp/ph22-sol01 Sol01Demo)
(cd sol-02-pool-quota      && $JAVAC -encoding UTF-8 -d /tmp/ph22-sol02 *.java && $JAVA -cp /tmp/ph22-sol02 Sol02Demo)
(cd sol-03-scheduling      && $JAVAC -encoding UTF-8 -d /tmp/ph22-sol03 *.java && $JAVA -cp /tmp/ph22-sol03 Sol03Demo)
(cd sol-04-release-decision && $JAVAC -encoding UTF-8 -d /tmp/ph22-sol04 *.java && $JAVA -cp /tmp/ph22-sol04 Sol04Demo)
```

四题全部 `ALL PASS` 后继续到 [`project/`](../project/)：AI 平台最小控制面（aiplat）。
