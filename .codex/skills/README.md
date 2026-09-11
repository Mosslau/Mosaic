# 技术文档 skill 家族

本目录下是一组**窄范围**的技术文档写作 skill。每个 skill 负责一类主题，独立可用：单个安装即可生效，不依赖其他 skill，也不依赖本 README。

## 两个任务大类

| 类别 | 回答的问题 | 成员 |
| --- | --- | --- |
| **解释类**（explaining-*） | 它是什么、为什么这样设计、怎么运行 | `explaining-algorithms`、`explaining-systems` |
| **记录类**（documenting-*） | 怎么用、能依赖什么、怎么改、坏了怎么办 | 其余 8 个 |

## 选型矩阵

先按「用户要的东西」定位，再按边界确认。

| 用户要的 | 用哪个 skill |
| --- | --- |
| 讲清一个算法或数据结构 | `explaining-algorithms` |
| 讲清一个系统、框架或代码库 | `explaining-systems` |
| 记住一次设计取舍（ADR） | `documenting-design-decisions` |
| 讲一个可复用的设计模式 | `documenting-architecture-patterns` |
| 说清一个语言特性 | `documenting-language-features` |
| 说清一组接口能依赖什么 | `documenting-api-contracts` |
| 说清存了什么、怎么迁移 | `documenting-data-models` |
| 教读者完成一个任务 | `documenting-tutorials` |
| 故障怎么诊断、怎么回滚 | `documenting-runbooks` |
| **这次改了什么、怎么升级** | `documenting-changes` |

## 全套 10 个 skill

| Skill | 一句话边界 |
| --- | --- |
| `explaining-algorithms` | 一个算法或数据结构；不写语法、架构模式、系统 |
| `explaining-systems` | 一个系统/框架/代码库；内在分三个子模式 |
| `documenting-language-features` | 语言语法与语义；不写框架 API、不写入门教程 |
| `documenting-architecture-patterns` | 一个可复用模式的上下文与权衡；不描述某个系统实例 |
| `documenting-api-contracts` | 接口契约（网络/消息/进程内）；不写存储实体 |
| `documenting-data-models` | 实体、字段、约束、索引、迁移；不写接口契约 |
| `documenting-design-decisions` | 一次决策的问题、候选与后果；不描述系统现状 |
| `documenting-tutorials` | 让读者做成一个任务；不写故障处置 |
| `documenting-runbooks` | 症状 → 诊断 → 修复 → 回滚；不写教学步骤 |
| `documenting-changes` | 版本差异 → 迁移动作 → 兼容影响；不写单次决策的由来 |

## 判定顺序

用户的目的不明确时，按这个顺序判定，命中即停：

1. **有没有真实用户要完成一个任务？** → `documenting-tutorials`
2. **有没有故障或需要操作生产？** → `documenting-runbooks`
3. **有没有一个接口？**（HTTP/RPC/消息/进程内函数）→ `documenting-api-contracts`
4. **有没有持久化的结构？**（表、集合、类型、文件）→ `documenting-data-models`
5. **是不是「从 A 版到 B 版要做什么」？** → `documenting-changes`
6. **是不是要记录一次取舍？**（有候选方案、有被否方案）→ `documenting-design-decisions`
7. **是不是要讲一个通用做法？**（不绑定某个具体系统）→ `documenting-architecture-patterns`
8. **是不是要讲语言本身？** → `documenting-language-features`
9. **剩下的是「解释」**：对象是单个算法/数据结构 → `explaining-algorithms`；对象是一组代码或一个运行中的系统 → `explaining-systems`

## 一套文档的推荐生产顺序

新系统或新模块从零开始写文档时，按依赖顺序产出，后者引用前者，避免互相复制：

```text
1. documenting-design-decisions   为什么这样选（最先产生，且不可事后修改）
2. explaining-systems             它由什么组成、怎么运行
3. documenting-data-models        它存了什么
4. documenting-api-contracts      对外能依赖什么
5. documenting-architecture-patterns  其中可复用的做法（可选）
6. documenting-tutorials          使用者怎么上手（可选）
7. documenting-runbooks           值班怎么处置
8. documenting-changes            每个版本改了什么、怎么升级
```

`documenting-language-features` 独立于上链，只在涉及语言层面的主题时使用。
`explaining-algorithms` 独立于上链，只在需要讲清一个算法/数据结构时使用。

## 跨领域请求怎么拆

1. **先定主文档**：用户最想拿到的那一份用对应 skill 写。
2. **其余作为独立文档**，各自用自己的 skill，并互相链接；**不合并成一篇**。
3. **只在用户会分别使用它们时才拆**。信息能被主文档一句话带过时，不要拆——拆出来的文档若没有独立读者，就是碎片。
4. 拆分时在主文档开头列出这一组文档及其关系。
5. 同时命中两个以上时，向用户确认主文档是哪一个，不要替用户决定。

典型拆分：

- 「讲清这个系统并给出接口契约」→ `explaining-systems`（主）+ `documenting-api-contracts`（附）
- 「记录选型并说明为什么」→ `documenting-design-decisions`（主）+ `documenting-architecture-patterns`（附，若涉及通用模式）
- 「写一份升级指南」→ `documenting-changes`（主）+ `documenting-api-contracts`（附，若含破坏性变更）

## 都不匹配时怎么办

本家族不覆盖的常见请求，按下表处理，**不要硬套**：

| 请求 | 处理 |
| --- | --- |
| 写 README、项目介绍 | 不套用本家族；按仓库既有约定写 |
| 写 commit message、PR 描述 | 不套用；用团队的提交规范 |
| 写营销文案、能力介绍 | 不套用 |
| 写产品需求或设计稿评审 | 不套用 |
| 只是回答问题、不产出文档 | 直接对话回答，不启动任何 skill |
| 一次改动很小、不值得成文 | 直接在对话里说明，不产物文档 |

判断标准：**没有明确读者、没有需要保存的事实、或产出不会被再次查阅时，不写文档。** 本家族的每个 skill 都要求先确认读者与目的，这一条是它们的共同前提。

## 约定

- 每个 `SKILL.md` 统一采用 7 节结构：使用边界 / 写作前确认 / 写作流程 / 输出契约 / 写作质量门 / 相关资源 / 与其他 skill 的边界。
- 详细的领域写作标准在各自的 `references/` 中，`SKILL.md` 只做入口与门禁。
- **`SKILL.md` 与其 reference 冲突时，以 reference 为准**（每个 `SKILL.md` 都有这句话）。
- 全族共用一套事实标签词表（`源码确认` / `运行确认` / `规范确认` / `来源确认` / `文档确认` / `设计意图` / `未验证`）与证据书写规范，详见任一 reference 的「事实标注与证据规范」一节。
- 产出文档可用 `_design/check_doc_quality.py` 做机械自检：

  ```bash
  python _design/check_doc_quality.py <文件或目录>
  python _design/check_doc_quality.py --allow-pending <目录>   # 骨架文档的待办占位降为 warning
  ```

本 README 是选型入口。设计依据与实施状态见 `_design/technical-doc-skills-design.md`。
