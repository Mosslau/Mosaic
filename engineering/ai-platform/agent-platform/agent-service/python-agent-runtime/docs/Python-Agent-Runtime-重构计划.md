# Python Agent Runtime 重构计划

- **文档类型**：重构计划（可执行）
- **版本**：**v1.10**（2026-10-30 修订，对齐 50 项能力全景：附录 H 矩阵 + 6 项已有能力约束 + 34 项回归清单）
- **日期**：2026-10-29
- **重构对象**：`python-agent-runtime`（中型 Python 服务，企业级可靠性要求）
- **工期估算**：**12 周 / 59 人日**（单人；重构 29 + 能力追平 25 + 缓冲 5）
- **参考手册**：[企业级项目设计参考](../../docs/企业级项目设计参考.md)（13 个能力域的通用设计标准）·
  [Agent 服务能力与扩展点全景](Agent%20服务能力与扩展点全景.md)（9 域 50 项能力、7 个端口、12 条扩展轴）
- **单一事实来源**：原《代码质量评估》《能力评估与高可用差距分析》《能力待办清单》《能力追平计划》已合并进本文档，
  原始版本保留在 git 历史提交 `19b27e6`

## 修订记录

| 版本 | 变更 | 原因 |
|---|---|---|
| v1.0 | 初版：4 组分层、6 阶段、度量看板、风险登记 | —— |
| **v1.10** | 按《[Agent 服务能力与扩展点全景](Agent%20服务能力与扩展点全景.md)》50 项能力对标后补齐：<br>① 新增 **附录 H：50 项能力矩阵**（状态/落点/本次动作）<br>② 新增 **§3.12 已有能力约束**（6 项"代码有、文档无"的能力，防重构误改）<br>③ 新增 **§7.6 能力回归清单**（34 项 ✅ 能力 → 断言映射）<br>④ §1.2 范围改为能力口径（改 34 / 加 6 / 补约束 6 / 不做 5）<br>⑤ §14 补 3 项空缺与 2 项归属<br>⑥ DoD 增补 3 条（矩阵一致性、回归用例齐备、6 项冻结核对） | 让计划从"改造清单"变成"服务全貌 + 改造方案" |
| **v1.9** | 新增 **附录 G：架构图**（9 张，含系统上下文、分层、端口、部署、时序、状态机、数据、能力叠加、排期），并附章节对应表与图例 | 让"代码怎么分、请求怎么走、存了什么"可一图看懂，减少口头解释 |
| **v1.8** | **去掉迁移包袱（用户决策：未上线、未开发完成）**：<br>① §八 重写为「数据与契约设计」，删除兼容窗口、双写、滚动升级四象限、回滚演练、迁移脚本<br>② §1.3 底线从 5 条降到 4 条（删除"迁移可回滚"）<br>③ §1.1 目标 C 改为「直接演进（无历史包袱）」<br>④ 删除 §8.5 破坏性变更管理；§9.6 弃用政策降级为"上线后启用"<br>⑤ DoD 从 64 → **58**（删除 C 组迁移安全 6 条）<br>⑥ 排期从 14 → **12 周**（59 人日），去掉迁移/双跑/回滚演练三条轨<br>⑦ 允许直接改 Redis Key 与 TTL（同步更新所有权表） | 项目未上线，无生产数据与外部调用方，迁移机制是纯成本 |
| **v1.7** | **定调变更（用户决策）**：不再是"行为不变的重构"，改为 **"更好的设计 + 完整的能力"**，允许破坏性更新，但必须保证可迁移。<br>① §1.1 目标改为三件事：设计升级 / 能力完整 / 可迁移的破坏性变更<br>② §1.2 把 6 项能力追平**纳入范围**<br>③ §1.3 红线从"契约零破坏"改为"**数据不丢、任务可恢复、迁移可回滚、可靠性不降、安全不收窄**"<br>④ 新增 **§8.5 破坏性变更管理**<br>⑤ 新增 **Phase 6（Track C）能力追平**，排期改为 12.5–14 周<br>⑥ §十五 从"不属本次范围"改为"本次范围的 Track C"<br>⑦ DoD 重构为三组：设计 48 + 能力 10 + 迁移安全 6 = 64 条 | 用户明确：可以破坏，但必须换来更好的设计与完整能力 |
| **v1.6** | ① 合并《能力追平计划》为 **§十五**（6 项：回放/隔离层级/HITL 编辑/后台卸载/协议适配/建队），明确"不属重构范围"<br>② docs 精简：`python-agent-runtime/docs/` 仅保留本文档；原能力评估、代码质量评估、待办清单、追平计划归档到 git 历史（提交 `19b27e6`）<br>③ 头部"关联文档"改为指向根 `docs/企业级项目设计参考.md` | 单一事实来源，避免多份文档互相漂移 |
| **v1.5** | 按用户设定的 **内部 9.5 / 外部 9.0** 达标线补全：<br>① **§3.9 核心类型清单**（12 个此前未定义的类型）<br>② **§3.10 扩展点与注册表**（扩展矩阵 + D15 插件决策）<br>③ **§3.11 模块健康度判据**（内聚/导出面/fan-out）<br>④ §3.2 补 `config` 层归属与 `RuntimeLimits` 切片<br>⑤ **§6.4 Profiling**、**§7.5 测试数据管理**<br>⑥ **§9.8.5 PII 分类**、**§9.8.6 配置变更审计**、**§9.10 多可用区与容灾姿态**<br>⑦ **§10.9 CHANGELOG 与 onboarding**<br>⑧ **附录 D 与运维手册的接口**、**附录 E 成熟度自评**<br>⑨ DoD 扩至 48 条 | 把"外置项"从"缺失"变成"有归属+有接口"，并补齐抽象与扩展性缺口 |
| **v1.4** | 只补 4 项二级缺口后**冻结**：<br>① 新增 **§6.3 指标基数与标签规范**（防多租户标签爆炸）<br>② 新增 **§9.8.4 密钥与敏感配置托管**（Secret 来源/校验/审计）<br>③ 新增 **§10.7 依赖故障隔离与熔断**（模型网关 + MCP）<br>④ 新增 **§10.8 文档由代码生成**（事件/指标/路由表 + CI 防漂移）<br>⑤ DoD 扩至 36 条 | 补完即冻结，转入执行（Phase 0） |
| **v1.3** | 按《[企业级项目设计参考](../../docs/企业级项目设计参考.md)》30 项清单对标（17✅/6⚠️/7❌）后补齐：<br>① 新增 **§8.4 数据所有权与生命周期**（所有权表 + TTL/删除 + 对账）<br>② 新增 **§9.8 安全补遗**（密钥轮换、HTTP body 上限、审计留存）<br>③ 新增 **§9.9 成本口径**（单位成本/token/租户归因）<br>④ 新增 **§10.6 协作与治理规则**（CODEOWNERS、PR 规范、技术债预算）<br>⑤ 新增 **§7.4 已实现能力回归清单**（6 项 ⚠️ 转为验收项）<br>⑥ DoD 扩至 **32 条**；运维类两项（备份/值班）明确划归独立运维手册 | 让"重构计划"覆盖上线前的数据/安全/治理缺口，同时不越界成运维手册 |
| **v1.2** | ① §5 阶段表与 §12 排期**对账**（24+5+3+5=37 人日 ≈ 7.5 周），Phase 标注所属轨道<br>② 新增 **§3.7 端口方法签名**（7 个端口的完整方法）<br>③ 新增 **§3.8 协作者签名**（attachments/usage/interrupts/result）<br>④ 新增 **§9.4–9.7**：灰度发布、API 弃用政策、多租户部署形态、容量模型换算<br>⑤ 修正 §6.1 CI 阶段列（0→2→4→6 与 Track B 对齐） | 消除"阶段与排期不一致""只有端口名没有方法"两类问题 |
| **v1.1** | ① 拆分为 **Track A（代码重构）/ Track B（生产就绪）** 双轨（§1.5）<br>② 新增 **结果指标与投入产出**（§1.4.2–1.4.3）<br>③ 新增 **终止与降级准则**（§1.6）<br>④ 新增 **原子性边界**：`RunLifecyclePort` 拥有 4-key 事务（§3.5）<br>⑤ 新增 **迁移与兼容矩阵**：`schema_version` + 滚动升级四象限（§8.1–8.3）<br>⑥ 新增 **容量与性能门禁**（§6.2）<br>⑦ 排期改为双轨 7–8 周，含功能冻结窗口（§12）<br>⑧ 补齐：供应链（SBOM/签名/依赖更新）、burn-rate 告警、看板即代码、`config` 向后兼容导出<br>⑨ 一致性修正：`infra` 依赖规则、端口数 7 个、新增 §3.6 端口契约摘要（`Delivery`/`EnqueueResult`/`AgentHandle`） | 评审发现 v1.0 把"分布式迁移"当成了"目录整理" |

---

## 一、目标、范围与成功判据

### 1.1 目标

把当前运行时升级为**"更好的设计 + 完整的能力"**，**允许破坏性变更**，但必须保证变更可迁移、可回滚、不丢数据。

三件事，缺一不可：

**A. 设计升级（结构）**

- 类型即契约：公共面无 `Any`，核心层可 `mypy --strict`；
- 边界可校验：分层依赖由测试守住，而不是靠约定；
- 核心可测：纯逻辑脱离 Redis / 模型 / 沙箱即可单测；
- 失败可判定：重试/死信由错误分类决定；
- 一条命令交付：CI + 镜像 + 探针 + 迁移。

**B. 能力完整（功能）**

- 对标 AgentScope Service 的 6 项能力全部补齐：会话回放、HITL 编辑参数、工作区隔离层级、后台工具卸载、协议适配（AG-UI/A2A）、运行时建队；
- 能力不是"有接口"，而是"**可灰度、可观测、可回滚、有预算上限**"。

**C. 直接演进（无历史包袱）**

- 项目**未上线**：无生产数据、无外部调用方、无历史版本，因此契约与数据结构**可直接调整**，不做兼容窗口、双写与迁移脚本；
- 但仍保留两条工程约束：**数据所有权唯一**（防两处写）、**生命周期明确**（防膨胀）。

> **与 v1.6/v1.7 的区别**：v1.6 要求"行为不变"，v1.7 要求"可迁移"，
> v1.8 明确"**未上线 → 直接演进**"，把迁移相关的流程成本全部去掉。

### 1.2 范围

| 在范围内 | 不在范围内 |
|---|---|
| `src/data_agent_runtime/` 的结构、类型、错误、配置 | 控制面（`java-agent-platform`） |
| 测试结构调整、契约测试、集成测试 | 依赖大版本升级（DeepAgents / LangChain） |
| 工具链配置、CI、Dockerfile、Helm/K8s 清单 | citations、产物下载等**业务功能**（归产品迭代） |
| 运维产物（告警、Runbook、ADR、看板） | 计费与账单（归产品侧） |
| **能力追平 6 项**（回放/隔离层级/HITL 编辑/后台卸载/协议适配/建队） | 音频/视频输入、Cron 调度、Schema 驱动前端 |

**能力面口径（v1.10）**：对照《Agent 服务能力与扩展点全景》的 **50 项能力**，本计划：

| 类别 | 项数 | 含义 |
|---|---|---|
| **改**（结构升级） | 34 | 已有能力，重构中只改结构不改行为（回归清单见 §7.6） |
| **加**（Track C） | 6 | 本次新增：回放 / 隔离层级 / HITL 编辑 / 后台卸载 / 协议适配 / 建队 |
| **补约束** | 6 | 已有能力但无设计（压缩/记忆/结构化输出/规划/自评/缓存），补"现状与约束"防误改（§3.12） |
| **不做 / 外置** | 5 | SDK/Webhook、模型路由降级、评估体系、Cron、工作流 DAG（§14） |

逐项状态见 **附录 H**。项目未上线，契约与数据结构可直接改（保留所有权与生命周期两条约束）。

### 1.3 不可退步的底线（v1.8）

**可以直接改**：HTTP 字段与行为、事件 schema、配置项、Redis Key 与 TTL、内部模块边界。
**不允许退步**的是下面四条：

| 底线 | 约束 | 违反后果 |
|---|---|---|
| **数据不丢** | 状态/事件/文件/Checkpoint 在单次升级内不丢失、不损坏（无历史数据，故无需跨版本迁移） | 运行期事故 |
| **任务可恢复** | 进程重启时在跑 Run 要么完成、要么回到队列重投，不得静默消失 | 用户感知"任务丢了" |
| **可靠性不降** | 幂等、三层租约、死信、At-least-once、不 ACK 语义不得退化 | 语义倒退 |
| **安全不收窄** | HMAC、双准入、SSRF/DNS 策略、沙箱隔离、租户归属校验不得放松 | 越权风险 |

**测试基线的含义**：不再是"165 个用例全绿"，而是
**"每个被替代的旧行为都有对应的新用例或明确说明"**——允许删除用例，但必须解释原因。

### 1.4 成功判据（可量化）

| 指标 | 现状 | 目标 |
|---|---|---|
| 公共面 `Any`（`api.py` + `core/` + `ports.py`） | 约 40 处 | **0** |
| 全仓 `Any` | 153 | ≤ 60（内部允许） |
| `except Exception` | 18 | **≤ 3**（仅进程顶层兜底） |
| 最大单文件行数 | 920（`executor.py`） | **≤ 300** |
| `pyproject.toml` 的 `[tool.*]` 段 | **0** | ruff / mypy / pytest / coverage 全配置 |
| 覆盖率 | 未统计 | **≥ 85%**（`core/` ≥ 95%） |
| CI 流水线 | 无 | lint → type → unit → integration → security → build 全绿 |
| 镜像 | 无 | 多阶段、非 root、含 HEALTHCHECK |
| 架构约束 | 无 | import 方向测试，违反即红 |
| 启动时间 | 未知 | P95 ≤ 3s（不含依赖探测） |

### 1.4.1 静态指标（过程指标）

上表所有判据都是**代码形态指标**——它们可自动化验证，但只能证明"改到位了"，
不能证明"改得值"。因此另设结果指标。

### 1.4.2 结果指标（价值指标）

| 指标 | 基线（当前） | 目标 | 采集方式 |
|---|---|---|---|
| 变更前置时间（改一个能力到上线） | 未度量，预估 3–5 天 | **≤2 天** | Git 提交 → 部署时间 |
| 新增能力所需改动文件数 | 3–6 个 | **≤3 个**（模块边界生效） | PR diff 统计 |
| 回归逃逸次数（上线后回滚/热修） | 未度量 | **0 次/季度** | 事故记录 |
| 新人上手到首个 PR | 未度量，预估 3–5 天 | **≤2 天** | 入职记录 |
| 单元测试运行时长 | 约 3s | **≤5s**（不得因重构变慢） | CI 计时 |
| 单 Run Redis 命令数 | 未度量 | 建立基线后 **不得劣化 >10%** | 见 §6.2 |
| Run P95 时延 | 未度量 | 建立基线后 **不得劣化 >10%** | 见 §6.2 |

### 1.4.3 投入产出

| 项 | 估算 |
|---|---|
| 总投入 | **12 人周**（重构 29 人日 + 能力追平 25 人日 + 缓冲 5 人日） |
| 直接收益 | 类型化减少编译期无法发现的契约错误；端口化使核心可脱离 Redis 测试；CI/镜像把"能跑"变成"能交付" |
| 可量化预期 | 新增能力改动文件数 ↓（6→3）、上手时间 ↓（5→2 天）、回归逃逸 ← 靠 CI + 契约测试收敛 |
| 不做的代价 | 每新增一个能力都要复制现有模式；契约变化靠联调；交付依赖手工，无法灰度 |

> **注意**：结果指标需要至少一个季度的观察才有统计意义。重构本身的验收仍以 §1.4.1 的静态指标为主，
> 结果指标用于**评估这次投入是否值得**，而不是阶段门禁。

### 1.4.4 成熟度达标线（v1.5 新增）

本文档以《[企业级项目设计参考](../../docs/企业级项目设计参考.md)》为标尺，设定两条验收线：

| 维度 | 达标线 | 自评（见附录 E） |
|---|---|---|
| **内部结构 6 项**（架构/抽象/扩展/分层/模块化/服务化） | **每项 ≥ 9.5** | 9.5 × 6 |
| **外部能力 13 域** | **每域 ≥ 9.0** | 13 域中 12 域 ≥9.0，1 域明确外置且接口已定义 |
| **能力完整（6 项）** | **6/6 可灰度、可观测、可回滚** | 见 §十五 验收 |


> 说明：外置项（备份恢复、值班事故）**不计为缺口**，但必须在附录 D 中写明归属方、接口要求与验收方式，
> 否则视为未达标——"有归属"和"没人管"是两件事。

### 1.5 双轨划分（v1.1 新增）

v1.0 把"代码重构"与"生产就绪建设"混在一个 6 阶段计划里，导致**风险与责任人错配**：
代码重构改的是内部结构，生产就绪改的是交付与运维能力，两者的回滚方式、验收标准、
失败影响面完全不同。v1.1 拆成两条并行轨道。

| | **Track A：代码重构** | **Track B：生产就绪** |
|---|---|---|
| 目标 | 类型、边界、可测性 | 可交付、可观测、可运维 |
| 内容 | Phase 0–4（工具链/类型化/端口/拆分/归位） | Phase 5（CI/镜像/K8s/告警/SLO/Runbook/供应链） |
| 改动面 | `src/` + `tests/` | `.github/`、`Dockerfile`、`deploy/`、`ops/` |
| 对线上影响 | 契约可直接改（未上线，无兼容负担） | 新增部署路径，可先只在预发启用 |
| 验收 | §1.4.1 静态指标 + 测试全绿 | 镜像可启动 + CI 六阶段 + 告警规则可加载 |
| 回滚 | `git revert` 单阶段 | 保留旧部署方式，镜像与清单可删 |
| 责任人角色 | 后端/平台工程师 | SRE / 平台工程师 |
| 可独立停止 | ✅ 任一阶段结束都可停 | ✅ 可只上 CI，不上 K8s |

**并行关系**：Track B 的 CI 部分（lint/type/test）**必须早于 Track A 的 Phase 1** 上线，
否则类型化与拆分没有门禁保护；其余（镜像/K8s/告警）可与 Track A 并行。

### 1.6 终止与降级准则（v1.1 新增）

重构最大的风险不是"做不完"，而是"做不完还不肯停"。预先定义停止条件：

| 触发条件 | 判定 | 动作 |
|---|---|---|
| Phase 1 结束时，事件类型化导致 >5 个用例长期红 | 设计不匹配 | **停止 P1**，回退到"事件加 `schema_version` + 保留 dict payload"，把类型化推迟 |
| Phase 2 结束时，契约测试暴露 >3 个真实现行为缺陷 | 存量质量问题 | **暂停端口化**，先修缺陷并补回归，再评估是否继续 |
| Phase 3 结束时，出现 >2 次线上/预发回归 | 拆分引入风险 | **停止拆分**，保留 `executor` 现状，仅完成 P0/P1 收益 |
| 任一阶段超出估算 **50%** | 估算失效 | 触发复盘；评估是否缩减后续阶段范围 |
| 连续两周无法投入（功能需求插队） | 资源冲突 | **冻结 Track A**，只保留 Track B（CI 门禁），下次窗口重启 |
| 某个能力项在灰度出现数据异常 | 能力缺陷 | **关闭该能力开关**（不回滚整体），修复后重新灰度 |

**降级路径**（保底收益）：即使 Track A 全部停止，P0（工具链 + 错误分类）与 Track B（CI + 镜像）
仍可独立交付并产生价值——这是本计划"可分段收敛"的设计意图。

---

## 二、现状基线

| 项 | 值 | 说明 |
|---|---|---|
| 源码 | **9,002 行 / 39 文件** | 最大 920 行（`runtime/executor.py`） |
| 测试 | **7,246 行 / 24 文件 / 165 passed + 4 skipped** | 全 mock，无集成测试 |
| 对外路由 | 15 条 | `/v1/runs*`、`/v1/files*`、`/v1/sessions*`、`/v1/memories*`、探针 |
| 事件类型 | 15 种 | 以裸字符串 + `dict` payload 表达 |
| 指标 | 8 个 | 无告警规则、无 SLO |
| 配置项 | **108 个环境变量** | 单层扁平 `Settings` |
| 工具链配置 | `pyproject.toml` **无任何 `[tool.*]` 段** | ruff 用默认、无 mypy、无覆盖率门禁 |
| 交付产物 | 无 CI / 无 Dockerfile / 无 K8s 清单 | —— |

**结论**：可靠性内核（幂等/租约/准入/隔离）是资产，**工程化与类型是欠账**。重构重心应放在后者，绝不动前者。

---

## 三、目标架构（中型 Python 项目标准）

### 3.1 分层（4 组 + 横切，不用 DDD 目录）

```
┌─ entrypoints ───────────────────────────────┐  api.py / worker_main.py / main.py
│  只做协议转换与进程生命周期                    │
├─ runtime（编排） ───────────────────────────┤  submit / execute / resume / cancel + 协作者
│  只依赖 core 与 ports                        │
├─ adapters ──────────────────────────────────┤  redis / sandbox / llm
│  实现 ports，唯一碰 IO 的地方                  │
├─ core（纯逻辑） ────────────────────────────┤  models / events / failures / documents / policies
│  无 IO、无 Settings、可 100% 单测              │
└─────────────────────────────────────────────┘
        ↑ infra（横切）：config / logging / tracing / metrics / signing
        ↑ wiring.py（唯一组合根）
```

### 3.2 依赖规则（由测试守住）

| 层 | 允许依赖 |
|---|---|
| `core` | 仅 stdlib + pydantic（**禁止 `infra`**，保持纯逻辑可单测） |
| `runtime` | `core` + `ports` + **`infra`（仅观测与配置读取，不含业务逻辑）** |
| `adapters` | `core` + `ports` + `infra` |
| `entrypoints` | `runtime` + `core` + `ports` + `infra`（实现只经 `wiring` 注入） |
| `infra` | 仅 stdlib + pydantic-settings（**禁止** import `core`/`runtime`/`adapters`） |
| `config`（`infra` 的配置子包） | 仅 stdlib + pydantic-settings；**只允许** `wiring`/`entrypoints`/`adapters`/`infra` 读取；`core` 与 `runtime` **只能**接收 `RuntimeLimits` 等只读切片 |
| `wiring` | 全部（唯一例外） |

**为什么 `infra` 允许被多层依赖**：日志、trace、指标是横切关注点，要求每层通过端口访问它们
会产生大量样板。约束改为"`infra` 不得包含业务逻辑、不得反向依赖上层"——这是可执行且实用的规则。

**不建立抽象的三个例外**（避免过度设计）：
`Clock`（无第二实现，测试用 `monkeypatch`）、`NetworkPolicy`（纯函数）、`Documents`（纯函数）。
判断标准仍是：**有第二个实现或需要测试替身，才建 Protocol**。

### 3.3 目标目录（新旧对照）

| 现状 | 目标 | 动作 |
|---|---|---|
| `schemas.py` | `core/models.py` + `core/events.py` | 拆分：边界模型 / 事件模型分离 |
| `runtime/admission.py` 的纯规则部分 | `core/policies.py` | 抽纯函数（输入 `Limits`，不读 Settings） |
| `runtime/documents.py` | `core/documents.py` | 移动（本就是纯函数） |
| 无 | `core/failures.py` | **新增**：错误分类体系 |
| 无 | `ports.py`（7 个 Protocol） | **新增**：RunLifecycle / Queue / State / Events / File / Sandbox / AgentFactory |
| `runtime/executor.py`（920 行） | `runtime/execute.py`（≤300）+ `runtime/attachments.py` + `runtime/usage.py` + `runtime/interrupts.py` + `runtime/result.py` | 拆分 |
| `api.py`（680 行）的业务守卫 | `runtime/submit.py` | 抽出限流/背压/准入编排 |
| `api.py` 路由 | 保留 `api.py`（目标 ≤ 250 行） | 只留路由与错误映射 |
| `runtime/{queue,state,events,files,ratelimit}.py` | `adapters/redis/*` | 端口实现下沉到 adapters |
| `runtime/memory.py` | `adapters/redis/memory.py` | 属于存储适配器，不属编排 |
| `runtime/metrics.py` | `infra/metrics.py` | 属于横切基础设施 |
| `clients/*` | `adapters/sandbox/*` | 移动并去掉对 `runtime` 的反向依赖（签名下沉到 `infra`） |
| `runtime/factory.py` | `adapters/llm/deepagents_factory.py` | 唯一 import DeepAgents 的地方 |
| `config.py` | `config/`（`base/redis/auth/sandbox/observability/limits`） | 分组 + 启动校验 |
| `runtime/bootstrap.py` + 手工装配 | `wiring.py` | 唯一组合根，消除 `app.state` 服务定位 |

### 3.4 目录树（目标态）

```
src/data_agent_runtime/
├── core/                  # 纯逻辑
│   ├── models.py          # AgentSnapshot / RunRequest / FileAttachment / RunStatus
│   ├── events.py          # EventType(StrEnum) + payload 模型 + RunEvent union
│   ├── failures.py        # RuntimeFailure 体系
│   ├── documents.py       # CSV / XLSX / PDF 解析（纯函数）
│   └── policies.py        # 准入规则（纯函数）
├── ports.py               # 7 个 Protocol + Delivery / EnqueueResult 等 dataclass
│                          # 拆分阈值：>300 行 或 >8 个端口时按域拆成 ports/ 包
├── adapters/
│   ├── redis/{queue,state,events,files,ratelimit,nonce}.py
│   ├── sandbox/{http,docker,kubernetes,local}.py
│   └── llm/deepagents_factory.py
├── runtime/               # 只放编排（不直接 import redis / httpx / deepagents）
│   ├── submit.py  execute.py  resume.py  cancel.py  worker.py
│   └── attachments.py  usage.py  interrupts.py  result.py
├── config/{base,redis,auth,sandbox,observability,limits}.py
├── infra/{logging,tracing,metrics,signing,network}.py
├── api.py  main.py  worker_main.py
└── wiring.py              # build_api(settings) / build_worker(settings)

# 仓库级文档（与代码同仓，见 §10.8）
docs/contracts/*.md        # 手写契约说明（语义/SLA/错误码含义）
docs/generated/*.md|json   # 由 scripts/gen_docs.py 生成，CI 校验无 diff
deploy/helm/...            # Helm chart + values-{env}.yaml（§9.2）
```

### 3.5 原子性边界（v1.1 新增，关键）

**问题**：现有实现把"幂等键、状态初始化、请求载荷、任务投递"放在**同一个 Lua 脚本**里，
审批同样跨"状态 + 载荷 + 投递"。若按 v1.0 的端口划分让 `QueuePort` 与 `StatePort` 各自发命令，
**原子性会被打碎**——而它正是 `run_id` 幂等与"受理即入队"的根基。

```python
# runtime/queue.py 现状（v1.0 计划未覆盖）
# 入队脚本：4 个 key 一次事务
SET   KEYS[1]   # claim            ← 幂等域
HSET  KEYS[2]   # state            ← 状态域
SET   KEYS[4]   # request payload  ← 载荷域
XADD  KEYS[3]   # stream           ← 队列域

# 审批脚本：3 个 key 一次事务
HGET state → GET payload → XADD → HSET state → DEL payload
```

**修订后的端口职责**：

| 端口 | 拥有的操作 | 是否跨域事务 |
|---|---|---|
| **`RunLifecyclePort`** | `enqueue(request)`（claim+state+payload+XADD）、`approve(run_id)`（state+payload+XADD） | ✅ **唯一**允许跨域 |
| `QueuePort` | `read` / `reclaim` / `ack` / `retry` / `dead_letter` / `depth` | 单 key |
| `StatePort` | `get` / `set_status` / `request_cancel` / 租约与配额（**事务外**） | 单 key 或同域多 key |
| `FilePort` / `EventPort` | 文件与事件 | 单 key |

**约束**：
1. `StatePort` **不得**参与入队/审批事务；状态初始化只由 `RunLifecyclePort` 在事务内完成；
2. `run/execute/submit` 只能通过 `RunLifecyclePort` 提交任务，禁止直接 `XADD`；
3. 事务脚本保留在 adapter 内部，端口只暴露语义方法（`enqueue` 而非 `xadd`）。

**必须新增的场景级契约测试**（普通端口契约测试覆盖不到）：

| 场景 | 断言 |
|---|---|
| 同一 `run_id` 并发 enqueue × 10 | 只有 1 条消息、1 份状态、1 份载荷；其余返回"已存在" |
| approve 与 cancel 并发 | 只有一方成功；状态与载荷一致（无悬空载荷） |
| enqueue 后立即崩溃（进程被杀） | 消息、状态、载荷三者同时存在（要么都在，要么都不在） |
| approve 时载荷缺失 | 状态转 `FAILED`，不投递 |
| 重复 approve | 幂等，不重复投递 |

> 结论：**端口的划分依据不是"数据属于谁"，而是"哪些操作必须在同一个事务里"。**
> 这一点在 v1.0 中被忽略，是本次修订最重要的技术改动。

### 3.6 端口契约摘要（v1.1 补充，避免"只有名字没有形状"）

| 类型 | 字段 / 方法 | 说明 |
|---|---|---|
| `Delivery`（dataclass） | `message_id` / `kind`（`run`\|`resume`）/ `request` / `decisions` / `attempt` / `trace` | 队列投递的统一形态，取代五元组 |
| `EnqueueResult` | `accepted: bool` / `stream_id: str \| None` / `reason: str \| None` | 幂等命中时 `accepted=False` + `reason="exists"` |
| `AgentHandle` | `aclose()` / `sandbox_provider: SandboxPort \| None` | `AgentFactoryPort.build()` 的返回值，编排层只依赖这两个能力 |
| `Metrics`（鸭子类型，不建 Protocol） | `run_accepted` / `run_finished` / `queue_retry` / `queue_dead_letter` / `tool_call` / `llm_tokens` / `record_queue_depth` | 由构造器注入；测试用 OTel `InMemoryMetricReader`，无 provider 时自动 no-op |
| `RunLifecyclePort` | `enqueue(request) -> EnqueueResult` / `approve(run_id) -> str` | **唯一**允许跨域事务的端口（见 §3.5） |

> 注：`AgentHandle` 不暴露 `agent` 对象本身——编排层不应直接操作图，只有 `adapters/llm` 知道它是什么。

### 3.7 端口方法签名（v1.2 新增）

> 只列方法签名与关键约束；实现细节留给 adapter。所有方法均为 `async`，异常统一抛 `RuntimeFailure` 子类。

```python
# ports.py —— 7 个 Protocol
class RunLifecyclePort(Protocol):
    """唯一允许跨域事务的端口（§3.5）。"""
    async def enqueue(self, request: RunRequest) -> EnqueueResult: ...
    async def approve(self, run_id: str) -> str: ...          # 返回 stream id
    async def reject(self, run_id: str, reason: str) -> None: ...

class QueuePort(Protocol):
    """只做单 key 操作；不负责入队/审批。"""
    async def read(self, consumer: str, *, count: int = 1) -> list[Delivery]: ...
    async def reclaim(self, consumer: str, *, min_idle_ms: int) -> list[Delivery]: ...
    async def renew_delivery(self, consumer: str, delivery: Delivery) -> None: ...
    async def ack(self, delivery: Delivery) -> None: ...
    async def retry(self, delivery: Delivery, *, delay_seconds: float) -> str: ...
    async def dead_letter(self, delivery: Delivery, failure: RuntimeFailure) -> str: ...
    async def depth(self) -> int: ...

class StatePort(Protocol):
    """事务外的状态读写；禁止参与 enqueue/approve 事务。"""
    async def get(self, run_id: str) -> RunState | None: ...
    async def set_status(self, run_id: str, status: RunStatus, **fields: Any) -> RunState: ...
    async def request_cancel(self, run_id: str) -> bool: ...
    async def is_cancel_requested(self, run_id: str) -> bool: ...
    # 租约与配额（各自独立 key）
    async def acquire_run_lease(self, run_id: str, worker: str, attempt: int) -> bool: ...
    async def renew_run_lease(self, run_id: str, worker: str) -> bool: ...
    async def release_run_lease(self, run_id: str, worker: str) -> None: ...
    async def acquire_session_lease(self, tenant: str, session: str) -> bool: ...
    async def release_session_lease(self, tenant: str, session: str) -> None: ...
    async def acquire_concurrency(self, principal: str, run_id: str, limit: int) -> bool: ...
    async def release_concurrency(self, principal: str, run_id: str) -> None: ...

class EventsPort(Protocol):
    async def publish(self, run_id: str, event: EventDraft) -> str: ...   # 返回 stream id
    async def read(self, run_id: str, cursor: str | None) -> list[RunEvent]: ...

class FilePort(Protocol):
    async def put(self, *, tenant_id: str, user_id: str | None, name: str,
                  media_type: str, data: bytes) -> FileMeta: ...
    async def get(self, *, tenant_id: str, file_id: str) -> StoredFile | None: ...
    async def delete(self, *, tenant_id: str, file_id: str) -> bool: ...

class SandboxPort(Protocol):
    """隔离执行；实现必须在容器/Pod 内执行，禁止在宿主执行调用方命令。"""
    async def ensure_created(self) -> SandboxCreateResponse: ...
    async def write_file(self, path: str, content: bytes, *, encoding: str = "utf-8") -> SandboxFileResponse: ...
    async def read_file(self, path: str) -> bytes: ...
    async def run(self, executable: str, args: Sequence[str], *,
                  timeout_seconds: int | None = None,
                  max_output_bytes: int | None = None) -> SandboxCommandResult: ...
    async def collect_artifact(self, path: str, *, name: str | None = None) -> SandboxArtifact: ...
    async def destroy(self) -> None: ...
    async def aclose(self) -> None: ...

class AgentFactoryPort(Protocol):
    """唯一允许 import DeepAgents 的地方（实现位于 adapters/llm）。"""
    async def build(self, *, snapshot: AgentSnapshot, run_id: str, session_id: str,
                    tenant_id: str, checkpointer: Any, store: Any,
                    memories: Any, files: FilePort) -> AgentHandle: ...
```

**约束三条**：
1. 端口只暴露**语义方法**（`enqueue` 而非 `xadd`），Redis 命令细节不出 adapter；
2. 所有方法必须有超时（实现内部 `asyncio.timeout`），端口签名不暴露超时参数——由部署配置决定；
3. 端口方法抛 `RuntimeFailure` 子类，不抛 `redis.RedisError` 等实现细节。

### 3.8 协作者签名（v1.2 新增）

编排层拆出的四个模块，签名先定死，Phase 3 只做搬家不做设计：

```python
# runtime/usage.py —— 纯函数，可 100% 单测
def normalise(raw: Mapping[str, Any] | None) -> Usage | None: ...
def from_event(event: Mapping[str, Any]) -> tuple[str, Usage] | None: ...
def merge(target: Usage, model_name: str, usage: Usage) -> Usage: ...

# runtime/attachments.py
@dataclass(frozen=True)
class LoadedAttachments:
    injected_text: str                    # 拼进用户消息的文本段
    images: list[dict[str, Any]]          # LangChain 多模态块
    raw: list[RawFile]                    # 用于写入沙箱
async def load(request: RunRequest, files: FilePort, limits: AttachmentLimits) -> LoadedAttachments: ...
async def materialise(handle: AgentHandle, loaded: LoadedAttachments, run_id: str) -> None: ...
    # 写沙箱失败只告警（文本已注入），不使 Run 失败

# runtime/interrupts.py
@dataclass(frozen=True)
class PendingInterrupt:
    interrupt_id: str
    request: dict[str, Any]
async def detect(agent: HasState, config: RunConfig) -> list[PendingInterrupt]: ...
    # 无中断返回 []；检测本身不得吞异常

# runtime/result.py —— 纯函数
@dataclass(frozen=True)
class RunResult:
    answer: str
    structured: Any | None
    todos: list[dict[str, Any]] | None
    async_tasks: dict[str, Any] | None
    usage: Usage | None
def build(output: Any, usage: Usage | None) -> RunResult: ...
```

### 3.9 核心类型清单（v1.5 新增）

> §3.7/§3.8 的签名引用了下列类型，此前只有名字没有字段。这里一次性定义，
> **实现阶段只允许按此实现，不允许重新设计**。内部类型用 `dataclass(frozen=True)`，边界类型用 `pydantic`。

| 类型 | 形态 | 字段 / 方法 | 用途 |
|---|---|---|---|
| `RunState` | pydantic | `run_id` / `tenant_id` / `session_id` / `status: RunStatus` / `agent_id` / `agent_version` / `attempt` / `cancel_requested` / `wait_reason` / `error_code` / `created_at` / `updated_at` | 状态投影（Redis Hash 映射） |
| `Usage` | frozen dataclass | `input_tokens` / `output_tokens` / `total_tokens` / `reasoning_tokens: int = 0` | token 计量 |
| `EventDraft` | pydantic（union） | 各事件的 payload 字段；**不含** `run_id` / `sequence` / `created_at` / `schema_version` | 编排层发布事件时的草稿 |
| `FileMeta` | pydantic | `file_id` / `name` / `media_type` / `size` / `created_at` | 文件元数据（对外） |
| `StoredFile` | frozen dataclass | `meta: FileMeta` / `data: bytes` | 文件读取结果（对内） |
| `SandboxCreateResponse` | frozen dataclass | `sandbox_id` / `endpoint: str \| None` / `expires_at: datetime \| None` | 沙箱创建结果 |
| `SandboxCommandResult` | frozen dataclass | `exit_code: int` / `stdout: str` / `stderr: str` / `duration_ms: int` / `truncated: bool` | 命令执行结果 |
| `SandboxArtifact` | frozen dataclass | `path` / `name: str \| None` / `size_bytes` / `sha256: str \| None` / `download_url: str \| None` | 产物引用 |
| `AttachmentLimits` | frozen dataclass | `max_files` / `max_chars` / `preview_rows` / `allowed_media_types: frozenset[str]` | 附件处理上限（从 config 切片而来） |
| `RawFile` | frozen dataclass | `name` / `media_type` / `data: bytes` | 附件原始字节（落沙箱用） |
| `HasState` | Protocol | `async def aget_state(config: RunConfig) -> Any` | 中断检测所需的最小 Agent 能力，避免依赖具体 Agent 类型 |
| `RunConfig` | frozen dataclass | `thread_id` / `run_id` / `recursion_limit` / `timeout_seconds` / `callbacks: tuple = ()` | 传给 Agent 的运行配置 |

**命名与不可变约定**：
1. 所有跨层传递的类型必须 `frozen`（pydantic 用 `model_config = ConfigDict(frozen=True)`）；
2. 禁止在端口签名里出现 `dict[str, Any]`；确需扩展点用显式字段或 `Mapping[str, str]`；
3. `RunStatus` 用 `StrEnum`，状态迁移只允许经 `StatePort.set_status`。

### 3.10 扩展点与注册表（v1.5 新增）

**目标**：让"加一个东西"有明确路径，而不是每次重新发明。

| 扩展类型 | 需要实现 | 注册位置 | 改动文件数 | 是否支持第三方 |
|---|---|---|---|---|
| 沙箱后端 | `SandboxPort`（7 方法） | `wiring.py` 的 provider 注册表 | 2 | ❌（需改源码） |
| 模型 provider | `adapters/llm/*` + 模型白名单 | `adapters/llm/registry.py` | 2–3 | ❌ |
| 工具 | 无需实现（MCP 声明） | Snapshot 的 `mcp_servers` | **0** | ✅（配置级） |
| 事件类型 | `core/events.py` 的 payload + `EventType` | 事件 union 自动纳入 | 2 + 下游 | ❌ |
| 协议接入（AG-UI / A2A） | 新增 `adapters/protocol/*` | `wiring.py` | 新增层 | ❌（预留） |
| 存储后端 | `QueuePort`/`StatePort`/`FilePort` + `RunLifecyclePort` | `wiring.py` | 4–6 | ❌ |

**D15 决策：不引入动态插件机制（`entry_points`）**

| 理由 | 说明 |
|---|---|
| 无第三方需求 | 当前所有扩展都在本仓库内完成 |
| 启动确定性 | 动态发现会让"加载了哪些实现"依赖环境，难排查 |
| 安全面 | 插件等于任意代码执行，需要签名与审计机制，成本远高于收益 |
| 预留路径 | 若将来需要，在 `wiring.py` 之上加一层 `entry_points` 适配即可，**端口不变** |

**验收**：① 六类扩展在表中都能找到路径；② 新增 provider 的 PR 只改 `adapters/*` + `wiring.py`；③ §14 明确"不引入动态插件"。

### 3.11 模块健康度判据（v1.5 新增）

> 只靠"文件 ≤300 行"衡量模块化是不够的，补四条可检查的判据。

| 判据 | 阈值 | 检查方式 |
|---|---|---|
| 单文件行数 | ≤300（`api.py` ≤250） | 静态度量，CI 失败 |
| 单一变更原因 | 一个模块只对应一类变更（存储/协议/编排/解析） | 代码评审 + CODEOWNERS |
| 导出面受控 | 包级 `__all__` 白名单，禁止 `import *` | ruff 规则 + 评审 |
| 扇出（fan-out） | 单模块直接依赖的兄弟模块 ≤7 | `scripts/module_health.py`（import 图统计） |

**补充规则**：同一模块**每月变更 ≥3 次**时，评审必须回答"是否该拆分"——高频变更是最强的内聚反证。

### 3.12 已有能力约束（v1.10 新增）

> 这 6 项能力**代码里已经实现**，但计划此前没有描述。重构时最容易被"顺手改好"或"顺手删掉"，
> 所以这里只写**现状与约束**，不写改造方案——本次重构对它们的要求是**行为不变**。

#### 3.12.1 上下文压缩

| 项 | 内容 |
|---|---|
| 现状 | 摘要中间件，只消费 `trigger_tokens` |
| 约束 | `keep_recent_messages` / `summary_max_tokens` / `persist_summary` 三个字段**契约里有、代码里无消费者** |
| 本次不改 | 不实现这三个字段，也不删除它们（删除是契约变更，需单独决策） |
| 误改风险 | 以为字段生效而"顺手接上"，会改变上下文行为与成本 |

#### 3.12.2 记忆

| 项 | 内容 |
|---|---|
| 现状 | 会话历史（List，按会话上限裁剪）+ 长期记忆（条目上限，尾部 N 条） |
| 约束 | **没有相关度召回**，读取顺序即写入顺序；写入只能经 API |
| 本次不改 | 不引入向量召回、不做自动抽取 |
| 误改风险 | 改动读取顺序或裁剪策略，会让"记忆"表现突变 |

#### 3.12.3 结构化输出

| 项 | 内容 |
|---|---|
| 现状 | `response_format` 透传给 Agent 框架，终态透出 `structured` |
| 约束 | **没有校验失败重试**；输出不合规直接失败 |
| 本次不改 | 不加重试/纠错（属能力扩展，需单独立项） |
| 误改风险 | 加"重试"会改变时延与调用次数，影响成本与超时语义 |

#### 3.12.4 规划 / Todo

| 项 | 内容 |
|---|---|
| 现状 | `plan.todo_tool` 控制 `TodoListMiddleware`，**默认关闭** |
| 约束 | 开启后 `todos` 随终态透出；关闭时不产生任何 Todo 事件 |
| 本次不改 | 不改默认值（默认关闭是升级安全的一部分） |
| 误改风险 | 把默认改成开启，会让所有旧快照多出工具与事件 |

#### 3.12.5 自评迭代

| 项 | 内容 |
|---|---|
| 现状 | `rubric` 触发 `RubricMiddleware`，每轮迭代**额外一次模型调用** |
| 约束 | 必须保持**显式开启**；关闭时不得产生额外调用 |
| 本次不改 | 不改评分策略、不改模型 |
| 误改风险 | 默认开启或隐式触发，会让 token 成本接近翻倍 |

#### 3.12.6 参数与缓存

| 项 | 内容 |
|---|---|
| 现状 | prompt caching 由 Agent 框架装配链**无条件追加**，按 provider 生效 |
| 约束 | 运行时**既不能关也不能调**；只能在文档里声明"不可控" |
| 本次不改 | 不尝试接管缓存策略（接管需绕过框架装配） |
| 误改风险 | 重构装配顺序时"顺手去掉"，会悄悄增加 token 成本 |

---

## 四、关键技术决策（ADR 摘要）

| # | 决策 | 选项 | 结论与理由 |
|---|---|---|---|
| D1 | 是否采用 DDD 分层（domain/application/infrastructure） | 采用 / 不采用 | **不采用**。无聚合、无仓储需求；`core` 只表达"纯数据 + 纯规则"，避免仪式化 |
| D2 | 抽象用 `Protocol` 还是 `ABC` | Protocol / ABC | **Protocol**。结构化鸭子类型，适配器无需继承，测试替身零成本 |
| D3 | 边界模型用 pydantic 还是 dataclass | pydantic / dataclass | **边界用 pydantic**（校验 + schema 生成），**内部用 dataclass**（轻量、不可变） |
| D4 | 是否引入 DI 容器 | 引入 / 不引入 | **不引入**。单组合根 + 构造器注入足够；容器会让调用链难追踪 |
| D5 | 错误用异常还是 Result | 异常 / Result | **异常 + 分类**（`retryable`/`http_status`）。Python 生态惯例；Result 会给每层加样板 |
| D6 | 事件用 `StrEnum + union` 还是裸 dict | — | **`StrEnum` + Pydantic union**，SSE 序列化集中一处，前端可直接生成类型 |
| D7 | 配置是否分组 | 扁平 / 分组 | **分组**（6 组），并在 `model_post_init` 做跨字段校验，启动期失败 |
| D8 | 是否重排目录 | 重排 / 渐进 | **渐进**：先加 `core`/`ports`/`wiring`，最后一步才移动文件（单独 commit 保 blame） |
| D9 | mypy 策略 | 全仓 strict / 分层 strict | **分层**：`core`+`api`+`ports` 先 strict，其余渐进 |
| D10 | 集成测试用什么 | testcontainers / docker compose / 真实环境 | **docker compose 提供的 Redis**（CI service），不引入 testcontainers 依赖 |

---

## 五、分阶段计划

### 5.1 轨道归属与工时对账（v1.2 新增）

| 阶段 | 轨道 | 人日 | 时间窗 | 说明 |
|---|---|---|---|---|
| Phase 0 工具链与类型地基 | **Track A** | 3 | W1 | 与 Track B 的 lint/type 同步落地 |
| Phase 1 契约类型化 | **Track A** | 4 | W2 | 含 `schema_version` |
| Phase 2 端口与适配器 | **Track A** | 4 | W3 | 含原子性场景契约测试 |
| Phase 3 编排拆分 | **Track A** | 5 | W4 | 依赖 P2 稳定 ≥3 天 |
| Phase 4 目录归位与组合根 | **Track A** | 3 | W5 | 单独"纯移动"commit |
| Phase 5 交付与运维 | **Track B** | 5 | W1/W4–W8 | **不是五天连做**，而是 Track B 的收口 |
| Phase 6 能力追平 | **Track C** | 25 | W4–W12 | 依赖 P1 事件类型化 + P2 端口 |
| 存量测试补齐（覆盖率 → 85%） | Track A 延伸 | 5 | W6–W7 | v1.0 未计入 |
| **Phase 6 能力追平（6 项）** | **Track C** | **25** | W4–W10 | v1.7 纳入范围 |
| 缓冲（回归修复、文档收口） | —— | 5 | W11–W12 | 预留约 8% |
| **合计** | | **59 人日 ≈ 12 周** | W1–W12 | 与 §12 排期一致 |

> v1.8 起总工期 = 重构 29 人日（P0–P5 + 测试补齐）+ 能力追平 25 人日 + 缓冲 5 人日 = **59 人日 ≈ 12 周**。
> 去掉了 v1.7 的迁移/联调 3 人日——项目未上线，无兼容包袱。**Phase 6 属于 Track C**，P1/P2 完成后启动。

> 每阶段结束的**统一验收**：`./scripts/verify.sh` 全绿（163+ 用例）+ `ruff check` 通过 + 新增度量达标 + 阶段文档更新。

### Phase 0（Track A）：工具链与类型地基（3 天）

| 项 | 内容 |
|---|---|
| 目标 | 让"类型与规范"可被机器检查 |
| 改动 | ① `pyproject.toml` 增加 `[tool.ruff]`（含 `ASYNC`/`S` 规则集）、`[tool.mypy]`（分层 strict）、`[tool.pytest.ini_options]`（markers：`unit`/`integration`/`p0`）、`[tool.coverage]`（`fail_under=85`，`core` 单独 95）；② 新增 `core/failures.py` 并让现有异常继承；③ `pip-audit`/`bandit` 纳入 CI 预备 |
| 验收 | `ruff check` 0 错误；`mypy` 对 `core/`+`api.py` 0 错误；覆盖率报告可生成 |
| 风险 | mypy 存量错误过多 → 先用 `per-module` 白名单，逐步放开 |
| 回滚 | 纯配置，`git revert` 即回退 |

### Phase 1（Track A）：契约类型化（4 天）

| 项 | 内容 |
|---|---|
| 目标 | 事件、错误、投递对象从"字符串 + dict"变为强类型 |
| 改动 | ① `core/events.py`：`EventType(StrEnum)` + 15 个 payload 模型 + `RunEvent` union；② `EventPublisherPort.publish(event: RunEvent)`；③ 全仓替换 `events.publish(run_id, "x", {...})` 调用点（约 30 处）；④ SSE 序列化改由模型统一 `model_dump_json()`；⑤ `Delivery` dataclass 取代 `parse_message` 五元组 |
| 验收 | 公共面 `Any` 归零；新增"事件 schema 快照测试"（防契约漂移）；165+ 用例全绿 |
| 风险 | 调用点遗漏 → 用 `grep publish(` 清单逐项核对 + 类型检查兜底 |
| 回滚 | 保留旧 `publish` 一周作为过渡（deprecation 注释） |

### Phase 2（Track A）：端口与适配器（4 天）

| 项 | 内容 |
|---|---|
| 目标 | 核心可脱离 Redis / Agent 测试 |
| 改动 | ① `ports.py` 定义 7 个 Protocol + 数据类；② `adapters/redis/*` 实现 Queue/State/Events/File 端口（现有代码平移 + 类型标注）；③ `adapters/llm/deepagents_factory.py` 实现 `AgentFactoryPort`；④ 删除手写 `FakeRedis`，改用内存 fake + **契约测试**（同一套断言跑真实现与 fake） |
| 验收 | 每个端口 ≥ 6 条契约断言；`runtime` 层不再 import `redis`；集成测试（真 Redis）通过 |
| 风险 | 契约测试暴露真实现行为差异（如 TTL 语义）→ 以此为准修正 fake |
| 回滚 | 端口是新增文件，可并行保留旧实现 |

### Phase 3（Track A）：编排拆分（5 天）

| 项 | 内容 |
|---|---|
| 目标 | 单文件 ≤300 行；`api.py` 只做协议转换 |
| 改动 | ① `runtime/execute.py`（骨架 ≤300）；② 拆出 `attachments.py`（加载/解析/沙箱落盘）、`usage.py`（token 汇总，纯函数）、`interrupts.py`（中断检测与待决策）、`result.py`（answer/structured/todos 组装）；③ `runtime/submit.py`：限流/背压/准入编排从 `api.py` 搬出；④ `api.py` 只留路由 + 异常映射表 |
| 验收 | 每文件 ≤300 行；`api.py` ≤250 行；用例数不减（可增）；纯函数单测覆盖 ≥95% |
| 风险 | 拆分导致隐式状态丢失 → 每拆一个模块就跑一次全量测试 |
| 回滚 | 按模块粒度提交，可单独 revert |

### Phase 4（Track A）：目录归位与组合根（3 天）

| 项 | 内容 |
|---|---|
| 目标 | 目标目录落地，依赖方向可校验 |
| 改动 | ① 文件移动到 `core/`、`adapters/`、`config/`、`infra/`；② `wiring.py` 提供 `build_api()`/`build_worker()`；③ `AppContext` 取代 33 处 `app.state`；④ 新增 `tests/test_architecture.py`（import 方向断言）；⑤ 修正 `adapters/sandbox` 对 `runtime` 的反向依赖（签名/追踪下沉 `infra`） |
| 验收 | 架构测试通过；`git log --follow` 可追溯（移动与修改分开提交） |
| 风险 | 大范围移动导致 review 困难 → **单独一次"纯移动"commit**，不改内容 |
| 回滚 | 该阶段单独分支，可整体放弃 |

### Phase 5（Track B）：交付与运维（约 5 人日，摊在 W1/W4–W8）

| 项 | 内容 |
|---|---|
| 目标 | 一条命令构建、可观测可运维 |
| 改动 | ① CI 六阶段（lint/type/unit/integration/security/build）；② 多阶段 `Dockerfile`（非 root、tini、HEALTHCHECK）；③ K8s 清单（探针、`terminationGracePeriodSeconds` > drain 超时、PDB、resources、topologySpread）；④ 告警规则（队列水位/死信/失败率/P95）+ SLO 文档；⑤ Runbook（队列堆积、死信重放、租约异常）；⑥ ADR 目录（D1–D10 各一页） |
| 验收 | CI 全绿；镜像可跑通 `/v1/health`；`kubectl apply --dry-run=server` 通过；告警规则语法校验通过 |
| 风险 | 镜像体积/启动时间 → 只装运行时依赖（`uv sync --frozen --no-dev`） |
| 回滚 | 交付物独立，可先只上 CI |

### Phase 6（Track C）：能力追平 6 项（25 人日，W4–W12）

| 项 | 内容 |
|---|---|
| 目标 | 补齐对标 AgentScope Service 的 6 项能力，且可灰度、可观测、可单独关闭 |
| 前置 | Phase 1（事件类型化）、Phase 2（端口）完成 |
| 改动 | ① 会话事件回放（会话级流 + `Last-Event-ID`）<br>② HITL 编辑参数（`edit` 决策 + schema 校验 + 审计）<br>③ 工作区隔离层级（Run/Session/User/Tenant）<br>④ 后台工具卸载（超时转后台 + 恢复机制唤醒）<br>⑤ 协议适配（`adapters/protocol/`：AG-UI/A2A）<br>⑥ 运行时建队（leader spawn 子 Run + 能力收窄 + 预算） |
| 验收 | §十五 的 10 条 DoD；每项独立灰度开关与回滚路径 |
| 风险 | 建队成本放大 → 默认关闭 + 硬预算 + 单租户灰度；协议适配映射错 → 快照测试 |
| 回滚 | 每项独立开关，可单独关闭而不回滚整个版本 |

---

## 六、度量看板（重构前后）

### 6.1 代码形态与过程指标

| 指标 | 基线 | P0 后 | P2 后 | P3 后 | 目标 |
|---|---|---|---|---|---|
| 公共面 `Any` | ~40 | 40 | 10 | 5 | **0** |
| 全仓 `Any` | 153 | 153 | 120 | 90 | ≤60 |
| `except Exception` | 18 | 10 | 8 | 4 | ≤3 |
| 最大文件行数 | 920 | 920 | 900 | **≤300** | ≤300 |
| `[tool.*]` 配置段 | 0 | 4 | 4 | 4 | ≥4 |
| 测试用例 | 165 | 170 | 190 | 200 | ≥200 |
| 契约测试 | 0 | 0 | 6 组 | 6 组 | ≥6 |
| 集成测试 | 0 | 0 | 3 | 5 | ≥5 |
| 覆盖率 | — | 报告可用 | 80% | 85% | ≥85% |
| CI 阶段 | 0 | 2（lint+type，Track B W1） | 4 | 6 | 6 |
| **单 Run Redis 命令数** | 基线待测 | 记录 | ≤基线×1.1 | ≤基线×1.1 | ≤基线×1.1 |
| **提交 P95 时延** | 基线待测 | 记录 | ≤800ms | ≤800ms | ≤800ms |
| **`schema_version` 覆盖** | 0 | 事件 | 事件+消息 | 全部 | 全部 |

### 6.2 容量与性能门禁（v1.1 新增）

**问题**：v1.0 只有"启动 ≤3s"。重构最容易引入的退化是**每轮循环多打几次 Redis**、
事件发布从 1 次变 2 次（thinking 分流）、`aget_state` 调用上升——这些只有压测能发现。

#### 6.2.1 必须建立的基线（Week 1 内完成）

| 指标 | 采集方式 | 用途 |
|---|---|---|
| 单 Run Redis 命令数（按命令分类） | `redis-cli INFO commandstats` 差值 / 单 run | 防 N+1 |
| 单 Run `aget_state` 调用次数 | 代码埋点 / trace 计数 | 防状态查询膨胀 |
| 提交接口 P50/P95 时延 | 压测脚本 | 防受理路径变慢 |
| 单 Worker 吞吐（Run/分钟，mock 模型） | 压测脚本 | 防编排变慢 |
| 队列积压恢复时间（10k 任务） | 压测脚本 | 容量模型 |
| 内存常驻（RSS，稳定态） | 容器监控 | 防泄漏 |

#### 6.2.2 冒烟压测（每次合并到 main 触发）

```bash
# 目标：30 秒内跑完，作为 CI 的一个阶段（不阻塞主流程，但失败告警）
python scripts/loadtest_smoke.py \
  --runs 200 --concurrency 20 \
  --assert-p95-ms 800 --assert-redis-cmds-per-run 40
```

门禁阈值：

| 指标 | 硬阈值 | 软告警 |
|---|---|---|
| 提交 P95 | ≤ 800ms | > 600ms |
| 单 Run Redis 命令数 | ≤ 基线 × 1.1 | > 基线 × 1.05 |
| 单 Run `aget_state` 次数 | ≤ 3 | > 2 |
| 冒烟吞吐 | ≥ 基线 × 0.9 | < 基线 |

> 压测使用**假模型**（返回固定响应）与**内存端口**，不消耗真实 token；
> 真实端到端压测放在季度演练，不放进 CI。

#### 6.2.3 重构期规则

- 每个 Phase 合并前后各跑一次冒烟压测，把数据记入 §6 度量看板；
- 超过硬阈值 → 该 Phase 不得合并；
- 基线本身若在 Phase 0 发现已不达标（如单 Run Redis 命令数过高），先记录为技术债，不在本次重构中优化。

### 6.3 指标基数与标签规范（v1.4 新增）

**问题**：多租户环境下把 `tenant_id` / `run_id` / `session_id` 作为指标标签，会让时间序列数量随租户与请求线性增长，
最终拖垮指标后端（内存、查询、抓取超时）。这类问题上线后才暴露，且很难回退。

#### 6.3.1 标签白名单（只允许有界值）

| 允许的标签 | 取值来源 | 说明 |
|---|---|---|
| `status` | 枚举（completed/failed/cancelled/…） | 有界 |
| `token.type` | 枚举（input/output/reasoning） | 有界 |
| `model` | **白名单内**的模型名（来自 `ALLOWED_MODEL_PROVIDERS` 解析结果） | 需校验，不接受任意字符串 |
| `tool.name` | 内置工具白名单；MCP 工具按 server 名（非函数名） | 有界 |
| `queue.kind` | 枚举（run/resume） | 有界 |
| `dependency` | 枚举（model/mcp/sandbox/redis） | 有界 |

**禁止作为标签**：`tenant_id`、`user_id`、`run_id`、`session_id`、任意 URL/路径、错误消息原文、任意用户输入。

#### 6.3.2 无界维度怎么观测

| 需求 | 做法 |
|---|---|
| 按租户看用量 | 日志字段 + trace 属性（不受基数限制）；或用**独立聚合**（每租户一个计数器，仅当租户数 <50） |
| 定位单个 Run | trace（`run_id` 作为 span 属性）与日志，不做指标标签 |
| 错误详情 | 日志与事件 payload，指标只记分类（`error.class`） |

#### 6.3.3 基数上限与门禁

| 项 | 阈值 |
|---|---|
| 每个指标的时间序列 | ≤ 1,000 |
| 全部指标序列总数 | ≤ 5,000 |
| CI 检查 | 静态扫描 `metrics.py` 的仪器标签名，命中禁止清单即失败 |
| 运行时保护 | 新增标签前必须过白名单校验函数（`infra/metrics.py` 内断言） |

**验收**：① 新增指标必须通过标签白名单检查；② `/metrics` 导出的 series 数 < 5,000；③ 压测 100 租户后 series 数不随租户数线性增长。

### 6.4 Profiling 与热点分析（v1.5 新增）

| 项 | 规则 |
|---|---|
| 触发条件 | P95 回归 >10%、CPU 持续 >70%、内存较上版本增长 >20% |
| 工具 | `py-spy`（线上采样，无需重启）、`cProfile`（函数级）、`tracemalloc`（内存） |
| 输出 | `docs/perf/profile-YYYYMMDD.md`：热点函数、占比、结论、是否需优化 |
| 频率 | 每次大版本发布前一次；热点变化时随时 |
| 禁止 | 用 profiling 结论替代压测；profiling 只在预发或采样模式下进行 |

**验收**：① 每个大版本有一份 profile 记录；② 优化项有前后对比数据。

---

## 七、测试策略

### 7.1 金字塔

| 层 | 数量目标 | 工具 | 说明 |
|---|---|---|---|
| 单元（纯逻辑/协作者/路由） | ≥140 | pytest | 不依赖 Redis/模型 |
| 契约（每个 Port 真实现 + fake） | ≥6 组 | pytest + 内存 fake + 真 Redis | 防 fake 漂移 |
| 集成（真 Redis） | ≥5 | pytest + docker compose | 队列/租约/幂等/死信 |
| 属性测试 | ≥3 | hypothesis | 文档解析器、用量归一化 |
| 故障注入 | ≥4 | respx / monkeypatch | Redis 超时、模型 500、沙箱不可达 |

### 7.2 标记与执行

```toml
[tool.pytest.ini_options]
markers = ["unit", "integration", "p0", "slow"]
addopts = "-q --strict-markers"
```

- 本地默认：`pytest -m "not integration"`（约 3 秒）
- CI：先 `not integration`，再起 Redis service 跑 integration
- P0（可靠性）套件保留 `SIGALRM` 逐用例超时（已有）

### 7.3 覆盖率门禁

| 范围 | 门槛 |
|---|---|
| 全仓 | 85% |
| `core/` | 95% |
| `runtime/` 编排 | 80%（含分支） |

### 7.4 已实现能力的回归清单（v1.3 新增）

> 这 6 项**不是缺失**，而是"已实现但计划未纳入验收"——重构最容易让它们悄悄退化。
> 每项都必须有对应的自动化断言，否则视为完成度不足。

| # | 能力 | 现状 | 回归方式 | 纳入阶段 |
|---|---|---|---|---|
| 1 | 外部调用超时 | Redis 已配；HTTP 部分依赖客户端默认 | 自定义 lint/测试：扫描 `httpx`/`redis` 调用必须带 timeout；或启动期断言 | Phase 0 |
| 2 | 过载保护 | 限流 429 + 背压 503 已实现 | 集成测试：mock 深度超阈值 → 503；超限流 → 429 + `Retry-After` | Phase 1 |
| 3 | 日志关联 ID | 已注入 `run_id`/`request_id`/`traceparent` | 断言规范字段：日志样例必须含三者；缺失即测试失败 | Phase 2 |
| 4 | 资源归属校验 | `_state_owner` 等已实现 | 安全回归：跨租户读 run/file/session/memory 必须 403/404 | Phase 3 |
| 5 | 请求体上限 | **未实现**（见 §9.8.2） | 413 用例 + 分块传输中断用例 | Phase 0 |
| 6 | 数据结构变更 | 未上线，可直接改 | PR 模板勾选"是否触及数据结构"；改动后更新 §8.3 所有权/生命周期表 | 全程 |

### 7.5 测试数据管理（v1.5 新增）

| 项 | 规则 |
|---|---|
| 工厂 | `tests/factories.py` 提供 `make_request()` / `make_snapshot()` / `make_run_state()`，默认值合理、可局部覆盖 |
| 禁止 | 任何生产数据进入测试（含脱敏后）；CI 不连生产环境 |
| 脱敏 | 若必须用采样数据，先在 `scripts/anonymize.py` 处理后入库，并记录来源与处理方式 |
| 确定性 | 固定随机种子（`random.seed` / `Faker.seed`），时间用 `time-machine` 冻结 |
| 隔离 | 每个用例独立租户 id（如 `t-test-{uuid}`），避免测试间串数据 |

**验收**：① 测试不依赖外部网络与生产数据；② 同一用例重复运行 10 次结果一致。

### 7.6 能力回归清单（34 项，v1.10 新增）

> 附录 H 中状态为 ✅ 的 34 项能力，重构期间**必须保持行为不变**。
> 每项至少 1 个自动化断言；没有的，在 Phase 3 之前补齐。
> 编号与附录 H 一致。

| # | 能力 | 回归方式（断言） |
|---|---|---|
| 3 | 限流 / 配额 / 背压 | 超限返回 429 + `Retry-After`；队列水位超阈返回 503 |
| 4 | 协议适配（AG-UI / A2A） | 事件映射快照测试；未知事件不影响主流程 |
| 6 | 文件上传与附件 | 上传 201 / 超限 413 / 解析注入 / 图片多模态块 / 缺失文件失败 |
| 7 | 会话生命周期 | 创建-读取-删除闭环；TTL 到期后不可读 |
| 8 | 历史与回放 | 历史按会话隔离；回放断线重连不重不漏（含截断标记） |
| 11 | 工作区 | 四层隔离可见性符合预期；路径穿越被拒；清理无残留 |
| 12 | Agent 循环 | mock 模型端到端跑通一次 Run，事件序列符合预期 |
| 13 | 工具调用 | MCP 白名单生效；工具开始/完成/失败事件成对出现 |
| 14 | 沙箱 | 三后端契约测试（HTTP 用 fake 网关）；宿主不执行调用方命令 |
| 15 | HITL | 中断 → approve/reject/edit → 精确续跑；非法编辑 422 |
| 17 | 子 Agent / 团队 | 子快照越权 422；父取消级联；结果回传 leader |
| 18 | 后台任务 | 长工具不阻塞；完成唤醒；并发上限生效；崩溃可重投 |
| 20 | Provider 抽象 | 模型白名单生效；未知模型准入拒绝 |
| 24 | 计量 | 输入/输出/推理 token 分别累加；按模型拆分正确 |
| 28 | 多租户隔离 | 跨租户读 run/file/session 返回 403/404 |
| 29 | 权限与 Scope | 缺失 Scope 返回 403；Scope 足够时放行 |
| 30 | 能力收窄 | 子 Agent 工具/模型超出父级 → 准入 422 |
| 31 | 审计 | 审计事件含 `run_id/tenant/principal/action/outcome/time` |
| 32 | PII 与保留期 | 日志抽样无原文；删除接口级联清理状态/事件/文件 |
| 33 | 成本归因 | token 指标可按租户聚合；用量突增有告警 |
| 34 | 幂等 | 并发 enqueue ×10 只产生 1 条消息、1 份状态 |
| 35 | 队列与租约 | 重投、接管、死信、终态不回退（P0 套件） |
| 36 | 重试与超时 | 可重试错误按退避重试；不可重试错误直接失败 |
| 37 | 熔断与降级 | 连续失败后快速失败；冷却后半开恢复 |
| 38 | 优雅停机 | 停机后在跑 Run 完成，未完成回到队列 |
| 40 | 日志 / 指标 / 追踪 | 日志含 `run_id/request_id/traceparent`；指标可导出 |
| 41 | 告警与 SLO | 告警规则可加载；burn-rate 阈值生效 |
| 42 | 看板与 Runbook | 看板 JSON 可解析；每个 P1/P2 告警有 Runbook 链接 |
| 44 | CI/CD | 六阶段全绿；主干可发布 |
| 45 | 镜像与 IaC | `helm template` 无错误；镜像启动通过健康检查 |
| 46 | 灰度与回滚 | 四阶段灰度可执行；`helm rollback` 后服务恢复 |
| 47 | 供应链 | SBOM 生成、镜像签名、依赖扫描产物存在 |
| 48 | 健康检查与探针 | 存活不依赖 Redis；就绪在 Redis 不可用时失败 |
| 49 | 配置与密钥管理 | 缺必要密钥启动失败；启动日志脱敏；配置分组校验 |

**覆盖要求**：34 项 → 至少 34 条断言；Phase 3 结束时逐项勾选一次，Phase 6 结束时再勾选一次。

---

## 八、数据与契约设计（未上线，无兼容包袱）

> 项目**尚未上线**：无生产数据、无外部调用方、无历史版本。
> 因此**不做**兼容窗口、双写双读、滚动升级四象限、废弃流程、迁移脚本、回滚演练。
> 契约与数据结构**可以直接调整**；只保留两类约束：**数据所有权**（防两处写）与**生命周期**（防膨胀）。

### 8.1 契约版本（预留，不实现兼容）

| 项 | 设计 |
|---|---|
| 版本字段 | 消息 / 事件 / 状态带 `schema_version`（当前 `1`） |
| 用途 | 为将来上线后的演进预留判定依据；**当前不实现兼容读取** |
| 变更 | 未上线期间版本号可直接升（`1 → 2`），不保留旧版本处理逻辑 |
| 生成式契约 | 事件表 / 路由表 / 指标表 / 错误码表由代码生成，CI 防漂移（§10.8） |

**理由**：现在就写"兼容读"是为不存在的调用方付维护成本；保留字段与生成机制成本近乎为零，需要时再实现。

### 8.2 数据结构（可直接调整）

| 项 | 规则 |
|---|---|
| Redis Key | 允许重命名、改结构、改 TTL；一次性切换，不做双写 |
| 状态字段 | 允许增删改；无历史数据需要兼容 |
| Checkpoint | 由 LangGraph 管理；重构期可清空重建 |
| 约束 | 改动必须同步更新 §8.3 的所有权表与生命周期表，避免"两处写" |

### 8.3 数据所有权与生命周期

#### 8.3.1 所有权表（唯一写入方）

| 数据 | 存储 | 唯一写入方 | 读取方 | 权威性 |
|---|---|---|---|---|
| Run 状态投影 | Redis Hash `agent:run:{id}:state` | `RunLifecyclePort` / `StatePort` | API、Worker | **权威** |
| 运行事件 | Redis Stream `agent:run:{id}:events` | `EventsPort` | SSE、审计消费 | 可裁剪副本 |
| 会话回放缓冲 | Redis Stream `agent:session:{tenant}:{sid}:events` | `EventsPort` | SSE 重连回放 | 可裁剪副本 |
| 幂等 claim | Redis `agent:run:{id}:claim` | `RunLifecyclePort` | Worker | 权威 |
| 请求/审批载荷 | Redis `agent:run:{id}:request` / `:approval-payload` | `RunLifecyclePort` | Worker | 权威 |
| 租约与配额 | Redis `:lease` / `agent:session:*` / `agent:principal:*` | `StatePort` | Worker | 权威（时效性） |
| 建队成员 | Redis `agent:team:{parent_run}:members` | `RunLifecyclePort` | 编排层 | 权威 |
| 上传文件 | Redis `agent:file:{tenant}:{id}` | `FilePort` | Worker | 权威（TTL 内） |
| 会话历史 | Redis List（按 tenant+user+session） | 编排层经 `HistoryPort` | 编排层 | 权威（有上限） |
| Checkpoint | PostgreSQL（LangGraph 管理） | LangGraph（运行时只读配置） | LangGraph | **外部组件所有** |
| 控制面业务数据 | 控制面 PostgreSQL | 控制面 | 控制面 | 不在本运行时范围 |

**规则**：任何数据只能有一个写入方；跨方读取必须经端口，不得直连。

#### 8.3.2 生命周期与删除策略

| 数据 | TTL / 上限 | 到期行为 | 删除接口 |
|---|---|---|---|
| Run 状态 | `RUN_STATE_TTL_SECONDS`（默认 7 天） | 自动过期 | 不存在即 404 |
| 运行事件 | `EVENT_STREAM_MAXLEN`（默认 1 万条） | 旧事件淘汰 | 随 Run 过期 |
| 会话回放缓冲 | `REPLAY_MAXLEN`（默认 1 万条）/ 24h | 旧事件淘汰 | 随会话过期 |
| 请求/审批载荷 | 与 Run 状态同 TTL | 随状态过期 | —— |
| 租约 key | 可见性超时（默认 900s） | 自动释放 | Worker 主动释放 |
| 上传文件 | `UPLOAD_TTL_SECONDS`（默认 1 小时） | 自动过期 | `DELETE /v1/files/{id}` |
| 会话历史 | 每会话 `CONVERSATION_HISTORY_MAX_MESSAGES`（默认 100 条） | 超出裁剪 | `DELETE /v1/sessions/{id}/messages` |
| 长期记忆 | 每个用户 `LONG_TERM_MEMORY_MAX_ITEMS` | 超出淘汰 | `DELETE /v1/memories/...` |
| 工作区文件 | 按隔离层级（Run/Session/User/Tenant） | Run 级立即、其余按 TTL | 沙箱清理 |
| Checkpoint | 由 LangGraph 与数据库策略管理 | 外部策略 | 外部工具 |

**约束**：允许调整 Key 与 TTL；调整后必须回填本节，并同步更新 §7.4 的对应回归断言。

#### 8.3.3 对账与修复（缺失时会出现什么）

| 风险 | 表现 | 对账方式 |
|---|---|---|
| 消息与状态不一致 | 有状态无消息（永不执行）或有消息无状态 | 按 `run_id` 抽样比对 Stream 与 state |
| claim 泄漏 | 同 run_id 永久不可重提 | 扫描无对应消息的 claim |
| 载荷与状态不一致 | 审批后投递失败 | 检查 `PENDING_APPROVAL` 且无 payload |
| 文件引用悬空 | Run 引用了已过期文件 | Run 失败并给出明确错误（**已实现**） |

**要求**：提供一个**只读对账脚本** `scripts/reconcile.py`（不自动修复），输出上述四类异常的数量与样例；修复由人工执行。

#### 8.3.4 备份与恢复（划归运维手册）

**未上线阶段无备份需求**。上线前由 `ops/运维手册.md` 定义 RPO/RTO、备份频率与恢复演练；
Checkpoint 由 LangGraph 管理，控制面数据由控制面负责。

---

## 九、交付与部署要点

### 9.1 镜像

- 多阶段构建：`uv sync --frozen --no-dev` → 复制 `src/`
- 非 root（`USER 10001`）、`tini` 作 PID 1、`HEALTHCHECK` 打 `/v1/health`
- 目标：镜像 ≤ 400MB（不含模型），冷启动 ≤ 3s

### 9.2 K8s 最小集与 IaC 形式

**IaC 形式**：Helm 3（chart 入库 `deploy/helm/data-agent-runtime/`），环境差异用 `values-{env}.yaml` 覆盖；
禁止手改集群内资源（与 §9.8.6 配置审计一致）。验收：`helm template` 无错误、`helm diff` 可预览变更。



| 项 | 值 | 说明 |
|---|---|---|
| `readinessProbe` | `GET /v1/ready` | Redis 可用才接流量 |
| `livenessProbe` | `GET /v1/health` | 进程级，避免依赖抖动导致重启风暴 |
| `terminationGracePeriodSeconds` | **> `SHUTDOWN_TIMEOUT_SECONDS`（默认 60s）** | 否则排空未完成就被 SIGKILL |
| `preStop` | `sleep 5` | 等 Endpoint 摘除 |
| `PodDisruptionBudget` | `minAvailable: 1` | 滚动/驱逐不中断 |
| `resources` | requests/limits 显式 | 防止 GC 抖动与 OOM |
| `topologySpreadConstraints` | 跨节点分散 | 单节点故障不团灭 |

### 9.3 CI 流水线

```
lint(ruff) → type(mypy) → unit(pytest -m "not integration")
→ integration(redis service) → security(pip-audit, bandit, secret scan)
→ build image → 推送（tag: git sha + semver）
```

门禁：覆盖率 ≥85%、mypy 0 错误、`uv.lock` 与 `pyproject.toml` 一致、镜像可启动并通过健康检查、
冒烟压测达标（§6.2）。

**供应链（v1.1 补充）**：

| 项 | 工具 | 频率 |
|---|---|---|
| 依赖漏洞扫描 | `pip-audit` | 每次 PR + 每日定时 |
| 镜像漏洞扫描 | `trivy` | 每次构建 |
| SBOM 生成 | `syft`（SPDX） | 每次构建，随镜像归档 |
| 镜像签名 | `cosign`（keyless） | 发布时 |
| 依赖更新 | Renovate（分组：patch 周更 / minor 双周） | 自动 PR |
| 许可证合规 | `pip-licenses` | 每周 |

### 9.4 灰度与发布策略（v1.2 新增）

| 对象 | 灰度方式 | 说明 |
|---|---|---|
| **Worker** | 按副本数比例（1 → 5 → 25 → 100%） | Worker 共享同一 Stream，直接按副本灰度；未上线无兼容矩阵，新旧副本需同版本 |
| **API** | 按 Header / 租户白名单 / 流量比例 | 需网关支持；灰度 API 写入的消息必须保持 `schema_version` 兼容 |
| **能力开关** | Snapshot 字段（默认关闭） | 新能力（如 `rubric`）先在单个 Agent 上验证，再放开 |
| **数据/Key** | 不做灰度 | 未上线可直接改；上线后按版本化处理 |

阶段门槛：

| 阶段 | 流量 | 观察指标 | 晋级条件 |
|---|---|---|---|
| Canary | 1% | 失败率、P95、死信数 | 30 分钟无异常 |
| 小流量 | 5% | 同上 + 租约丢失 | 2 小时无异常 |
| 半量 | 50% | 同上 | 24 小时无异常 |
| 全量 | 100% | 同上 | —— |

**回滚触发**：失败率较基线上升 >2 倍，或死信出现任何一条，即回滚到上一版本（保留旧副本 30 分钟）。

### 9.5 容量模型与副本换算（v1.2 新增）

```text
所需 Worker 副本数 ≈ ceil(峰值到达率 × 平均 Run 时长 / (单 Worker 并发 × 目标利用率))

示例（当前单 Worker 串行，并发=1）：
  峰值 200 Run/小时 = 0.056 Run/s
  平均 Run 时长 45s
  → 并发需求 = 0.056 × 45 ≈ 2.5
  → 目标利用率 70% → 副本数 = ceil(2.5 / 0.7) = 4
  
若单 Worker 并发提升到 4（P1 优化项）：
  → 副本数 = ceil(2.5 / (4 × 0.7)) = 1
```

| 输入 | 采集方式 |
|---|---|
| 峰值到达率 | 网关 QPS / `runtime.run.accepted` 速率 |
| 平均 Run 时长 | `runtime.run.duration` 的均值（按 status 分层） |
| 单 Worker 并发 | 配置值（当前 1） |
| 目标利用率 | 70%（留 30% 应对突发与 GC） |

**Redis 容量**：按 §6.2 的单 Run 命令数 × 峰值 TPS × 1.5 估算，并核对内存（事件流 `maxlen` + 状态 TTL）。
**扩容顺序**：先加 Worker（线性），再考虑提升单进程并发，最后才扩 Redis 规格。

### 9.6 API 版本策略（v1.8 简化）

| 项 | 规则 |
|---|---|
| 当前阶段 | **未上线，无弃用需求**：`/v1` 内的字段与行为可直接调整，不维护弃用清单与兼容窗口 |
| 版本号 | 保留路径版本 `/v1`；将来对外发布后，破坏性变更升 `/v2`，加性变更不升版本 |
| 上线后启用 | 弃用头（`Deprecation`/`Sunset`）、通知窗口（≥90 天）、`docs/deprecations.md` —— **上线时再落地** |
| 现在要做的 | 只保留契约快照测试，确保重构期间契约变化是"显式"的而不是"意外"的 |

### 9.7 多租户部署形态（v1.2 新增）

| 形态 | 适用 | 隔离 | 成本 | 决策依据 |
|---|---|---|---|---|
| **共享集群**（默认） | 绝大多数租户 | 逻辑隔离（Key 前缀 + Principal/Scope + 配额） | 低 | 租户数 > 20 且单租户负载 < 20% 集群容量 |
| **独立实例** | 大客户 / 强合规 | 物理隔离（独立 Redis + Worker 池） | 高 | 合同要求数据隔离，或单租户占集群 > 40% |
| **混合** | 平台初期 | 默认共享 + 白名单升独立 | 中 | 先共享，出现"吵闹邻居"再拆 |

**共享形态的硬要求**：所有 Redis Key 必须带租户维度（当前已满足：`agent:run:{id}` 中的 id 由租户内唯一保证，
文件为 `agent:file:{tenant}:*`）；配额与限流按 Principal 生效（已实现）。

**独立实例的迁移路径**：`wiring.py` 已按 `Settings` 构造，切换只需改部署配置（不同 Redis URL + 独立副本集），
**代码零改动**——这也是端口化的收益之一。

### 9.8 安全补遗（v1.3 新增）

> 补《企业级项目设计参考》§4.5 中本次重构必须闭环的三项；供应链已由 §9.3 覆盖。

#### 9.8.1 密钥轮换

| 项 | 设计 |
|---|---|
| 对象 | 入站 HMAC AK/SK（多调用方）、出站到沙箱的 AK/SK |
| 机制 | 注册表支持**同一身份两个有效 AK**（`access_key` + `previous_access_key`），新旧并行 |
| 流程 | ① 下发新 AK → ② 调用方切换 → ③ 观察旧 AK 使用率归零 → ④ 移除旧 AK |
| 窗口 | 旧 AK 保留 **2 个发布周期**（上线后策略；当前可直接替换） |
| 观测 | 指标 `runtime.auth.access_key{key_id}`，旧 AK 用量 >0 时告警提醒 |
| 失败处理 | 轮换期间新旧 AK 都可验签；旧 AK 移除后返回 401（不静默降级） |
| 范围 | Phase 3 完成（认证逻辑重构后）；**不改变 HMAC 协议本身** |

#### 9.8.2 HTTP 请求体上限

| 项 | 设计 |
|---|---|
| 现状 | 认证依赖里 `await request.body()` 无长度检查（DoS 面） |
| 设计 | 统一中间件：读取前检查 `Content-Length`，超限直接 **413**；分块传输时按累计字节数中断 |
| 配置 | `MAX_REQUEST_BODY_BYTES`（默认 2 MB；文件上传单独走 `MAX_UPLOAD_BYTES` 10 MB） |
| 验收 | ① 超限返回 413；② 上传端点不受 2 MB 限制；③ 无 `Content-Length` 的超大流被中断 |
| 落点 | Phase 0（中间件）+ 测试 |

#### 9.8.3 审计留存与不可篡改

| 项 | 设计 |
|---|---|
| 现状 | 运行事件流可被 `MAXLEN` 裁剪，不能作为合规审计依据 |
| 设计 | 定义**审计事件最小字段**：`run_id` / `tenant_id` / `principal_id` / `action` / `resource` / `outcome` / `occurred_at` / `schema_version` |
| 留存 | 审计事件独立于运行事件流（由控制面或独立消费者落库），保留期 ≥ **180 天**（按合规要求调整） |
| 不可篡改 | 只追加（append-only）+ 定期归档校验（哈希链或对象存储 WORM） |
| 查询 | 只读接口，按租户与时间范围；**不提供修改/删除** |
| 范围 | 本计划只定义**字段与边界**；落库与归档由控制面/运维实现（列入 §14 明确排除） |

#### 9.8.4 密钥与敏感配置托管（v1.4 新增）

| 项 | 设计 |
|---|---|
| 来源 | 生产：K8s Secret / 云 Secrets Manager / Vault 注入为环境变量；本地：`.env`（仅开发，gitignore） |
| 禁止 | 镜像内烘焙、提交到 Git、打印到日志或事件、写入错误响应 |
| 启动校验 | 必填项缺失 **fail-fast**；弱密钥检测（长度、重复字符、默认值黑名单） |
| 轮换 | 走 §9.8.1 的双 AK 流程；密钥版本由 Secret Manager 管理，应用只读当前值 |
| 变更审计 | 配置/密钥变更走 GitOps 或审批流程，记录操作人与时间（与 §10.6 治理规则一致） |
| 泄露响应 | 立即轮换 + 吊销旧值 + 审计日志回溯调用方 |
| 验收 | ① 镜像扫描无明文密钥；② 启动日志脱敏检查通过；③ 缺必要密钥时启动失败并给出可读原因 |

#### 9.8.5 数据分类与 PII 处理（v1.5 新增）

| 分类 | 示例 | 允许落日志 | 允许作指标标签 | 存储要求 |
|---|---|---|---|---|
| 公开 | Agent id、版本 | ✅ | ✅ | 无 |
| 内部 | run_id、状态、耗时 | ✅ | ✅（有界值） | 无 |
| 敏感 | 提示词、模型输出、文件内容 | ❌（仅摘要/哈希） | ❌ | 加密 + TTL |
| 个人数据 | user_id、手机号、邮箱 | ❌ | ❌（见 §6.3） | 加密 + 最小化 + 可删除 |

**规则**：
1. `run_id` / `session_id` / `tenant_id` / `user_id` **只允许**出现在日志与 trace 属性中，不得作为指标标签（与 §6.3 一致）；
2. 用户输入与模型输出默认按"敏感"处理：日志只记长度、哈希前 8 位与分类，不记原文；
3. 删除请求：`DELETE` 接口必须级联清理状态、事件、文件与会话历史；
4. 保留期见 §8.3.2，到期自动过期，不做"永久留存"。

**验收**：① 日志抽样检查无 PII 原文；② 删除接口有级联清理测试；③ 指标标签白名单检查通过。

#### 9.8.6 配置变更审计（v1.5 新增）

| 项 | 设计 |
|---|---|
| 变更通道 | 配置与密钥走 GitOps（Helm values / K8s 清单），禁止手工改线上 |
| 审批 | 变更 PR 需 owner 审批（§10.6），记录操作人与时间 |
| 启动摘要 | 启动时打印**脱敏**配置摘要（开关状态、外部依赖地址、限流阈值），便于比对 |
| 回滚 | 配置版本化，回滚 = 回退清单 + 重新部署 |
| 验收 | ① 任一线上配置可在 Git 找到来源；② 启动日志含配置摘要且无明文密钥 |

### 9.9 成本口径（v1.3 新增，轻量）

| 指标 | 口径 | 用途 |
|---|---|---|
| `cost.tokens.per_run` | 单 Run 的 `usage.total_tokens`（含 reasoning） | 成本归因基础（已有 token 计量） |
| `cost.tokens.per_tenant` | 按 `tenant.id` 聚合的 token 用量 | 租户成本分摊 |
| `cost.runs.per_thousand` | 每千次提交的实例成本（按副本数 × 单价估算） | 报价/容量决策 |
| 告警 | 单租户 token 用量日环比 > 3 倍 | 异常调用/滥用检测 |

**范围**：本计划只定义**指标口径与采集点**；计费、账单、成本看板随后续迭代实现。
**不做**：定价模型、发票、预算扣减。

### 9.10 多可用区与容灾姿态（v1.5 新增）

**当前形态**：单区域部署；本文档只定义**姿态与接口**，具体拓扑由运维手册承接（附录 D）。

| 项 | 目标 | 说明 |
|---|---|---|
| 无状态 API | 可跨 AZ 多副本 | 状态全在 Redis/PG，API 无本地状态 |
| Redis | 主从 + 多 AZ | 队列与状态在同一实例组；不做跨区双写 |
| PostgreSQL（Checkpoint） | 多 AZ 托管实例 | 由基础设施保障，运行时仅配置连接 |
| RTO | ≤ 30 分钟 | 单 AZ 故障时恢复服务 |
| RPO | ≤ 5 分钟 | 允许丢失最近 5 分钟内的状态写入（队列消息由 Stream 持久化） |
| 切换演练 | 每季度一次 | 归运维手册；本计划保证"无状态可切" |

**本计划的责任边界**：
1. **保证**：API 无状态、状态外置、启动不依赖本地磁盘、优雅停机不丢在跑任务；
2. **不保证**：Redis/PG 拓扑、跨区复制、DNS 切换——由运维手册与基础设施负责。

**验收**：① 任意 AZ 的 API 副本被杀，剩余副本可继续服务；② 状态与队列不依赖本地磁盘；③ 容灾演练记录在运维手册中。

---

## 十、运维与治理

### 10.1 告警（对应已有指标）

| 告警 | 条件 | 级别 |
|---|---|---|
| 队列积压 | `runtime.queue.depth` > 80% 水位，持续 5 分钟 | P2 |
| 死信出现 | `runtime.queue.dead_letter` 速率 > 0，10 分钟内 | P1 |
| Run 失败率 | `run.finished{status=failed}` 占比 > 5%，15 分钟 | P1 |
| 时延超 SLO | `run.duration` P95 > 60s，30 分钟 | P2 |
| 租约丢失 | Worker 日志 `lease was lost` 出现 | P1 |
| 限流触发 | `429` 占比突增 3 倍 | P3 |

### 10.1.1 告警分级与 burn-rate（v1.1 补充）

| 级别 | 语义 | 响应 |
|---|---|---|
| P1 | 用户可见错误或数据风险 | 立即（5 分钟内） |
| P2 | 容量/性能退化，未直接影响成功 | 1 个工作日内 |
| P3 | 趋势性指标 | 周会处理 |

SLO burn-rate 告警（替代单点阈值，减少误报）：

| 窗口 | 条件 | 级别 |
|---|---|---|
| 5 分钟 | burn-rate > 14.4×（1 小时耗尽月度预算） | P1 |
| 1 小时 | burn-rate > 6× | P2 |
| 6 小时 | burn-rate > 1× | P3 |

**错误预算政策**：月度预算耗尽 → 冻结功能发布，只允许修复类变更，直到下一个周期。

### 10.2 SLO

| SLI | 目标 |
|---|---|
| Run 成功率（非用户错误） | 99.5% / 月 |
| 提交接口可用性 | 99.9% / 月 |
| 提交 P95 时延 | < 500ms |
| 队列积压恢复时间 | < 10 分钟 |

### 10.3 Runbook 清单（Phase 5 交付）

1. 队列堆积排查（看深度 → 看 Worker 数 → 看单 Run 时延 → 看死信）
2. 死信重放（导出 → 修 payload → 重新入队）
3. 租约异常（哪些 run_id、哪个 Worker、是否进程被杀）
4. Redis 故障降级路径（认证 fail-closed 的表现与恢复）
5. 模型网关不可用（错误分类 → 重试行为 → 是否需要暂停消费）

### 10.4 ADR 清单

D1 不采用 DDD · D2 Protocol 而非 ABC · D3 pydantic 边界/dataclass 内部 ·
D4 不引入 DI 容器 · D5 异常分类而非 Result · D6 事件 union ·
D7 配置分组 · D8 渐进式目录迁移 · D9 分层 mypy · D10 集成测试用 compose ·
**D11 跨进程数据带 `schema_version`（§8.1）** · **D12 跨域原子操作归 `RunLifecyclePort`（§3.5）** ·
**D13 不修改 Redis Key 结构以保留回滚能力（§8.3）** ·
**D14 `infra` 可被多层依赖但不含业务逻辑；`Clock`/纯函数不建抽象（§3.2）** ·
**D15 不引入动态插件机制，扩展经 `wiring` 手动注册（§3.10）**

每条 ADR 使用统一模板：`adr/0000-template.md`（背景 / 选项 / 决定 / 后果 / owner / 复审条件），
并在合并前由至少一名非作者评审。

### 10.5 看板即代码（v1.1 补充）

- Grafana JSON 或 `dashboards/*.json` 入库，随部署自动加载；
- 每张看板至少含：RED（QPS/错误率/时延）、USE（队列深度/Worker 占用/Redis 连接）、
  token 用量、死信与重试；
- 服务级 + 租户级两个视角。

### 10.6 协作与治理规则（v1.3 新增）

| 项 | 规则 | 产物 |
|---|---|---|
| **CODEOWNERS** | 每个顶层目录有 owner；跨目录改动需 owner 评审 | `.github/CODEOWNERS` |
| **PR 规范** | 单 PR ≤400 行、单一目的；模板必填"影响面/回滚方式/测试" | `.github/PULL_REQUEST_TEMPLATE.md` |
| **分支保护** | `main` 禁止直推；必需 CI 六阶段 + 1 名非作者 review | 仓库设置 |
| **提交规范** | `feat/fix/refactor/docs/chore` 前缀；破坏性变更标 `BREAKING CHANGE` | commitlint 配置 |
| **技术债预算** | 每迭代预留约 **20%** 容量用于还债；登记在看板（含 owner 与优先级） | 技术债看板 |
| **依赖升级** | patch 周更、minor 双周；Renovate 自动 PR + CI 验证 | `renovate.json` |
| **架构变更** | 涉及分层/端口/契约的改动必须先写 ADR | `adr/` |

**重构期的特别约定**：
1. Track A 阶段（W1–W6）`src/` 只接受缺陷修复与本次重构任务（§12.1 冻结窗口）；
2. 阶段 PR 必须标注"阶段号 + 验收项"，便于回滚时按阶段定位；
3. 移动类 commit **单独提交**且不改内容（§Phase 4 约定），评审时以 `--follow` 查看历史。

### 10.7 依赖故障隔离与熔断（v1.4 新增）

**问题**：现有只有"超时 + 重试"。当下游持续失败（模型网关 500、MCP server 不可达）时，
`Worker × 重试` 会形成**放大效应**：每次失败都重试，把已经过载的下游打得更死。

#### 10.7.1 作用对象与不做对象

| 依赖 | 是否熔断 | 理由 |
|---|---|---|
| 模型网关（LLM） | ✅ | 最贵、最容易限流/超时 |
| MCP server | ✅ | 第三方服务，不可控 |
| 沙箱网关（HTTP） | ✅ | 网络抖动常见 |
| Redis | ❌ | 熔断 Redis 等于自杀（状态与队列都在上面） |
| PostgreSQL（checkpoint） | ❌ | 由连接池与超时处理；熔断会让 HITL 无法恢复 |

#### 10.7.2 状态机与阈值

```
closed ──(窗口内失败率 > 50% 或 连续 5 次失败)──► open
  ▲                                                │
  │                                                │ 冷却 30s
  └──(探测成功)── half-open ◄──────────────────────┘
                     │
                     └──(探测失败)──► open
```

| 参数 | 默认 | 可配置 |
|---|---|---|
| 统计窗口 | 30s | ✅ |
| 失败率阈值 | 50% | ✅ |
| 连续失败阈值 | 5 次 | ✅ |
| 冷却时间 | 30s | ✅ |
| 半开探测数 | 1 | 固定 |

#### 10.7.3 与既有机制的关系

| 机制 | 关系 |
|---|---|
| 重试 | 熔断打开时**快速失败**，不消耗重试预算；抛出 `UpstreamFailure(retryable=True)`，由队列退避重试 |
| 准入 | 不参与准入（准入不调用外部依赖，避免把可用性问题前置成 422） |
| 降级 | 模型不可用时**不做降级模型**（本次范围外），Run 直接失败并可重试 |
| 多 Worker | 熔断状态**进程内**（不做分布式），理由：进程内足够抑制放大效应，且无额外依赖 |

#### 10.7.4 落点与观测

| 项 | 内容 |
|---|---|
| 实现位置 | `adapters/*` 内包装外部客户端（`llm`、`mcp`、`sandbox`），**不进入 `runtime/` 编排** |
| 指标 | `runtime.dependency.circuit_state{dependency}`（0=closed/1=half/2=open）、`runtime.dependency.failures{dependency}` |
| 告警 | `circuit_state=2` 持续 > 2 分钟 → P2 |
| 测试 | 故障注入：连续失败 → 打开 → 快速失败 → 恢复后自动闭合 |

**验收**：① 注入 100% 失败后，第 6 次起快速失败（耗时 < 5ms）；② 冷却后半开探测成功即闭合；③ 指标与告警可见。

### 10.8 文档由代码生成（v1.4 新增）

**问题**：事件表、指标表、路由表手写在文档里，改代码不改文档 → 文档必然撒谎。
这类"两套真相"是长期维护中最常见的漂移来源。

#### 10.8.1 生成物清单

| 生成物 | 数据源 | 输出 |
|---|---|---|
| 路由表 | `FastAPI.app.routes` | `docs/generated/routes.md` |
| OpenAPI | FastAPI 自动 | `docs/generated/openapi.json` |
| 事件表 | `core/events.py` 的 `EventType` + payload 模型 | `docs/generated/events.md` + `events.schema.json` |
| 指标表 | `infra/metrics.py` 的仪器定义 | `docs/generated/metrics.md` |
| 错误码表 | `core/failures.py` 的 `code` / `http_status` | `docs/generated/errors.md` |

**契约目录约定**：手写的契约说明放 `docs/contracts/`（API 语义、鉴权、错误码含义、SLA），
与 `docs/generated/`（机器生成）分工明确——前者解释"为什么"，后者保证"是什么"不漂移。

#### 10.8.2 机制与门禁

| 项 | 规则 |
|---|---|
| 生成脚本 | `scripts/gen_docs.py`，本地可重复执行（幂等） |
| CI 门禁 | 重新生成后 `git diff --exit-code docs/generated/`，有差异即失败（防手改、防漂移） |
| 文档引用 | 架构文档只**引用**生成文件，不再手写事件/端点/指标表 |
| 审查 | 生成物随 PR 提交，reviewer 看 diff 即可知道契约变了什么 |

**验收**：① CI 有 `docs-drift` 检查；② 事件数、路由数、指标数与代码一致；③ 手改生成文件会被 CI 拒绝。

### 10.9 CHANGELOG 与 onboarding（v1.5 新增）

| 产物 | 规则 |
|---|---|
| `CHANGELOG.md` | 遵循 Keep a Changelog；按 `feat/fix/refactor/security` 分类；破坏性变更单独标注 `BREAKING` 与迁移步骤 |
| `docs/onboarding.md` | 目标：**30 分钟内**从 clone 到跑通测试；含环境要求、命令、常见问题 |
| 生成 | 由 commit 类型自动汇总（与 §10.6 提交规范联动），人工补充影响说明 |
| 验收 | 新人按 onboarding 操作可跑通；每次发布更新 CHANGELOG |

---

## 十一、风险登记册

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 重构引入行为回归 | 中 | 高 | 165 用例全程绿；每阶段小步提交；P0 可靠性套件每阶段跑 |
| R2 | mypy 存量错误导致被放弃 | 高 | 中 | 分层 strict + per-module 白名单，先锁 `core`/`api` |
| R3 | 目录移动导致 blame 断裂 | 高 | 低 | 移动与修改分开提交；`git log --follow` 验证 |
| R4 | 契约测试暴露既有 bug | 中 | 中 | 视为收益：先记录到待办，不阻塞重构主线 |
| R5 | 工期被功能需求打断 | 中 | 中 | P0/P1 独立可交付（类型化 + 端口），不依赖后续阶段 |
| R6 | 集成测试在 CI 不稳定 | 中 | 中 | 固定 Redis 版本；用例级超时；重试仅限基础设施抖动 |
| R7 | 镜像体积/启动时间超标 | 低 | 中 | 多阶段构建 + `--no-dev`；启动耗时纳入 CI 断言 |
| R8 | 配置分组改变读取顺序 | 低 | 高 | 保持 env 名不变；新增启动期"配置来源摘要"日志 |
| R9 | 事件 union 改动破坏旧客户端 | 低 | 高 | 只加不改；schema 快照测试；灰度期保留旧序列化路径 |
| R10 | 单人重构中断 | 中 | 中 | 每阶段产出可合并的独立 PR；文档先行 |

---

## 十二、里程碑与排期（v1.8：三轨 12 周）

### 12.1 前置条件：功能冻结窗口

| 项 | 规则 |
|---|---|
| 冻结范围 | `src` 只接受**本计划内**的重构、能力追平与缺陷修复；不接受"计划外"的新功能 |
| 时长 | W1–W12（Track A + Track C 期间） |
| 例外 | 安全/数据正确性修复，需负责人批准 |
| 说明 | v1.7 起，能力追平属**计划内**工作，因此不受冻结限制——冻结针对的是"插队需求" |

### 12.2 排期

| 周 | Track A（重构） | Track B（生产就绪） | Track C（能力追平） |
|---|---|---|---|
| W1 | Phase 0：工具链 + 错误体系 | CI 前两阶段（lint/type）先行 | —— |
| W2 | Phase 1：事件类型化 + `schema_version` | CI unit | —— |
| W3 | Phase 2：端口 + 契约测试 | 集成测试 | —— |
| W4 | Phase 3：编排拆分 | 镜像 + 冒烟压测 | **P1 回放**（依赖 P1/P2） |
| W5 | Phase 4：目录归位 + 组合根 | Helm + PDB | **P3 隔离层级** |
| W6 | 测试补齐（上半） | 告警 + SLO + 看板 + 安全补遗 + 治理 + 熔断 | **P2 HITL 编辑** |
| W7 | 测试补齐（下半）→ 覆盖率 85% | SBOM/签名/Renovate + 灰度方案 | **P4 后台卸载** |
| W8 | 契约快照 + 文档收口 | Runbook + ADR + 容量收口 | **P5 协议适配** |
| W9 | —— | 看板收口 | **P6 建队（灰度）** |
| W10 | —— | —— | 建队灰度观察 + 能力项验收 |
| W11 | 回归修复 | —— | 能力开关回滚验证 |
| W12 | 缓冲 + 文档收口 | —— | 缓冲 |

**依赖门禁**：Track C 的 P1/P2 依赖 Track A 的 Phase 1/2；能力灰度依赖 Track B 的发布能力。
**注意**：v1.8 去掉了迁移/双跑/回滚演练三条轨——项目未上线，无兼容包袱。

> 相比 v1.0 的 5–6 周，增量来自：存量测试补齐（约 1 周）、能力追平 6 项（约 5 周）、缓冲（约 1 周）。
> **不做缓冲的排期等于没有排期。**

---

## 十三、完成定义（DoD，v1.8 两组）

> **A 组（设计 48 条）+ B 组（能力 10 条）= 58 条。** 两组都必须全绿才算完成。
> v1.8 删除了 C 组（迁移安全 6 条）——项目未上线，无兼容与迁移要求。

### A 组：设计达标（48 条）

- [ ] `ruff check` 与 `mypy`（分层 strict）0 错误
- [ ] `pytest` ≥200 用例全绿，覆盖率 ≥85%（`core` ≥95%）
- [ ] 公共面 `Any` = 0；`except Exception` ≤3
- [ ] 单文件 ≤300 行
- [ ] 架构 import 测试通过
- [ ] 6 组契约测试通过（真实现 + fake）
- [ ] 集成测试在 CI（Redis service）通过
- [ ] `/v1` 契约零破坏（现有 165 用例 + schema 快照）
- [ ] CI 六阶段全绿，镜像可启动并通过健康检查
- [ ] K8s 清单 `--dry-run=server` 通过，宽限期 > drain 超时
- [ ] 告警规则与 SLO 文档入库（含 burn-rate 与错误预算政策）
- [ ] Runbook 五篇、ADR 十三篇入库（含模板）
- [ ] 看板即代码（Grafana JSON）入库
- [ ] 跨进程数据带 `schema_version` 字段（§8.1），版本号变更在契约快照中体现
- [ ] **原子性场景测试**通过：并发 enqueue / approve-cancel 竞争 / 崩溃恢复（§3.5）
- [ ] **容量基线已建立**，冒烟压测进 CI 且达标（§6.2）
- [ ] 镜像回滚可执行：`helm rollback` 后服务恢复正常（不要求混合版本）
- [ ] 供应链：SBOM 生成、镜像签名、Renovate 接入（§9.3）
- [ ] 终止准则与降级路径已评审确认（§1.6）
- [ ] 灰度发布方案与回滚触发条件已落地（§9.4）
- [ ] API 弃用政策文档化，`docs/deprecations.md` 建立（§9.6）
- [ ] 多租户部署形态已决策并写入部署文档（§9.7）
- [ ] 容量模型（副本换算公式 + 输入采集）已文档化（§9.5）
- [ ] 数据所有权表与生命周期策略已文档化（§8.3.1–8.3.2）
- [ ] 只读对账脚本 `scripts/reconcile.py` 可用，四类异常可输出（§8.3.3）
- [ ] 密钥轮换方案可用，新旧 AK 并行验证通过（§9.8.1）
- [ ] HTTP body 上限生效：超限 413、上传端点单独限额（§9.8.2）
- [ ] 审计事件最小字段与保留期已定义（§9.8.3，落库可由控制面实现）
- [ ] 成本口径（token/租户/千次提交）已定义并接入指标（§9.9）
- [ ] CODEOWNERS / PR 模板 / 分支保护 / 技术债预算已落地（§10.6）
- [ ] 6 项已实现能力的回归用例全部通过（§7.4）
- [ ] 指标标签白名单校验生效，`/metrics` series 数 < 5,000（§6.3）
- [ ] 密钥托管方案落地：镜像无明文、缺失 fail-fast、启动日志脱敏（§9.8.4）
- [ ] 熔断在模型网关与 MCP 生效：快速失败、半开恢复、指标与告警可见（§10.7）
- [ ] `scripts/gen_docs.py` 可生成 5 类文档，CI `docs-drift` 检查通过（§10.8）
- [ ] §3.9 的 12 个核心类型全部落地，端口签名无 `dict[str, Any]`（§3.9）
- [ ] 六类扩展点均可按 §3.10 路径实现；`wiring` 注册表可用（§3.10）
- [ ] 模块健康度检查通过：行数、导出面、fan-out ≤7（§3.11）
- [ ] `config` 只经 `wiring`/`entrypoints` 读取，`runtime` 只接收 `RuntimeLimits` 切片（§3.2）
- [ ] Helm chart（含各环境 values）可用，`helm template` 无错误（§9.2）
- [ ] 多区姿态验证：任一 AZ 副本被杀后服务可用（§9.10）
- [ ] PII 分类落地：日志抽样无原文、删除接口级联清理（§9.8.5）
- [ ] 配置变更走 GitOps，启动打印脱敏摘要（§9.8.6）
- [ ] 每个大版本有一份 profiling 记录（§6.4）
- [ ] 测试数据工厂可用，测试不依赖生产数据与网络（§7.5）
- [ ] CHANGELOG 与 onboarding 可用，新人 30 分钟跑通（§10.9）
- [ ] 附录 D 的 7 项运维接口已与运维团队确认（附录 D）
- [ ] 本计划的阶段状态与实际进度同步更新（每阶段结束勾选一次）
- [ ] 附录 H 的 50 项矩阵与代码实际一致（新增/删除能力时同步更新）
- [ ] §7.6 的 34 项能力回归断言齐备（每项至少 1 个自动化用例）
- [ ] §3.12 的 6 项已有能力在重构前后行为一致（冻结核对通过）

### B 组：能力完整（10 条，见 §十五.7）

- [ ] 6 项能力全部落地，各有正向 + 失败路径测试
- [ ] 回放：断线重连不重不漏（含截断标记）
- [ ] HITL 编辑：参数校验、审计、越权字段拒绝
- [ ] 隔离层级：四层路径隔离 + 穿越防护 + 清理策略
- [ ] 后台卸载：长工具不阻塞、完成续跑、崩溃可恢复
- [ ] 协议适配：AG-UI 映射快照测试、A2A 提交与查询
- [ ] 建队：能力收窄校验、级联取消、预算上限、`worker_id` 过滤
- [ ] 新增事件与端点进入生成式文档
- [ ] 每项有 Runbook 条目与告警
- [ ] 建队单租户灰度一周无异常

---

## 十四、不做清单（防范围蔓延）

| 不做 | 理由 |
|---|---|
| 六层 DDD 目录 | 无聚合/仓储需求，纯增仪式 |
| DI 容器 | 单组合根已足够 |
| 微服务拆分 | 两进程边界正确 |
| 替换 Redis Stream 为 Kafka/Celery | 现有语义满足，多组件多故障源 |
| 全仓 mypy strict | 存量错误会让人关闭它 |
| 重写 Agent 循环 | DeepAgents 是资产 |
| 追求 100% 覆盖率 | 覆盖率是下限，关键在失败路径 |
| ~~修改 Redis Key 结构 / TTL 语义~~ | **v1.8 起允许**：未上线无兼容包袱，改后同步 §8.3 表与回归断言 |
| 引入消息中间件做版本路由 | `schema_version` 字段已足够，多组件多故障 |
| **备份/恢复演练（RPO/RTO）** | 划归 `ops/运维手册.md`：Checkpoint 由 LangGraph 管理，控制面数据由控制面负责 |
| **值班表 / 事故分级 / 复盘流程** | 组织流程，划归 `ops/运维手册.md`（§8.3.4 已说明边界） |
| **审计落库与归档实现** | 本计划只定义字段与边界；实现归控制面/运维（§9.8.3） |
| **计费与账单** | 本计划只定义成本口径；定价与扣减属产品侧（§9.9） |
| **SDK / Webhook** | 运行时只提供 HTTP/SSE；客户端封装与回调由控制面或调用方负责 |
| **模型路由 / 降级链** | 单 provider 阶段；需要时在 `AgentFactory` 内部加路由表，不新增端口 |
| **评估体系（离线）** | 独立系统，消费事件与轨迹；不放进运行时 |
| **Cron 调度** | 归控制面；运行时只保证"被调用时可靠执行" |
| **工作流 / DAG 编排** | 归控制面；运行时负责单次 Run 的可靠执行 |
| **分布式熔断 / 熔断状态共享** | 进程内实现已足够抑制放大效应，跨进程共享需额外存储（§10.7.3） |
| **模型降级链（主备模型切换）** | 本次范围外；熔断只负责快速失败，不负责换模型 |

---

## 十五、能力追平（本次范围，Track C）

> **本章是本次升级的一部分**（v1.7 定调）：目标不是"行为不变"，而是"**更好的设计 + 完整的能力**"。
> 未上线、无兼容包袱：能力可以直接实现，但必须可灰度、可观测、可单独关闭。

### 15.1 为什么单列一章

虽然同属一次升级，仍单独成章，原因有三：

1. **验收口径不同**：设计达标看"结构指标"（`Any`、行数、覆盖率），能力达标看"行为可用"（回放、编辑、建队）；
2. **回滚粒度不同**：设计改动整体回滚，能力项要能**单独关闭**（开关级回滚）；
3. **顺序有依赖**：6 项能力依赖 Phase 1/2 的类型与端口，不能与重构同时开工。

因此本章单列，但**不再标注"不属本次范围"**；它与 §五 Phase 6、§十三 B 组、§十二 Track C 对应。

### 15.2 对标差距

| 维度 | AgentScope Service | 本项目现状 | 差距性质 |
|---|---|---|---|
| 会话事件流 | 多订阅者 + **重连回放缓冲** | 单流 + 状态兜底 | 体验 |
| 长工具 | **后台卸载**，完成再唤醒 | 同步等待，阻塞会话 | 体验 + 稳定性 |
| 工作区隔离 | 按 Agent / 会话 / 用户可配 | 按 Run 隔离 | 多租户安全 |
| HITL | 5 模式 + **运行中编辑工具参数** | approve / reject | 治理粒度 |
| 协议 | 中间件转 **AG-UI / A2A** | 自有 SSE | 生态接入 |
| 多 Agent | **运行时建队**（leader spawn worker） | 静态嵌套 + 远程异步子 Agent | 编排能力 |
| 可靠性语义 | 无幂等/租约/死信 | **有** | 本项目优势 |
| 多租户治理 | 路由层 `user_id` 归属 | **HMAC + Scope + 配额 + 双准入** | 本项目优势 |

**策略**：本次只做这 6 项（B 组 DoD）。不追"Schema 驱动前端""Cron 调度""音频输入"——与产品定位不匹配或收益低于成本。

### 15.3 六项与优先级

| # | 能力 | 优先级 | 估时 | 依赖 | 可独立上线 |
|---|---|---|---|---|---|
| 1 | 会话事件回放缓冲 | **P1** | 1–2 天 | 事件端口读接口（重构 P2） | ✅ |
| 2 | HITL 编辑工具参数 | **P1** | 2–3 天 | 中断载荷协议（重构 P1） | ✅ |
| 3 | 工作区隔离层级 | **P1** | 2–3 天 | 沙箱端口（重构 P2） | ✅ |
| 4 | 后台工具卸载 | P2 | 3–5 天 | 队列 + 事件（重构 P2） | ✅ |
| 5 | 协议适配（AG-UI / A2A） | P2 | 5–7 天 | 事件类型化（重构 P1） | ✅ |
| 6 | 运行时建队（leader/worker） | P3 | 8–10 天 | 子 Agent + 会话模型 + 配额 | ⚠️ 需灰度 |

**合计约 4–5 周**；建议顺序 1 → 3 → 2 → 4 → 5 → 6。

### 15.4 逐项设计

#### 15.4.1 会话事件回放缓冲（P1）

| 项 | 方案 |
|---|---|
| 存储 | 会话级事件流（独立于 Run 事件流），保留最近 1 万条、TTL 24h |
| 游标 | 事件序号即 SSE 的 `id:`；重连读 `Last-Event-ID`，从该序号之后回放 |
| 回放 | 先回放缓冲再接实时，按序号去重 |
| 多订阅者 | 同一会话允许多订阅者；订阅不消费（非队列语义） |
| 上限 | 超缓冲时返回"历史已截断"标记，前端提示 |
| 契约 | 事件序号跨 Run 单调连续 |

**验收**：断线重连不重不漏；两端订阅一致；超限有截断标记。

#### 15.4.2 HITL 编辑工具参数（P1）

| 项 | 方案 |
|---|---|
| 决策 | `action`：`approve` / `reject` / `edit` / `respond` |
| 编辑 | `edit` 携带 `edited_args`，按工具参数 schema 校验；不合法返回 422 |
| 审计 | 记录操作人、原参数摘要、新参数摘要、决定 |
| 续跑 | 使用编辑后参数；原始参数留档 |
| 安全 | **工具名与作用对象白名单字段禁止编辑**，防越权改目标 |
| 范围 | 仅限被 `interrupt_on` 命中的工具 |

**验收**：编辑后按新参数执行；非法参数 422；审计可追溯；越权字段被拒。

#### 15.4.3 工作区隔离层级（P1）

| 层级 | 路径 | 生命周期 | 适用 |
|---|---|---|---|
| Run（默认） | `/workspace/run/{run_id}` | Run 结束销毁 | 一次性分析 |
| Session | `/workspace/session/{tenant}/{session}` | 会话 TTL | 多轮迭代 |
| User | `/workspace/user/{tenant}/{user}` | 配额 + TTL | 个人资料 |
| Tenant | `/workspace/tenant/{tenant}` | 配额 + TTL | 共享只读数据集 |

**规则**：路径由运行时拼接，禁止调用方传相对路径或 `..`；只允许"向下读"，不允许"向上写"；按层级清理。
**验收**：可见性符合层级；路径穿越被拒；清理无残留；配额超限有明确错误。

#### 15.4.4 后台工具卸载（P2）

| 项 | 方案 |
|---|---|
| 触发 | 工具声明可后台，或执行超过 30s |
| 流程 | 发 `tool_deferred` → 后台执行 → 发 `tool_completed` → **复用恢复机制**唤醒 Agent |
| 失败 | 发 `tool_failed`；崩溃则按租约重投 |
| 上限 | 单 Run 同时后台任务上限 3，超出排队 |

**验收**：60s 工具不阻塞会话；完成后续跑；崩溃可恢复；并发上限生效。
**风险**：后台完成时恰在等审批 → 规则为"先落事件，再按状态决定是否续跑"。

#### 15.4.5 协议适配 AG-UI / A2A（P2）

| 项 | 方案 |
|---|---|
| 位置 | `adapters/protocol/`，不进编排 |
| AG-UI | 事件映射表（运行开始/文本/思考/工具开始/工具结束/运行结束）；未知事件丢弃并计数 |
| A2A | 任务提交/状态查询/取消 + Agent Card |
| 入口 | 独立路径（`/v1/ag-ui/*`、`/v1/a2a/*`），共享底层用例 |
| 范围 | 只做对外输出，不做反向接入 |

**验收**：官方 AG-UI 客户端可渲染一次完整 Run；映射表快照测试通过；A2A 可提交查询；未知事件不影响主流程。

#### 15.4.6 运行时建队 leader / worker（P3）

| 项 | 方案 |
|---|---|
| 触发 | 快照声明 `team`（leader 模板 + worker 模板 + 上限） |
| 建队 | leader 通过工具 `spawn_worker(task, role)` 创建**子 Run**（非线程），子 Run 有独立 run_id 与事件流 |
| 收窄 | 子快照必须是父快照的**子集**（工具/模型/沙箱/配额只能更小），准入时校验 |
| 配额 | 团队共享配额池；单 worker 不得超池；超限拒绝建队 |
| 生命周期 | 父取消 → 级联取消子；子失败不必然失败父（由 leader 决定） |
| 事件 | 默认聚合到父流并带 `worker_id`，也可独立订阅 |
| 预算 | 并发 worker ≤3、总 Run ≤10、token 硬上限 |

**验收**：leader 动态建 2 个 worker 并汇总；子快照越权被 422；取消父级联子；超预算停止建队；事件可按 `worker_id` 过滤。
**风险**：成本按 N 倍放大、调试复杂 → 默认关闭、必须有硬预算、单租户灰度。

### 15.5 与重构的关系

| 重构产物 | 本章如何使用 |
|---|---|
| 7 个端口 | 回放用事件端口、后台卸载用队列、隔离层级用沙箱、建队用生命周期端口 |
| 事件类型化 | 回放/协议/建队事件基于同一联合类型扩展 |
| 错误分类 | 新增错误（越权编辑、超预算、越层访问）复用同一体系 |
| 装配层 | 新增能力只改装配，不扩散到入口 |
| 生成式文档 | 新事件/新端点自动进入 `docs/generated/`，不手写 |

**约束**：本章任何一项都不得修改 Phase 0–4 定义的分层、端口语义与事务边界；如需扩展端口，按 §3.10 的扩展流程走。

### 15.6 排期

| 阶段 | 内容 | 周 |
|---|---|---|
| 前置 | Phase 1（事件类型化）+ Phase 2（端口）完成 | W1–W3 |
| 第一批（P1） | 回放 → 隔离层级 → HITL 编辑 | W4–W6 |
| 第二批（P2） | 后台卸载 → 协议适配 | W7–W8 |
| 第三批（P3） | 运行时建队（灰度） | W9–W10 |
| 收口 | 能力项回滚开关验证 + 验收 | W11–W12 |

**与重构的关系**：与 Track A 的后段并行（W4 起），但不得早于 Phase 2；与 Track B 的灰度方案联动。

### 15.7 验收（DoD）

**验收清单见 §十三 B 组（10 条）**，此处不重复维护，避免两处漂移。
B 组通过即视为 6 项能力验收完成；每项另需满足"独立开关可关闭"的验证。

### 15.8 不做清单

| 不做 | 理由 |
|---|---|
| Schema 驱动前端 | 有自有控制面与前端，不需要 |
| Cron 调度 | 属控制面能力，当前无定时任务需求 |
| 音频/视频输入 | 场景未提，成本高于收益 |
| 反向接入其它 Agent 生态 | 只做对外输出 |
| 跨集群建队 | 需要新的调度层，超出现阶段 |

---

## 附录 A：目标 `pyproject.toml` 工具段

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "ASYNC", "S", "RUF"]
ignore = ["S101"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_unreachable = true

[[tool.mypy.overrides]]
module = ["data_agent_runtime.core.*", "data_agent_runtime.ports", "data_agent_runtime.api"]
disallow_any_explicit = true

[[tool.mypy.overrides]]
module = ["data_agent_runtime.adapters.*", "data_agent_runtime.runtime.*"]
disallow_untyped_defs = false

[tool.pytest.ini_options]
markers = ["unit", "integration", "p0", "slow"]
addopts = "-q --strict-markers"

[tool.coverage.run]
branch = true
source = ["data_agent_runtime"]

[tool.coverage.report]
fail_under = 85
skip_covered = true
```

## 附录 B：架构约束测试骨架

```python
"""分层依赖约束：违反即失败。"""
import ast
from pathlib import Path

RULES = {
    "core": set(),
    "runtime": {"core", "ports"},
    "adapters": {"core", "ports", "config", "infra"},
    "api": {"runtime", "core", "ports"},
    "wiring": None,  # None = 允许全部
}

def _imported_packages(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("data_agent_runtime."):
                names.add(node.module.split(".")[1])
    return names

def test_layers_only_depend_downwards():
    root = Path("src/data_agent_runtime")
    for module, allowed in RULES.items():
        if allowed is None:
            continue
        for file in (root / module).rglob("*.py"):
            extra = _imported_packages(file) - allowed - {module}
            assert not extra, f"{file} 违规依赖: {extra}"

def test_core_has_no_io():
    """core 层禁止任何 IO 库，且不允许函数内延迟 import 绕过。"""
    forbidden = {"redis", "httpx", "socket", "requests", "psycopg", "deepagents", "langchain_core"}
    for file in Path("src/data_agent_runtime/core").rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):          # walk 会进入函数体，覆盖延迟 import
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".")[0]}
            else:
                continue
            assert not (names & forbidden), f"{file}:{node.lineno} core 层禁止 IO 依赖 {names & forbidden}"
```

## 附录 C：阶段验收命令

```bash
cd python-agent-runtime

# 每阶段统一验收
./scripts/verify.sh                  # pytest + ruff + docstring + diff check
.venv/bin/python -m mypy src          # 分层 strict
.venv/bin/python -m pytest -m "not integration" -q
P0_TEST_REDIS_URL='redis://:root@127.0.0.1:6379/15' \
  .venv/bin/python -m pytest -q tests/test_p0_reliability.py
git diff --check

# 容量与性能门禁（§6.2）
.venv/bin/python scripts/loadtest_smoke.py --runs 200 --concurrency 20 \
  --assert-p95-ms 800 --assert-redis-cmds-per-run 40

# 架构约束（§附录 B）
.venv/bin/python -m pytest -q tests/test_architecture.py
```

---

## 附录 D：与运维手册的接口（v1.5 新增）

> 下列事项**不在本计划范围**，但必须有明确归属与接口，否则视为"无人负责"。
> 归属方：`ops/运维手册.md`（运维 / SRE）。

| 事项 | 归属 | 本计划提供 | 运维手册需承接 | 验收 |
|---|---|---|---|---|
| 备份与恢复 | 运维 | 数据清单与生命周期（§8.3.1–8.3.2）；未上线阶段无备份需求 | RPO/RTO、备份频率、恢复演练 | 上线前定义并演练 |
| 值班与事故 | 运维 | 告警分级（§10.1.1）、Runbook（§10.3） | 值班表、升级路径、复盘模板 | P1 有复盘且行动项闭环 |
| 混沌/故障演练 | 运维 | 熔断开关（§10.7）、超时与重试配置 | 演练计划、故障注入清单 | 季度一次 |
| 多区切换 | 运维 | 无状态 API、状态外置（§9.10） | 拓扑、DNS 切换、跨区复制 | 季度切换演练 |
| 审计落库 | 控制面 | 审计字段与保留期（§9.8.3） | 落库、归档、只读查询接口 | 可按租户/时间查询 |
| 计费与账单 | 产品 | 成本口径（§9.9） | 定价、扣减、账单 | 月度对账 |
| 证书与域名 | 运维 | —— | TLS 证书轮换、域名解析 | 到期前 30 天告警 |

**接口约定**：本计划新增或变更的告警、指标、Runbook 条目，必须在合并时同步更新本表，
保证运维侧知道"要接什么"。

---

## 附录 E：成熟度自评（v1.5）

### E.1 内部结构 6 项

| # | 维度 | 得分 | 依据 |
|---|---|---|---|
| 1 | 架构设计 | **9.5** | §3.1–3.2 分层与依赖规则、§3.5 事务边界、附录 B 可执行约束、契约目录（§10.8） |
| 2 | 封装与抽象 | **9.5** | §3.7 端口签名、§3.8 协作者签名、§3.9 核心类型清单（12 个类型已定义）、§3.2 不抽象三例外 |
| 3 | 扩展性 | **9.5** | §3.10 六类扩展矩阵 + D15 插件决策（含理由与预留路径）、§1.4.2 改动文件数指标 |
| 4 | 分层 | **9.5** | §3.2 规则表含 `infra`/`config`、`RuntimeLimits` 切片隔离、附录 B 延迟 import 扫描 |
| 5 | 模块化 | **9.5** | §3.11 四条健康度判据（行数/变更原因/导出面/fan-out）、§3.3 新旧对照、`ports` 拆分阈值 |
| 6 | 服务化 | **9.5** | 两进程 + 探针 + 宽限期（§9.2）、灰度（§9.4）、容量公式（§9.5）、多区姿态（§9.10） |

### E.2 外部能力 13 域

| # | 能力域 | 得分 | 关键证据 |
|---|---|---|---|
| 1 | 契约与演进 | 9.0 | §8.1 版本字段、§9.6 版本策略、§10.8 生成式契约 |
| 2 | 数据与状态 | 9.0 | §8.3.1–8.3.3、§8.2 结构规则、附录 D 备份接口 |
| 3 | 可靠性工程 | 9.0 | §10.7 熔断、§10.1.1 预算、§8.3.3 对账、附录 D 混沌接口 |
| 4 | 可观测与运维 | 9.5 | §6.3 基数、§10.1–10.5、§10.3 Runbook |
| 5 | 安全与合规 | 9.0 | §9.3 供应链、§9.8.1–9.8.6（轮换/上限/审计/托管/PII/配置审计） |
| 6 | 性能与容量 | 9.0 | §6.2 门禁、§6.4 profiling、§9.5 容量公式 |
| 7 | 测试体系 | 9.0 | §7.1–7.5（金字塔/契约/集成/属性/故障注入/数据管理） |
| 8 | 交付与发布 | 9.0 | §9.1–9.4、§10.6 治理、Helm 形态（§9.2） |
| 9 | 配置与密钥 | 9.5 | §3.2 config 层、§9.8.1/9.8.4/9.8.6 |
| 10 | 文档与知识 | 9.0 | §10.4 ADR、§10.8 生成式、§10.9 CHANGELOG/onboarding |
| 11 | 研发流程与治理 | 9.0 | §10.6 全套规则、§12.1 冻结窗口 |
| 12 | 成本与效率 | 9.0 | §9.9 口径、附录 D 计费接口 |
| 13 | 团队与事故 | 9.0（外置） | 附录 D 明确归属与接口，非"无人负责" |

### E.3 达标结论

| 维度 | 标准 | 自评 | 结果 |
|---|---|---|---|
| 内部 6 项 | 每项 ≥9.5 | 9.5 × 6 | ✅ 达标 |
| 外部 13 域 | 每域 ≥9.0 | 12 域 ≥9.0 + 1 域外置但接口齐备 | ✅ 达标 |
| 30 项清单 | ≥90% | 27 ✅ / 1 ⚠️ / 2 外置（有接口） | ✅ 达标 |
| 能力完整（6 项） | 6/6 可灰度/可观测/可回滚 | 设计完成，实现待 Phase 6 | ⚠️ 设计达标 |


> **自评的性质**：这是"设计覆盖度"自评，不是"实现完成度"。代码侧实际通过项以 DoD 为准（当前 0/46）。
> 评估的可靠做法是：按 DoD 逐条勾选，而不是按章节数标题。

---

## 附录 F：版本演进一览

| 版本 | 主题 | 行数 |
|---|---|---|
| v1.0 | 初版：4 组分层 + 6 阶段 | 517 |
| v1.1 | 双轨、原子性边界、迁移矩阵、性能门禁、终止准则 | 845 |
| v1.2 | 排期对账、端口/协作者签名、灰度/弃用/多租户/容量 | 1,048 |
| v1.3 | 数据生命周期、安全补遗、成本口径、治理规则、回归清单 | 1,197 |
| v1.4 | 指标基数、密钥托管、熔断、文档生成 | 1,333 |
| **v1.5** | 核心类型清单、扩展矩阵、模块健康度、Profiling、测试数据、PII、配置审计、多区姿态、CHANGELOG、运维接口 | 1,591 |
| v1.6 | 合并能力追平为 §十五、docs 精简为单一文档 | 1,756 |
| v1.7 | 定调「设计升级 + 能力完整」，引入破坏性变更管理与迁移轨 | 1,887 |
| v1.8 | 未上线：去掉迁移/兼容/回滚流程，DoD 58，排期 12 周 | 1,782 |
| v1.9 | 新增附录 G：9 张架构图 | 2,097 |
| **v1.10** | 对齐 50 项能力全景：附录 H 矩阵、§3.12 已有能力约束、§7.6 回归清单 | 当前 |

---

## 附录 G：架构图（v1.9 新增）

> 以下全部为**目标态**（重构 + 能力追平完成后的设计终点），不是当前代码。
> 阅读顺序：G.2 看代码怎么分 → G.3 看抽象在哪 → G.5 看请求怎么走 → G.7 看存了什么 → G.9 看什么时候做什么。

### G.1 系统上下文

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐
│ Java 控制面   │ │ 其它业务调用方│ │ AG-UI / A2A  │ │ 运维 / CI   │
│ AK/SK + HMAC │ │ AK/SK + HMAC │ │ 第三方客户端  │ │ helm/kubectl│
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └─────┬──────┘
       │ /v1             │ /v1            │ /v1/ag-ui    │
       │                 │                │ /v1/a2a      │
       ▼                 ▼                ▼              ▼
┌────────────────────────────────────────────────────────────────────┐
│                    Python Agent Runtime                            │
│   ┌───────────────────────┐      ┌───────────────────────┐         │
│   │ API 进程               │      │ Worker 进程            │         │
│   │ 受理 / 查询 / SSE      │      │ 执行 / 恢复            │         │
│   │ 协议适配（AG-UI/A2A）  │      │ 后台任务 / 建队         │         │
│   └───────────────────────┘      └───────────────────────┘         │
└───┬──────────┬──────────┬──────────────┬──────────────┬───────────┘
    ▼          ▼          ▼              ▼              ▼
┌────────┐ ┌──────────┐ ┌────────┐ ┌────────────┐ ┌──────────────┐
│ Redis  │ │PostgreSQL│ │模型网关 │ │ MCP Server │ │ 沙箱          │
│队列/状态│ │Checkpoint│ │ (LLM)  │ │  (工具)    │ │ HTTP/Docker/ │
│事件/回放│ │          │ │        │ │            │ │ K8s          │
└────────┘ └──────────┘ └────────┘ └────────────┘ └──────────────┘
```

### G.2 分层与依赖

```
┌──────────────────────────────────────────────────────────────────┐
│ 入口 entrypoints                                                 │
│   api.py（/v1/* · /v1/ag-ui/* · /v1/a2a/* · SSE）                 │
│   worker_main.py（进程生命周期 · 信号 · 优雅停机）                 │
└─────────────────────────────┬────────────────────────────────────┘
                              │ 只调用用例
┌─────────────────────────────▼────────────────────────────────────┐
│ 编排 runtime                                                     │
│   submit   execute   resume   cancel   worker                    │
│   ├─ attachments  附件加载/解析/落沙箱                             │
│   ├─ usage        token 汇总（纯函数）                             │
│   ├─ interrupts   中断检测与待决策                                 │
│   ├─ result       答案/结构化/todos（纯函数）                       │
│   ├─ replay       会话事件回放                                    │
│   └─ team         建队：spawn / 收窄校验 / 汇总                    │
└──────────┬───────────────────────────────┬───────────────────────┘
           │ 7 个端口                       │ 只读切片
┌──────────▼───────────────┐      ┌────────▼──────────────────────┐
│ ports.py（7）             │      │ RuntimeLimits                 │
│ Lifecycle Queue State    │      │ 上限·步数·附件·排空·预算       │
│ Events File Sandbox      │      └───────────────────────────────┘
│ AgentFactory             │
└──────────┬───────────────┘
           │ 适配器实现
┌──────────▼───────────────────────────────────────────────────────┐
│ adapters（唯一接触外部系统）                                       │
│   redis/{lifecycle,queue,state,events,files,memory,...}          │
│   sandbox/{http,docker,kubernetes,local}                         │
│   llm/{deepagents_factory,registry,circuit_breaker}              │
│   protocol/{ag_ui,a2a}   只消费事件，不改编排                      │
└──────────┬───────────────────────────────────────────────────────┘
           │ 依赖
┌──────────▼───────────────────────────────────────────────────────┐
│ core（无 IO · 无配置 · 可 100% 单测）                              │
│   models  events  failures  policies  documents                  │
└──────────────────────────────────────────────────────────────────┘

横切 infra：logging · tracing · metrics · signing · network
配置 config：base · redis · auth · sandbox · observability · limits
装配 wiring.py：唯一知道"哪个实现配哪个端口"
```

**铁律**：箭头只向下；`core` 无 IO；`adapters/protocol` 不被编排反向依赖。

### G.3 七端口与实现

```
RunLifecyclePort ─┬─ RedisRunLifecycle   enqueue: claim+state+payload+XADD（1 个 Lua）
                  │                      approve: state+payload+XADD（1 个 Lua）
                  │                      建队：父 Run 创建子 Run（同一端口）
QueuePort        ─── RedisTaskQueue       read/reclaim/ack/retry/dead_letter/depth
                  │                      后台卸载复用"恢复消息"
StatePort        ─── RedisRunState        状态投影 + Run/Session/配额 三套锁
                  │                      建队共享配额池
EventsPort       ─┬─ RedisEventPublisher  发布（盖章序号/schema_version）
                  └─ RedisEventReader     读取（回放 / 协议适配共用）
FilePort         ─── RedisFileStore       租户隔离 + TTL
SandboxPort      ─┬─ HttpSandbox          隔离层级（Run/Session/User/Tenant）
                  ├─ DockerSandbox
                  ├─ KubernetesSandbox
                  └─ LocalSandbox（仅开发）
AgentFactoryPort ─── DeepAgentsFactory    唯一 import Agent 框架（外层熔断）

非端口：protocol/{ag_ui,a2a} · replay —— 都只消费现有端口，不新增抽象
```

**关键**：6 项新能力**没有新增任何端口**——端口按事务边界切分，能力按用途叠加。

### G.4 部署视图

```
Kubernetes Namespace
┌──────────────────────────────────────────────────────────────────┐
│ Deployment: runtime-api                      replicas = 3        │
│   :8800  /v1/*  ·  /v1/ag-ui/*  ·  /v1/a2a/*  ·  SSE             │
│   liveness  → /v1/health（只看进程）                              │
│   readiness → /v1/ready （看 Redis）                              │
│   无本地状态；回放缓冲在 Redis，无需粘性会话                        │
├──────────────────────────────────────────────────────────────────┤
│ Deployment: runtime-worker                   replicas = 4        │
│   不暴露端口；消费 agent:tasks                                    │
│   后台工具、建队子 Run 在此执行                                    │
│   drain ≥60s；terminationGracePeriodSeconds = 90                 │
├──────────────────────────────────────────────────────────────────┤
│ PDB minAvailable=1 · topologySpread 跨 AZ · resources 显式         │
│ 镜像非 root + HEALTHCHECK                                         │
└───────────────┬──────────────────────────────┬───────────────────┘
        ┌───────▼────────┐            ┌────────▼─────────┐
        │ Redis 主从/多AZ │            │ PostgreSQL 多AZ  │
        │ 队列/状态/事件  │            │ Checkpoint       │
        │ 回放/文件/锁    │            │                  │
        └────────────────┘            └──────────────────┘
```

### G.5 时序

#### G.5.1 主路径

```
调用方     API        submit       队列/状态      Worker     execute      适配器
  │         │           │             │             │           │            │
  ├─POST───►│           │             │             │           │            │
  │         ├ HMAC/限流/背压          │             │           │            │
  │         ├──────────►│             │             │           │            │
  │         │           ├ 绑定身份/准入 │             │           │            │
  │         │           ├────────────►│             │           │            │
  │         │           │             ├ Lua 事务 ──►│             │           │
  │         │◄─202──────┤             │ claim+state │             │           │
  │         │  run_id   │             │ +payload+XADD             │           │
  │         │           │             ├ XREADGROUP ►│             │           │
  │         │           │             │             ├ 二次准入     │           │
  │         │           │             │             ├ 三层锁       │           │
  │         │           │             │             ├────────────►│           │
  │         │           │             │             │             ├ RUNNING   │
  │         │           │             │             │             ├ 事件 ────►│
  │         │           │             │             │             ├ 附件 ────►│
  │         │           │             │             │             ├ 构建 ────►│
  │         │           │             │             │             ├ 流式 ────►│
  │         │           │             │             │             │ 模型/MCP/沙箱
  │◄─SSE────┴───────────┴─────────────┴─────────────┴─────────────┤ 事件+回放  │
  │         │           │             │             │◄── 终态 ────┤           │
  │         │           │             │             ├ ACK/retry(3)/DLQ        │
```

#### G.5.2 三条能力支线

```
① 后台工具卸载
   工具超时(>30s) 或声明可后台
        ├─ 事件 tool_deferred ───────► 会话事件流（回放缓冲）
        ├─ 后台执行（单 Run 上限 3，超出排队）
        └─ 完成 ──► 结果注入 ──► 复用恢复机制唤醒 ──► Agent 继续
   失败：tool_failed；进程崩溃：租约到期重投

② 运行时建队
   leader ── spawn_worker(task, role) ──► 子 Run（独立 run_id / 事件流）
        ├─ 准入：子快照必须是父快照子集（工具/模型/沙箱/配额只能更小）
        ├─ 共享会话与配额池（并发 ≤3，总 Run ≤10，token 硬上限）
        ├─ 事件默认聚合父流（带 worker_id）
        └─ 父取消 → 级联取消；子结果作为工具结果回传 leader

③ 中断恢复（HITL）
   工具命中 interrupt_on
        ├─ 保存待决策 + 状态 WAITING_CONFIRMATION + ACK
        └─ POST /resume（approve / reject / edit / respond）
             ├─ edit：按工具 schema 校验，禁改工具名与作用对象
             ├─ 审计事件（谁改了什么）
             └─ RESUMING → RUNNING，从 checkpoint 精确续跑
```

### G.6 状态机

```
             ┌──────────┐
  POST ─────►│ ACCEPTED │
             └────┬─────┘
     需计划审批？  │
     ┌────────────┴──────────────┐
    是                           否
     ▼                            ▼
┌─────────────────┐        ┌──────────┐
│ PENDING_APPROVAL│        │  QUEUED  │
└───┬─────────┬───┘        └────┬─────┘
    │approve  │reject            │ 取到
    └────┬────┴──► CANCELLED     ▼
         └─────────────────► ┌──────────┐
                             │ RUNNING  │◄──────────────┐
                             └──┬─┬─┬─┬─┘               │
              ┌────────────────┘ │ │ └───────────┐     │
              ▼                  ▼ │             ▼     │
      ┌────────────┐   ┌──────────┐│  ┌──────────┴───────────┐
      │ COMPLETED  │   │  FAILED  ││  │ WAITING_CONFIRMATION │
      └────────────┘   └──────────┘│  └──────────────────────┘
                                    ▼      （resume → RESUMING → RUNNING）
                             ┌───────────┐
                             │ CANCELLED │
                             └───────────┘

中间态：RETRYING · RESUMING
后台卸载不改变 Run 状态，只发事件并在完成时唤醒。
```

### G.7 数据视图

```
Redis
├── agent:tasks                            Stream  任务队列（消费者组 + 死信）
├── agent:run:{id}:state                   Hash    状态投影（TTL 7 天）
├── agent:run:{id}:events                  Stream  运行事件（MAXLEN 裁剪）
├── agent:session:{tenant}:{sid}:events    Stream  会话回放缓冲（1 万条 / 24h）
├── agent:run:{id}:claim                   String  幂等键（SET NX EX）
├── agent:run:{id}:request                 String  请求载荷
├── agent:run:{id}:approval-payload        String  待审批载荷
├── agent:run:{id}:lease                   String  Run 租约
├── agent:session:{tenant}:{sid}:lease     String  会话租约
├── agent:principal:{hash}:concurrency     ZSET    并发配额（建队共享池）
├── agent:team:{parent_run}:members        Set     建队成员
├── agent:file:{tenant}:{fid}              String  附件（TTL 1 小时）
├── agent:auth:nonce:{ak}:{nonce}          String  防重放（TTL 300s）
└── mem:{tenant}:{user}:*                  List    会话历史 / 长期记忆

PostgreSQL
└── LangGraph checkpoint（thread / checkpoint / writes）
    —— 外部组件所有；建队子 Run 各自独立线程

沙箱内
└── /workspace/{run|session|user|tenant}/…   四层隔离

规则：Key 与 TTL 可直接调整；改后必须同步 §8.3 所有权/生命周期表与回归断言。
```

### G.8 能力叠加（13 域 + 6 项）

```
外部能力 13 域                        依赖的内部结构
├─ 契约与演进 ──────────────────────── 事件联合类型 + schema_version（预留）+ 生成式文档
├─ 数据与状态 ──────────────────────── RunLifecyclePort / StatePort / FilePort + 对账
├─ 可靠性工程 ──────────────────────── 幂等 + 三锁 + 死信 + 超时 + 熔断
├─ 可观测运维 ──────────────────────── infra/metrics（标签白名单）+ 告警 + 看板 + Runbook
├─ 安全与合规 ──────────────────────── HMAC + 双准入 + 轮换 + body 上限 + 审计 + PII
├─ 性能与容量 ──────────────────────── 基线 + 冒烟压测 + 容量公式 + profiling
├─ 测试体系 ────────────────────────── 契约 + 集成 + 属性 + 故障注入 + 测试工厂
├─ 交付与发布 ──────────────────────── CI 六阶段 + 镜像 + Helm + 灰度
├─ 配置与密钥 ──────────────────────── 6 组配置 + 启动校验 + Secret 托管 + GitOps
├─ 文档与知识 ──────────────────────── contracts + generated + ADR + CHANGELOG
├─ 研发治理 ────────────────────────── CODEOWNERS + PR 规范 + 分支保护 + 技术债
├─ 成本与效率 ──────────────────────── token/租户/千次提交 三口径
└─ 团队与事故 ──────────────────────── 外置运维手册（附录 D 七接口）

能力 6 项（Track C）                  依赖的内部结构
├─ 会话回放 ────────────────────────── EventsPort.read + 会话事件流
├─ HITL 编辑 ───────────────────────── 中断载荷协议 + 参数校验 + 审计
├─ 隔离层级 ────────────────────────── SandboxPort + 路径拼接
├─ 后台卸载 ────────────────────────── QueuePort + 恢复机制
├─ 协议适配 ────────────────────────── adapters/protocol（消费 EventsPort）
└─ 运行时建队 ──────────────────────── RunLifecyclePort + 配额 + 子快照收窄
```

### G.9 三轨排期

```
        W1  W2  W3  W4  W5  W6  W7  W8  W9 W10 W11 W12
Track A ████████████████████████████████████████░░░░░░░
        P0  P1  P2  P3  P4  测试补齐    收口
Track B ██████████████████████████████████████████████░
        CI  unit 集成 镜像 Helm 告警 供应链 灰度 收口
Track C ░░░░░░░░░░░░██████████████████████████████░░░░░
                    回放 隔离 HITL 后台 协议 建队 灰度
                                  ▲ 依赖 P1/P2 完成
```

**工期**：59 人日 ≈ 12 周（重构 29 + 能力 25 + 缓冲 5）。
**说明**：未上线、无兼容包袱，因此没有迁移轨。

### G.10 图与章节对应

| 图 | 章节 |
|---|---|
| G.1 系统上下文 | §1、§3.1 |
| G.2 分层与依赖 | §3.1、§3.2、附录 B |
| G.3 端口与实现 | §3.5、§3.6、§3.7 |
| G.4 部署 | §9.1、§9.2、§9.10 |
| G.5 时序 | §5 Phase 2–3、§15.4 |
| G.6 状态机 | §三、§七 |
| G.7 数据视图 | §8.3 |
| G.8 能力叠加 | §一、§十五 |
| G.9 排期 | §十二 |

### G.11 图例

| 符号 | 含义 |
|---|---|
| `──►` | 调用 / 依赖 |
| `┌──┐` | 进程或部署单元 |
| `├──` | 存储键或模块 |
| `░` / `█` | 排期中的空档 / 占用 |

---

## 附录 H：50 项能力矩阵（v1.10 新增）

> 标尺：仓库根 `docs/Agent 服务能力与扩展点全景.md`（若已迁入运行时目录则为其同名副本）。
> 状态：✅ 有设计 / ⚠️ 已实现但计划需补约束 / ❌ 空缺 / ⛔ 明确不做。
> 合计：**34 ✅ · 11 ⚠️ · 3 ❌ · 2 ⛔**。

| # | 能力 | 域 | 状态 | 计划落点 | 本次动作 |
|---|---|---|---|---|---|
| 1 | HTTP API / SSE / WS | 接入 | ⚠️ | §3、§9 | 保持（WS 未支持，明确不做） |
| 2 | 服务间认证 / 用户认证 | 接入 | ⚠️ | §9.8.1 | 服务间保持；用户认证归控制面 |
| 3 | 限流 / 配额 / 背压 | 接入 | ✅ | §7.4-2、§7.6 | 保持 |
| 4 | 协议适配（AG-UI/A2A） | 接入 | ✅ | §15.4.5 | 新增（Track C） |
| 5 | SDK / Webhook | 接入 | ❌ | §14 | 不做 |
| 6 | 文件上传与附件 | 接入 | ✅ | §3.8、§7.6 | 保持 |
| 7 | 会话生命周期 | 会话 | ✅ | §8.3.2 | 保持 |
| 8 | 历史与回放 | 会话 | ✅ | §15.4.1、§7.6 | 历史保持；回放新增 |
| 9 | 上下文压缩 | 会话 | ⚠️ | §3.12.1 | 补约束，行为不变 |
| 10 | 记忆 | 会话 | ⚠️ | §3.12.2 | 补约束，行为不变 |
| 11 | 工作区 | 会话 | ✅ | §15.4.3 | 新增隔离层级 |
| 12 | Agent 循环 | 执行 | ✅ | §3.7 | 保持（委托） |
| 13 | 工具调用（MCP） | 执行 | ✅ | §3.10 | 保持 |
| 14 | 沙箱 | 执行 | ✅ | §3.7 | 保持（三后端） |
| 15 | HITL | 执行 | ✅ | §15.4.2 | 保持 + 编辑参数 |
| 16 | 结构化输出 | 执行 | ⚠️ | §3.12.3 | 补约束，不加重试 |
| 17 | 子 Agent / 团队 | 执行 | ✅ | §15.4.6 | 新增建队 |
| 18 | 后台任务 | 执行 | ✅ | §15.4.4 | 新增卸载 |
| 19 | 调度（Cron） | 执行 | ⛔ | §14 | 不做（归控制面） |
| 20 | Provider 抽象 | 模型 | ✅ | §3.10 | 保持 |
| 21 | 路由与降级 | 模型 | ❌ | §14 | 不做（单 provider） |
| 22 | 参数与缓存 | 模型 | ⚠️ | §3.12.6 | 补约束，不可控 |
| 23 | 多模态 | 模型 | ⚠️ | §15.4.3 | 图/表格保持；音频不做 |
| 24 | 计量 | 模型 | ✅ | §3.8、§9.9 | 保持 |
| 25 | 规划 / Todo | 编排 | ⚠️ | §3.12.4 | 补约束，默认关闭 |
| 26 | 工作流 / DAG | 编排 | ⛔ | §14 | 不做（归控制面） |
| 27 | 自评迭代 | 编排 | ⚠️ | §3.12.5 | 补约束，显式开启 |
| 28 | 多租户隔离 | 治理 | ✅ | §9.7 | 保持 |
| 29 | 权限与 Scope | 治理 | ✅ | §7.4-4 | 保持 |
| 30 | 能力收窄 | 治理 | ✅ | §15.4.6 | 保持 + 建队校验 |
| 31 | 审计 | 治理 | ✅ | §9.8.3 | 保持 |
| 32 | PII 与保留期 | 治理 | ✅ | §9.8.5、§8.3.2 | 保持 |
| 33 | 成本归因 | 治理 | ✅ | §9.9 | 保持 |
| 34 | 幂等 | 可靠 | ✅ | §3.5 | 保持 |
| 35 | 队列与租约 | 可靠 | ✅ | §3.5、§3.7 | 保持 |
| 36 | 重试与超时 | 可靠 | ✅ | §7.4-1 | 保持 |
| 37 | 熔断与降级 | 可靠 | ✅ | §10.7 | 新增熔断 |
| 38 | 优雅停机 | 可靠 | ✅ | §9.2 | 保持 |
| 39 | 灾备 | 可靠 | ⚠️ | §9.10、附录 D | 多区姿态；RPO/RTO 外置 |
| 40 | 日志 / 指标 / 追踪 | 可观测 | ✅ | §6.3、§7.4-3 | 保持 |
| 41 | 告警与 SLO | 可观测 | ✅ | §10.1、§10.2 | 保持 |
| 42 | 看板与 Runbook | 可观测 | ✅ | §10.3、§10.5 | 保持 |
| 43 | 评估 | 可观测 | ❌ | §14 | 不做（独立离线系统） |
| 44 | CI/CD | 交付 | ✅ | §9.3 | 保持 |
| 45 | 镜像与 IaC | 交付 | ✅ | §9.1、§9.2 | 保持 |
| 46 | 灰度与回滚 | 交付 | ✅ | §9.4 | 保持 |
| 47 | 供应链 | 交付 | ✅ | §9.3 | 保持 |
| 48 | 健康检查与探针 | 交付 | ✅ | §9.2 | 保持 |
| 49 | 配置与密钥管理 | 交付 | ✅ | §9.8.4、§3.2 | 保持 |
| 50 | 版本与升级 | 交付 | ⚠️ | §8.1 | 只留版本字段，无升级路径 |

### H.1 按域统计

| 域 | ✅ | ⚠️ | ❌ | ⛔ |
|---|---|---|---|---|
| 接入 | 3 | 2 | 1 | 0 |
| 会话与状态 | 3 | 2 | 0 | 0 |
| 执行 | 6 | 1 | 0 | 1 |
| 模型 | 2 | 2 | 1 | 0 |
| 编排 | 0 | 2 | 0 | 1 |
| 治理 | 6 | 0 | 0 | 0 |
| 可靠性 | 5 | 1 | 0 | 0 |
| 可观测 | 3 | 0 | 1 | 0 |
| 交付 | 6 | 1 | 0 | 0 |
| **合计** | **34** | **11** | **3** | **2** |

### H.2 口径说明

- **覆盖率**：34/50 = **68%** 有设计；加上 11 项"已实现、本次仅补约束"后为 **45/50 = 90%**；
- 剩余 5 项（❌ 3 + ⛔ 2）均已在 §14 写明"不做/外置"及理由；
- ⚠️ 共 11 项：其中 **6 项**（9/10/16/22/25/27）在 §3.12 有专门约束；其余 **5 项**（1/2/23/39/50）在 §3.7、§9.10、§15.4.3、附录 D 已有说明。
- **维护规则**：新增或删除能力时，必须同步更新本表与 §7.6 回归清单，否则视为文档未完成。
