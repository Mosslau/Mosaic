# ph22 阶段项目：AI 平台最小控制面（aiplat，收官项目）

> 对应 roadmap §22 与主文档 [`22-ai-platform.md`](../22-ai-platform.md) 第 7 章「阶段项目」。
> 本项目是 Java 学习路线的**最后一个阶段项目**（roadmap 第 22 节即最后一节）：把 ph01~ph21 的机制
> （DDD 聚合与状态机、sealed + switch 穷尽、SPI 可插拔策略、CHM 实时状态、事件驱动计量、控制器循环、
> Prometheus 文本指标）组织成**一个纯 Java、可 `javac` 编译、可离线自检的模块集**。
>
> 主文档的两条边界在这里被严格遵守：**不碰训练框架内核**（训练作业 = 一个消耗 GPU 的黑盒进程）、
> **不碰推理引擎内核**（推理服务 = 需要被编排生命周期与流量的副本集合）。
> 所有数据在代码内确定性自造（固定时钟 + 固定提交时间），无第三方依赖、无外部文件、无外部进程。

## 需求

主文档第 1 章给出的闭环是：**多租户提交训练任务（配额 + 幂等）→ 排队与调度（GPU 池 + 优先级/回填）
→ 任务生命周期推进（含失败重试）→ 产物登记为模型版本（血缘 + 晋级）→ 推理服务灰度发布（收敛 + 回滚）
→ 运维一屏与指标输出**。本项目把它落成一条端到端流水线，每个模块 = 一个限界上下文：

```text
                        ┌──────────────────────── AiPlatform（控制面门面）────────────────────────┐
 提交 JobSpec            │                                                                        │
 ──────────▶ QuotaGuard ─┼─▶ 拒绝(可读原因)   ┌── 排队队列 ──┐   Policy(FIFO/优先级/回填) 决策      │
            幂等键命中 ──┼─▶ 返回原任务       │ TrainingJob  │ ────────▶ GpuPool.tryAllocate      │
                        │                    │  QUEUED      │            （不变量 allocated+free  │
                        │                    └──────┬───────┘             == total）              │
                        │                           │ RUNNING                                    │
                        │              ┌────────────┴────────────┐                                 │
                        │       执行体上报成功              执行体上报失败                          │
                        │              │                       │                                  │
                        │              ▼                       ▼                                  │
                        │        SUCCEEDED(artifactId)   FAILED ──retry(attempt+1, ≤3)──▶ QUEUED   │
                        │              │                       └──attempt 用尽──▶ FAILED(终态)     │
                        │              │ 释放 GPU + MeteringLedger 记一条 GPU 秒事件              │
                        │              ▼                                                          │
                        │      ModelRegistry.register（血缘 dataset+job 必填，禁止版本倒退）       │
                        │              │                                                          │
                        │              ▼  promote（指标不劣于当前 PROD，唯一 PROD，旧版归档）      │
                        │      InferenceService：reconcile 每轮一步                                │
                        │        先有副本(SURGE 2→4→6) → 再切流量(TRAFFIC 10%→50%→100%) → 最后改版本   │
                        │        健康失败/人工 → ROLLING_BACK：流量归零 → 排空候选 → 期望改回旧版本     │
                        └───────────────────────────┬────────────────────────────────────────────┘
                                                    ▼
                              OpsConsole：队列 / 算力 / 版本 / 服务 四块 + Prometheus 文本
                              DatasetVersion.Ledger：数据集版本 + 快照校验（模型血缘的另一半）
```

图中箭头即「控制面只做决策与台账，执行体只做计算」这条契约：训练/推理执行体是黑盒，
控制面与它的接口只有两个——**状态上报**与**产物登记**。因此把执行体换成真实 PyTorch 作业或真实推理进程，
控制面代码不需要改。

## 模块清单

| 类 | 职责 | 对应主文档小节 |
|----|------|----------------|
| `JobSpec` | 训练任务的不可变定义（tenant/name/gpuCount/priority/estMinutes/submitTs）+ 幂等键与规格指纹 | 3.1 |
| `JobState` | 生命周期状态机：sealed interface + Queued/Running/Succeeded/Failed/Cancelled 五个 record | 3.1 |
| `TrainingJob` | 任务聚合根：合法迁移校验、重试上限 3、终态不可变、审计轨迹 `(ts, from, to, reason, operator)` | 3.1 |
| `GpuPool` | GPU 台账：分配/回收/租户占用 + 硬不变量 `allocated + free == total` | 3.2 |
| `Policy` | 调度策略接口 + 候选视图 `Candidate`（纯函数：同输入必同决策） | 3.3 |
| `FifoPolicy` | 先到先得，队头放不下即停止（队头阻塞的形成机制） | 3.3 / 4.1 |
| `PriorityPolicy` | 优先级降序、同级 FIFO；不跳过放不下的高优先级任务 | 3.3 / 4.1 |
| `BackfillPolicy` | 队头大任务阻塞时放行「放得下且不超过 `maxBackfillMinutes`」的小任务 | 3.3 / 4.1 |
| `ModelVersion` | 语义化版本 + Stage(STAGING/PROD/ARCHIVED) + 血缘（数据集 + 训练产物）+ 指标 | 3.4 |
| `ModelRegistry` | 登记（血缘校验 / 禁止版本倒退）、晋级门槛、唯一 PROD（旧 PROD 自动归档） | 3.4 |
| `DatasetVersion` | 数据集版本 record + `Ledger` 台账 + 快照校验和比对（fail-closed） | 3.6 |
| `Quota` | 租户配额三维度：单任务卡数 / 排队任务数 / 每日 GPU 秒 | 3.7 |
| `QuotaGuard` | 提交前校验，超限返回**可读原因**（如「配额不足：GPU 4/2」）而不是静默排队 | 3.7 / 4.4 |
| `MeteringLedger` | 事件驱动的 GPU 秒计量：分配/释放事件 + 秒级时间戳，按租户/按天汇总 | 3.7 / 4.4 |
| `InferenceService` | 期望状态 + 控制器循环收敛、分批滚动、灰度切流、健康失败回滚（回滚即反向收敛） | 3.5 / 4.2 / 4.3 |
| `AiPlatform` | 控制面门面：把提交/调度/生命周期/台账/发布编成一条闭环，统一逻辑时钟 | 第 7 章「阶段项目」 |
| `OpsConsole` | 运维一屏：队列/算力/版本/服务四块聚合 + Prometheus 文本指标（同一份快照，不可能互相矛盾） | 3.8 |
| `AiPlatformDemo` | 端到端演示 + 14 项验收断言（输出即验收报告） | 阶段验收清单 |

## 目录结构

```text
project/
├── README.md
├── Makefile                       # 可选：make / make run / make clean（产物只落 /tmp）
└── src/aiplat/
    ├── AiPlatformDemo.java        # 端到端闭环 + 14 项断言（14 行 PASS）
    ├── AiPlatform.java            # 控制面门面 + 固定逻辑时钟 + 审计
    ├── JobSpec.java               # 不可变任务定义 + 幂等键
    ├── JobState.java              # sealed 状态机
    ├── TrainingJob.java           # 聚合根：迁移/重试/审计
    ├── GpuPool.java               # GPU 台账 + 不变量
    ├── Policy.java                # 策略 SPI
    ├── FifoPolicy.java            # FIFO
    ├── PriorityPolicy.java        # 优先级
    ├── BackfillPolicy.java        # 回填
    ├── ModelVersion.java          # 语义化版本 + 血缘
    ├── ModelRegistry.java         # 登记 / 晋级 / 唯一 PROD
    ├── DatasetVersion.java        # 数据集版本台账 + 快照校验
    ├── Quota.java                 # 配额定义
    ├── QuotaGuard.java            # 配额校验 + 可读原因
    ├── MeteringLedger.java        # GPU 秒计量事件
    ├── InferenceService.java      # 期望状态 + 收敛 + 灰度 + 回滚
    └── OpsConsole.java            # 运维一屏 + Prometheus 文本
```

## 构建与运行（已验证）

验证环境：**OpenJDK 17.0.18（Homebrew）**；零第三方依赖；构建产物只写到 `/tmp`。

```bash
# 在 languages/java/ph22-ai-platform/project/ 目录执行
javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java     # 1. 编译
java -cp /tmp/ph22-proj aiplat.AiPlatformDemo                 # 2. 运行（输出即验收报告）
rm -rf /tmp/ph22-proj                                         # 3. 清理
```

## 验收标准

### 命令与实测结果

```console
$ javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java && java -cp /tmp/ph22-proj aiplat.AiPlatformDemo
== AI 平台最小控制面（aiplat）闭环演示：提交→调度→生命周期→产物→灰度发布→运维一屏 ==
PASS 幂等：同一 (租户,名称,规格) 重复提交返回同一任务 job-0001，重发时间戳变化不影响幂等键，队列未新增任务
PASS 配额：租户 edge 单任务 4 卡超上限 2 卡 → 拒绝（配额不足：GPU 4/2（租户 edge 单任务上限 maxGpus）），未进入队列
PASS 调度：同一队列按优先级 9>5>1 决策为 [job-0002, job-0003, job-0001]，FIFO 为 [job-0001, job-0002, job-0003]（同输入重放决策完全相同）
PASS 回填：队头 8 卡大任务阻塞时纯优先级一个都不放行，回填放行 15 分钟小任务（空闲卡 4→2，利用率 0%→50%）
PASS 算力池：调度占满 8 卡后不变量 allocated + free == total 成立，超量申请被拒且账本不变（租户 cv 占用 8）
PASS 生命周期：job-0001 RUNNING→SUCCEEDED，产出 artifact://cv/detector/attempt-1，GPU 归还（free=4）
PASS 失败重试：job-0002 第 1 次尝试失败 → 重试后第 2 次尝试成功（attempt=2，审计 6 条）
PASS 重试上限：job-0003 第 3 次尝试仍失败 → FAILED 终态，再重试被拒（重试超上限：任务 job-0003 已用尽 3 次尝试（当前 attempt=3），FAILED 为终态），GPU 全部归还
PASS 血缘：数据集版本为空的登记被拒（血缘缺失：模型版本 detector:1.3.0 未绑定数据集版本（datasetVersion 为空））；快照校验和一致才可复现，篡改与未知版本都不通过
PASS 版本台账：禁止版本倒退：模型 detector 已登记最新版本 1.2.0，不能再登记 1.0.5；登记表仍为 3 条（1.0.0 / 1.1.0 / 1.2.0），倒挂版本未污染台账
PASS 晋级：晋级被拒：候选 1.2.0 指标 0.700 低于门槛 0.810（当前 PROD 1.0.0 指标 0.810 × 系数 1.00）；1.1.0（0.860）晋级成功，1.0.0 自动归档，PROD 全局唯一
PASS 滚动发布：6 副本按批 2 推进 [2, 4, 6]，副本齐备后流量 [10, 50, 100]，收敛到 1.1.0（已收敛时循环空转，不再产生动作）
PASS 灰度回滚：1.2.0 灰度 50% 时健康检查失败 → 流量归零、候选副本排空，回到 1.1.0 全量 6 副本（回滚即反向收敛）
+---------------------------- AI 平台运维一屏 ----------------------------+
  [任务] 排队 1 | 运行中 1 | 成功 2 | 失败 1
  [算力] GPU 6/8 已分配（利用率 75.0%）| 空闲 2 | 累计计量 3240 GPU·秒 / 6 条事件
  [版本] PROD=detector:1.1.0（PROD 1 / STAGING 1 / ARCHIVED 1）
  [服务] detector-svc 就绪 6/6 | 当前版本 1.1.0（流量 100%）| 阶段 ROLLED_BACK
+------------------------------------------------------------------------+
PASS 运维一屏：队列(1 排队/1 运行/2 成功/1 失败)、算力(6/8 已分配, 空闲 2, 计量 3240 GPU·秒)、版本(PROD detector:1.1.0)、服务(就绪 6/6)四块齐全，Prometheus 文本与快照逐项一致
ALL PASS: 14/14
```

- **14 行 `PASS`、0 行 `FAIL`，末行 `ALL PASS: 14/14`**；任何一项失败都会打印 `FAIL` 并以 `System.exit(1)` 结束（可直接接 CI）。
- 输出**逐字节可复现**：连续多次运行 `diff` 为空（固定提交时间 `T0` + 平台内部 +60 秒逻辑时钟，不读系统时间）。

### 14 项断言覆盖的语义

| # | 断言 | 覆盖语义（主文档小节） |
|---|------|------------------------|
| 1 | 幂等提交返回同一任务，队列不新增 | 幂等键只认业务定义（3.1） |
| 2 | 配额超限拒绝且原因可读，不静默排队 | 快速失败优于长时间等待（3.7） |
| 3 | 排队任务按优先级调度（与 FIFO 决策不同、各自确定） | 策略即数据、可解释（3.3） |
| 4 | 回填提升利用率（空闲卡 4→2 被真正分配） | 回填用预估换利用率（3.3/4.1） |
| 5 | GPU 台账不变量成立、超量申请被拒且不污染台账 | `allocated + free == total`（3.2） |
| 6 | 任务运行→成功并产出 artifactId，GPU 归还 | 状态机与产物锚点（3.1） |
| 7 | 失败任务重试后成功（attempt=2） | 重试语义（3.1） |
| 8 | 重试超上限进入 FAILED 终态，再重试被拒 | 重试上限防吃池（3.1） |
| 9 | 模型登记血缘缺失被拒 + 数据集快照校验（篡改/未知版本不通过） | 血缘完整 + 数据可追溯（3.4/3.6） |
| 10 | 模型版本倒退被拒 | 语义化比较 + 禁止倒退（3.4） |
| 11 | 指标不劣于 PROD 才可晋级（否则拒绝），且 PROD 唯一 | 晋级门槛 + 唯一 PROD（3.4） |
| 12 | 滚动更新分批推进（2→4→6）且就绪收敛、收敛后空转 | 期望状态 + 控制器循环（3.5/4.2） |
| 13 | 灰度健康失败触发回滚，副本/流量回到旧版本 | 副本→流量→版本顺序 + 回滚即反向收敛（4.3） |
| 14 | 运维一屏四块齐全，Prometheus 文本与状态逐项一致 | 队列/利用率/版本/就绪（3.8） |

## 运行手册

1. **看闭环是否健康**：`java -cp /tmp/ph22-proj aiplat.AiPlatformDemo`，只看末行 `ALL PASS: 14/14`。
2. **看某个任务为什么排队**：拿 `jobId` 读 `TrainingJob.audit()`——每次迁移都有 `(ts, from, to, reason, operator)`，
   「谁在什么时候把它推进到哪个状态、为什么」一条不缺。
3. **看配额为什么拒绝**：`AiPlatform.audit()` 里能看到 `提交被拒：<租户>/<任务> —— 配额不足：GPU x/y`；
   `QuotaGuard.Decision.reason()` 就是可直接展示给用户的文案。
4. **看调度决策是否可复盘**：`AiPlatform.queueSnapshot()` + `new PriorityPolicy().select(queue, free)`，
   纯函数，同输入必然同输出；`AiPlatform.schedule()` 的审计行记录了本轮 `free` 与选中列表。
5. **看一次发布用了什么数据**：`ModelVersion.datasetVersion()` 指向 `DatasetVersion.Ledger` 的条目，
   `ModelVersion.jobId()` 指向训练产物 `artifact://<租户>/<任务>/attempt-<n>`，配合任务审计可追到提交人。
6. **看服务为什么回滚**：`InferenceService.events()` 里有健康失败原因与「期望状态改回旧版本」这一步；
   `status().unhealthyReason()` 保留原因供值班复盘。
7. **接指标系统**：`OpsConsole.prometheusText()` 输出 `aiplat_jobs_queued` / `aiplat_gpus_allocated` /
   `aiplat_gpus_free` / `aiplat_jobs_total{state}` / `aiplat_model_versions{stage}` /
   `aiplat_service_replicas_ready{service}` / `aiplat_gpu_seconds_total`，把它挂到一个 HTTP `/metrics` 即可被 Prometheus 抓取。

## 与真实生产形态的差距（诚实清单）

| 本项目 | 生产形态 | 说明 |
|--------|----------|------|
| `GpuPool` 内存台账（卡数一维） | K8s device plugin / GPU Operator + MIG 切分 | 语义复刻（总量/分配/回收/不变量）；真实 `(卡数, 显存)` 二维与拓扑感知见主文档 4.4，标「未在本环境验证」 |
| 逻辑时钟 +60 秒 | 真实 UTC 时钟与事件时间 | 为了让审计与计量数值可复现；生产要注意时钟漂移与事件时间/处理时间之分 |
| 调度只做单轮决策，不抢占 | 抢占 + 老化 + 多资源 DRF | 抢占需要可安全中断（checkpoint），本项目只做决策不做中断（3.3/4.1） |
| `InferenceService` 副本是内存数字 | Deployment/ReplicaSet + readinessProbe + Service/Ingress 权重 | 复刻「期望状态 + 控制器循环 + 分批 + 切流」；真实 YAML/CRD 见扩展方向 |
| 单 JVM 内存模块 | 多服务 + 事件总线 + 持久化 | 状态机/台账本身是纯领域逻辑，`AiPlatform` 可整体换成 Spring 装配并加一层 HTTP（ph14/ph16） |
| `ModelRegistry` 存内存 | MLflow / 模型仓库 + 对象存储 | 语义复刻（语义化版本/阶段/血缘/唯一 PROD）；真实制品存储与签名未涉及 |
| 计量只在进程内汇总 | 事件写 Kafka → 计费流水 | 本项目展示「事件驱动计量」的语义；接 Kafka 见扩展方向（ph17） |

## 扩展方向

- **接真实 K8s CRD / Operator**：把 `TrainingJob` 落成 `TrainingJob` CRD（spec = `JobSpec`，status = `JobState`），
  `AiPlatform.schedule()` 变成 Operator 的 reconcile：读 CRD 队列 → 决策 → patch status；
  `InferenceService` 换成 `Deployment` 的 `replicas` + `image` patch，灰度用 `Service`/`Ingress` 权重。
  本项目的状态机与审计字段可直接映射成 CRD 的 `conditions` 与 `events`。
- **接真实 GPU 计量**：把 `MeteringLedger.record` 的调用点从「释放时」换成消费 DCGM/NVML 的采样事件，
  或消费 device plugin 的 allocate/deallocate 事件；账本语义（事件 + 秒级时间戳）不用改，
  只需要把「内存 List」换成 Kafka topic + 计费库（ph17 语义）。
- **接 Kafka 事件**：`MeteringLedger.record` → 生产 `aiplat.metering.v1`；任务状态迁移 → 生产
  `aiplat.job.state.v1`（key = jobId 保证同一任务事件保序）；消费者负责计费与告警，
  平台控制面因此变成「事件溯源 + 状态投影」，多实例横向扩展。
- **配额与公平性升级**：把 `QuotaGuard` 的三个维度换成 DRF（主导资源占比）并加入等待时间老化，
  解决纯优先级饿死低优先级的问题（3.3/4.1）。
- **发布策略升级**：`InferenceService` 增加 `maxSurge`/`maxUnavailable` 两个独立参数、
  观察期（多轮 reconcile 之间校验业务指标）、以及 A/B 与影子流量；同时把 `reportUnhealthy`
  接到真实健康检查与指标查询上（当前由 demo 主动上报）。
- **多资源与显存**：`JobSpec` 增加 `vramGb`，`GpuPool` 从「卡数」升到「(卡数, 显存) 二维装箱」，
  可以让断言覆盖「卡够但显存不够仍会 OOM」这一二级稀缺问题（4.4）。
