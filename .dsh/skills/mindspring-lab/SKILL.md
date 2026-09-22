---
name: mindspring-lab
description: MindSpring 仓库 algorithms/ 与 engineering/ 两条线的实验/项目写作与验证规范。当在 MindSpring 项目中新增算法实验、推进实验状态（⬜→🚧→✅）、补写/重构实验 README、做手写 vs 框架对照实验、新增或推进工程项目、检查完成度时使用。确保任何算法实验、任何工程项目的 README 结构、实验纪律、验证声明完全一致。本 skill 是 algorithms/ 与 engineering/ 写作任务的唯一权威规范，优先于对存量实验的直接模仿。本 skill 仅管辖 algorithms/ 与 engineering/；roadmap/、仓库根 README 等非实验文档不受本 skill 约束，禁止套用其模板结构。
agent_created: true
---

# MindSpring 实验与项目写作规范

## Overview

MindSpring 是 AI 核心技术实验室，两条线：**algorithms/**（手写算法 vs 框架对照，理解原理）与 **engineering/**（可运行工程系统，理解工程）。本 skill 定义两类交付物的 README 结构、实验纪律与完成度检查流程，保证任何实验、任何项目写出来都长一个样。本 skill 只含规范与模板，不维护任何实验的现状快照（哪个实验完成到哪，以 `algorithms/README.md` 索引表与磁盘目录为准）。

**适用范围**：本 skill 只管 `algorithms/` 与 `engineering/` 两个目录。`roadmap/` 是理论输入文档（实验章节锚点的来源），其写作不受本规范约束；仓库根 README、pyproject.toml 等也不归本 skill 管。

**管辖边界（不纳入本规范的内容）**：即使物理位置落在管辖目录下，以下内容也不受本规范约束，**写作与检查都跳过**：

- 自动生成或工具产物：`__pycache__/`、`.pytest_cache/`、`.ruff_cache/`、`.ipynb_checkpoints/` 等
- 实验产物：下载的数据集缓存、训练出的模型权重（`*.pth`/`*.ckpt`/`*.pkl`）、运行日志、matplotlib 输出的图片文件

判据：**该文件能否由某条命令重新生成，或是否由工具维护**——能，就不归本规范；只有人手写的 README 与源码才归本规范。

**存量兼容原则**：早期实验（含已标 ✅ 的）可能与本规范有出入（如 README 段落仍是括号占位）。执行任何任务时**以本 skill 为准**，不通过模仿旧实验来推断规范；旧实验的偏差在完成度检查（场景 D）中记录为待升级项，而非视为另一种合法格式。

## 目录结构

```
algorithms/<NN-族>/<算法名>/          # 01-search/a-star, 04-transformer/attention
├── README.md                        # 实验主文档（六段式，必含）
├── impl.py                          # 手写实现（核心纪律管的就是它）
├── framework.py 或 baseline.py      # 对照版：框架 或 基线算法（按算法族二选一）
└── demo.py                          # 同数据双跑对比的入口

engineering/<NN-项目>/                # 01-text-corpus-pipeline ~ 07-ai-platform
├── README.md                        # 项目主文档（六段式，必含）
└── <项目源码>                       # 可运行系统
```

规则：

- 实验目录命名：`algorithms/` 下族目录用 `NN-<kebab-case 族名>`（编号即学习顺序，与索引表分组一致），实验目录用 kebab-case 算法名
- **文件名按算法族而定，不强制三件套齐全**：搜索族是 `impl.py + baseline.py + demo.py`，监督估计器族是 `impl.py + framework.py + demo.py`，也可能对照逻辑内嵌在 demo.py 里。族的接口约定见 `references/algorithm-families.md`——**本 skill 规范 README 结构与实验纪律，不统一代码接口形态**
- 每个源码文件附可复现的运行方式：README 写明验证环境（Python/依赖版本）、运行命令、预期输出要点。验证声明规范见下节

## 核心纪律

这五条是 MindSpring 的灵魂，全部可被检查（部分由 `scripts/validate.py` 自动查，部分在场景 D 人工深检）：

### ① 手写纪律

核心算法逻辑手写（numpy / 纯 Python），**禁止在 `impl.py` 中调 sklearn / torch.nn / tensorflow 等库的现成算法接口**。界限：张量运算与自动求导可用（如 `torch.Tensor`、`torch.autograd`），现成层/模型/优化器/估计器不可用（如 `nn.Linear`、`torch.optim.Adam`、`sklearn.linear_model.LinearRegression`）。数据加载、可视化、评估指标计算可用现成工具。`framework.py` 是对照版，不受此限。`validate.py` 对 `impl.py` 做违禁 import 扫描。

### ② 双跑对照

每个实验必须同时跑手写版与对照版（框架或基线算法），**对比指标与耗时，并分析差异原因**——手写理解原理，对照理解工程。只跑手写版不算完成。「实验结果」段必须有真实数字（来自实际运行的输出），并给出复现命令。

### ③ 章节锚定

每个 README 开头声明理论锚点：

- algorithms：`> 对应文档章节：\`roadmap/人工智能代表算法演进路线.md\` 第 X.Y.Z 章`
- engineering：`> 对应 roadmap 阶段：第 N 阶段` + `> 对应文档：\`roadmap/大模型数据中心平台工程师.md\``

锚定的章节/阶段必须真实存在（`validate.py` 自动核对），且 engineering 的第 N 阶段必须与目录编号 NN 一致。

### ④ 状态机

每个实验/项目三个状态，README 首行声明、索引表同步维护：

| 状态 | 含义 | 格式 |
|---|---|---|
| ⬜ 未开始 | 只有骨架 | `> 状态：⬜ 未开始` |
| 🚧 进行中 | 部分段落已填 | `> 状态：🚧 进行中` |
| ✅ 已完成 | 六段齐全、双跑对照有实数 | `> 状态：✅ 已完成（YYYY-MM-DD）` |

**✅ 的门槛**：双跑对照完成、实验结果有真实数字与复现命令、README 无占位段落（`validate.py` 对 ✅ 状态的占位/空段记硬伤）。pytest 全绿**不是** ✅ 的门槛，是 `validate.py --pytest` 的可选执行项。✅ 必须带完成日期；索引表（`algorithms/README.md` / `engineering/README.md`）的状态与日期必须与各 README 一致。

**状态迁移不设中间限制**：允许 ⬜ 直接推进到 ✅（跳过 🚧），只要 ✅ 门槛全部满足。

### ⑤ 验证状态声明规范

「已验证」必须可被第三方重跑复现，而不是一句声明。三态：

| 状态 | 何时使用 | 必须写出的内容 |
|------|---------|--------------|
| `已验证` | 在本环境按所给命令实际跑过并观察到结果 | ① 命令（含 Python/依赖版本）② 输入（数据集/种子/环境前提）③ 观察到的结果（输出要点，不做概括） |
| `未在本环境验证` | 依赖缺失、无 GPU、沙箱限制等未能实跑 | ① 缺什么 ② 为什么缺 ③ 读者怎么验证 |
| `无法验证` | 原理上不可复现 | 写明不可复现的原因 |

正例：`已验证：Python 3.13 + numpy 2.x，python3 demo.py；21×21 网格 30% 障碍率种子固定 → A* 与 Dijkstra 路径长度均为 47，扩展节点 214 vs 239`
反例（一律不通过）：`已验证`、`已跑通，结果正确`

**禁止**：裸写「已验证」不给三要素；声称跑过实际没有的硬件/服务（GPU、Redis、K8s）——必须标「未在本环境验证」；把「跑通无报错」说成「指标验证通过」。

**时效性**：`已验证` 是某次运行的快照。依赖升级、源码编辑后旧证据可能失效；场景 D 应把这类声明当作易过期元信息回访。

## 工作流

### 场景 A：新增一个算法实验

1. 确定理论锚点：读 `roadmap/人工智能代表算法演进路线.md`，确定该实验对应的章节号 X.Y.Z
2. 确定所属算法族与对照对象（查 `references/algorithm-families.md`）：这决定文件形态（framework.py 还是 baseline.py）与自然接口
3. 创建 `algorithms/<NN-族>/<算法名>/`，写 README 骨架：按 `references/algorithm-readme-template.md` 的六段式，状态 ⬜，章节锚点填真实章节号
4. 在 `algorithms/README.md` 对应族的索引表登记一行：实验链接、章节号、状态 ⬜、日期留空
5. 跑 `python3 .dsh/skills/mindspring-lab/scripts/validate.py` 确认索引 ↔ 目录双向对齐

### 场景 B：推进实验（⬜/🚧 → ✅）

1. 读锚定的 roadmap 章节，明确该算法在演进路线中的位置（它解决什么问题、被谁取代、引出谁）
2. **数学推导先行**：在 README「数学推导」段手推关键公式，推完再写代码——这是本仓库的方法论，不是形式主义
3. 写 `impl.py`（手写，守纪律 ①），带行内注释解释关键步骤与坑
4. 写对照版 `framework.py`/`baseline.py` 与 `demo.py`（同数据、同指标双跑）
5. 实跑 demo，把真实数字填进「实验结果」段：指标对比表 + 耗时 + 复现命令 + 按纪律 ⑤ 写验证声明；无法实跑的（如无 GPU）如实标「未在本环境验证」
6. 补「局限与延伸」：该算法的边界、引出哪个后续算法（带相对链接，如 `../mcts/`）
7. 状态推进为 ✅（带日期），同步索引表；跑 `validate.py` 全量检查通过
8. 提交前核对变更集：确认 `__pycache__`、模型权重、数据集缓存不在提交里（`validate.py --git` 辅助）

### 场景 C：新增/推进一个工程项目

1. 读 `roadmap/大模型数据中心平台工程师.md` 对应阶段，明确该项目在职业路线中的位置
2. 按 `references/engineering-readme-template.md` 写 README 六段：目标 / 技术栈 / 系统架构 / **复用的算法实验** / 验收标准 / 实施笔记
3. 「复用的算法实验」是 MindSpring 独有的闭环：**必须显式列出本项目用到 `algorithms/` 里哪些手写实验的原理/代码**（带相对链接）。没有可复用的就写明"无——原因"，不许空着
4. 「验收标准」用可验证的条目（`- [ ] 能……` 句式），推进时逐条打勾
5. 「实施笔记」记关键决策与踩坑——这是最有复利的一段，搭建过程中随手记，不要事后补
6. 状态推进与索引同步、验证声明、变更集核对，同场景 B 第 5~8 步

### 场景 D：完成度检查

分两层：**第 1~2 步存在性检查**（自动），**第 3 步内容质量深检**（人工）。被场景 A/B/C 作为提交前验收调用时，可只对本批涉及的目录跑。

1. 跑自动检查：
   ```bash
   cd <MindSpring 根>
   python3 .dsh/skills/mindspring-lab/scripts/validate.py            # 全量存在性检查
   python3 .dsh/skills/mindspring-lab/scripts/validate.py --deep     # 额外列出需人工核对的项
   python3 .dsh/skills/mindspring-lab/scripts/validate.py --pytest   # 可选：实跑 pytest
   python3 .dsh/skills/mindspring-lab/scripts/validate.py --git      # 提交前变更集核对
   ```
2. 输出完成度矩阵，格式：
   ```markdown
   ## 完成度矩阵（YYYY-MM-DD）

   图例：✅ 完整 | 🟡 存在但不完整 | ❌ 缺失

   | 线 | 单元 | README 六段 | 对照双跑 | 验证声明 | 索引同步 | 备注 |
   |----|------|------------|---------|---------|---------|------|
   | algorithms/02-statistical-ml | linear-regression | 🟡 有占位段 | ❌ | ❌ | ✅ | |
   ```
3. **内容质量深检**（存在性全绿不代表合格，逐项核对）：
   - **推导真空**：「数学推导」段是否真的推出了关键公式，还是只有名词罗列
   - **结果空话**：「实验结果」是否有真实数字（指标、耗时）；「可视化结论」是否有实质观察
   - **差异分析**：手写 vs 对照的差异是否分析了**原因**（框架做了什么手写版没做的优化），而不是只贴数字
   - **占位残留**：是否还有整段 `（……）` 模板提示语未填
   - **锚点属实**：README 声明的章节内容与该实验真的对得上（不是随手填的号）
   - **验证声明**：逐条对照纪律 ⑤，证据三要素是否齐全
   - **易漂移项**：README 中的版本号是否与本机实测一致；是否用行号引用其他文件（改为引用符号/片段内容）
   - **闭环检查（engineering）**：「复用的算法实验」声称复用的实验是否真的存在且相关
   - 深检发现的问题并入缺口汇总：`- <目录>：[深检] <问题>：<建议动作>`
4. 记录落盘：`.dsh/memory/YYYY-MM-DD.md`（当日文件，无则新建），沿用缺口汇总格式，**必须写明基线**（`基线：main @ <短 SHA>` 或 `基线：工作区（未提交）`），不要事后补记 SHA

## README 结构规范

- **算法实验**：六段式——设计原理 / 数学推导 / 手写实现要点 / 对照（框架对照 或 基线对照，段名按算法族）/ 实验结果 / 局限与延伸。完整模板与填充示例见 `references/algorithm-readme-template.md`。允许在「手写实现要点」前加一段「目录形态」表格（文件 × 角色 × 接口），格式见算法模板
- **工程项目**：六段式——目标 / 技术栈 / 系统架构 / 复用的算法实验 / 验收标准 / 实施笔记。模板见 `references/engineering-readme-template.md`
- 模板即权威结构，不指向任何具体存量文件（存量会重构，模板不过期）

## 写作风格约定

- 语言：简体中文，技术术语保留英文原文（如 backpropagation、attention）
- 结构：多用表格对比维度（指标对比、文件角色）；代码块带语言标注
- 代码：带行内注释解释关键步骤与坑；数学公式用文本或 LaTeX 记法，与代码变量名对应
- 阶段隔离与链接：提到其他实验/项目时用相对链接（`../mcts/`）；「局限与延伸」必须指出后续方向
- 索引表维护：每完成一个实验，把索引表状态改为 ✅ 并记录日期——索引表是唯一现状快照。索引表的**列序是 `validate.py` 的解析契约**，格式规范见 `references/index-format.md`

## Resources

### scripts/

- `scripts/validate.py` — 场景 D 的存在性与纪律自动检查。覆盖：索引表 ↔ 目录双向核对（含 ✅ 日期一致性）、状态一致性、README 六段齐全、占位段检测（✅ 状态下为硬伤）、章节锚点有效性、`impl.py` 违禁 import 与属性调用扫描、engineering 阶段编号一致性、✅ 项目验收标准打勾核对；`--pytest` 实跑测试，`--git` 核对变更集，`--deep` 列出需人工核对的漂移项（并打印 git 基线供记忆落盘引用）。退出码 0 = 无问题，1 = 存在问题（可作提交前门禁）。**不管**推导质量、结果分析深度等教学判断——那些按场景 D 第 3 步人工深检。

### references/

- `references/algorithm-readme-template.md` — 算法实验 README 六段式权威模板（含自含填充示例）
- `references/engineering-readme-template.md` — 工程项目 README 六段式权威模板
- `references/algorithm-families.md` — 算法族接口约定（四族的自然接口与对照对象，新增实验时先查）
- `references/index-format.md` — 两条线索引表的列序契约（validate.py 按此解析，调整前先读）

### 记忆落点

- `.dsh/memory/YYYY-MM-DD.md` — 场景 D 每次执行后的缺口登记落点，每条记录必须带基线（分支与提交）

写作时先读对应模板再动笔；检查时先跑 `scripts/validate.py` 再做人工深检。
