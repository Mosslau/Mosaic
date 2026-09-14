# 企业级 Data + AI 平台参考架构

> 本文档定义"一个通用的、企业级的 Data+AI 平台应该长什么样"——与具体行业无关。
> 定位:**参照系**。OceanVerse 的设计、选型、差距分析均以本文为尺。
> 版本 v1.0 · 2026-09-14

---

## 0. 总览:八大能力域

```
┌─────────────────────────────────────────────────────────────────┐
│ ⑧ AI 工程化    特征平台→训练→模型管理→推理服务→LLM 应用(RAG/Agent)│
├─────────────────────────────────────────────────────────────────┤
│ ⑦ 语义与服务   指标层 · 标签层 · API 服务 · BI                   │
├─────────────────────────────────────────────────────────────────┤
│ ⑥ 数据治理     质量 · 血缘 · 安全 · 成本          (控制面核心)    │
├─────────────────────────────────────────────────────────────────┤
│ ⑤ 开发工作台   SQL/Notebook/管道 IDE · 调度 · 调试 · 版本管理     │
├─────────────────────────────────────────────────────────────────┤
│ ④ 统一目录     表/模型/特征/指标 —— Data+AI 一个 Catalog          │
├─────────────────────────────────────────────────────────────────┤
│ ③ 计算引擎     批流一体(Spark/Flink) · OLAP(CK/Doris) · AI(Ray) │
├─────────────────────────────────────────────────────────────────┤
│ ② 存储底座     湖仓一体(Iceberg/Delta/Hudi + 对象存储)            │
├─────────────────────────────────────────────────────────────────┤
│ ① 数据集成     批 / 流 / CDC / 文件 / API 全域接入                │
└─────────────────────────────────────────────────────────────────┘
        横切: 可观测性 · 多租户与权限 · 开放 API · 部署运维(K8s)
```

**判断一个平台好坏的四条标准**(超越功能清单):

1. **统一目录是不是单一真相源**——还是又一个元数据孤岛
2. **治理是内建在流水线里**——还是事后外挂的补丁
3. **Data 和 AI 是否真正共栈**——特征、权限、血缘是否打通,还是两套系统各玩各的
4. **开放性**——开放表格式 + 开放 API,不被单一厂商锁定

---

## ① 数据集成(Data Integration)

**职责**:把所有形态的数据接进来——这是平台的"进口",决定了平台能吃多大的世界。

| 接入形态 | 说明 | 代表实现 |
|---|---|---|
| 流式 | 消息队列/设备上报,秒级 | Kafka、Pulsar;Flink CDC |
| 批量 T+1 | 业务库定时抽取 | DataX、SeaTunnel、Sqoop(淘汰) |
| CDC | 数据库变更捕获,分钟级 | Debezium、Flink CDC、Canal |
| 文件 | Excel/CSV/日志/报表 | 自研文件服务 + 对象存储 |
| 多模态 | 图片/音频/视频 | 对象存储 + 元数据管道 |
| API/SaaS | 第三方系统拉取 | Airbyte(300+ 连接器) |

**业界实践**:Airbyte(开源连接器生态)、Apache SeaTunnel(国内开源,批流一体集成)、Apache InLong(腾讯开源,万亿级接入)、Flink CDC(阿里开源)。

**企业级要求**:接入任务可配置化(非硬编码)、断点续传、脏数据隔离(DLQ)、接入审计、Schema 契约管理。

**OceanVerse 落点**:实时通道(Go 网关)+ 离线通道(文件服务/CDC/MinIO),期①建设;连接器生态不自建,需要时引入 SeaTunnel。

---

## ② 存储底座(Storage Foundation)

**职责**:一份数据、多处可用——湖仓一体是企业级的共识答案。

| 要素 | 说明 | 代表实现 |
|---|---|---|
| 开放表格式 | ACID、Schema 演进、时间旅行、隐藏分区 | **Iceberg**(生态最中立)、Delta Lake(Databricks)、Hudi( upsert 强) |
| 对象存储 | 廉价、弹性、近乎无限 | S3 / MinIO / OSS / HDFS |
| 数据分层 | ODS→DWD→DWS→ADS + DIM | 行业通用数仓方法论 |
| 加速层 | 面向查询的 MPP 引擎 | ClickHouse、Doris、StarRocks |

**企业级要求**:开放表格式(不锁定)、存储计算分离、分层生命周期(热温冷)、小文件治理、表级 owner/SLA 元数据。

**关键认知**:湖(Iceberg)是**底座与真相源**,OLAP 引擎(ClickHouse)是**serving 加速层**——两者不是竞品,是分工。平台成熟度的标志之一是"任何一张服务层的表都能从湖仓重建"。

**OceanVerse 落点**:Iceberg + MinIO(期①底座)+ ClickHouse(serving 层);数据分层规约见《项目架构》文档。

---

## ③ 计算引擎(Compute Engines)

**职责**:三类负载,三类引擎,各司其职。

| 负载 | 引擎类型 | 代表实现 |
|---|---|---|
| 流处理 | 状态化流计算 | **Flink**(事实标准) |
| 批处理 | 离线 ETL/分层转换 | Spark(生态最全)、Flink 批模式 |
| 交互式分析 | MPP OLAP | ClickHouse、Doris、StarRocks、Trino(联邦) |
| AI 计算 | Python 原生分布式 | **Ray**(训练/批量推理/embedding/多模态) |
| ML 训练 | GPU 框架 | PyTorch、TensorFlow |

**企业级要求**:批流一体(同一 SQL 语义)、资源隔离与弹性(K8s/Yarn)、作业全生命周期管理(提交/监控/savepoint/版本)、计算成本可归因。

**关键认知**:Ray 与 Flink/Spark **不是并列的第三数据引擎**——Flink/Spark 算数据,Ray 算模型。Ray 服务 AI 层:批量推理、embedding 生成、超参搜索、多模态预处理。

**OceanVerse 落点**:Flink(实时主力)+ Flink 批模式(分层转换,暂缓 Spark)+ ClickHouse(OLAP)+ Ray(第 3 阶段,AI 负载出现时启用)。

---

## ④ 统一目录(Unified Catalog)

**职责**:Data+AI 一个 Catalog——表、文件、模型、特征、指标,一处注册、处处可见。**这是平台的心脏,也是"项目"与"平台"的分水岭。**

| 能力 | 说明 |
|---|---|
| 技术元数据 | 表/字段/分区/文件/模型/特征的定义与统计 |
| 业务元数据 | 口径、负责人、标签、密级 |
| 运行时元数据 | 任务、血缘、质量结果、用量 |
| 统一授权 | 基于 Catalog 的行列级权限,一处授权处处生效 |
| 开放接口 | REST/JDBC/HCatalog 兼容,引擎与工具自由接入 |

**业界实践**:Unity Catalog(Databricks)、DataHub、OpenMetadata、**Apache Gravitino**(面向 Data+AI 统一目录,含模型/文件,最年轻也最有方向感)、Hive Metastore(上一代事实标准)。

**OceanVerse 落点**:期①–② 用"指标口径字典 + 数据资产清单"(Markdown+表)做最小真相源;第 4 阶段(平台化)评估引入 **Gravitino/DataHub**,不自研。

---

## ⑤ 开发工作台(Development Workbench)

**职责**:数据开发与 AI 开发的"IDE"——让生产者自助,是平台被用起来的关键。

| 能力 | 说明 | 代表实现 |
|---|---|---|
| SQL IDE | 多引擎 SQL 编辑/执行/结果预览 | DataGrip、Hue、DBeaver |
| Notebook | Python/Scala 交互开发 | Jupyter、Zeppelin |
| 管道开发 | DAG 编排、任务依赖、回填 | DolphinScheduler、Airflow |
| 调试与诊断 | 日志、执行计划、数据探查 | 引擎 UI + 平台封装 |
| 版本管理 | 脚本/DAG Git 化、评审流 | Git + CI |
| 发布管理 | 开发/测试/生产环境隔离与一键发布 | 平台能力 |

**业界实践**:**WeDataSphere(微众银行开源套件:Linkis 计算中间件 + DataSphere Studio 工作台 + Qualitis 质量 + Exchangis 交换)**——国内最完整的开源参照;商业对标 DataWorks/DataLeap 的开发空间。

**OceanVerse 落点**:DolphinScheduler(调度)+ Git(脚本资产化)起步;工作台不自研,期④研究 WeDataSphere 复用。

---

## ⑥ 数据治理(Governance,控制面核心)

**职责**:让数据可信、可控、可追责——管控不出活,但让出活的东西值得信任。

| 域 | 内容 | 开源实现 |
|---|---|---|
| 数据质量 | 空值/唯一/完整/时效/波动检测,质量分 | Great Expectations、Qualitis |
| 血缘 | 表/字段/任务/指标血缘,影响分析 | OpenLineage、DataHub |
| 安全合规 | 行列级权限、脱敏、审计、密级 | Ranger、Catalog 内建 |
| 成本治理 | 存储/计算/查询/Token 成本归因与优化 | 自研 + 账单分析 |

**企业级要求**:质量规则**内建于流水线**(不通过即阻断/告警),而非事后扫描;血缘自动采集(非人工登记);权限一点配置全栈生效。

**OceanVerse 落点**:期②起交付最小控制面(质量日检 + 资产清单 + 审计);血缘与安全随统一目录(④)在第 4 阶段系统化。

---

## ⑦ 语义与服务(Semantic & Serving)

**职责**:把数据翻译成业务语言,并以服务的形式交付——消费方不碰表,只碰语义。

| 层 | 内容 | 代表实现 |
|---|---|---|
| 指标层 | 口径一处定义,BI/API/AI 处处复用 | Cube、Headless BI |
| 标签层 | 实体画像(用户/车辆标签) | 自研 + Doris/CK |
| API 服务 | 指标/数据 REST 化 | Java 微服务、Kyuubi |
| BI 可视化 | 看板、自助分析 | Superset、Grafana、FineBI |

**企业级要求**:指标口径字典是强约束(新指标先登记后开发);所有出口(报表/API/AI)引用同一口径——**"昨天故障率"在任何出口答案一致**。

**OceanVerse 落点**:指标口径字典(期②)+ Java 指标服务(期②)+ Grafana/Superset 看板;AI 问数(期③)只消费字典登记的指标。

---

## ⑧ AI 工程化(AI Engineering)

**职责**:AI 从 Demo 到生产的全生命周期——与数据共栈是新一代平台的分水岭。

```
数据资产(①–④) → 特征平台 → 训练(Ray/PyTorch) → 模型管理(MLflow)
→ 推理服务(vLLM/Triton) → AI 应用(RAG/Agent/Copilot) → 评测与反馈
```

| 能力 | 说明 | 代表实现 |
|---|---|---|
| 特征平台 | 特征定义/离线在线一致/复用 | Feast |
| 模型管理 | 版本/登记/灰度/回滚 | MLflow |
| 推理服务 | 在线推理、批推理 | vLLM、Triton、Ray Serve |
| LLM 应用 | RAG/Agent/Tool Calling | LangChain/LangGraph、Dify |
| 评测体系 | 评测集、幻觉检测、质量分 | RAGAS、自研 |
| AI 治理 | Prompt 版本、调用审计、Token 成本、权限边界 | 与⑥打通 |

**企业级铁律**:AI 的权限边界 = 数据权限边界(AI 经 API 取数,不直连库);AI 输出可追溯(血缘到源数据);AI 成本可计价。

**OceanVerse 落点**:期③ 诊断助手 + 问数 Copilot(Tool Calling 调 API,RAG 后置);Ray 提供算力底座;评测集与调用审计内建。

---

## 附 A:业界平台速查

| 类别 | 平台 | 一句话 |
|---|---|---|
| 国际标杆 | Databricks | Data+AI 融合天花板(Lakehouse + Unity Catalog + Mosaic AI) |
| 国际标杆 | Snowflake | 易用性标杆(Cortex AI),封闭 |
| 国际标杆 | Palantir Foundry | 本体(Ontology)思想标杆 |
| 国内商业 | 阿里 DataWorks / 字节 DataLeap / 腾讯 WeData / 华为 DataArts / 网易数帆 / 袋鼠云数栈 / 星环 | 一站式开发治理平台 |
| 国内开源 | **WeDataSphere**(微众) | 最完整的开源数据平台套件 |
| 开源生态 | Gravitino / DataHub / SeaTunnel / InLong / Dinky / StreamPark / Kyuubi / Qualitis | 各能力域的可复用轮子 |

## 附 B:OceanVerse 差距与路线对照

| 能力域 | OceanVerse 现状 | 落点 |
|---|---|---|
| ① 数据集成 | 实时通道雏形(无鉴权限流),离线通道无 | **期①** |
| ② 存储底座 | CK 已部署无分层;Iceberg/MinIO 未建 | **期①** |
| ③ 计算引擎 | 3 个演示 Flink SQL;无状态管理 | **期①**(Ray 期③) |
| ④ 统一目录 | 无 | 期②字典/清单起步,第 4 阶段引 Gravitino/DataHub |
| ⑤ 开发工作台 | 无;DS 期①引入 | 期①起步,工作台不自研 |
| ⑥ 数据治理 | 无 | 期②最小控制面 |
| ⑦ 语义与服务 | analysis-service 雏形,口径未统一 | 期② |
| ⑧ AI 工程化 | 无 | 期③ |

> 原则:**平台能力向开源借力(④⑤⑥),场景能力(车联网领域模型、告警→工单闭环、售后诊断 AI)自己深耕。**
