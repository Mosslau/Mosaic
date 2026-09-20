# scripts —— 仓库工具脚本

> 本目录 6 个脚本：`check-docs.sh` / `check-mermaid.sh` 进 CI 的 `docs` 作业，`check-pipeline-health.sh` 进 `pipeline-health` 作业，
> `check-compose-budget.sh` + `test-compose-budget.sh` 进 `compose` 作业；本地改动后先跑一遍再提交。

## check-mermaid.sh — 文档 Mermaid 图渲染校验

文档里的流程图现在是**图即代码**：语法错了整张图不显示，且只在渲染端才暴露。改动任何 `.md` 里的 `mermaid` 块后跑一遍：

```bash
scripts/check-mermaid.sh                      # 全仓校验（跳过 .dsh/ 第三方技能文件）
scripts/check-mermaid.sh ingest/README.md     # 只校验指定文件
```

依赖 Docker（用 `minlag/mermaid-cli` 镜像渲染），临时产物在 `.tmp-mmdc/`（已 gitignore）。
**注意**：挂载目录必须在 `$HOME` 下——Rancher Desktop 只共享 `$HOME` 给 VM，`/tmp` 挂不进（与 `deploy/README` Q9 同源限制）。

## check-pipeline-health.sh — 链路健康自检（含 Q11 僵尸消费组判据）

把"消息明明被消费了、但**这个实例**的指标却冻结"这类**常规检查看不出来**的故障固化成一条命令。
起因（2026-09-18 实测）：评测时被「新 codec 实例 `/metrics` 计数恒 0 + 消费组 `LAG=0` + offset 在涨」
迷惑了十几分钟，真因是早期 `go run` 残留的**孤儿 codec 进程**仍持有分区 ——
`docker compose ps` 全绿、Prometheus target 全 up、lag=0，全都看不出来。

```bash
scripts/check-pipeline-health.sh            # 6 组判据, 期望 "异常 0 项" 且 exit 0
scripts/check-pipeline-health.sh -w 30      # 加长观测窗口
scripts/check-pipeline-health.sh -m         # 多副本横扩后放宽"成员数=1"
PROBE=0 scripts/check-pipeline-health.sh    # 空闲时不灌探针帧(不改动链路数据)
```

判据：① 消费组成员数（单副本应恒为 1）② 同一分区是否被多个成员持有
③ 服务端口监听者数量（>1 = 孤儿实例）④ `/metrics` 的 `consumed` 活性
（空闲时自动灌少量**合法**帧做强判据）⑤ 网关"受理 == 落盘"⑥ 自检前后是否**新增**告警。

> 探针会用 `bin-simulator` 发合法帧（真实经过链路），所以 `consumed/decoded` 会小幅增加 —— 属预期。
> 早期版本用 `"##probe"` 这类非法载荷，结果**探针自己触发了 `CodecDLQGrowing` 告警**（已修）。

## check-docs.sh — 文档事实校验

把"人工审计"固化成可重复执行的门禁，覆盖三类**曾真实发生**的漂移：

| 检查 | 挡住什么 |
|---|---|
| ① 禁用词/旧路径扫描 | 旧目录名（`ingest/simulator`）、旧的数量声明（`五包`、`11 项配置`）、旧端口（`localhost:8080`）、**文档重构前的旧文件名**（`接入层与车端接入网关设计-v1.md` 等 5 个） <!-- check-docs:allow --> |
| ② 章节引用检查 | 裸 `§x.y` 实际指向别的文档（跨文档引用必须带《》/"设计文档"/ 带 `.md` 的文件名） |
| ③ 数字声明 vs 代码 | 配置项数、gateway 测试包数等"易腐数字"与实现对齐 |
| ④ topic/QoS 单一源 | 该表只允许出现在设计文档 §4.2 |
| ⑤ Mermaid 围栏嵌套 | ` ```text ` 里面又套 ` ```mermaid `（曾出现 4 处） |
| ⑥ 引用目标存在性 | 指向不存在的 `.md` |
| ⑦ 引用密度 | 服务手册指向层文档篇数超限（服务手册 ≤3、层文档 ≤4）——防"总分结构"重新退化成网状引用 |

```bash
scripts/check-docs.sh        # 失败即非零退出（CI 门禁）
```

## check-realtime-e2e.sh — 实时层端到端自检

注入测试数据 → 等窗口关闭 → **断言三张 ADS 表真的有数**。起因（2026-09-20 评估）：
CI 此前只到"建表 + 提作业 + 断言作业 RUNNING"，**不验证数据落表** —— SQL 语义 / 字段类型 / 时区改坏了照样全绿；
而当时的端到端验证是人工跑的。本脚本把那次人工验证固化成一条命令。

```bash
scripts/check-realtime-e2e.sh                 # 全过 exit 0（典型 ~4 分钟, 最坏 ~6 分钟）
E2E_TIMEOUT=300 scripts/check-realtime-e2e.sh # 放宽等待窗口（默认 240s, 从心跳结束开始计时）
```

> 耗时构成：等到整分钟（≤60s）→ 注入 → 心跳 120s（推进 watermark 让窗口关闭）→ 四条断言**共享一个截止时间**轮询。
> **注意 `earliest-offset` 的重放代价**：作业刚重启时先从最早留存位点重放，此时自检要等它追平 ——
> 本地留存量大时请放宽预算（如 `E2E_TIMEOUT=600`）；**CI 里 topic 是新建的空 topic，不受影响**。

四条断言（每条都能失败）：
① **在线数**：窗口内去重车辆数 ≥ 注入的车辆数；
② **故障数 + QoS1 去重**：同一条 `(vin, ts, code)` **注入两次**，`fault_cnt` 必须恰为 **1**；
③ **高温分级**：58℃ → `alarm`、47℃ → `warn`（阈值真的生效）；
④ **探针不污染**：三张表里不得出现 `OVPROBE*`。

退出码：`0` 全过 / `1` 有断言不成立 / `2` 前置不满足（集群或表没就绪，属环境问题）。

> **测试数据命名空间**：VIN 用 `OVE2E*`、故障码用 `E2E01`（自检保留段，会真实落进 ADS 表）。
> 注意与 `OVPROBE*` 的区别：探针会被 Flink 过滤掉（验链路活性），而自检数据必须**流到底**才能断言。

## check-compose-budget.sh — 容器内存预算门禁

`mem_limit` 只约束**单个**容器，不阻止"上限之和 > 物理内存"（实测出现过：八容器上限合计 6.88 GiB，
而 VM 只有 6.2 GiB）。本脚本把 `deploy/README.md` §3 那段人工算术变成可执行判据，五类：

| 判据 | 挡住什么 |
|---|---|
| ① 每服务都有 `mem_limit` | 漏一个就等于那个容器没有上限 |
| ② 合计 ≤ 预算（默认 6.5 GiB，`OV_BUDGET_MIB` 可覆盖；其中 1536 MiB 是给第 3 步 Flink 的预留额度） | 账面超配 |
| ③ 合计 ≤ VM 容量 × 0.85（本机可探测时） | 留不出 dockerd / VM 自身的余量 |
| ④ 成对约束 | ClickHouse 进程内上限 ≥ `mem_limit`、Redis `maxmemory` 相对 `mem_limit` 过高；**另含四个更隐蔽的失效方式**：`limits.xml` 没被 compose 挂进容器（死配置）/ `ratio=0`（实测语义是关上限）/ compose 里又把那个不生效的环境变量当配置写 / **缓存上限没显式声明**（镜像默认 mark 5 GiB、uncompressed 8 GiB 会与查询抢额度）。<br>注："上限必须显著高于进程地板（重启后 ≈850 MiB）"**不进门禁**——地板是测量值，只能写进 `limits.xml` 头注 + `deploy/README.md` Q17 |
| ⑤ 文档数字 vs compose | `deploy/README.md` 内存预算段的每个 `<服务> Nm`、合计、百分比与实际配置漂移（2026-09-20 就漂过一版：compose 抬到 1280m 而文档仍写 1152m） |

```bash
scripts/check-compose-budget.sh        # 失败即非零退出（CI 的 compose 作业调用）
```

> **判据 ④ 曾长期处于"跳过"状态**：它去 compose 里找 `CLICKHOUSE_MAX_SERVER_MEMORY_USAGE`，而该变量
> 早已按实测结论挪进 `limits.xml` —— 名义上有门禁、实际没跑（"一直是绿的"只说明它从来没跑）。
> **新增或修改判据请照 `test-compose-budget.sh` 的做法配负向对照**，并让"跳过"打印出**为什么**跳过。

### 负向对照：`test-compose-budget.sh`

门禁自己也会退化成"僵尸判据"，所以把对照固化下来：在**隔离假树**（`.tmp-budget-selftest/`，跑完即删，
不备份也不还原真实文件——中断都不会留下半改状态）里施加 11 种扰动，每一种都必须让门禁**变红并命中预期原因**。

```bash
scripts/test-compose-budget.sh     # 基线绿 + 11 则对照全红 = 门禁有鉴别力（CI 的 compose 作业调用）
```

覆盖：进程内上限越线 / `limits.xml` 未挂载 / `ratio=0` / 文件缺失 / **缓存上限未显式声明** / 无效环境变量当配置 /
README 合计漂移 / README 单值漂移 / README 漏服务 / 百分比不自洽 / 合计超预算。

## 文档结构约定（2026-09-18 重构后，方案 B）

**总分结构**：一份"总"（`ingest/README.md` = 阅读地图 / 文档分工 / 链路全景）+ 各模块"分"（自足手册）。

| 层 | 文件 | 必须包含 | 禁止 |
|---|---|---|---|
| 总 | `ingest/README.md` | 从哪看起、文档分工表、查哪篇、链路全景、当前状态 | 不写服务操作步骤 |
| 层（设计/规格/示例） | `ingest/docs/0{1,2,3}-*.md` | 为什么这么设计、契约、字节规格、可判定示例 | 不复制服务手册的跑/配/验步骤 |
| 分（服务手册） | `ingest/device-*/README.md` | 跑 / 配 / 验 / 排障 / 设计要点 / 延伸阅读 | 不复述层文档内容，指针 ≤3 篇 |

配套纪律：

- **章节编号**：服务手册的 `##` 一律带序号（`## 1.` …），其下 `### N.x` 的 N 必须与父节号一致——否则 `§x.y` 读者找不到
- **跨文档引用写法**：统一用简称《接入层设计》/《GB32960 映射》/《示例集》（每篇手册头部一行"简称约定"给出相对路径），不用 `《../docs/xx.md》` 这种路径式写法
- **单一源不变**：topic/QoS → 《接入层设计》§4.2；配置全表 → `device-gateway/README.md`；模拟器参数 → `device-simulator/README.md`；字节规格 → 《GB32960 映射》；进度 → `roadmap/项目进度.md`

## 文档图表约定

| 用 Mermaid | 保留代码块（不转） |
|---|---|
| 流程图 / 拓扑图 / 分层架构 / 泳道 / 状态机 / 时序 / 依赖树 | **目录树**（无 tree 语法，代码块对齐更好读）<br/>**字节布局与字段偏移**（`[类型 1B][版本 1B][长度 2B]` 这类精确表达）<br/>**公式**（对账等式）<br/>**配置对齐线**（`emqx.conf ═══ GATEWAY_WEBHOOK_TOKEN` 靠 `═══` 视觉表达对齐）<br/>**命令 / JSON 示例**（本就不是图） |

其它要求：

- **单一真相**：一处图只保留一种形式（转 Mermaid 即删 ASCII），避免两处漂移
- **大图拆分**：一张图超过 ~40 行就拆（例：《OceanVerse 架构总览》§1.1 的 154 行 ASCII 拆成"分层总览 / 接入层细节 / 湖仓与计算细节"三张）
- **渲染前提**：Mermaid 需要渲染器（GitHub / VS Code / GitLab / 多数 Markdown 预览）；纯终端 `cat` 不可读——因此**面向排障的速查内容仍用文字/表格**

## 目录约定（2026-09-17 决定）

| 目录 | 图表形式 | 理由 |
|---|---|---|
| `ingest/` | **Mermaid** | 层设计与协议文档，读者多在渲染环境（编辑器/GitHub）看；流程与拓扑密度高 |
| `roadmap/` | **ASCII** | 规划与个人路线文档，需**随处可读**（纯文本、终端、任意平台），且改动以文字为主 |
| `deploy/` | 无图（命令/配置） | 排障手册在终端用 |

> 因此 `scripts/check-mermaid.sh` 只对使用 Mermaid 的目录有意义（默认全仓扫描；`roadmap/` 下无 mermaid 块，天然跳过）。

