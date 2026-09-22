# Mosaic 合并设计（TenetLang + MindSpring + OceanVerse → 单仓）

- 状态：待实施（设计已评审通过）
- 日期：2026-09-22
- 范围：仓库合并与结构重排；**不含**内容改写与去车联网

## 1. 背景与目标

工作区 `/Users/ninebot/code/mosslau` 下有三个彼此独立的 git 仓库，各自有独立远端，各自已演进到稳定态：

| 仓库 | 跟踪文件 | 提交数 | `.git` | 定位 | 远端 |
|---|---|---|---|---|---|
| TenetLang | 3955 | 154 | 38M | 语言学习路线（6 语言 × 126 阶段）+ 语言设计解剖 + Tenet 语言与编译器 | `Mosslau/TenetLang` |
| MindSpring | 674 | 41 | 4.1M | AI 核心算法实验室（5 学科 23 个实验）+ AI 平台工程（7 个项目） | `Mosslau/MindSpring` |
| OceanVerse | 152 | 123 | 2.5M | 大数据平台（Go 接入 / Kafka / Flink SQL / ClickHouse / 部署） | `Mosslau/OceanVerse` |

三者面向同一目标——**通用数据平台 + AI 平台数据中心**——但被切成三个仓库，导致：跨域引用靠 `../TenetLang/` 这类仓库外路径；技能资产三份重复；唯一的一条 CI 只管一个域；读者要开三个仓才能看全一个方向。

**目标**：合并为单仓 **Mosaic**，顶层严格按三部分组织——开发语言部分、算法部分、工程系统部分——同时**完整保留三个仓的提交历史**，且迁移过程**不改动任何正文内容**。

### 分类判定

本任务重构组件归属、改变路径接口、并新建仓库，属 architectural 路径：设计 → spec（本文）→ 用户评审 → 实施计划 → 实施。

## 2. 非目标（明确不做）

1. **不做去车联网**：OceanVerse 的 GB/T 32960 协议层、VIN 语义、CI 断言保持原样；合并完成并验收后单独一轮处理。
2. **不做内容改写**：126 个阶段、23 个算法实验、7 个工程项目的正文一个字不动。本次是纯搬迁 + 路径假设修正。
3. **不动 `languages/studies/` 内的 L3 车辆教学示例**（约 169 个文件，py 87 / go 57 / java 23 / rs 2）：它们是语言路线的教学素材，与工程域的去车联网是两件事，前序讨论已确认保留。
4. **不删三个源仓**：验收全绿前一律不动；验收后统一 Archive（不删除）。
5. **站点不扩展内容族**（决策 D6）：本次站点仍只服务语言域，算法域与工程域暂不进站。

## 3. 决策记录

| # | 决策 | 理由 |
|---|---|---|
| D1 | 顶层三部分目录：`languages/` + `algorithms/` + `engineering/` | 与「开发语言 / 算法 / 工程系统」一一对应。 |
| D2 | 语言域内部三条主线**同层**：`languages/{studies,analysis,tenet}/` | 前一版把 `analysis/` + `tenet/` 捆成 `language-design/` 并列于 `languages/` 是错的：抽象层级不一致（素材库 vs 研究活动），且凭空造了一层。学/析/合本来就是并列主线。 |
| D3 | 语言学习路线的子目录名 `studies/` | 表达「学习路线 + 阶段笔记」；三个候选（`learning` / `studies` / `tracks`）中选定。 |
| D4 | 新建仓库 `Mosaic`，`git subtree` 保留历史 | 拒绝「以 TenetLang 为基座改名扩仓」（会继承无关的 issue/star 语境）、「submodule」（三仓仍独立演进，不成其为单仓）、「裸拷贝」（丢历史）。 |
| D5 | `roadmap/` 保留在顶层 | `MindSpring` 的 23 个算法实验 README 以 `> 对应文档章节：第 X.Y.Z 章` 锚定 `roadmap/人工智能代表算法演进路线.md`，且 `mindspring-lab/validate.py` 的 `parse_roadmap_chapters()` 从 `ROOT/roadmap/` 读取。保持该路径 → 23 处锚点与校验器**零改动**。 |
| D6 | 站点本次只服务语言域（方案 S1） | 站点（VitePress + `curriculum.json`）是语言课程站。一次吞五域要把首页/导航/数据结构一起重做，会把「搬迁」与「改版」混在一个变更里。算法/工程域进站列为后续项。 |
| D7 | `OceanVerse` **整仓搬入** `engineering/data-platform/` | `scripts/check-*.sh` 全部以 `ROOT="$(cd "$(dirname "$0")/.." && pwd)"` 自定位，`deploy/` 的 compose 构建上下文也是域内相对路径。整体平移 → 这些一行都不用改。 |
| D8 | 技能目录 `tenetlang-notes` / `mindspring-lab` 暂不改名 | 二者是「辖区」名，被多处文档引用；改名的收益只是观感，成本是全域引用更新。列为后续项。 |
| D9 | 本次只修「会失效的路径与指代」，不改「仓名自称」 | 分界线：**路径类引用必须修**（不改就断链/失效，实测约 68 处）；**仓名自称不改**（TenetLang 22 / MindSpring 16 / OceanVerse 47 = 85 行，不影响可运行性，且混入会让 `git diff` 无法区分「搬动」与「改写」，破坏 §9 门禁的可判定性）。自称退休列入 §11 后续项。**例外**：4 个文件里的「与 TenetLang 的分工/边界」是实质内容，随新域 README 一并改写成新词汇（见 §6）。 |

## 4. 目标结构

每项标注来源；`←` 表示原样搬迁（不含内容改动）。

```
Mosaic/
├── README.md                        新写：三部分总入口
├── LICENSE                          ← 三份逐字节相同（md5 e58bcab3…），留一份
├── .gitignore                       三份并集 + 路径锚定修正（见 §5）
├── .mcp.json                        ← 三份逐字节相同（md5 f99d3636…），留一份
├── pyproject.toml                   ← MindSpring（改项目名/描述 + testpaths）
├── .python-version                  ← MindSpring
│
├── languages/                       ① 开发语言部分
│   ├── README.md                    新写：学/析/合 三主线导航 + 边界 + 校验命令
│   ├── studies/                     ← TenetLang/languages/（6 语言 × 126 阶段）
│   ├── analysis/                    ← TenetLang/analysis/
│   └── tenet/                       ← TenetLang/tenet/
│
├── algorithms/                      ② 算法部分
│   ├── README.md                    ← MindSpring/algorithms/README.md
│   └── 01-search … 05-generative/   ← MindSpring/algorithms/（23 个实验）
│
├── engineering/                     ③ 工程系统部分
│   ├── README.md                    新写：两域分工与边界（吸收 MindSpring README 的分工/依赖表）
│   ├── ai-platform/
│   │   ├── README.md                ← MindSpring/engineering/README.md（01–07 项目总览）
│   │   └── 01-text-corpus-pipeline … 07-ai-platform/   ← MindSpring/engineering/
│   └── data-platform/               ← OceanVerse 整仓（内部结构一字不动）
│
├── roadmap/                         路线图（顶层）
│   ├── README.md                    ← MindSpring/roadmap/README.md 扩写为全仓路线索引
│   ├── 人工智能代表算法演进路线.md    ← MindSpring（**路径不变**，D5）
│   ├── 大模型数据中心平台工程师.md    ← MindSpring
│   └── 智能大数据平台工程师.md        ← OceanVerse（出链 0、入链 0，搬运零成本）
│
├── books/                           ← TenetLang/books/
├── website/                         ← TenetLang/website/（VitePress；站点唯一，见 D6）
├── .github/workflows/ci.yml         ← OceanVerse（全仓唯一 CI）
└── .dsh/skills/                     16 个 skill 的并集
```

### 4.1 关键「搬对了就零成本」的证据

- **OceanVerse 内部相对路径全部继续成立**（D7）。
- **`智能大数据平台工程师.md` 上移零成本**：实测其在 OceanVerse 内出链 0、入链 0；OceanVerse 只引用 `项目进度.md` 与 `OceanVerse架构总览.md`，后两者留在 `engineering/data-platform/roadmap/`，域内引用不受影响。
- **`studies/` 内部数百条阶段互链（`../../<lang>/phNN-*`）全是域内相对路径**，域整体平移后全部继续成立。这正是「域整体搬迁」优于「文件级重排」的地方。
- **`.dsh/skills/` 去重是真正的并集**：14 个共享 skill 在三仓间 `diff -rq` 差异块均为 0，并集 = TenetLang 15 个 + `mindspring-lab` = 16 个。

### 4.2 被否决的备选结构

- **B（零改名）**：`languages/ analysis/ tenet/` 三个平铺顶层。链接零改动，但顶层 8 个目录，归属只靠 README 说明，目录名本身不表达「这三个属于第①部分」。
- **C（`language/` 单数域根）**：与 A 成本相同，仅命名差异，未采用。

## 5. 顶层公共资产合并规则

| 资产 | 规则 |
|---|---|
| `LICENSE` | 三份 md5 相同，保留一份。 |
| `.mcp.json` | 三份 md5 相同，保留一份。 |
| `.gitignore` | 三份并集。**必须修正的点**：OceanVerse 的 `.tmp-gocache` / `.tmp-gh-cache` / `.tmp-mmdc` 等模式原本相对仓根，合并后需写成 `engineering/data-platform/.tmp-*` 或 `**/.tmp-*`；TenetLang 忽略 `website/docs/`（站点产物）需保留且路径仍成立。逐条核对并集**不得新增误伤**（例如不得让某个模式意外匹配到 `languages/studies/` 内的文件）。 |
| `pyproject.toml` | 取自 MindSpring：`name`/`description` 更新为 Mosaic；`testpaths = ["algorithms", "engineering"]` → `["algorithms", "engineering/ai-platform"]`。保留在仓库根（`mindspring-lab/validate.py` 以 `cwd=ROOT` 跑 `pytest`）。 |
| `.dsh/skills/` | 16 个 skill 并集，逐字节去重（D8：`tenetlang-notes` / `mindspring-lab` 不改名）。 |
| `MindSpring/website/` | 仅含一行标题的 stub（`# MindSpring 文档站`），内容无独有信息，**删除**。 |
| `MindSpring/roadmap/README.md` | 扩写为全仓路线索引（四份路线文档的入口）。 |
| `.github/` | 仅 OceanVerse 有，直接落 `Mosaic/.github/`；workflow 内路径需加域前缀（见 §6）。 |

## 6. 路径假设修正清单（迁移的技术核心）

以下为**实测**的改动全集；除这些位置外，正文与链接不动。

| 位置 | 改动 | 量 |
|---|---|---|
| `languages/analysis/{cpp,java,py,rs}/README.md` | `../../languages/<lang>/` → `../studies/<lang>/` | 4 条 |
| `languages/studies/` 内指向 `books/`、`website/` 的链接 | `../../` → `../../../`（深度增加一级） | 2 条 |
| `engineering/ai-platform/{01,02,03,04,05,06,07}-*/README.md` | 「复用的算法实验」段的 `../../algorithms/<学科>/<实验>/` → `../../../algorithms/…`（工程域下沉一级） | 24 条 |
| `engineering/ai-platform/README.md` | `../roadmap/大模型数据中心平台工程师.md` → `../../roadmap/大模型数据中心平台工程师.md` | 1 条 |
| `.dsh/skills/tenetlang-notes/scripts/validate.py` | `lang_root = root / "languages"` → `root / "languages" / "studies"`（含第 447 行错误提示文案） | 1 行 |
| `.dsh/skills/mindspring-lab/scripts/validate.py` | `ENG_INDEX` → `engineering/ai-platform/README.md`；`ROOT.glob("engineering/[0-9][0-9]-*")` → `engineering/ai-platform/[0-9][0-9]-*` | 2 处 |
| `website/scripts/sync-docs.mjs` | `FAMILIES`（第 23 行）改为带路径的三元组；`REPO_DIR/'languages'/<lang>`（347/357/481/495/505）→ `languages/studies/<lang>`；`rootReadme`（476 行）由 `REPO_DIR/README.md` 改指 `languages/README.md`；`analysisDocs`/`tenetDocs`/`languageDocs` 计数键（530–532）随 FAMILIES 调整；372/417/435 行路径随域前缀调整 | 约 11 处 |
| `website/README.md` | 内容真源描述 `languages/`、`analysis/`、`tenet/` → 新路径 | 措辞 |
| `.github/workflows/ci.yml` | 13 处 `working-directory` + 8 处 `matrix.module` 取值 + 1 处 `path` 加 `engineering/data-platform/` 前缀 | 22 处 |
| `.dsh/skills/tenetlang-notes/SKILL.md`、`.dsh/skills/mindspring-lab/SKILL.md` | 管辖范围措辞（`languages/` 相关共 15 行） | 措辞 |
| `engineering/ai-platform/README.md`（原 `MindSpring/engineering/README.md`） | 项目总览表格内无跨目录相对链接，仅需更新管辖路径措辞 | 0 条链接 |
| 跨仓指代（`MindSpring/README.md:24,26`；`MindSpring/engineering/README.md:45,47`；`MindSpring/engineering/07-ai-platform/README.md:89`） | 「与 TenetLang 的分工/边界」实质内容改写成新域词汇（`languages/` ↔ `engineering/ai-platform/`）；其中 `../TenetLang/` 路径链接复用新 `languages/README.md` 锚点 | 4 文件 6 行 |
| 新写 | `README.md`、`languages/README.md`、`engineering/README.md`、`roadmap/README.md` | 4 个 |

**合计：73 处路径/指代修正 + 4 个新文档 + 2 处 SKILL 措辞**（4 + 2 + 24 + 1 + 1 + 2 + 11 + 22 + 6）。

不动的相关项（已核实无需处理）：

- `algorithms/README.md → ../roadmap/人工智能代表算法演进路线.md`：`algorithms/` 与 `roadmap/` 都保持深度 1，链接继续成立。
- `OceanVerse/.dsh/skills/_desgin/agent-skills-comparison.md` 的 3 处 TenetLang 表述：属于技能选型的历史设计记录，且该文件在 TenetLang/OceanVerse 两处逐字节相同，保留原文。

**CI 的改法**：采用**显式加前缀**，不用 workflow 级 `defaults.run.working-directory`——GitHub 的 step 级 `working-directory` 与 workflow 默认值的交互需要实测，不值得为一个机械替换引入不确定性。

## 7. 搬迁机制与历史保留

```bash
git init -b main Mosaic && cd Mosaic
git remote add tl ../TenetLang && git fetch tl --all --tags      # 同理 ms / ov
git subtree add --prefix=_import/TenetLang  tl/main              # 保留完整提交历史
git subtree add --prefix=_import/MindSpring ms/main
git subtree add --prefix=_import/OceanVerse ov/main
# 之后一律 git mv 把 _import/<repo>/… 重排到目标位置
git rm -r _import                                                # 最后删空壳
```

- `git mv` 保历史 → `git log --follow` 可追到旧仓提交；验收须抽查验证。
- 源仓那 279M 未跟踪的 `.tmp-gocache` 等**不会被带过来**（subtree / `git mv` 只搬已跟踪内容）。
- 三个源仓在验收前**一律不动**；任何一步出错都可 `rm -rf Mosaic` 从零重建。
- 远端 `Mosslau/Mosaic` 在 C7 之前不推送。

## 8. 提交切分（逐阶段提交，每个 commit 后对应域校验可跑绿）

| # | 内容 | 该 commit 后的可验证状态 |
|---|---|---|
| C0 | 仓库初始化 + 本 spec（根提交） | — |
| C1 | `git subtree` 导入三仓 → `_import/` | 三仓内容原样在 `_import/` 下 |
| C2 | 顶层公共资产：`.dsh/skills/` 并集、`LICENSE`、`.mcp.json`、`.gitignore` 并集、`pyproject.toml` | 技能与配置就位 |
| C3 | 语言域：`studies/analysis/tenet` 重排 + 4 条 `analysis→studies` 链接 + 2 条 `books`/`website` 链接 + 站点脚本 + `tenetlang-notes` 校验器 + `languages/README.md` | `validate.py` 全绿（含 `--links`）、站点可 build |
| C4 | 算法域：`algorithms/` + 顶层 `roadmap/` + `roadmap/README.md` | 算法实验 README 锚点全部解析成功 |
| C5 | 工程域 ai-platform：7 个项目 + 25 条跨目录链接修正 + 4 文件 6 行边界文案改写 + `mindspring-lab` 校验器 + `pyproject.toml` testpaths | `mindspring-lab/validate.py` 全绿、根目录 `pytest` 通过 |
| C6 | 工程域 data-platform：OceanVerse 整仓 + CI 前缀 | `check-docs.sh` / `check-mermaid.sh` / `check-compose-budget.sh` 通过、`docker compose config` 通过 |
| C7 | 顶层 `README.md` + 删 `_import/` + 全量校验 + 推送 `Mosslau/Mosaic` | §9 全部门禁绿 |

## 9. 验收门禁（不绿不推送）

1. `.dsh/skills/tenetlang-notes/scripts/validate.py`（含 `--links` 悬空链接检查）在 Mosaic 根执行通过。
2. `.dsh/skills/mindspring-lab/scripts/validate.py` 通过；根目录 `python -m pytest -q` 通过；`ruff check` / `ruff format --check` 通过。
3. OceanVerse 的 `scripts/check-docs.sh`、`check-mermaid.sh`、`check-compose-budget.sh` 通过；`docker compose -f engineering/data-platform/deploy/docker-compose.yml config` 通过。
4. `website/`：`npm run build`（内部已含 `sync`，会重新生成 gitignored 的 `docs/`）通过。
5. `git log --follow` 抽样（语言域、算法域、工程域各 1 个文件）能追到源仓提交。
6. 仓库内 `grep` 确认无残留的失效路径：`../TenetLang/`、`../MindSpring/`、`../OceanVerse/`、`_import/`（仓名自称的 85 行按 D9 允许保留，不在本条门禁内）。
7. `git status` 干净，无构建产物入库（`target/`、`docs/`、Go 二进制、`__pycache__`）。

## 10. 风险与回滚

| 风险 | 缓解 |
|---|---|
| `.gitignore` 并集误伤 | C2 后立即用 `git status` 与 `git check-ignore -v` 抽样比对，确认无文件被意外忽略/纳入。 |
| CI 路径前缀遗漏（22 处） | C6 后逐个 job 本地复算命令；`paths:` 过滤条件一并核对。 |
| 中文文件名（`人工智能代表算法演进路线.md` 等）在 macOS(NFD) / Linux(NFC) 的规范化差异 | 该风险在原仓已存在，迁移不新增；不在本次范围内解决。 |
| `git subtree add` 首次导入耗时（TenetLang 3955 文件） | 纯本地操作、可重试；不推送直到 C7。 |
| 站点 `docs/` 是 gitignored 产物 | 迁移后重建，不入库。 |
| 语言域 build-status 门禁依赖路径 | C3 后运行 `validate.py` 的构建检查项确认。 |
| 回滚 | 三个源仓未动；`rm -rf Mosaic` 即可完全回退，无副作用。 |

## 11. 后续项（不在本次范围）

1. **OceanVerse 去车联网**（GB/T 32960 协议层、VIN 语义、CI 断言）——合并验收后单独一轮。
2. **仓名自称退休**（决策 D9 的欠账）：把正文里的 `TenetLang` 22 行 / `MindSpring` 16 行 / `OceanVerse` 47 行统一改为新域词汇，包含文件名 `OceanVerse/roadmap/OceanVerse架构总览.md`（改名会牵动 2 处入链）。建议与第 1 项合并为同一轮「文案统一」。
3. **算法域 / 工程域进站**（站点方案 S2）：首页、导航、`curriculum.json` 结构重做。
4. **技能改名**：`tenetlang-notes` → 语言域辖区的更贴切名字；`mindspring-lab` 同理。
5. **三仓 Archive**：Mosaic 验收全绿后执行。
6. 已知小问题：`a-star` 深检提示「实验结果段未写明复现方式」；`rs/ph25` 两处陈旧表述。

## 12. 开放问题

无。本文所有决策均已确认（结构方案 A、子目录名 `studies/`、新仓名 `Mosaic`、`git subtree` 保历史、`roadmap/` 留顶层、站点范围 S1、旧仓 Archive）。
