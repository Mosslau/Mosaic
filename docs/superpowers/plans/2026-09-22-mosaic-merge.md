# Mosaic 三仓合并 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 TenetLang / MindSpring / OceanVerse 三个仓库合并为单仓 `Mosaic`，顶层按「开发语言 / 算法 / 工程系统」三部分组织，完整保留三仓提交历史，不改动任何正文内容。

**Architecture:** 用 `git subtree add --prefix=_import/<repo>` 把三仓历史整体导入到一个新仓的暂存区，再用 `git mv` 把每个「域」作为整体重排到目标位置（域整体平移 → 域内数百条相对链接自动继续成立）。每个域搬完后立刻修正该域的路径假设（校验器、站点脚本、CI、`.gitignore`），使每个 commit 之后对应域的校验可以跑绿。最后删除 `_import/` 暂存区。

**Tech Stack:** git（subtree / mv / log --follow）、Python 3（两套 `validate.py`、pytest、ruff）、Node 20（VitePress 站点）、Go 1.25（语言域与数据平台域）、Docker Compose、GitHub Actions、`gh` CLI。

**Spec:** `docs/superpowers/specs/2026-09-22-mosaic-merge-design.md`

**任务编号对应 spec 的提交切分：** Task 1 = C1，Task 2 = C2，……，Task 8 = C7 之后的旧仓归档。

## Global Constraints

以下约束适用于**每一个** Task，不再重复：

- **源仓只读**：迁移期间不得修改 `../TenetLang`、`../MindSpring`、`../OceanVerse` 的任何文件。只允许 `git fetch` 与 `git ls-files` 这类读操作。
- **冻结点**：`TenetLang 37b494a`、`MindSpring a0d1d7d`、`OceanVerse 2ef5087`，三仓 `git status --porcelain` 均为空。
- **不改正文**：126 个阶段、23 个算法实验、7 个工程项目的正文一个字不动。本次只做搬迁 + **93 处**路径/指代修正。
- **不做去车联网**：`GB/T 32960`、`VIN` 语义、相关 CI 断言一律保持原样。
- **不改仓名自称**（spec 决策 D10）：正文里 `TenetLang` 22 行 / `MindSpring` 16 行 / `OceanVerse` 47 行保留原样，留给后续「文案统一」轮。本次例外只有「分工/边界」段落与随域根对齐的治理/索引文案（Task 5：`engineering/ai-platform/README.md` 45/47、`07-ai-platform/README.md` 89、`engineering/README.md` 26/28 共 3 文件 5 行；fix round 2 再补 `index-format.md` 3/24/37、`engineering-readme-template.md` 3、`07-ai-platform/README.md:72` 显示文本、`engineering/ai-platform/README.md:10` 表头共 6 处）。
- **路径修正总数 93 处** = 4（`analysis→studies`）+ 27（工程→算法实验）+ 2（工程索引→路线文档）+ 1（`tenetlang-notes/validate.py`）+ 2（`mindspring-lab/validate.py`）+ 7（`sync-docs.mjs`）+ 10（`languages/.gitignore`）+ 12（`languages/website/README.md`）+ 22（CI）+ 6（边界文案行）。
- **按「路径模式」替换，不要只替换链接形态**：实测有 3 处 `../../algorithms/` 与 1 处 `../roadmap/…` 写在内联代码里（同一行内联代码 + 链接各一份）。只匹配 `](…)` 会静默漏改。
- **`git mv` 而非 `cp`**：所有搬迁必须用 `git mv`，以便重命名被**记录**为 R100（历史可经 `git log <源 tip> -- <原路径>` 追溯）。注意 `git log --follow` **不能**穿过 subtree 合并提交——这是 git 的限制，不是 `git mv` 的缺陷。
- **沙箱环境变量**：Go 命令一律加 `GOCACHE=/tmp/gocache-mosaic GOPATH=/tmp/gopath-mosaic`；npm 一律加 `--cache /tmp/npm-cache-mosaic`（`~/.npm` 不可写）。
- **中文文件名**：所有列文件清单的 git 命令加 `-c core.quotepath=false`，否则 `tenet/Tenet架构设计.md` 会被写成八进制转义。
- **`sed` 分隔符冲突**：不要写 `sed -E 's|…(a|b)…|…|g'`——交替里的 `|` 会与 `s|…|` 的分隔符冲突，BSD sed 报
  `RE error: parentheses not balanced` 且**静默不替换**。换 `#` 作分隔符，或直接用 Python（本计划凡带交替的替换一律走 Python）。
- **中间态的已知报错**：`pyproject.toml` 的 `testpaths` 指向 `algorithms/` 与 `engineering/ai-platform/`，这两处要到 Task 4/5 才存在——在它们落地前执行 `pytest` 会报「目录不存在」，`readme = "README.md"` 同理由 Task 7 补齐。这是**预期中间态**，不是缺陷（Task 2 审查者指出原文只说明了 `readme`，未说明 `testpaths`）。
- **`ruff` 是既存红，只做差分、不是绝对门禁**：三个源仓都没有让 ruff 绿过——MindSpring 在冻结点 `a0d1d7d`
  即 **420 处错误 + 45 个文件需重排**，且 `mindspring-lab/validate.py` **根本不运行 ruff**（它唯一的 `ruff`
  字样是基线忽略路径正则里的 `.ruff_cache`）。合并后 `ruff check .` 覆盖了从未按这份配置写过的
  `languages/`（79）、`.dsh/`（111）以及过渡态 `_import/`（168）。因此：**不要**试图把全仓 ruff 修绿，
  **不要**给 `pyproject.toml` 加 `exclude`/`per-file-ignores`，**不要**把 `ruff format --check` 当门禁
  （45 个文件是源仓自带的状态）。任何任务对 ruff 的要求只有一条：**不新增**——改动过的文件其计数不得高于源仓同类计数。
- **对只读源仓跑 ruff 必须加 `--no-cache`**：ruff 默认会在被检查的目录里写 `.ruff_cache/`。本迁移的差分核验
  曾对 `../MindSpring` 跑过 ruff，因而在**只读源仓**与 `_import/MindSpring/` 下各留了一个被 gitignore 的
  `.ruff_cache/`（跟踪内容未变、冻结点未变，但违反了「源仓只读」的意图）。后续核验一律 `ruff check --no-cache <path>`，
  且**不要**去删源仓里的那个目录（对源仓的任何写操作都不做）。
- **不推送**：`Mosslau/Mosaic` 远端在 Task 7 之前不推送。
- **回滚**：任何一步出错 → `rm -rf /Users/ninebot/code/mosslau/Mosaic && git clone <spec 提交>` 重建，源仓无副作用。

---

## File Structure

### 新建文件

| 路径 | 责任 |
|---|---|
| `.gitignore` | 顶层通用忽略规则（三仓通用部分并集） |
| `pyproject.toml` | Python 工程配置，覆盖 `algorithms/` 与 `engineering/ai-platform/` 两域 |
| `README.md` | 三部分总入口 + 校验命令 + 边界 |
| `languages/README.md` | 语言域导航（学/析/合 + 6 语言阶段表）；同时是站点「总览」页源（`sync-docs.mjs` 的 `rootReadme` → `docs/about.md`） |
| `engineering/README.md` | 工程域导航：两域分工、依赖关系与开工顺序 |
| `roadmap/README.md` | 全仓路线索引（4 份路线文档） |
| `languages/.gitignore` | 语言域产物清单（由 `TenetLang/.gitignore` 改名而来，10 行前缀修正） |

### 搬迁映射（源 → 目标）

| 源 | 目标 |
|---|---|
| `TenetLang/languages/` | `languages/studies/` |
| `TenetLang/analysis/` | `languages/analysis/` |
| `TenetLang/tenet/` | `languages/tenet/` |
| `TenetLang/website/` | `languages/website/` |
| `TenetLang/books/` | `books/` |
| `TenetLang/.dsh/skills/*`（15 个） | `.dsh/skills/*` |
| `MindSpring/algorithms/` | `algorithms/` |
| `MindSpring/roadmap/` | `roadmap/` |
| `MindSpring/engineering/` | `engineering/ai-platform/` |
| `MindSpring/.dsh/skills/mindspring-lab/` | `.dsh/skills/mindspring-lab/` |
| `OceanVerse/roadmap/智能大数据平台工程师.md` | `roadmap/智能大数据平台工程师.md` |
| `OceanVerse/{contracts,deploy,ingest,lakehouse,scripts,roadmap}/` | `engineering/data-platform/` 同名子目录 |
| `OceanVerse/README.md` | `engineering/data-platform/README.md` |
| `OceanVerse/.gitignore` | `engineering/data-platform/.gitignore` |
| `OceanVerse/.github/` | `.github/` |
| 其余 `_import/**` | Task 7 `git rm -r _import` 删除 |

### 修改文件（精确位置见各 Task）

`.dsh/skills/tenetlang-notes/scripts/validate.py`、`.dsh/skills/tenetlang-notes/SKILL.md`、`.dsh/skills/mindspring-lab/scripts/validate.py`、`.dsh/skills/mindspring-lab/SKILL.md`、`languages/website/scripts/sync-docs.mjs`、`languages/website/README.md`、`engineering/ai-platform/README.md`、`engineering/ai-platform/07-ai-platform/README.md`、`.github/workflows/ci.yml`、4 个 `analysis/*/README.md`、7 个 `engineering/ai-platform/*/README.md`。

---

## Task 1: 冻结点核对 + subtree 导入三仓

**Files:**
- Create: `_import/TenetLang/`、`_import/MindSpring/`、`_import/OceanVerse/`（全部内容）
- 无新提交：`git subtree add` 自带 3 个 merge commit

**Interfaces:**
- Consumes: 三个源仓在冻结点且干净
- Produces: `_import/<repo>/` 下三仓完整内容 + 三仓提交历史可追溯；后续所有 Task 从这里 `git mv`

- [ ] **Step 1: 核对三个源仓冻结点（前置断言，不满足则中止）**

```bash
cd /Users/ninebot/code/mosslau
for r in TenetLang:37b494a MindSpring:a0d1d7d OceanVerse:2ef5087; do
  name=${r%%:*}; want=${r##*:}
  got=$(git -C $name rev-parse --short HEAD)
  dirty=$(git -C $name status --porcelain | wc -l | tr -d ' ')
  [ "$got" = "$want" ] || { echo "FAIL $name HEAD=$got 期望 $want"; exit 1; }
  [ "$dirty" = "0" ]  || { echo "FAIL $name 有 $dirty 个未提交变更"; exit 1; }
  echo "OK $name @ $got 干净"
done
```

Expected: 三行 `OK … 干净`，无 `FAIL`。

- [ ] **Step 2: 加 remote 并 fetch（只读，不改源仓）**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
git remote add tl ../TenetLang
git remote add ms ../MindSpring
git remote add ov ../OceanVerse
git fetch tl --tags && git fetch ms --tags && git fetch ov --tags
git remote -v
```

Expected: 6 行（3 个 remote × fetch/push），HEAD 与冻结点一致。

- [ ] **Step 3: 逐个 subtree 导入（保留完整历史）**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
git subtree add --prefix=_import/TenetLang  tl/main
git subtree add --prefix=_import/MindSpring ms/main
git subtree add --prefix=_import/OceanVerse ov/main
```

Expected: 每条打印 `Added dir '_import/<name>' …`。若报 `working tree has modifications`，回到 Step 1 核对源仓。

- [ ] **Step 4: 验证文件完整性与历史连通**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
# 基线自带 2 个跟踪文件（specs/…-design.md 与 plans/…-mosaic-merge.md），故 +2
expect=$(( $(git -C ../TenetLang ls-files | wc -l) + $(git -C ../MindSpring ls-files | wc -l) + $(git -C ../OceanVerse ls-files | wc -l) + 2 ))
got=$(git ls-files | wc -l | tr -d ' ')
echo "跟踪文件数 got=$got expect=$expect（+2 是基线自带的两个文档）"
[ "$got" = "$expect" ] && echo "OK 文件数一致" || echo "FAIL 文件数不一致"

# 历史连通：subtree 的历史挂在 Add commit 的**第二父**上，
# 所以 `git log -- _import/<name>` 只返回 1 条（路径过滤不追第二父），
# 也无法用 `git log --follow`（文件由 merge 引入，--follow 不跟 merge，实测返回 0 条）。
for c in $(git log --format='%h %s' --grep='^Add ' | awk '{print $1}'); do
  printf "  %s  ^2=%s  提交数=%s\n" "$c" "$(git rev-parse --short $c^2)" "$(git rev-list --count $c^2)"
done
git rev-list --count HEAD    # 期望 324 = 154+41+123 + 基线 3 + 空提交 1 + 3 个 Add merge
```

Expected: `跟踪文件数 got=4783 expect=4783` + `OK 文件数一致`；三条 Add commit 的 `^2` 分别为 `37b494a` / `a0d1d7d` / `2ef5087`，提交数 154 / 41 / 123；`HEAD` 可达提交数 324。

- [ ] **Step 5: 确认源仓未被改动**

```bash
for r in TenetLang MindSpring OceanVerse; do
  printf "%-12s %s %s\n" $r "$(git -C /Users/ninebot/code/mosslau/$r rev-parse --short HEAD)" \
    "$(git -C /Users/ninebot/code/mosslau/$r status --porcelain | wc -l | tr -d ' ')"
done
```

Expected: 三个冻结点 hash，脏文件数均为 0。

- [ ] **Step 6: 提交记录（无内容变更，仅一个空提交标记里程碑）**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
git commit --allow-empty -m "chore: 三仓 subtree 导入完成（保留完整历史）

_import/TenetLang  154 提交 / 3955 文件
_import/MindSpring  41 提交 /  674 文件
_import/OceanVerse 123 提交 /  152 文件

下一步起用 git mv 逐域重排到目标结构。"
```

---

## Task 2: 顶层公共资产与跨域资产

**Files:**
- Create: `.gitignore`、`pyproject.toml`、`.dsh/skills/`（16 个 skill）
- Move: `_import/TenetLang/.dsh/skills/*` → `.dsh/skills/`；`_import/MindSpring/.dsh/skills/mindspring-lab` → `.dsh/skills/mindspring-lab`；`_import/TenetLang/books` → `books`；`_import/TenetLang/{LICENSE,.mcp.json}` → 顶层；`_import/MindSpring/.python-version` → 顶层

**Interfaces:**
- Consumes: Task 1 的 `_import/`
- Produces: `.dsh/skills/{tenetlang-notes,mindspring-lab,…}`（供 Task 3/5 改校验器）、顶层 `.gitignore`（供后续所有 Task 的产物纪律）、`pyproject.toml`（供 Task 5 的 pytest）

- [ ] **Step 1: 断言三份 LICENSE 与 .mcp.json 逐字节相同**

```bash
cd /Users/ninebot/code/mosslau
md5 -q TenetLang/LICENSE MindSpring/LICENSE OceanVerse/LICENSE | sort -u | wc -l   # 期望 1
md5 -q TenetLang/.mcp.json MindSpring/.mcp.json OceanVerse/.mcp.json | sort -u | wc -l  # 期望 1
```

Expected: 两个 `1`。若不是 1，停止并回报差异（本计划假定相同）。

- [ ] **Step 2: 移动跨域资产与根级元文件**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
git mv _import/TenetLang/books books
git mv _import/TenetLang/LICENSE LICENSE
git mv _import/TenetLang/.mcp.json .mcp.json
git mv _import/MindSpring/.python-version .python-version
git -c core.quotepath=false ls-files books LICENSE .mcp.json .python-version
```

Expected: `books/books.md`、`LICENSE`、`.mcp.json`、`.python-version` 各一行。

- [ ] **Step 3: 并集技能目录（16 个）**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
mkdir -p .dsh/skills
git mv _import/TenetLang/.dsh/skills/* .dsh/skills/
git mv _import/MindSpring/.dsh/skills/mindspring-lab .dsh/skills/mindspring-lab
ls .dsh/skills | wc -l | tr -d ' '            # 期望 16
```

Expected: `16`。

- [ ] **Step 4: 断言并集没丢内容（与 OceanVerse 的副本逐字节对比）**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
for s in $(ls _import/OceanVerse/.dsh/skills); do
  diff -rq ".dsh/skills/$s" "_import/OceanVerse/.dsh/skills/$s" >/dev/null || echo "DIFF: $s"
done
echo "对比完成（无 DIFF 行为通过）"
```

Expected: 只有 `对比完成…`，没有任何 `DIFF:` 行。

- [ ] **Step 5: 写顶层 `.gitignore`**

Create `.gitignore`：

```gitignore
# ============================================================
# Mosaic 顶层通用忽略规则
#
# 这是三仓 .gitignore 的「通用部分」并集。域内特有的产物清单
# 由各域自带，不在这里重复：
#   languages/.gitignore                     （语言域构建产物）
#   languages/website/.gitignore             （站点 node_modules/ 与 docs/）
#   engineering/data-platform/.gitignore     （数据平台 bin/ 与 .tmp-*）
# ============================================================

# --- 系统 / 编辑器 ---
.DS_Store
.workbuddy/
.idea/
.vscode/

# --- 构建产物（不锚定，覆盖全域）---
target/
target
debug
/build/
/dist/
/site
*.o
*.a
*.so
*.pdb
*.class
*.jar
*.war
**/*.rs.bk
**/mutants.out*/
hs_err_pid*
replay_pid*

# --- Python ---
__pycache__/
*.py[cod]
*.py[codz]
*$py.class
*.egg
*.egg-info/
wheels/
MANIFEST
pip-log.txt
pip-delete-this-directory.txt
*.manifest
*.spec
.venv/
venv/
ENV/
env/
env.bak/
venv.bak/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.dmypy.json
dmypy.json
.pyre/
.pytype/
.coverage
.coverage.*
coverage.xml
htmlcov/
.tox/
.nox/
.hypothesis/
.cache
.ipynb_checkpoints/
docs/_build/
.streamlit/secrets.toml
.env
.envrc
.pypirc
**/outputs/
**/data/cache/

# --- 日志 ---
# 语言域的教学样例里**故意跟踪** .log 数据文件（py/ph05 的 sample_logs.log、
# rs/ph06 的 sample.log），下面两行豁免必须保留——删掉它们会让以后新增的同
# 类样例被静默忽略（gitignore 不作用于已跟踪文件，症状只在新增文件时出现）。
*.log
!languages/studies/py/ph05-file-exception/project/sample_logs.log
!languages/studies/rs/ph06-cargo-module/project/log-analyzer/sample.log
```

- [ ] **Step 6: 写 `pyproject.toml`**

Create `pyproject.toml`：

```toml
[project]
name = "mosaic"
version = "0.1.0"
description = "Mosaic：通用数据平台 + AI 平台数据中心 —— 语言 / 算法 / 工程系统三部分实验与实践仓库"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "numpy>=2.0",
    "matplotlib>=3.9",
    "scikit-learn>=1.5",
]

[project.optional-dependencies]
deep-learning = [
    "torch>=2.4",
]
engineering = [
    "fastapi>=0.115",
    "uvicorn>=0.30",
]
dev = [
    "pytest>=8.0",
    "ruff>=0.6",
]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.pytest.ini_options]
testpaths = ["algorithms", "engineering/ai-platform"]
```

> `readme = "README.md"` 指向 Task 7 才创建的顶层 README。本仓未声明 `[build-system]`，pytest / ruff 都不解析该字段，中间态无影响。

- [ ] **Step 7: 验证忽略规则没有误伤**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
git status --porcelain | head -20
echo "--- 抽样确认关键文件不被忽略 ---"
for f in docs/superpowers/specs/2026-09-22-mosaic-merge-design.md pyproject.toml LICENSE .mcp.json; do
  git check-ignore -q "$f" && echo "误伤: $f" || echo "OK 未忽略: $f"
done
echo "--- 确认域内容没被顶层规则误伤 ---"
git -c core.quotepath=false ls-files _import/TenetLang/languages | wc -l   # 期望 3789
```

Expected: `git status` 输出为本次新增/改名项；4 行 `OK 未忽略`；`3789`。

- [ ] **Step 8: 提交**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
git add -A
git commit -m "chore: 合并顶层公共资产与跨域资产

- .dsh/skills/ 并集 16 个（TenetLang 15 + mindspring-lab），与 OceanVerse 副本逐字节一致
- LICENSE / .mcp.json 三份逐字节相同，各留一份
- .gitignore 顶层通用规则（分层方案：域内产物由各域自带）
- pyproject.toml 取自 MindSpring，改名 mosaic、testpaths 指向 engineering/ai-platform
- books/ 为跨域计算机书单，留顶层"
```

---

## Task 3: 语言域重排（`languages/{studies,analysis,tenet,website}`）

**Files:**
- Move: 见 Step 1
- Modify: `languages/analysis/{cpp,java,py,rs}/README.md`（4 处）、`.dsh/skills/tenetlang-notes/scripts/validate.py:445`、`languages/website/scripts/sync-docs.mjs`（7 处）、`languages/website/README.md`（12 处）、`.dsh/skills/tenetlang-notes/SKILL.md`（10 行）
- Create: `languages/README.md`

**Interfaces:**
- Consumes: Task 2 的 `.dsh/skills/tenetlang-notes/`
- Produces: `languages/` 域，`validate.py` 可跑绿；`languages/README.md`（Task 7 的顶层 README 会链接它；`sync-docs.mjs` 的 `rootReadme` 依赖它（落 `docs/about.md`））

- [ ] **Step 1: 四组 `git mv` + `.gitignore` 改名**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
mkdir -p languages
git mv _import/TenetLang/languages languages/studies
git mv _import/TenetLang/analysis  languages/analysis
git mv _import/TenetLang/tenet     languages/tenet
git mv _import/TenetLang/website   languages/website
git mv _import/TenetLang/.gitignore languages/.gitignore
ls languages
```

Expected: `analysis  studies  tenet  website  .gitignore`。

- [ ] **Step 2: 验证搬迁完整性（源清单 ↔ 目标清单逐条比对）**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
diff \
  <(git -C ../TenetLang -c core.quotepath=false ls-files \
    | grep -v -E '^(README\.md|LICENSE|\.mcp\.json|\.gitignore|\.dsh/|books/)' \
    | sed -e 's|^languages/|languages/studies/|' \
          -e 's|^analysis/|languages/analysis/|' \
          -e 's|^tenet/|languages/tenet/|' \
          -e 's|^website/|languages/website/|' | sort) \
  <(git -c core.quotepath=false ls-files languages | grep -v -E '^languages/(README\.md|\.gitignore)$' | sort) \
  && echo "OK 语言域搬迁无遗漏、无多余"
```

Expected: 只有 `OK 语言域搬迁无遗漏、无多余`（`diff` 无输出）。

- [ ] **Step 3: 修 4 条 `analysis → studies` 链接**

对 `languages/analysis/{cpp,java,py,rs}/README.md` 各一条：`](../../languages/<lang>/)` → `](../../studies/<lang>/)`。

⚠ **深度不变，只换族名段。** 源文件同时也下沉了一级（`analysis/cpp/` → `languages/analysis/cpp/`）：原来的两个 `../`
是「爬出 `analysis/` 到仓库根」，现在的两个 `../` 是「爬出 `languages/analysis/` 到 `languages/`」——步数相同。
写成 `](../studies/…)` 会指向不存在的 `languages/analysis/studies/`（实施时确实踩到，站点同步报了 4 条失效链接）。

⚠ 这 4 条链接**不在语言域校验器的管辖范围内**（`lang_root = languages/studies`，而它们位于 `languages/analysis/`），
`validate.py --links` 抓不到；**只有 Step 11 站点同步的死链报告能发现它们**，所以 Step 11 必须要求 **0 条失效链接**。

```bash
cd /Users/ninebot/code/mosslau/Mosaic
sed -i '' -e 's|](\.\./\.\./languages/|](../../studies/|g' \
  languages/analysis/cpp/README.md languages/analysis/java/README.md \
  languages/analysis/py/README.md  languages/analysis/rs/README.md
grep -rho '](\.\./\.\./studies/' languages/analysis | wc -l  # 期望 4（正确深度）
grep -rho '](\.\./studies/'           languages/analysis | wc -l  # 期望 0（错误深度）
grep -rho '\.\./\.\./languages/'      languages/analysis | wc -l  # 期望 0（残留旧形态）
for l in cpp java py rs; do test -d "languages/studies/$l" || echo "❌ languages/studies/$l 不存在"; done
echo "四个目标目录均存在"
```

Expected: `4` / `0` / `0` + `四个目标目录均存在`。

⚠ **Step 2 的映射 diff 只在 Step 7b 之前有效。** Step 7b 把 `content/languages/index.md` 改名为
`content/studies/index.md`（族名改了，手写总览页必须落在对应的**路由**上），此后重跑 Step 2 会多出 2 行。
那是**纯改名、零内容丢失**，用 blob 比对即可证伪：

```bash
cd /Users/ninebot/code/mosslau/Mosaic
a=$(git rev-parse ../TenetLang:website/content/languages/index.md)
b=$(git rev-parse HEAD:languages/website/content/studies/index.md)
test "$a" = "$b" && echo "OK 纯改名，blob 相同：$a" || echo "❌ 内容变了：$a vs $b"
```

- [ ] **Step 4: 修 `languages/.gitignore` 的 10 行前缀**

`/languages/go/ph21-data-ingest-gateway/…` → `/studies/go/ph21-data-ingest-gateway/…`：

```bash
cd /Users/ninebot/code/mosslau/Mosaic
sed -i '' 's|^/languages/go/|/studies/go/|' languages/.gitignore
grep -c '^/studies/go/' languages/.gitignore                 # 期望 10
grep -c '^analysis/cpp/demos/\|^tenet/compiler-' languages/.gitignore  # 期望 9（零改动部分）
grep -c '^/languages/' languages/.gitignore                  # 期望 0
```

Expected: `10`、`9`、`0`。

- [ ] **Step 5: 修 `tenetlang-notes/validate.py` 的管辖根**

把 `.dsh/skills/tenetlang-notes/scripts/validate.py:445` 的

```python
    lang_root = root / "languages"
```

改为

```python
    lang_root = root / "languages" / "studies"
```

（`:447` 的报错文案用 f-string 插值 `lang_root`，自动跟着变，**不要**手工改。）

```bash
cd /Users/ninebot/code/mosslau/Mosaic
grep -n 'lang_root = root' .dsh/skills/tenetlang-notes/scripts/validate.py  # 期望 1 行含 "studies"
```

- [ ] **Step 6: 跑语言域校验（TDD 的「先看它绿」）**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
python3 .dsh/skills/tenetlang-notes/scripts/validate.py --links
echo "exit=$?"
```

Expected: `exit=0`，输出无 `✗` / `悬空`。若报悬空链接，检查 Step 3 是否漏改。

- [ ] **Step 6b: 复算忽略规则审计（此刻应回到 0）**

Task 2 结束时该审计为 **2**：两份教学 `.log` 样例当时仍在 `_import/TenetLang/languages/…`，
而豁免行锚定的是**最终路径** `languages/studies/…`。本步把 `languages/` 落到顶层后必须回到 0：
若仍为 2，说明搬迁没把 `languages/` 放到位。

```bash
cd /Users/ninebot/code/mosslau/Mosaic
git -c core.quotepath=false ls-files > /tmp/mosaic-tracked.txt
n=$(git check-ignore --no-index --stdin < /tmp/mosaic-tracked.txt 2>/dev/null | wc -l | tr -d ' ')
echo "被忽略的已跟踪文件数: $n（期望 0）"
if [ "$n" != "0" ]; then git check-ignore --no-index -v --stdin < /tmp/mosaic-tracked.txt | head; fi
# 负向对照：确认这个审计是活的（站点 docs/ 是被 .gitignore 忽略的产物目录）
printf 'languages/website/docs/index.md\n' | git check-ignore --no-index --stdin \
  && echo "OK 负向对照有效（能识别出确应被忽略的路径）" \
  || echo "⚠ 负向对照未生效：审计可能是恒 0，不可信"
```

Expected: `被忽略的已跟踪文件数: 0（期望 0）` + `OK 负向对照有效`。

- [ ] **Step 7: 修站点同步脚本的 7 处**

站点移入 `languages/website/` 后，`REPO_DIR = path.resolve(SITE_DIR, '..')` **自动等于语言域根 `languages/`**，因此第 17 行**不动**。改以下 7 处：

| 行 | 原文 | 改为 |
|---|---|---|
| 23 | `const FAMILIES = ['languages', 'analysis', 'tenet']` | `const FAMILIES = ['studies', 'analysis', 'tenet']` |
| 347 | `path.resolve(REPO_DIR, 'languages', langId, ch.detail)` | `path.resolve(REPO_DIR, 'studies', langId, ch.detail)` |
| 357 | `path.resolve(REPO_DIR, 'languages', langId, ch.dir, layer.dir)` | `path.resolve(REPO_DIR, 'studies', langId, ch.dir, layer.dir)` |
| 481 | `path.join(REPO_DIR, 'languages', meta.id)` | `path.join(REPO_DIR, 'studies', meta.id)` |
| 505 | `path.join(DOCS_DIR, 'languages', lang.id, 'index.md')` | `path.join(DOCS_DIR, 'studies', lang.id, 'index.md')` |
| 495 | `docs: familyFiles.languages.filter((f) => f.startsWith(langDir + path.sep)).length,` | `docs: familyFiles.studies.filter((f) => f.startsWith(langDir + path.sep)).length,` |
| 530 | `languageDocs: familyFiles.languages.length,` | `languageDocs: familyFiles.studies.length,` |

> ⚠ **495 与 530 是同一个坑**：`FAMILIES` 的键改成 `studies` 后，`familyFiles.languages` 变成 `undefined`，`.filter` / `.length` 会在运行时抛 TypeError。两处**都必须**改。

**不要改**：476 行 `rootReadme = path.join(REPO_DIR, 'README.md')`（自动指向 `languages/README.md`）；372/417/435 行（`analysis/`、`tenet/` 相对域根不变）；531/532 行（`familyFiles.analysis` / `familyFiles.tenet` 键名不变）。

```bash
cd /Users/ninebot/code/mosslau/Mosaic
f=languages/website/scripts/sync-docs.mjs
python3 - "$f" <<'PY'
import sys,pathlib
p=pathlib.Path(sys.argv[1]); t=p.read_text(encoding='utf-8')
reps=[("const FAMILIES = ['languages', 'analysis', 'tenet']","const FAMILIES = ['studies', 'analysis', 'tenet']"),
      ("path.resolve(REPO_DIR, 'languages', langId, ch.detail)","path.resolve(REPO_DIR, 'studies', langId, ch.detail)"),
      ("path.resolve(REPO_DIR, 'languages', langId, ch.dir, layer.dir)","path.resolve(REPO_DIR, 'studies', langId, ch.dir, layer.dir)"),
      ("path.join(REPO_DIR, 'languages', meta.id)","path.join(REPO_DIR, 'studies', meta.id)"),
      ("path.join(DOCS_DIR, 'languages', lang.id, 'index.md')","path.join(DOCS_DIR, 'studies', lang.id, 'index.md')"),
      ("docs: familyFiles.languages.filter((f) => f.startsWith(langDir + path.sep)).length,","docs: familyFiles.studies.filter((f) => f.startsWith(langDir + path.sep)).length,"),
      ("languageDocs: familyFiles.languages.length,","languageDocs: familyFiles.studies.length,")]
for a,b in reps:
    assert t.count(a)==1, f"命中 {t.count(a)} 次: {a}"
    t=t.replace(a,b)
p.write_text(t,encoding='utf-8'); print("sync-docs.mjs 7 处已改")
PY
grep -c "'languages'" "$f"   # 期望 0
grep -n "REPO_DIR = " "$f"   # 期望仍是 path.resolve(SITE_DIR, '..')，未改
```

Expected: `sync-docs.mjs 7 处已改`；`0`（文件里再无 `'languages'` 字面量）；`const REPO_DIR = path.resolve(SITE_DIR, '..')`（未改）。

再补一条断言，确认 `familyFiles` 的两个键都已改名：

```bash
cd /Users/ninebot/code/mosslau/Mosaic
grep -c 'familyFiles\.languages' languages/website/scripts/sync-docs.mjs   # 期望 0
grep -c 'familyFiles\.studies'   languages/website/scripts/sync-docs.mjs   # 期望 2
```

Expected: `0` 与 `2`。

- [ ] **Step 7b: 修站点侧的**全部**族名假设（路由 + 监听路径 + 文案）**

Step 7 只改了 `sync-docs.mjs` 的**数据路径**。站点的族名假设还有三层，且每层的失败方式都不同——**必须三层一起改**：

| 层 | 文件 | 行 | 原文 | 改为 |
|---|---|---|---|---|
| 路由 | `scripts/sync-docs.mjs` | 494 | `` board: `/languages/${meta.id}/`, `` | `` board: `/studies/${meta.id}/`, `` |
| 路由 | `.vitepress/config.mts` | 59 | `{ text: '六门语言总览', link: '/languages/' }` | `link: '/studies/'` |
| 路由 | `.vitepress/config.mts` | 80 | `` `/languages/${lang.id}/`, `` | `` `/studies/${lang.id}/`, `` |
| 路由 | `.vitepress/config.mts` | 104 | `'/languages/': [` | `'/studies/': [` |
| 路由 | `.vitepress/theme/components/ThreePaths.vue` | 12 | `link: '/languages/',` | `link: '/studies/',` |
| 路由 | `content/analysis/index.md` | 20 | `[六门语言](/languages/)` | `[六门语言](/studies/)` |
| 路由 | `content/languages/index.md` | — | （文件） | `git mv` 为 `content/studies/index.md` |
| **监听** | `scripts/dev.mjs` | 23 | `path.join(REPO_DIR, 'languages'),` | `path.join(REPO_DIR, 'studies'),` |
| 文案 | `scripts/dev.mjs` | 5 / 21 | 「内容真源是 `languages/`…与仓库根 README」/「三个内容族（仓库根）」 | 域根下的 `studies/`…与域根 README /（域根） |
| 文案 | `scripts/sync-docs.mjs` | 7 / 486 | 头注释「仓库里的 `languages/`」/ 告警文案 `languages/${meta.id}/` | 域根下的 `studies/` / `studies/${meta.id}/` |
| 文案 | `package.json` | 6 | description `languages / analysis / tenet 三族` | `studies / analysis / tenet 三族` |

**三层各自的失败方式是本步存在的理由：**
- **路由层**不改：构建照样成功，但导航与侧边栏每个语言链接**静默 404**。
- **监听层**（`dev.mjs:23`）不改：`REPO_DIR` 现在是语言域根，该路径解析为不存在的 `languages/languages`，而第 78 行的
  `fs.existsSync` 守卫**静默跳过**它——`npm run dev` 正常启动，但**不再监听 3905 个语言源文件**。
- **文案层**不改：不影响运行，但会误导后来者。

⚠ **不要改** `curriculum.languages` / `stats.languages`——那是 `curriculum.json` 的**数据模型键**（由 `sync-docs.mjs:524/528`
产出，与路径无关）；`dev.mjs:29` 的 `path.join(REPO_DIR, 'README.md')` 也是**对的**（现在解析为 `languages/README.md`）。

```bash
cd /Users/ninebot/code/mosslau/Mosaic/languages/website
python3 - <<'PY'
import pathlib
edits = {
  'scripts/sync-docs.mjs': [("    board: `/languages/${meta.id}/`,", "    board: `/studies/${meta.id}/`,"),
                            ("内容唯一真源始终是仓库里的 `languages/`、`analysis/`、`tenet/`。",
                             "内容唯一真源始终是域根下的 `studies/`、`analysis/`、`tenet/`。"),
                            ("warn(`languages/${meta.id}/ 顶层应有且仅有 1 篇 roadmap",
                             "warn(`studies/${meta.id}/ 顶层应有且仅有 1 篇 roadmap")],
  '.vitepress/config.mts': [("{ text: '六门语言总览', link: '/languages/' },", "{ text: '六门语言总览', link: '/studies/' },"),
                            ("    `/languages/${lang.id}/`,", "    `/studies/${lang.id}/`,"),
                            ("  '/languages/': [", "  '/studies/': [")],
  '.vitepress/theme/components/ThreePaths.vue': [("    link: '/languages/',", "    link: '/studies/',")],
  'content/analysis/index.md': [("[六门语言](/languages/)", "[六门语言](/studies/)")],
  'scripts/dev.mjs': [("  path.join(REPO_DIR, 'languages'),", "  path.join(REPO_DIR, 'studies'),"),
                      ("内容真源是 `languages/`、`analysis/`、`tenet/` 与仓库根 README",
                       "内容真源是域根下的 `studies/`、`analysis/`、`tenet/` 与域根 README"),
                      ("三个内容族（仓库根）", "三个内容族（域根）")],
  'package.json': [("languages / analysis / tenet 三族", "studies / analysis / tenet 三族")],
}
n=0
for f,reps in edits.items():
    q=pathlib.Path(f); s=q.read_text(encoding='utf-8')
    for a,b in reps:
        assert s.count(a)==1, f"{f}: 命中 {s.count(a)} 次: {a[:45]}"
        s=s.replace(a,b); n+=1
    q.write_text(s,encoding='utf-8')
print(f"共改 {n} 处（期望 15）")
PY
git mv content/languages/index.md content/studies/index.md
rmdir content/languages 2>/dev/null || true

echo "--- 路由层：站点工程内不得再有 /languages 路由引用 ---"
grep -rn '/languages' .vitepress scripts content 2>/dev/null | grep -v node_modules | grep -v '/dist/' | wc -l  # 期望 0
test -f content/studies/index.md && echo "OK 总览页已在 content/studies/index.md"
test ! -e content/languages && echo "OK content/languages/ 已不存在"
echo "--- 监听层：dev server 必须真的在监听 studies ---"
timeout 30 node scripts/dev.mjs 2>&1 | grep -m1 '监听中'   # 必须出现 studies
echo "--- 文案层：陈旧表述清零 ---"
grep -rn "REPO_DIR, 'languages'\|仓库里的 `languages/`\|仓库根 README" scripts package.json | wc -l  # 期望 0
```

Expected: `共改 15 处（期望 15）`；`0` + 两行 `OK …`；`监听中：studies、analysis、tenet、website/content、README.md`（站点现在位于域根之下，故 `content` 的相对路径带 `website/` 前缀）；最后 `0`。

- [ ] **Step 7c: 修内容正文与代码块里的旧族名路径（20 文件 23 处）**

Step 3 只修了**链接目标**。正文与代码块里的**路径提及**同属 spec D10 的「路径类引用」——照着敲会失败，
最典型的是 4 个 Go 项目 README 里的 `cd languages/go/<阶段>/project`。规则唯一：
`languages/<语言>/` → `languages/studies/<语言>/`（只有 6 个语言名，无其它形态）。

⚠ **不要用 `sed -E` 且以 `|` 作分隔符写这条替换**：交替内的 `|` 会与 `s|…|…|` 的分隔符冲突，
BSD sed 报 `RE error: parentheses not balanced`，**替换静默不生效**（实测；换 `#` 作分隔符即正常，说明
与 BSD 是否支持 `-E` 交替无关）。用 Python 更稳，且用负向断言避免消费后一个字符。

```bash
cd /Users/ninebot/code/mosslau/Mosaic/languages
python3 - <<'PY'
import re, pathlib
FILES = [
  'studies/py/ph18-data-platform-automation/18-data-platform-automation.md',   # 3 处
  'studies/py/ph17-advanced-python/17-advanced-python.md',                     # 2 处
  'studies/go/ph14-advanced-go/project/README.md',
  'studies/go/ph14-advanced-go/14-advanced-go.md',
  'studies/go/ph17-architecture-layering/project/README.md',
  'studies/go/ph15-version-toolchain/project/README.md',
  'studies/go/ph15-version-toolchain/examples/README.md',
  'studies/go/ph01-basic-syntax/project/README.md',
  'studies/go/ph13-perf-optimization/project/README.md',
  'studies/go/ph13-perf-optimization/13-perf-optimization.md',
  'studies/java/ph23-lakehouse-orchestration/23-lakehouse-orchestration.md',
  'studies/java/ph23-lakehouse-orchestration/project/README.md',
  'studies/java/ph22-ai-platform/project/README.md',
  'studies/java/ph22-ai-platform/22-ai-platform.md',
  'studies/cpp/ph22-storage-engine-db-kernel/22-storage-engine-db-kernel.md',
  'analysis/py/README.md', 'analysis/java/README.md', 'analysis/rs/README.md', 'analysis/cpp/README.md',
  'analysis/cpp/notes/03-multiparadigm.md',
]
pat = re.compile(r'languages/(c|cpp|go|java|py|rs)(?![a-z0-9_-])')
total = 0
for f in FILES:
    q = pathlib.Path(f); s = q.read_text(encoding='utf-8')
    s2, n = pat.subn(r'languages/studies/\1', s)
    assert n >= 1, f"{f}: 命中的 {n} 处（每文件应 ≥1）"
    q.write_text(s2, encoding='utf-8'); total += n
print(f"共替换 {total} 处（期望 23）")
PY
```

另两处同族、同一步处理：
- `languages/tenet/README.md:87` 的裸 `` `languages/` `` 指的是**「学」主线**（三条主线应为 `studies/`、`analysis/`、`tenet/`；
  `languages/` 是**域根**，不是主线名）→ 改为 `` `studies/` ``；
- `.dsh/skills/tenetlang-notes/scripts/validate.py:454` 的硬编码陈旧消息
  `f"找不到语言目录 languages/{args.lang}"` → `f"找不到语言目录 {lang_root / args.lang}"`（与 `:447` 一致，不会再过期）。

```bash
cd /Users/ninebot/code/mosslau/Mosaic
echo "--- 旧族名路径必须清零 ---"
grep -rnE 'languages/(c|cpp|go|java|py|rs)([^a-z0-9_-]|$)' --include='*.md' languages/studies languages/analysis languages/tenet \
  | grep -v 'languages/studies/' | wc -l            # 期望 0
echo "--- 改动面必须恰好 22 个文件（20 内容 + tenet/README.md + validate.py）---"
git diff --name-only | wc -l | tr -d ' '
echo "--- 治理内容被改动，校验器必须复跑 ---"
python3 .dsh/skills/tenetlang-notes/scripts/validate.py --links; echo "exit=$?"
```

Expected: 旧族名 0；改动 22 个文件；校验器 `0 个问题` + `exit=0`；站点构建仍 0 条失效链接。

- [ ] **Step 8: 修 `languages/website/README.md` 的 12 处路径（站点内容根 = 语言域根）**

站点移进 `languages/` 后，它的**内容根就是语言域根**，所以内容族名写成 `studies/`（不是 `languages/studies/`），
而站点自身与产物的路径要加 `languages/` 前缀。逐行改：

| 行 | 原文（片段） | 改为 |
|---|---|---|
| 3 | 把仓库里 `languages/`、`analysis/`、`tenet/` 三个目录族 | 把域根下 `studies/`、`analysis/`、`tenet/` 三个目录族 |
| 15 | `cd website` | `cd languages/website` |
| 22 | 会监听 `languages/`、`analysis/`、`tenet/`、站点 `content/` 与仓库根 `README.md` | 会监听 `studies/`、`analysis/`、`tenet/`、站点 `content/` 与域根 `README.md` |
| 40 | `languages/ analysis/ tenet/  +  根 README.md` | `studies/ analysis/ tenet/  +  域根 README.md` |
| 44 | `website/docs/` | `languages/website/docs/` |
| 50 | `git add website/` | `git add languages/website/` |
| 56 | `website/`（目录树根标签） | `languages/website/` |
| 61 | `│   ├── languages/…  ← 从 repo 的 languages/ 复制` | `│   ├── studies/…   ← 从域根的 studies/ 复制` |
| 62–63 | `← 从 repo 的 analysis/`、`← 从 repo 的 tenet/` | `← 从域根的 analysis/`、`← 从域根的 tenet/` |
| 64 | `about.md  ← 从 repo 根 README.md 复制` | `about.md  ← 从语言域 README.md 复制` |
| 73 | 复制三个内容族与根 README 的全部 Markdown | 复制三个内容族与域根 README 的全部 Markdown |
| 101 | `languages/<语言>/<语言>.md` | `studies/<语言>/<语言>.md` |

**不要改**：第 1 行标题里的 `TenetLang`（仓名自称，spec D10）；第 10 行的 `.dsh/skills/tenetlang-notes/SKILL.md`
（仓库根相对路径，约定不变）；第 74 行的 `/analysis/py/`（站点路由，未变）；第 113/116 行的
`scripts/sync-docs.mjs`（站点内相对路径，未变）。

```bash
cd /Users/ninebot/code/mosslau/Mosaic
f=languages/website/README.md
echo "--- 应清零的旧写法 ---"
grep -n '仓库里 `languages/`\|cd website$\|`website/docs/`\|git add website/\|languages/<语言>/' "$f" || echo "OK 旧写法已清零"
echo "--- 应到位的新写法 ---"
grep -cn 'studies/' "$f"; grep -n 'cd languages/website' "$f"; grep -n 'languages/website/docs/' "$f"
echo "--- 该保留的 ---"
grep -n 'TenetLang 文档站\|tenetlang-notes/SKILL.md\|/analysis/py/' "$f"
```

Expected: `OK 旧写法已清零`；`studies/` 命中若干行；`cd languages/website` 1 行；`languages/website/docs/` 1 行；
最后一条打印第 1、10、74 行（证明该保留的没被误改）。

- [ ] **Step 9: 写 `languages/README.md`**

Create `languages/README.md`（**必须是站点可读的域导航页**：`sync-docs.mjs:476` 的 `rootReadme` 会把它复制成站点的
「总览」页 `docs/about.md`——**不是**首页，首页是手写的 `content/index.md`）：

````markdown
# languages —— 开发语言部分

Mosaic 的第 ① 部分。三条**并列**主线，对应「学 → 析 → 合」：

| 目录 | 主线 | 内容 |
|---|---|---|
| `studies/` | 学 | 6 门主流语言 × 126 个阶段的系统化学习路线 |
| `analysis/` | 析 | 语言设计解剖：C / C++ / Java / Python / Rust 的机制对比 |
| `tenet/` | 合 | Tenet 语言设计与 3 个编译器实现（cpp / rs / arm64） |

## studies —— 六门语言的学习路线

| 语言 | 路线文档 | 阶段数 |
|---|---|---|
| C | [`studies/c/c.md`](studies/c/c.md) | 16 |
| C++ | [`studies/cpp/cpp.md`](studies/cpp/cpp.md) | 23 |
| Go | [`studies/go/go.md`](studies/go/go.md) | 21 |
| Java | [`studies/java/java.md`](studies/java/java.md) | 23 |
| Python | [`studies/py/python.md`](studies/py/python.md) | 18 |
| Rust | [`studies/rs/rust.md`](studies/rs/rust.md) | 25 |
| **合计** | | **126** |

每个阶段目录（`studies/<语言>/ph<NN>-<slug>/`）固定四层交付物：

```
ph<NN>-<slug>/
├── <NN>-<slug>.md    知识文档
├── examples/         示例代码
├── exercises/        代码练习
└── project/          综合项目
```

## 文档站

本域的 VitePress 站点在 [`website/`](website/)，内容真源就是 `studies/`、`analysis/`、`tenet/` 三个目录。

```bash
cd languages/website && npm run build
```

## 校验

```bash
python3 .dsh/skills/tenetlang-notes/scripts/validate.py --links
```

## 写作规范

`languages/studies/` 下所有文档受 `.dsh/skills/tenetlang-notes/` 管辖；`analysis/` 与 `tenet/` 不在其列。
````

```bash
cd /Users/ninebot/code/mosslau/Mosaic
test -f languages/README.md && wc -l < languages/README.md
```

Expected: 打印行数（约 55）。

- [ ] **Step 10: 修 `tenetlang-notes/SKILL.md` 的管辖路径（10 行，只改路径不改仓名）**

规则：把指代**管辖目录**的 `languages/` 改为 `languages/studies/`；已经写成 `languages/analysis/`、`languages/tenet/` 的（若有）不要再叠加。**不改** `TenetLang` 仓名（spec D10）。

需要改的 10 行（行号基于改动前）：`3`、`11`、`13`、`15`、`25`、`147`、`172`、`182`、`281`、`335`。

```bash
cd /Users/ninebot/code/mosslau/Mosaic
f=.dsh/skills/tenetlang-notes/SKILL.md
python3 - "$f" <<'PY'
import re,sys,pathlib
p=pathlib.Path(sys.argv[1]); lines=p.read_text(encoding='utf-8').splitlines(True)
# 只替换「管辖目录」义：languages/ 后面不跟 analysis/ 或 tenet/，且不已经是 languages/studies/
pat=re.compile(r'languages/(?!studies/|analysis/|tenet/)')
n=0
for i,l in enumerate(lines):
    if pat.search(l):
        lines[i]=pat.sub('languages/studies/', l); n+=1
p.write_text(''.join(lines),encoding='utf-8'); print(f"改动 {n} 行")
PY
grep -c 'languages/studies/' "$f"
grep -n 'languages/' "$f" | grep -v 'languages/studies/' | head
```

Expected: `改动 10 行`（已逐字预跑确认：10 行被改，改后「含 `languages/` 但不含 `languages/studies/`」的行数为 **0**）；最后一条 grep **无输出**。若最后一条 grep 有输出，说明正则漏了某种形态，**逐行核对后再继续**。

- [ ] **Step 11: 站点构建验证**

```bash
cd /Users/ninebot/code/mosslau/Mosaic/languages/website
npm install --cache /tmp/npm-cache-mosaic --no-audit --no-fund
npm run build
ls docs/index.md docs/studies 2>/dev/null | head
```

Expected: 构建成功（`✓ building client + server bundles`、`build complete`）；**同步输出中 0 条「失效链接」**
（这是 Step 3 那 4 条 `analysis → studies` 链接的**唯一**把关点，见 Step 3 的说明）。

产物归属（**不要搞错**）：
- `docs/index.md` ← **手写的 `content/index.md`**（站点首页），**不是** `languages/README.md`；
- `docs/about.md` ← `languages/README.md`（域导航页落成站点的「总览/about」页，`sync-docs.mjs:475–477` 的 `rootReadme`）；
- `docs/studies/index.md` ← Step 7b 改名的 `content/studies/index.md`（六门语言总览页）；
- `docs/studies/<lang>/index.md` ← 生成的语言卡片页；**`docs/languages` 必须不存在**。

- [ ] **Step 12: 提交**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
git add -A
git commit -m "refactor(languages): 语言域重排为 languages/{studies,analysis,tenet,website}

- TenetLang/{languages,analysis,tenet,website} → languages/ 同名四目录
- 站点归入语言域：sync-docs.mjs 的 REPO_DIR 收缩为语言域根，
  FAMILIES 变 ['studies','analysis','tenet']，净改动 7 处
- analysis→studies 链接 4 条；.gitignore 10 行前缀；validate.py 管辖根
- 新增 languages/README.md（同时作为站点首页源）"
```

---

## Task 4: 算法域与路线图（`algorithms/` + 顶层 `roadmap/`）

**Files:**
- Move: `_import/MindSpring/algorithms` → `algorithms`；`_import/MindSpring/roadmap` → `roadmap`；`_import/OceanVerse/roadmap/智能大数据平台工程师.md` → `roadmap/`
- Create: `roadmap/README.md`

**Interfaces:**
- Consumes: Task 1 的 `_import/`
- Produces: `algorithms/README.md`（`mindspring-lab/validate.py` 的 `ALGO_INDEX`）、`roadmap/人工智能代表算法演进路线.md`（23 个实验 README 的章节锚点 + `ALGO_ROADMAP`）——两者路径与 MindSpring 中完全一致，故校验器零改动

- [ ] **Step 1: 搬迁（算法域与 `roadmap/` 保持深度 1，链接零改动）**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
git mv _import/MindSpring/algorithms algorithms
git mv _import/MindSpring/roadmap roadmap
git mv "_import/OceanVerse/roadmap/智能大数据平台工程师.md" roadmap/
ls algorithms roadmap
```

Expected: `algorithms` 下有 `01-search … 05-generative README.md`；`roadmap` 下有 4 个文件。

- [ ] **Step 2: 验证搬迁完整性**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
# ⚠ 右侧会**多出** Step 1 从 OceanVerse 上移的那一份路线文档，所以左侧必须显式补上它，
#   否则 diff 会因恰好 1 行而失败，看起来像"搬迁有遗漏"。
diff <(cat <(git -C ../MindSpring -c core.quotepath=false ls-files algorithms roadmap) \
          <(echo 'roadmap/智能大数据平台工程师.md') | sort) \
     <(git -c core.quotepath=false ls-files algorithms roadmap | sort) \
  && echo "OK 算法域与路线图搬迁完整（MS 原样 + 1 份上移的 OceanVerse 路线文档）"
echo "--- 两侧行数（都应 97）---"
echo "左侧 $(cat <(git -C ../MindSpring ls-files algorithms roadmap) <(echo 'roadmap/智能大数据平台工程师.md') | wc -l | tr -d ' ') / 右侧 $(git ls-files algorithms roadmap | wc -l | tr -d ' ')"
echo "--- 被引用的路线文档确实在位 ---"
test -f roadmap/人工智能代表算法演进路线.md && test -f roadmap/大模型数据中心平台工程师.md \
  && echo "OK 两份被锚定的路线文档在位"
```

Expected: `OK 算法域与路线图搬迁完整（MS 原样 + 1 份上移的 OceanVerse 路线文档）`、`左侧 97 / 右侧 97`、`OK 两份被锚定的路线文档在位`。

- [ ] **Step 3: 跑校验器确认算法线绿，并记录工程线此刻是空转的**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
python3 .dsh/skills/mindspring-lab/scripts/validate.py; echo "exit=$?"
python3 -c "
import pathlib
root=pathlib.Path('.')
print('ENG_INDEX 存在:', (root/'engineering'/'README.md').is_file())
print('工程目录匹配数:', len([p for p in root.glob('engineering/[0-9][0-9]-*') if p.is_dir()]))
"
```

Expected: `exit=0`（算法线与路线图锚点全绿），且打印 `ENG_INDEX 存在: False`、`工程目录匹配数: 0`。

> ⚠ **不要把这个绿色当作工程线已被覆盖**：`validate.py` 的 `read_text()` 对缺失文件返回空串，
> 而 `ROOT.glob("engineering/[0-9][0-9]-*")` 此刻匹配 0 个目录，于是整个 `# --- engineering 线 ---`
> 段落**静默跳过**。这正是 Step 5 要把它接回来的原因，也是 Task 5 Step 9b 必须用负向对照证明
> 检查是「活的」的原因。若这里出现任何与 `algorithms/`、`roadmap/`、章节锚点相关的报错，
> 说明 Task 4 有问题，**停下排查**。

- [ ] **Step 4: 写 `roadmap/README.md`**

Create `roadmap/README.md`：

```markdown
# roadmap —— 路线图

本仓库所有「路线」类文档的统一入口。

| 文档 | 面向 | 用途 |
|---|---|---|
| [人工智能代表算法演进路线.md](人工智能代表算法演进路线.md) | 算法部分 | 五个学科族的演进脉络；`algorithms/` 下 23 个实验 README 的章节锚点（`> 对应文档章节：第 X.Y.Z 章`）都指向本文件 |
| [大模型数据中心平台工程师.md](大模型数据中心平台工程师.md) | 工程部分 · AI 平台 | 七个阶段的职业与项目路线；`engineering/ai-platform/` 下 7 个项目的阶段锚点来源 |
| [智能大数据平台工程师.md](智能大数据平台工程师.md) | 工程部分 · 数据平台 | 大数据平台工程师成长路径 |
| [../languages/README.md](../languages/README.md) | 语言部分 | 6 门语言 × 126 阶段的学习路线总表 |

> `人工智能代表算法演进路线.md` 的**路径不可变更**：23 个算法实验 README 的章节锚点与
> `.dsh/skills/mindspring-lab/scripts/validate.py` 的 `parse_roadmap_chapters()` 都按
> `roadmap/人工智能代表算法演进路线.md` 定位。移动它需同步改 23 个锚点。
```

- [ ] **Step 5: 独立验证章节锚点全部可解析**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
python3 - <<'PY'
import re,pathlib
root=pathlib.Path('.')
rm=root/'roadmap'/'人工智能代表算法演进路线.md'
chapters={m.group(1) for m in re.finditer(r'^#+\s*([0-9]+(?:\.[0-9]+)*)', rm.read_text(encoding='utf-8'), re.M)}
units=sorted(p for p in root.glob('algorithms/[0-9][0-9]-*/*') if p.is_dir())
bad=[]
for u in units:
    f=u/'README.md'
    if not f.exists(): continue
    m=re.search(r'对应文档章节：`roadmap/人工智能代表算法演进路线\.md`\s*第\s*([0-9.]+)\s*章', f.read_text(encoding='utf-8'))
    if not m: bad.append((str(u),'无锚点')); continue
    if m.group(1) not in chapters: bad.append((str(u),f"章节 {m.group(1)} 不存在"))
print(f"算法实验 {len(units)} 个；章节标题 {len(chapters)} 个")
print("全部锚点可解析" if not bad else f"FAIL {bad}")
PY
```

Expected: `算法实验 23 个；…` + `全部锚点可解析`。

- [ ] **Step 6: 提交**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
git add -A
git commit -m "refactor(algorithms,roadmap): 算法域与路线图就位

- MindSpring/{algorithms,roadmap} → algorithms/ + roadmap/（深度不变，链接零改动）
- OceanVerse 的 智能大数据平台工程师.md 上移 roadmap/（出链 0、入链 0）
- 新增 roadmap/README.md 作为全仓路线索引
- 23 个实验的章节锚点全部可解析"
```

---

## Task 5: 工程域 · ai-platform（`engineering/ai-platform/`）

**Files:**
- Move: `_import/MindSpring/engineering` → `engineering/ai-platform`
- Modify: 27 处工程→算法路径、2 处工程索引→路线文档路径、`.dsh/skills/mindspring-lab/scripts/validate.py`（3 处）、`.dsh/skills/mindspring-lab/SKILL.md`（管辖路径）、`engineering/ai-platform/README.md` + `engineering/ai-platform/07-ai-platform/README.md`（边界文案）
- Create: `engineering/README.md`

**Interfaces:**
- Consumes: Task 4 的 `algorithms/` 与 `roadmap/`
- Produces: `engineering/README.md`（`mindspring-lab/validate.py` 将来的域总览入口不需要它——`ENG_INDEX` 指向 `engineering/ai-platform/README.md`）；`validate.py` 转绿

- [ ] **Step 1: 搬迁**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
mkdir -p engineering
git mv _import/MindSpring/engineering engineering/ai-platform
ls engineering/ai-platform
```

Expected: `01-text-corpus-pipeline … 07-ai-platform` 七个目录 + `README.md`。

- [ ] **Step 2: 验证搬迁完整性**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
diff <(git -C ../MindSpring -c core.quotepath=false ls-files engineering | sed 's|^engineering/|engineering/ai-platform/|' | sort) \
     <(git -c core.quotepath=false ls-files engineering/ai-platform | sort) \
  && echo "OK ai-platform 搬迁无遗漏、无多余"
```

Expected: 只有 `OK …`。

- [ ] **Step 3: 修 29 处跨目录路径（27 处 `../../algorithms/` + 2 处 `../roadmap/`）**

⚠ **必须按「路径模式」全局替换，不能只替换 `](…)` 链接形态**：实测 27 处里有 **3 处是内联代码里的路径**
（`07-ai-platform/README.md` 第 68、69 行与 `06-agent-nest/README.md` 第 53、54、55 行各含 2 处，
即同一行内联代码 + 链接各一份）。只匹配链接形态会静默漏掉它们。同理 `engineering/README.md` 第 3 行
的 `../roadmap/大模型数据中心平台工程师.md` 内联代码与链接各出现一次（共 2 处）。

```bash
cd /Users/ninebot/code/mosslau/Mosaic
# 27 处：7 个项目的「复用的算法实验」段，工程域下沉一级
sed -i '' 's|\.\./\.\./algorithms/|../../../algorithms/|g' engineering/ai-platform/0*/README.md
# 2 处：ai-platform 索引 → 路线文档（同行内联代码 + 链接）
sed -i '' 's|\.\./roadmap/大模型数据中心平台工程师\.md|../../roadmap/大模型数据中心平台工程师.md|g' \
  engineering/ai-platform/README.md

# ⚠ 残留检查必须用锚点，不能直接 grep '../..\/algorithms/'：
#   '../../../algorithms/' **包含** '../../algorithms/' 作为子串，
#   朴素 grep 会把新形态也算成残留，断言永远不可能通过。
#   下面用 ERE 要求匹配前一个字符不是 '.' 或 '/'（macOS grep 无 -P，故不用前瞻）。
OLD_A='(^|[^./])\.\./\.\./algorithms/'
OLD_R='(^|[^./])\.\./roadmap/大模型数据中心平台工程师\.md'
echo "--- 验证：旧深度必须清零，新深度必须到位 ---"
printf "残留 ../../algorithms/ : %s 处（期望 0）\n"  "$(grep -rEo "$OLD_A" engineering/ai-platform | wc -l | tr -d ' ')"
printf "新 ../../../algorithms/ : %s 处（期望 27）\n" "$(grep -rFo '../../../algorithms/' engineering/ai-platform | wc -l | tr -d ' ')"
printf "残留 ../roadmap/大模型… : %s 处（期望 0）\n"  "$(grep -rEo "$OLD_R" engineering/ai-platform | wc -l | tr -d ' ')"
printf "新 ../../roadmap/大模型… : %s 处（期望 2）\n"  "$(grep -rFo '../../roadmap/大模型数据中心平台工程师.md' engineering/ai-platform | wc -l | tr -d ' ')"

echo "--- 负向对照：故意制造一处旧形态，锚点必须抓到 ---"
cp engineering/ai-platform/04-gpu-scheduler-demo/README.md /tmp/nc-readme.bak
sed -i '' 's|](../../../algorithms/01-search/a-star/)|](../../algorithms/01-search/a-star/)|' \
  engineering/ai-platform/04-gpu-scheduler-demo/README.md
nc=$(grep -rEo "$OLD_A" engineering/ai-platform | wc -l | tr -d ' ')
cp /tmp/nc-readme.bak engineering/ai-platform/04-gpu-scheduler-demo/README.md
echo "扰动后残留计数=$nc （必须 ≥1，否则说明锚点无效、前面的 0 不可信）"
```

Expected: `0` / `27` / `0` / `2`，随后 `扰动后残留计数=1`。若锚点的负向对照得到 0，说明正则没抓到——**先修断言再继续**，不要接受一个恒真的门禁。

- [ ] **Step 4: 用链接解析器证明 ai-platform 树内没有断链**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
python3 - <<'PY'
import re,pathlib
root=pathlib.Path('.').resolve(); b=root/'engineering'/'ai-platform'
pat=re.compile(r'\]\(([^)]+)\)'); res=[]; miss=[]
for f in b.rglob('*.md'):
    for m in pat.finditer(f.read_text(encoding='utf-8',errors='ignore')):
        t=m.group(1).split('#')[0].strip()
        if not t or t.startswith(('http','mailto:')) or not t.startswith('.'): continue
        tgt=(f.parent/t).resolve(); res.append((str(f.relative_to(root)),t))
        if not tgt.exists(): miss.append((str(f.relative_to(root)),t))
print(f"ai-platform 内相对链接 {len(res)} 条；解析不到的 {len(miss)} 条")
for f,t in miss: print(f"   MISSING {f} -> {t}")
PY
```

Expected: `ai-platform 内相对链接 212 条；解析不到的 2 条`，且这 2 条**恰好**是：

```
06-agent-nest/agent-core/docs/实施计划方案.md -> ../frameworks/README.md
06-agent-nest/agent-core/docs/技术架构方案.md -> ../frameworks/README.md
```

⚠ 这**不是**本次迁移引入的：`frameworks/` 是 `agent-core` 的**兄弟**目录，正确写法应为
`../../frameworks/`，源仓 `a0d1d7d` 起就是这样，且没有任何校验器覆盖它（`mindspring-lab/validate.py`
无链接检查）。本次**不修**（属内容改写，超出迁移范围）。因此本步的判据是**「不新增坏链」**：
条数必须等于基线 **2**、集合必须与上面两条完全一致。**若出现第 3 条**，说明 Step 3 的路径
替换制造了新的断链，必须停下排查。

- [ ] **Step 5: 修 `mindspring-lab/validate.py` 的工程域定位（7 处 = 2 处定位 + 5 处文案）**

**定位**（决定检查是否作用在正确的目录上）：

| 行 | 原文 | 改为 |
|---|---|---|
| 32 | `ENG_INDEX = ROOT / "engineering" / "README.md"` | `ENG_INDEX = ROOT / "engineering" / "ai-platform" / "README.md"` |
| 411 | `ROOT.glob("engineering/[0-9][0-9]-*")` | `ROOT.glob("engineering/ai-platform/[0-9][0-9]-*")` |

**文案**：同文件里 `engineering/README.md` 这个**字面串**共出现 **5 次**（140 行 docstring、151/156 行 warn、
414/417 行 err），全部要跟着改成 `engineering/ai-platform/README.md`。⚠ 只改 414 会漏掉 417 —— 而 417 正是
**负向对照**会触发的那条消息（实测报错为 `❌ engineering/README.md 项目总览登记了 01-text-corpus-pipeline，但磁盘目录不存在`），
留着会让排查者按图索骥去找一个已不存在的文件。

（`algorithms` 相关的 393–400 行不动；`ROOT = parents[4]` 仍然正确，因为 `.dsh/skills/mindspring-lab/` 的深度没变。）

```bash
cd /Users/ninebot/code/mosslau/Mosaic
f=.dsh/skills/mindspring-lab/scripts/validate.py
python3 - "$f" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text(encoding='utf-8')

# ① 两处定位
for a, b in [('ENG_INDEX = ROOT / "engineering" / "README.md"',
              'ENG_INDEX = ROOT / "engineering" / "ai-platform" / "README.md"'),
             ('ROOT.glob("engineering/[0-9][0-9]-*")',
              'ROOT.glob("engineering/ai-platform/[0-9][0-9]-*")')]:
    assert t.count(a) == 1, f"定位项命中 {t.count(a)} 次: {a}"
    t = t.replace(a, b)

# ② 五处文案（字面串，含 docstring 与两条 err 消息）
lit = 'engineering/README.md'
n = t.count(lit)
assert n == 5, f"字面串 {lit} 命中 {n} 次（期望 5）"
t = t.replace(lit, 'engineering/ai-platform/README.md')

p.write_text(t, encoding='utf-8'); print("validate.py 7 处已改（2 定位 + 5 文案）")
PY
python3 -c "import ast,pathlib;ast.parse(pathlib.Path('$f').read_text());print('语法 OK')"
grep -c 'engineering/README\.md' "$f"    # 期望 0
```

Expected: `validate.py 3 处已改` + `语法 OK`。

- [ ] **Step 6: 修 `mindspring-lab/SKILL.md` 的管辖路径**

规则：把指代**管辖目录** `engineering/` 改为 `engineering/ai-platform/`；`algorithms/`（深度不变）与 `roadmap/` 一律不动；不改仓名（spec D10）。

需要核对的行（改动前行号）：`3`、`11`、`13`、`33`、`75`。

```bash
cd /Users/ninebot/code/mosslau/Mosaic
f=.dsh/skills/mindspring-lab/SKILL.md
python3 - "$f" <<'PY'
import re,sys,pathlib
p=pathlib.Path(sys.argv[1]); lines=p.read_text(encoding='utf-8').splitlines(True)
pat=re.compile(r'engineering/(?!ai-platform/)')
n=0
for i,l in enumerate(lines):
    if pat.search(l):
        lines[i]=pat.sub('engineering/ai-platform/', l); n+=1
p.write_text(''.join(lines),encoding='utf-8'); print(f"改动 {n} 行")
PY
grep -n 'engineering/' "$f" | grep -v 'engineering/ai-platform/' | head
```

Expected: `改动 5 行`（已逐字预跑确认：5 行被改，改后「含 `engineering/` 但不含 `engineering/ai-platform/`」的行数为 **0**）；最后一条 grep **无输出**。

- [ ] **Step 7: 改写「分工/边界」段落为新域词汇**

⚠ 计数更正（实测）：参与改写的只有 **3 个文件 5 行**——`engineering/ai-platform/README.md` 第 45、47 行，
`engineering/ai-platform/07-ai-platform/README.md` 第 89 行（**该行有 3 处 `TenetLang`，全部要改**），
`engineering/README.md` 第 26、28 行。第 4 个文件 `_import/MindSpring/README.md` **不单独改**——它的正文
（含分工段落与依赖关系表）已在 Step 8 并入新建的 `engineering/README.md`，旧文件随 Task 7 的 `_import/` 一起消失。
计划原写「4 文件 6 行」是**汇总数算错**（5 行 + 2 行未触碰 = 7，不是 6），各文件的具体改动本身是对的。

把「与 TenetLang 的分工/边界」改写成「语言域（`languages/`）与 AI 平台工程域（`engineering/ai-platform/`）的分工/边界」，其中 `../TenetLang/` 这条路径链接改为 `../../languages/`。原文如下，逐处替换：

**`engineering/ai-platform/README.md`**（原 `MindSpring/engineering/README.md` 第 45、47 行）：

```markdown
## 与 languages/ 的边界

languages/ 承载**语言与工程纪律的语义层**（AI 平台控制面的任务/配额/模型/发布语义、湖仓与编排的口径语义，已实跑验证），本项目做**真实系统与真实指标**（真调度、真推理、真压测、真成本）。同一个概念（例如"GPU 资源账本的不变量"或"幂等回填的下游闭包"）在两处的分工是：**languages/ 讲清"应该怎么做、为什么"，engineering/ai-platform/ 交付"跑起来的系统与实测数字"**——写项目定义时先查 languages/ 是否已覆盖语义，避免重复造文档。
```

**`engineering/ai-platform/07-ai-platform/README.md` 第 89 行**：把 `**与 TenetLang 的边界（2026-09 明确）**：TenetLang 承载…` 中的**三处** `TenetLang` 全部改为 `languages/`。
（实测该行恰好有 3 处，全部在 89 行；计划原写「两处」是漏数，且与本节自己的门禁「engineering/ai-platform 下 `TenetLang` 命中数应为 0」自相矛盾——以门禁为准。）

**原 `MindSpring/README.md` 第 24、26 行**：该文件的正文内容（含分工段落与依赖关系表）将在 Step 8 合并进新建的 `engineering/README.md`，因此这里无需单独改；其 `[TenetLang](../TenetLang/)` 链接在 Step 8 的 `engineering/README.md` 中写为 `[languages/](../../languages/)`。

```bash
cd /Users/ninebot/code/mosslau/Mosaic
grep -rn 'TenetLang' engineering/ai-platform | cut -c1-120
```

Expected: 只应剩 Step 8 将处理的位置之外无残留；`engineering/ai-platform/` 下 `TenetLang` 命中数应为 **0**。

- [ ] **Step 8: 写 `engineering/README.md`（吸收原 MindSpring README 的分工与依赖表）**

Create `engineering/README.md`：

````markdown
# engineering —— 工程系统部分

Mosaic 的第 ③ 部分。两个**并列**域：把「AI 平台」与「数据平台」做成真实可运行的系统，与 `algorithms/`（学原理）不同，这里交付**跑起来的系统与实测数字**。

| 域 | 目录 | 内容 | 规模 |
|---|---|---|---|
| AI 平台 | `ai-platform/` | 语料流水线、RAG 知识库、湖仓+向量、GPU 调度、推理服务、Agent 平台、端到端整合 | 7 个项目 |
| 数据平台 | `data-platform/` | Go 接入网关与编解码、Kafka/Flink SQL 流处理、ClickHouse 服务层、Compose 部署与门禁 | 1 套系统 |

## ai-platform 的依赖关系与开工顺序

每个项目的**项目定义**（各自 README 的六段）已给出「复用的算法实验」；开工顺序建议：**先纵切两端（01 数据入口 + 05 推理出口）**，再补中间（03 存储版本、02 检索），最后做受硬件约束的 04 与集成层 07。

| 阶段 | 项目 | 前置算法实验（`algorithms/`） | 前置项目 | 受什么约束 |
|---|---|---|---|---|
| 一 | 01-text-corpus-pipeline | `05-generative/mini-rag`（向量化口径）、`02-statistical-ml/kmeans`、`02-statistical-ml/pca`；**去重算法需新增手写实验** | — | 数据规模（10GB 需流式/Spark） |
| 二 | 02-rag-knowledge-base | `05-generative/mini-rag`（内核）、`04-transformer/attention`（Rerank 原理）、`kmeans`、`pca` | 01（语料与向量） | 向量库与 LLM 外部依赖 |
| 三 | 03-lakehouse-vector | `mini-rag`（索引口径）、`kmeans`（布局/聚簇）、`pca`（压缩分析） | 01 | 表格式与对象存储 |
| 四 | 04-gpu-scheduler-demo | 无直接复用（基础设施编排）；`01-search/a-star` 的"可解释评估"思想可类比 | — | **真实 GPU + K8s（最大约束）** |
| 五 | 05-inference-server | `04-transformer/mini-gpt`、`mini-transformer`、`attention`（prefill/decode 与 KV Cache） | 04（算力与部署）可选 | GPU / 量化工具链 |
| 六 | 06-agent-nest | 自身在 Part 1 沉淀，编码期再回访相关实验 | 02/05（作为工具与模型来源） | 沙箱与运行时依赖 |
| 七 | 07-ai-platform | 集成层：复用前六个项目，不直接依赖单个算法实验 | 一~六全部 | 单机资源（Compose 起步） |

> 交叉约束：**04 是唯一受硬件门槛限制的项目**（无 GPU 时只能做逻辑层验证，其 README 已把验收拆成"逻辑层/真实层"两层）；**07 可增量推进**（骨架先行，每完成一个阶段接入一个组件），因此不必等前面全部完成。

## 与 languages/ 的分工

[`languages/`](../languages/) 承载**语言学习与工程纪律的语义层**（如 AI 平台控制面的任务/配额/模型/发布语义、湖仓与编排的口径语义，已实跑验证）；本域承载**真实系统的实现与真实指标**（真调度、真推理、真压测、真成本）。**languages/ 讲"应该怎么做、为什么"，engineering/ 交付"跑起来的系统与实测数字"——两者不重复。**

## 校验

```bash
python3 .dsh/skills/mindspring-lab/scripts/validate.py
cd ../engineering/data-platform && bash scripts/check-docs.sh
```
````

- [ ] **Step 9: 跑工程域校验（应转绿）**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
python3 .dsh/skills/mindspring-lab/scripts/validate.py; echo "exit=$?"
```

Expected: `exit=0`，无 `✗`。若报「目录存在但未在 … 项目总览登记」，检查 Step 5 的 `ENG_INDEX` 是否指向 `engineering/ai-platform/README.md`。

- [ ] **Step 9b: 证明工程线是「活的」而非空转（负向对照）**

Task 4 Step 3 已确认：路径改错时校验器会**静默变绿**。所以绿色本身不足以证明有覆盖，必须施加扰动看它变红：

```bash
cd /Users/ninebot/code/mosslau/Mosaic
python3 -c "
import pathlib
root=pathlib.Path('.')
eng=root/'engineering'/'ai-platform'
print('ENG_INDEX 存在:', (eng/'README.md').is_file())
print('工程目录匹配数:', len([p for p in root.glob('engineering/ai-platform/[0-9][0-9]-*') if p.is_dir()]))
"
# 期望：ENG_INDEX 存在: True / 工程目录匹配数: 7

echo "--- 负向对照：把一个项目移出匹配范围，校验器必须变红 ---"
mv engineering/ai-platform/01-text-corpus-pipeline /tmp/nc-01-text-corpus-pipeline
python3 .dsh/skills/mindspring-lab/scripts/validate.py > /tmp/nc-out.txt 2>&1; nc=$?
mv /tmp/nc-01-text-corpus-pipeline engineering/ai-platform/01-text-corpus-pipeline
echo "扰动后 exit=$nc （必须非 0）"
grep -i '01-text-corpus-pipeline' /tmp/nc-out.txt || echo "（未命中项目名，需人工看 /tmp/nc-out.txt）"
```

Expected: `ENG_INDEX 存在: True`、`工程目录匹配数: 7`、扰动后 `exit` **非 0**，且输出中出现 `01-text-corpus-pipeline`（方向为「总览登记了但磁盘目录不存在」）。

若扰动后 `exit` 仍为 0，说明工程线检查是空转的，**必须先修好再继续**——否则后面所有绿色都不可信。

- [ ] **Step 10: 跑 pytest 与 ruff**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
python3 -m pytest -q 2>&1 | tail -8
# ruff 是既存红、只做差分（见 Global Constraints）：不得新增，不要求变绿
python3 -m ruff check .dsh/skills/mindspring-lab/scripts/validate.py 2>&1 | tail -2
python3 -m ruff check algorithms engineering/ai-platform 2>&1 | tail -2
```

Expected: pytest 全绿（`48 passed`；`testpaths = ["algorithms", "engineering/ai-platform"]` 生效）。
- `validate.py` 的 ruff 计数须**与源仓持平 = 2 处 E501**：Step 5 把 `engineering/README.md` 换成更长的
  `engineering/ai-platform/README.md` 会让 156/414 两行越过 100 列（2 → 4），故必须把这两行 f-string **折行**
  （隐式拼接，内容不变），折行后回到 2。
- `algorithms + engineering/ai-platform` 的总数须与源仓同类计数持平（实测 40 + 294 = **334**，源仓同样 334）。

⚠ 若 pytest 报了 `engineering/ai-platform` 之外的路径缺失，说明 Task 2 Step 6 的 `testpaths` 写错。

- [ ] **Step 11: 提交**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
git add -A
git commit -m "refactor(engineering): AI 平台域归位 engineering/ai-platform/

- MindSpring/engineering → engineering/ai-platform（7 个项目 + 索引）
- 29 处跨目录路径修正（27 处复用的算法实验 + 2 处路线文档，含 4 处内联代码形态）
- mindspring-lab 校验器 7 处（2 处定位 + 5 处陈旧文案）+ SKILL 管辖路径
- 『分工/边界』段落改写为新域词汇（3 文件 5 行）+ 治理契约与索引文案随域根对齐（6 处）
- 新增 engineering/README.md：两域分工 + 依赖关系与开工顺序
- validate.py exit 0 / pytest 48 passed；ruff 为**既存红**（源仓 a0d1d7d 即 420 处 + 45 文件需重排，
  且本仓契约里 validate.py 并不运行 ruff），本任务只保证不新增：validate.py 的 E501 与源仓持平在 2 处"
```

---

## Task 6: 工程域 · data-platform（`engineering/data-platform/`）

**Files:**
- Move: `_import/OceanVerse/{contracts,deploy,ingest,lakehouse,scripts,roadmap}` → `engineering/data-platform/`；`README.md`、`.gitignore` 同上；`.github/` → 顶层
- Modify: `.github/workflows/ci.yml`（22 处）

**Interfaces:**
- Consumes: Task 1 的 `_import/OceanVerse/`
- Produces: `engineering/data-platform/` 域；`.github/workflows/ci.yml` 在仓库根（GitHub Actions 只从默认分支根读取）

- [ ] **Step 1: 搬迁（整仓平移，域内相对路径不变）**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
mkdir -p engineering/data-platform
for d in contracts deploy ingest lakehouse scripts roadmap; do
  git mv "_import/OceanVerse/$d" "engineering/data-platform/$d"
done
git mv _import/OceanVerse/README.md   engineering/data-platform/README.md
git mv _import/OceanVerse/.gitignore  engineering/data-platform/.gitignore
git mv _import/OceanVerse/.github     .github
ls -A engineering/data-platform
```

Expected: `README.md  .gitignore  contracts  deploy  ingest  lakehouse  roadmap  scripts`。

- [ ] **Step 2: 验证搬迁完整性（排除已处置的 4 类文件）**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
# ⚠ 排除模式必须**分段锚定**。写成 '^(A|B|\.dsh/|C)$' 时，$ 作用于整个 alternation，
#   于是 '^\.dsh/…$' 要求整行恰好等于 '.dsh/' —— 没有真实路径满足，41 个 .dsh/ 文件
#   会被漏排除，右侧（已丢弃这些文件）不含它们 → 本检查会**误报「搬迁有遗漏」**。
EXCL='^(LICENSE|\.mcp\.json)$|^\.dsh/|^roadmap/智能大数据平台工程师\.md$'
left=$(git -C ../OceanVerse -c core.quotepath=false ls-files | grep -v -E "$EXCL" | sort)
right=$(git -c core.quotepath=false ls-files engineering/data-platform .github \
        | sed -e 's|^engineering/data-platform/||' -e 's|^\.github/|.github/|' | sort)
echo "左侧 $(echo "$left" | wc -l | tr -d ' ') 行 / 右侧 $(echo "$right" | wc -l | tr -d ' ') 行（两侧都应为 108）"
diff <(echo "$left") <(echo "$right") && echo "OK 数据平台域搬迁无遗漏、无多余"

# 负向对照：确认这个 diff 真能发现遗漏（删一行应报出差异）
diff <(echo "$left" | head -107) <(echo "$right") >/dev/null \
  && echo "⚠ 负向对照未生效：删掉一行后 diff 仍通过，说明检查无效" \
  || echo "OK 负向对照有效（删一行即被发现）"
```

Expected: `左侧 108 行 / 右侧 108 行`、`OK 数据平台域搬迁无遗漏、无多余`、`OK 负向对照有效`。
（`LICENSE`/`.mcp.json` 与顶层重复；`.dsh/` 全 41 个文件已并集到顶层；`智能大数据平台工程师.md` 已在 Task 4 上移到 `roadmap/`。152 − 44 = 108。）

- [ ] **Step 3: 验证 OceanVerse 的自定位脚本仍能找到自己的根**

```bash
cd /Users/ninebot/code/mosslau/Mosaic/engineering/data-platform
grep -n 'ROOT=' scripts/*.sh
bash scripts/check-docs.sh && echo "OK check-docs"
```

Expected: 每条脚本 `ROOT="$(cd "$(dirname "$0")/.." && pwd)"` 不变（`scripts/` 与 `deploy/` 的相对位置未变）；
`check-docs.sh` 通过。

⚠ **`check-mermaid.sh` 依赖 Docker daemon + `minlag/mermaid-cli` 镜像**（脚本头注释即写明；它用
`docker run … minlag/mermaid-cli` 逐张渲染，并把 docker 的报错 `>/dev/null 2>&1` 吞掉，所以失败时只显示
「❌ … 首行: flowchart LR」，看不到真正原因）。**必须先判别失败原因，再决定算不算通过**：

```bash
cd /Users/ninebot/code/mosslau/Mosaic/engineering/data-platform
if docker info >/dev/null 2>&1; then echo "docker daemon 可用 → check-mermaid 必须通过"; bash scripts/check-mermaid.sh; echo "exit=$?"; else
  echo "docker daemon 不可用 → check-mermaid 无法运行，按环境缺失记录"
  docker run --rm hello-world 2>&1 | head -2      # 复现真实原因（脚本把它吞掉了）
  echo "--- 负向核对：在**无污染探针**里跑源仓的同一脚本 ---"
  # ⚠ 两处坑（实施时踩到）：
  #   ① Step 1 之后 `_import/OceanVerse/scripts/` **已搬走**（该目录只剩 `.dsh/`、`.mcp.json`、`LICENSE`），
  #      那里已无脚本可跑（`exit 127`）；
  #   ② **绝不能对只读源仓 `../OceanVerse` 就地跑**：`check-mermaid.sh` 会写 `$ROOT/.tmp-mmdc/`
  #      （脚本里有 `rm -rf` + `mkdir -p`），那是对只读源仓的写操作。
  #   做法：把源仓的脚本与含 mermaid 的 .md **复制**进 `.superpowers/tmp/`（gitignore 区）再跑；脚本按自身
  #   位置定位 ROOT，故目录结构照搬，跑完即弃。
  probe=.superpowers/tmp/mmdc-probe
  rm -rf "$probe" && mkdir -p "$probe/scripts"
  cp ../OceanVerse/scripts/check-mermaid.sh "$probe/scripts/"
  ( cd ../OceanVerse && grep -rl '```mermaid' --include='*.md' . | grep -v '^./.dsh/' | sed 's|^\./||' ) \
    | while IFS= read -r rel; do mkdir -p "$probe/$(dirname "$rel")"; cp "../OceanVerse/$rel" "$probe/$rel"; done
  ( cd "$probe" && bash scripts/check-mermaid.sh >/dev/null 2>&1; echo "源仓内容副本同项 exit=$?" )
  shasum scripts/check-mermaid.sh ../OceanVerse/scripts/check-mermaid.sh | awk '{print $1}' | sort -u | wc -l   # 期望 1（两侧同一份脚本）
  rm -rf "$probe"
fi
```

- **daemon 不可用**：把 `check-mermaid.sh` 记为**未验证（环境缺 docker daemon / minlag 镜像）**，并**必须**
  用上面的探针作对照——两侧若同样全失败（预期如此），则证明是**环境问题而非迁移回归**；表现不一致就说明
  是回归，**停下排查**。不要把这项写成「通过」。
- **daemon 可用而图仍失败**：那是真问题（图语法确实坏了或 `deploy/` 相对位置变了），必须停在原地查。

- [ ] **Step 4: 修 `.github/workflows/ci.yml` 的 22 处路径前缀**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
f=.github/workflows/ci.yml
python3 - "$f" <<'PY'
import sys,pathlib,re
p=pathlib.Path(sys.argv[1]); t=p.read_text(encoding='utf-8'); n=0
P='engineering/data-platform/'
# ① 4 处矩阵取值
for m in ['ingest/device-contracts','ingest/device-gateway','ingest/device-codec','ingest/device-simulator']:
    a=f'          - {m}\n'; b=f'          - {P}{m}\n'
    assert t.count(a)==1, f"矩阵值命中 {t.count(a)}: {m}"; t=t.replace(a,b); n+=1
# ② 8 处 working-directory: deploy
a='working-directory: deploy\n'; c=t.count(a); assert c==8, f"working-directory 命中 {c}"
t=t.replace(a, f'working-directory: {P}deploy\n'); n+=c
# ③ 5 处 docker build 路径（行首即 docker build，无 working-directory）
r3=[('-f ingest/device-gateway/Dockerfile -t oceanverse/device-gateway:ci .',
     f'-f {P}ingest/device-gateway/Dockerfile -t oceanverse/device-gateway:ci {P[:-1]}'),
    ('-f ingest/device-codec/Dockerfile -t oceanverse/device-codec:ci .',
     f'-f {P}ingest/device-codec/Dockerfile -t oceanverse/device-codec:ci {P[:-1]}'),
    ('-f deploy/flink/Dockerfile -t oceanverse/flink:ci deploy/flink',
     f'-f {P}deploy/flink/Dockerfile -t oceanverse/flink:ci {P}deploy/flink')]
for a,b in r3:
    cnt=t.count(a)
    if cnt==0: continue
    t=t.replace(a,b); n+=cnt
# ④ 5 处无 working-directory 的 run: bash scripts/…
for s in ['scripts/check-pipeline-health.sh','scripts/check-compose-budget.sh','scripts/test-compose-budget.sh','scripts/check-docs.sh','scripts/check-mermaid.sh']:
    a=f'run: bash {s}'; c=t.count(a); assert c==1, f"脚本调用命中 {c}: {s}"
    t=t.replace(a, f'run: bash {P}{s}'); n+=1
p.write_text(t,encoding='utf-8'); print(f"CI 共改 {n} 处（期望 22）")
PY
```

Expected: `CI 共改 22 处（期望 22）`。

- [ ] **Step 5: 验证 CI 无残留的域内相对路径**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
f=.github/workflows/ci.yml
echo "--- 不该再有无前缀的相对路径 ---"
grep -nE '^\s+working-directory: (deploy|ingest)|^\s+- ingest/|run: bash scripts/|-f ingest/|-f deploy/' "$f" || echo "OK 无残留"
echo "--- 该保留的（矩阵引用自动生效，无需改动） ---"
grep -c 'matrix.module' "$f"                    # 期望 8
grep -n '\.\./scripts/\|\.\./lakehouse/\|bash emqx/' "$f"   # 期望 **4 行**（旧稿把「模式种类」当成了「行数」）
python3 -c "import yaml,sys;d=yaml.safe_load(open('$f'));print('YAML OK, jobs=',list(d['jobs']))"
```

Expected: `OK 无残留`；`8`；**4 行**匹配 `../scripts/`、`../lakehouse/`、`bash emqx/`（实测：222 `emqx/gen-certs.sh`、
311 `../lakehouse/…init.sql`、316 `../scripts/init-minio-bucket.sh`、318 `../lakehouse/…submit-jobs.sh`；
在**未修改的源仓**上同样是这 4 行同一位置，故是工作流固有、非迁移引入——旧稿写「3 行」是把**模式种类**当成了**行数**）；
`YAML OK, jobs= ['go', 'docker', 'pipeline-health', 'compose', 'docs']`。
这 4 行的 `working-directory` 均为 `engineering/data-platform/deploy`，`../` 仍指向域根，**无需改动**。

- [ ] **Step 6: 验证 compose 能解析、预算门禁通过**

```bash
cd /Users/ninebot/code/mosslau/Mosaic/engineering/data-platform
bash scripts/check-compose-budget.sh
bash scripts/test-compose-budget.sh
cd deploy && cp -n .env.example .env 2>/dev/null; docker compose config -q && echo "OK compose config"
```

Expected: 预算门禁与负向自检通过（**实测两者 exit 0**）；`OK compose config`。

⚠ **`docker compose config -q` 是纯客户端解析，不需要 daemon**——在 daemon 未运行的机器上实测仍 `exit 0`。
所以这一项**必须通过**，不得以「本机无 docker」为由跳过。只有 `docker compose up` 这类真正拉起容器的命令
才需要 daemon，而本计划不跑它们（那是 CI 的 compose 作业负责的事）。若 `config -q` 失败，那是 compose 文件
或 `.env` 的真问题。

- [ ] **Step 7: 提交**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
git add -A
git commit -m "refactor(engineering): 数据平台域归位 engineering/data-platform/

- OceanVerse 整仓搬入（域内相对路径与脚本 ROOT 自定位全部继续成立，零改动）
- 智能大数据平台工程师.md 已在上一提交上移 roadmap/
- .github/ 提到仓库根；CI 22 处路径加域前缀
- LICENSE/.mcp.json/.dsh 为重复资产，随 _import 一并清理"
```

---

## Task 7: 顶层 README、清理暂存区、全量门禁、推送

**Files:**
- Create: `README.md`
- Delete: `_import/`（整个）
- Remote: 新建 `Mosslau/Mosaic` 并推送

**Interfaces:**
- Consumes: Task 2–6 的全部产物
- Produces: 可为外部引用的最终仓库

- [ ] **Step 1: 写顶层 `README.md`**

Create `README.md`：

````markdown
# Mosaic

**通用数据平台 + AI 平台数据中心。**

把三件事放进同一个仓库：**怎么造语言工具**、**怎么让机器变聪明**、**怎么把系统真正跑起来**。

本仓由三个独立仓库合并而成（TenetLang / MindSpring / OceanVerse），完整保留全部提交历史；三者在合并验收后归档。

## 三部分

| 部分 | 目录 | 内容 | 规模 |
|---|---|---|---|
| ① 开发语言部分 | [`languages/`](languages/) | 学（多语言阶段式学习路线）/ 析（语言设计解剖）/ 合（Tenet 语言与编译器） | 6 语言 × 126 阶段 |
| ② 算法部分 | [`algorithms/`](algorithms/) | 手写算法 vs 框架对照实验，五个学科族 | 23 个实验 |
| ③ 工程系统部分 | [`engineering/`](engineering/) | `ai-platform/`（AI 平台）+ `data-platform/`（数据平台） | 7 个项目 + 1 套系统 |

## 跨域支撑

| 路径 | 用途 |
|---|---|
| [`roadmap/`](roadmap/) | 路线图：算法演进路线 + 两条职业路线 + 语言学习路线 |
| [`books/`](books/) | 计算机书单 |
| [`docs/superpowers/`](docs/superpowers/) | 本仓的设计 spec 与实施计划 |
| [`.dsh/skills/`](.dsh/skills/) | 写作与验证规范（15 个 skill + `_desgin` 设计笔记） |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | CI（数据平台域） |

## 校验

```bash
# ① 语言域：章节契约 + 悬空链接 + 构建产物纪律
python3 .dsh/skills/tenetlang-notes/scripts/validate.py --links

# ② 算法域 + AI 平台域：索引/状态/章节锚定/模板结构/违禁 import，以及单元测试
python3 .dsh/skills/mindspring-lab/scripts/validate.py
python3 -m pytest -q

# ③ 数据平台域（check-mermaid.sh 需要 Docker daemon + minlag/mermaid-cli 镜像；
#    无 daemon 时该项无法运行，属环境缺失，不是仓库问题）
(cd engineering/data-platform \
  && bash scripts/check-docs.sh \
  && bash scripts/check-compose-budget.sh \
  && bash scripts/test-compose-budget.sh \
  && bash scripts/check-mermaid.sh)

# ④ 语言域文档站
(cd languages/website && npm run build)
```

> ⚠ 这段必须**可顺序执行**：`cd` 会改变后续命令的 cwd，故涉及子目录的一律用子 shell `( … )`。
> 旧稿在 `cd engineering/data-platform` 之后又写 `cd languages/website`，第二个 `cd` 会失败
> （实测 `bash: cd: languages/website: No such file or directory`）；且漏了 `test-compose-budget.sh`、
> 未提 `check-mermaid.sh` 的 Docker 前提。

## 边界

`languages/` 承载**语义与教学**（"应该怎么做、为什么"），`engineering/` 承载**真实系统与真实指标**（"跑起来是什么样"）。同一个概念在两处出现时，前者讲清纪律，后者交付可运行的实现与实测数字——不重复造文档。

## 为什么叫 Mosaic

三块各自独立的图块拼成一张完整图景：语言、算法、工程。每块可以单独看，合起来才是全貌。
````

- [ ] **Step 2: 全仓残留路径扫描**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
echo "--- 同类仓库外路径（交付内容必须为 0）---"
# ⚠ 排除三类**非交付物**，否则会误报（实测：不排除时命中 9 处）：
#   ① `./docs/superpowers/`（本迁移的 spec/plan，属交付物但其中引用了旧仓路径示例）
#   ② `./.superpowers/`（**SDD 进程目录**，gitignore 且不会发布；原稿只排除了 docs/superpowers，
#      漏了这一项，于是 ledger 里的 8 处命中被当成残留）
#   ③ `./_import/`（Step 3 会整体删除；其内的旧仓 README 本就含 `../TenetLang` 之类表述）
grep -rn '\.\./TenetLang/\|\.\./MindSpring/\|\.\./OceanVerse/' \
  --include='*.md' --include='*.py' --include='*.mjs' --include='*.yml' --include='*.sh' . \
  | grep -v -e '^\./docs/superpowers/' -e '^\./\.superpowers/' -e '^\./_import/' \
  || echo "OK 无仓外路径"
echo "--- 旧语言域路径（必须为 0）---"
grep -rnE "REPO_DIR,[[:space:]]*'languages'|root / \"languages\"$" --include='*.py' --include='*.mjs' . || echo "OK 无旧路径假设"
```

Expected: 两行 `OK …`。Step 3 删除 `_import/` 之后，再用**只看已跟踪内容**的方式复核一次：
`git grep -n '\.\./TenetLang/\|\.\./MindSpring/\|\.\./OceanVerse/' -- . ':(exclude)docs/superpowers'` 应无输出。

- [ ] **Step 3: 删除暂存区并验证无丢失**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
before=$(git ls-files | wc -l | tr -d ' ')
git rm -rq _import
# ⚠ `git rm` 只删**已跟踪**文件：`_import/` 下若留有未跟踪且被忽略的目录（如 ruff 的 `.ruff_cache/`），
#   目录本身会留在磁盘上，而 `git status` 依然是干净的（被忽略），`git ls-files` 也看不见它。
#   本仓库的验证曾对源仓跑过 ruff，故必须显式清掉：
rm -rf _import
test ! -e _import && echo "OK _import/ 已从磁盘彻底移除"
git status --porcelain --ignored=matching | grep -c '_import' || true   # 期望 0
git add -A
after=$(git ls-files | wc -l | tr -d ' ')
echo "删除前 $before → 删除后 $after"
git -c core.quotepath=false ls-files | cut -d/ -f1 | sort | uniq -c | sort -rn
```

Expected: 顶层只剩 `languages` `algorithms` `engineering` `roadmap` `books` `docs` `.dsh` `.github` 与根文件。
**逐个核对没有意外消失的域**（实测：`languages` **3907**、`engineering` **637** = 529 ai-platform + 107 data-platform + 1（`engineering/README.md` 域总览，不属任一子域）、
`algorithms` **93**；已跟踪文件总数 **4787 → 4702**，差额 −86 + 1（新 README）恰为 `_import/` 的已跟踪内容。
原稿写的「约 350 / 约 300」是早期粗估，与实测差一个量级，**以实测为准**）。

- [ ] **Step 4: 全量门禁（spec §9 的 7 项）**

```bash
cd /Users/ninebot/code/mosslau/Mosaic
set -e
echo "== ① 语言域 =="
python3 .dsh/skills/tenetlang-notes/scripts/validate.py --links
echo "== ② 算法 + AI 平台域 =="
python3 .dsh/skills/mindspring-lab/scripts/validate.py
python3 -m pytest -q 2>&1 | tail -3
# ruff：既存红，只记录不判定（见 Global Constraints）。
# ⚠ 计数**不会**因删 _import/ 而下降：本步作用域是 algorithms/engineering/languages/.dsh，
#   而被删的 .py 都在 `_import/*/.dsh/`（注意不是 `.dsh/`），不在作用域内 ⇒ 预期**持平 522**。
#   差分 0 的证法：在父提交上测同一命令做对照
#     git worktree add /tmp/pre-ruff <本任务之前的提交> && (cd /tmp/pre-ruff && python3 -m ruff check algorithms engineering languages .dsh | tail -1)
#     git worktree remove /tmp/pre-ruff
#   PRE == POST 即差分 0。源仓侧对照：MindSpring/algorithms 40、MindSpring/engineering 294，与迁移后一致。
python3 -m ruff check algorithms engineering languages .dsh 2>&1 | tail -2
echo "== ③ 数据平台域 =="
(cd engineering/data-platform && bash scripts/check-docs.sh && bash scripts/check-compose-budget.sh && bash scripts/test-compose-budget.sh)
# check-mermaid 依赖 Docker daemon + minlag/mermaid-cli 镜像（见 Task 6 Step 3）。
# ⚠ 本步在 Step 3 删除 _import/ 之后运行，**已无源仓副本可对照**——故这里只做环境判定；
#    「两侧表现一致」的对照已由 Task 6 Step 3 完成（那时 _import/ 还在）。
if docker info >/dev/null 2>&1; then
  (cd engineering/data-platform && bash scripts/check-mermaid.sh) && echo "OK check-mermaid"
else
  echo "⚠ check-mermaid 未验证：本机无 docker daemon + minlag/mermaid-cli 镜像（环境缺失；Task 6 已用源仓副本证明非迁移回归）"
fi
echo "== ④ 站点 =="
(cd languages/website && npm run build 2>&1 | tail -3)
echo "== ⑤ 历史连通（subtree 感知：--follow 在此结构性失效，不要用它）=="
# ① 三个源 tip 都必须是 HEAD 的祖先
for tip in 37b494a a0d1d7d 2ef5087; do
  git merge-base --is-ancestor "$tip" HEAD && echo "OK $tip 是 HEAD 的祖先"
done
# ② 三仓全部历史可达（318 = 154+41+123，三仓无共享提交）
echo "可达提交数: $(git rev-list --count 37b494a) $(git rev-list --count a0d1d7d) $(git rev-list --count 2ef5087)"
# ③ 内容零丢失：新路径下的文件内容 == 源 tip 原路径的内容
diff <(git show 37b494a:languages/java/ph21-data-platform/21-data-platform.md) \
     <(git show HEAD:languages/studies/java/ph21-data-platform/21-data-platform.md) \
  && echo "OK 语言域样本内容与源 tip 一致"
diff <(git show a0d1d7d:algorithms/README.md) <(git show HEAD:algorithms/README.md) \
  && echo "OK 算法域样本内容与源 tip 一致"
diff <(git show 2ef5087:README.md) <(git show HEAD:engineering/data-platform/README.md) \
  && echo "OK 数据平台域样本内容与源 tip 一致"
# ⑥ 仓库内残留的失效路径扫描 —— 即本任务 Step 2，已单独执行（此处不重复）
echo "== ⑦ 工作树干净 =="
git status --porcelain | head
```

Expected: ①–④ 全绿；⑤ 三行 `OK … 是 HEAD 的祖先` + 提交数 `154 41 123` + 三行 `OK … 内容与源 tip 一致`；⑦ `git status` 无输出（除本步产生的构建产物，均在 gitignore 内）。

- [ ] **Step 5: 合并回 `main`、建远端并推送**

⚠ **本迁移全程在临时分支 `mosaic-merge` 上实施**（Setup Ruling 1：SDD 要求未经明确同意不得在 `main` 上实施）。
`main` 至今仍是引导期的三个文档提交，且是 `mosaic-merge` 的祖先（**实测领先 345 个提交**；该数字随计划修正提交增长，以实测为准），故可**快进**合并。
**必须先合并回 `main` 再推送**——`gh repo create --push` 推的是**当前分支**，不先切回就会把 `mosaic-merge`
推成默认分支。

```bash
cd /Users/ninebot/code/mosslau/Mosaic
git add -A
git commit -m "docs: 顶层 README + 清理 _import 暂存区

Mosaic 三部分总入口：导航、跨域支撑、校验命令、边界说明。
_import/ 暂存区已删除，三仓内容全部就位于目标结构。"

# 合并回 main（快进：main 无新提交）
git switch main
git merge --ff-only mosaic-merge
test "$(git rev-parse HEAD)" = "$(git rev-parse mosaic-merge)" && echo "OK main 已快进到 mosaic-merge"
git rev-list --count main          # 记录最终提交数

gh repo create Mosslau/Mosaic --private --source=. --remote=origin --push \
  --description "Mosaic: 通用数据平台 + AI 平台数据中心 —— 语言 / 算法 / 工程系统"
git remote -v
git log --oneline | head -3
git status -sb | head -2
```

Expected: 远端创建成功；`origin` 指向 `git@github.com:Mosslau/Mosaic.git`；**当前分支为 `main`** 且 `git status -sb`
显示 `## main...origin/main`（无 ahead/behind）；`main` 与 `mosaic-merge` 指向同一提交。

若 `gh repo create` 报「仓库已存在」：改用 `git remote add origin git@github.com:Mosslau/Mosaic.git && git push -u origin main`，
**不要**把已有仓库误当新建（也不要 `--force`）。推送成功后 `mosaic-merge` 分支可留可删（`git branch -d mosaic-merge`），不影响交付。

---

## Task 8: 归档三个旧仓

**Files:** 无（仅 GitHub 侧操作）

**Interfaces:**
- Consumes: Task 7 推送成功、新仓校验全绿
- Produces: 三个旧仓只读归档

- [ ] **Step 1: 归档前最后一次确认新仓可用**

```bash
gh repo view Mosslau/Mosaic --json name,visibility,defaultBranchRef,url
git -C /Users/ninebot/code/mosslau/Mosaic status -sb | head -2
```

Expected: 仓库存在、private、默认分支 `main`；本地与 origin/main 同步。

- [ ] **Step 2: 逐个归档**

```bash
for r in TenetLang MindSpring OceanVerse; do
  gh repo archive "Mosslau/$r" --yes && echo "已归档 $r"
done
```

- [ ] **Step 3: 验证归档状态**

```bash
for r in TenetLang MindSpring OceanVerse Mosaic; do
  printf "%-12s archived=%s\n" "$r" "$(gh repo view Mosslau/$r --json isArchived -q .isArchived)"
done
```

Expected: 前三个 `archived=true`，`Mosaic archived=false`。

- [ ] **Step 4: 记录结论（无需提交代码，写入最终报告）**

报告须包含：新仓 URL、三部分目录规模、7 项门禁的实际结果（含任何**未验证**项，例如本机无 docker 时的 compose 检查）、以及 spec §11 的 6 项后续欠账。

---

## Self-Review

**1. Spec coverage** — 逐节核对 spec：

| Spec 节 | 覆盖在 |
|---|---|
| §3 D1–D5、D8 | Task 1 / 3 / 4 / 5 的结构与 `git mv` 目标 |
| §3 D6、D7（站点只服务语言域 + 归入 `languages/website/`） | Task 3 Step 1、Step 7 |
| §3 D9（技能不改名） | Task 2 Step 3（保留原名） |
| §3 D10（只修路径、不改仓名） | Task 3 Step 10、Task 5 Step 6 + 各 Task 的验证 grep |
| §4 目标结构 | File Structure 的搬迁映射表 |
| §5 顶层资产（LICENSE/.mcp.json/`.gitignore` 分层/`pyproject.toml`/skills 并集/website stub） | Task 2；stub 删除随 `git rm -r _import`（Task 7 Step 3） |
| §6 93 处路径修正 | Task 3（4+1+7+12+10）、Task 4（0）、Task 5（27+2+1+2+6）、Task 6（22） |
| §7 subtree 保历史 | Task 1 Step 3、Task 7 Step 4 的 `--follow` 验证 |
| §8 C1–C7 提交切分 | Task 1–7 与之一一对应 |
| §9 七项门禁 | Task 7 Step 4 |
| §10 风险与回滚 | Global Constraints「回滚」条 + Task 3 Step 6 的 fail-fast |
| §11 后续项 | Task 8 Step 4 的报告要求 |

无遗漏。

**2. Placeholder scan** — 已清除「TBD/TODO/视情况/类似 Task N」；所有代码步骤都给了可直接粘贴的命令与预期输出；4 个新 README 给出完整正文而非提纲。唯一保留的弹性是 Task 3 Step 10 / Task 5 Step 6 的 SKILL 措辞（规则 + 行号 + 事后断言 grep 判定完整性），以及 Task 6 Step 6 在本机无 docker 时「记录跳过并如实标注」——两者都有明确的判定命令，不是占位符。

**3. Type consistency** — 关键标识符在全文一致：`languages/studies`（非 `learning`/`tracks`）、`engineering/ai-platform`（非 `engineering/ai`）、`engineering/data-platform`、`_import/<repo>`、`ENG_INDEX`、`lang_root`、`FAMILIES`、`rootReadme`、`REPO_DIR`、`matrix.module`。Task 5 Step 8 中引用的七个项目名与 Task 5 Step 1 的目录名一致。
