# 技术文档类 Codex Skill 家族设计方案

## 目标

本设计用于生成一组 Codex skill，帮助 Codex 把某一类技术主题写成高质量、可验证、可维护的文档。

覆盖对象包括：

- 解释一个算法或数据结构
- 说明一门程序设计语言的语法、特性设计和原理
- 说明一个架构设计模式
- 解释或解剖一个系统、框架、项目代码库
- 说明 API 或协议契约
- 说明数据模型
- 记录设计决策
- 编写教程
- 编写运维 runbook

## 设计结论

1. 不使用一个覆盖所有技术文档的总 skill。
2. 使用一组窄范围 skill，让 Codex 根据名称和描述直接命中正确任务。
3. 首批建立核心 4 个，随后建立第二批 5 个；两个批次共 9 个 skill 均已落地并统一改为独立的写作标准，后续按真实写作需求继续验证和修正。
4. 每个 skill 保持独立可用，不依赖一个未必会加载的父 skill。
5. 每个 skill 都要求先确认读者、目的、文档类型和事实来源。
6. skill 及其 reference 是文档内容标准的核心；仓库已有文档只能作为事实素材和定位上下文，不能优先于 skill 的准确性、完整性和验证要求。

## Skill 列表

### 第一批

| Skill 名称 | 目标 |
| --- | --- |
| `explaining-algorithms` | 解释算法和数据结构，覆盖正确性、复杂度、实现、边界例和算法对比 |
| `explaining-systems` | 解释或解剖系统、框架、项目代码库，内部区分三种子模式 |
| `documenting-language-features` | 说明语言语法、特性设计、语义、交互和迁移影响 |
| `documenting-architecture-patterns` | 说明架构模式的上下文、结构、权衡、适用性和反模式 |

### 第二批

| Skill 名称 | 目标 |
| --- | --- |
| `documenting-api-contracts` | 说明 API、协议或接口契约，覆盖消息、错误、状态机、兼容性 |
| `documenting-data-models` | 说明实体、字段、类型、约束、关系、索引和迁移 |
| `documenting-design-decisions` | 以 ADR 或决策记录形式保存问题、候选方案、权衡和结论 |
| `documenting-tutorials` | 编写带前置知识、步骤、示例、练习和验证的教程 |
| `documenting-runbooks` | 编写诊断、修复、回滚和验证流程 |

第二批共 5 个 skill 已经建立。每个 skill 仍应按使用反馈逐个完善，真实素材出现后至少做一次行为级冒烟测试，再决定是否增加或收窄章节。

## 目录结构

### 当前仓库安装形式

如果安装在使用这些 skill 的项目中，目录通常位于：

```text
.codex/skills/
├── explaining-algorithms/
├── explaining-systems/
├── documenting-language-features/
├── documenting-architecture-patterns/
├── documenting-api-contracts/
├── documenting-data-models/
├── documenting-design-decisions/
├── documenting-tutorials/
└── documenting-runbooks/
```

每个 skill 示例：

```text
explaining-systems/
├── SKILL.md
└── references/
    ├── system.md
    ├── framework.md
    └── project.md
```

### 可发布仓库形式

以后需要发布或跨项目安装时，改为一个仓库托管多个 skill：

```text
technical-doc-skills/
├── explaining-algorithms/
├── explaining-systems/
├── documenting-language-features/
└── documenting-architecture-patterns/
```

使用方式：

```bash
npx skills add owner/repo@explaining-algorithms -g -y
npx skills add owner/repo@explaining-systems -g -y
```

## Skill 命名与描述

命名规则：

- 使用小写字母、数字和连字符
- 使用动作式名称
- 名称短且说明真实能力
- 不把文档种类全部堆在一个名字里

示例描述：

```yaml
---
name: explaining-algorithms
description: >-
  解释一个算法或数据结构，并在必要时产出可验证的技术文档。
  覆盖问题定义、核心思想、正确性、复杂度、实现、边界例和算法对比。
  不适用于语言语法说明、架构模式说明或整个系统解释。
---
```

```yaml
---
name: explaining-systems
description: >-
  解释或解剖一个系统、框架或项目代码库。
  覆盖目标、模块边界、数据流、源码组织、入口点、运行方式、
  失败模式、扩展机制以及概念与代码的映射。
---
```

描述应足够精确，让相似任务不会误选。

## 每个 SKILL.md 的统一结构

所有 skill 的 `SKILL.md` 都采用以下逻辑，正文语言可以跟随项目使用中文：

1. 适用范围
2. 不适用范围
3. 写作前必须确认的事项
4. 必须覆盖的内容结构
5. 最终交付前的质量门
6. 需要时加载的 reference

正文应短于详细标准，详细领域标准放在 `references/` 中，避免每次写作都加载全部内容。

## 公共技术文档契约

每个 skill 都必须保留一份精简公共契约，作为独立运行时也能生效的底线：

- 写作前明确读者、目的、非目标和事实来源
- 未验证的内容不得写成事实
- 猜测、假设、预期结果要显式标注
- 结论先给，再展开原因
- 文档描述当前状态，不把历史演进写成当前行为
- 文档不复制代码，只解释代码不直接表达的设计、权衡和约束
- 示例必须能复现，至少包含正常例、边界例或错误例
- 每个文档应能追溯到权威源码、规范、实验或文档
- 仓库有本地文档和索引时，可以作为定位和链接上下文，但不得用较低质量的结构替换本 skill 的标准
- 不为了覆盖所有可能场景而写出空洞章节

## 第一批 skill 内容设计

### `explaining-algorithms`

目标文档是“算法说明”，不是代码注释，也不是项目运行报告。

必须覆盖：

- 算法解决的问题和输入输出约束
- 核心思想和关键不变量
- 步骤、伪代码或真实实现对应关系
- 正确性论证、终止条件和失败前提
- 时间复杂度、空间复杂度、最好/最坏/期望情形
- 实现关键点和容易踩的坑
- 普通示例、边界示例和反例
- 变体、相近算法和适用限制

不依赖任何项目仓库的模板文件。已有 README、索引和同主题文章只用于定位链接与术语，文档结构、正确性论证、复杂度前提和实现映射仍以本 skill 标准为准。

### `explaining-systems`

这个 skill 不是写产品简介，而是“解释或解剖”。需要根据对象选择三种子模式。

`SKILL.md` 中应包含：

| 对象 | 适用问题 | Reference |
| --- | --- | --- |
| 系统 | 它整体做什么、模块如何协作、运行后如何表现 | `references/system.md` |
| 框架 | 设计思想、核心 API、内部实现和扩展方式 | `references/framework.md` |
| 项目代码库 | 仓库结构、入口点、改动路径和调试方式 | `references/project.md` |

#### `references/system.md`

系统写作标准覆盖：

- 系统目标、目标用户、目标和非目标
- 运行环境、部署拓扑、外部依赖
- 模块划分、职责和边界
- 请求、数据、控制流全链路
- 状态和生命周期
- 外部接口、配置、可观测性
- 不变量、失败模式、安全和性能约束
- 哪些结论来自源码、运行观察、文档或假设

#### `references/framework.md`

框架解剖写作标准覆盖：

- 框架解决什么问题，和普通库的区别
- 设计哲学和核心抽象
- 核心 API、入口和生命周期
- 插件、回调、装饰器、配置等扩展点
- 内部模块结构和依赖关系
- 一次典型调用如何穿过内部模块
- 框架替你做了什么、没做什么
- 源码关键位置、扩展方式和常见误用

#### `references/project.md`

项目代码库解剖写作标准覆盖：

- 项目目标、输入输出和验收标准
- 仓库顶层结构和目录职责
- 构建、运行和测试入口
- 主入口和端到端调用链
- 核心业务模块、工具模块和基础设施模块
- 增加一个功能通常需要改动哪些文件
- 配置、环境变量和数据流
- 调试方式和常见问题
- 文档与代码的对应关系

### `documenting-language-features`

目标文档是“语言特性说明”，不是 API 手册，也不是入门教程。

必须覆盖：

- 特性解决的设计问题
- 语法形态和合法约束
- 语义、求值、类型检查、作用域和运行时行为
- 与其他特性的组合和交互
- 为什么采用当前设计而不是其他方案
- 正例、错误例和边界例
- 性能、安全性、兼容性和迁移影响
- 常见误区和调试路径

### `documenting-architecture-patterns`

目标文档是“模式说明”，应说明模式适合什么问题以及为什么值得付出代价。

必须覆盖：

- 上下文、问题和冲突力量
- 参与者、职责和协作方式
- 结构、调用流或数据流
- 优点、代价和失效方式
- 适用场景和不适用场景
- 相近模式、变体和反模式
- 在该项目中的真实落地位置

## 公共规则的组织方式

多个 skill 需要共享部分硬规则，但不能让安装后的 skill 依赖另一个未安装的 skill。

建议：

1. 每个 skill 自带一份精简公共清单。
2. 详细领域写作标准放在各自 `references/` 中。
3. 公共清单开始重复且体积变大后，在发布仓库建立共享源文件。
4. 通过发布或同步脚本把共享规则复制进各 skill，保证每个安装结果独立可用。

## 与 `technical-writing` 的关系

`technical-writing` 是通用文档写作规范，适合管理结构、措辞、事实、修订和风格。

本文设计的技术文档 skill 负责内容选择：

- 某类主题应回答哪些问题
- 哪些章节必须存在
- 示例和证据应达到什么质量

两者是叠加关系，不是替代关系：

- 先判断文档主题
- 再按该主题写作标准组织内容
- 最后按通用写作规则做结构、事实和语言检查

如果环境中已安装 `technical-writing`，可在 `SKILL.md` 中提示使用它做最终写作检查。`SKILL.md` 本身不能假设它一定存在。

## 验证方案

### 文件级验证

每个新建 skill 使用 Codex 的 `skill-creator` 校验脚本：

```bash
python /Users/minghui.liu/.codex/skills/.system/skill-creator/scripts/quick_validate.py <skill-path>
```

校验内容：

- `SKILL.md` 存在
- frontmatter 有 `name` 和 `description`
- 命名符合小写连字符规则
- 没有未完成的占位内容

### 行为级验证

用真实请求对每个 skill 做一次冒烟测试：

- 让 `explaining-algorithms` 解释一个尚未成文的真实算法或数据结构
- 让 `explaining-systems` 解剖一个真实系统、框架或项目代码库
- 让 `documenting-language-features` 说明一个具体语言特性
- 让 `documenting-architecture-patterns` 说明一个具体架构模式
- 9 个 skill 都应使用对应真实素材做冒烟测试，例如真实服务契约、迁移 schema、已实现决策、可运行教程或真实故障处置

检查产出是否满足：

- 结论可追溯
- 示例可复现
- 边界、限制、成本和错误路径没有被隐藏
- 文档没有虚构源码位置
- 源码位置、运行结果和文档结论可相互对应，没有把目录名或 README 声明当成架构事实

根据冒烟测试结果调整写作标准，避免只凭想象扩充章节。

## 实施状态

1. 已完成第一批 4 个 skill 的目录、入口和详细写作标准。
2. 已完成第二批 5 个 skill 的目录、入口和详细写作标准。
3. 9 个 skill 的 reference 均作为独立写作标准使用，不再以仓库模板为优先级。
4. 待执行：对每个 skill 使用对应真实素材做行为级冒烟测试，再根据结果收窄或扩展内容。

## 完成标准

每个已建立 skill 满足以下条件时视为完成：

- 每个 skill 都有独立可用的 `SKILL.md`
- 描述能精准匹配任务，不会互相误抢
- 每个领域写作标准都有明确必须回答的问题
- 公共契约能在每个 skill 中独立生效
- 已有仓库文档不被视为可以替代 skill 标准的高优先级模板
- 输出不把猜测写成事实，不虚构代码或来源
- 校验脚本通过，且至少一次真实请求验证通过
