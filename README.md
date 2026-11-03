# Mosaic

**通用数据平台 + AI 平台数据中心。**

把三件事放进同一个仓库：**怎么造语言工具**、**怎么让机器变聪明**、**怎么把系统真正跑起来**。

## 三部分

| 部分 | 目录 | 内容 | 规模 | 状态 |
|---|---|---|---|---|
| ① 开发语言部分 | [`languages/`](languages/) | 学（多语言阶段式学习路线）/ 析（语言设计解剖）/ 合（Tenet 语言与编译器） | 6 语言 × 126 阶段 | 已建成（正文 + 示例 + 文档站） |
| ② 算法部分 | [`algorithms/`](algorithms/) | 手写算法 vs 框架对照，五个学科族 | 42 个算法 | 已完成（42/42 完成，以 [`algorithms/README.md`](algorithms/README.md) 索引表为准） |
| ③ 工程系统部分 | [`engineering/`](engineering/) | [`ai-platform/`](engineering/ai-platform/)（AI 平台，D0–D10 共 11 阶段）+ [`data-platform/`](engineering/data-platform/)（通用数据平台，D0–D12 共 13 阶段） | 2 个平台 / 24 个阶段 | 设计阶段：ai-platform 0/11（D8 进行中，Part 1 资料完成，运行时代码未开始）；data-platform 0/13（路线 v48，设计文档，未实现） |

> 跨域执行路线：[`roadmap/AI-Infra数据侧学习开发路线.md`](roadmap/AI-Infra数据侧学习开发路线.md)（四轨：数据平台 / AI 平台 / 语言+Tenet / 算法；60 个月；每阶段带命令 + 输入 + 观察）。

## 校验

一条命令跑全部，各域使用自己的运行环境与 pytest 配置：

```bash
./verify.sh          # 文档契约 + 算法测试 + Agent 运行时
./verify.sh --site   # 追加语言域文档站构建（需网络）
```

退出码：`0` 全部通过 / `1` 有域失败 / `2` 无失败但有域跳过（跳过的域不算通过）。

| 域 | 实际命令 | 依赖 |
|---|---|---|
| 语言域文档契约 | `python3 .dsh/skills/tenetlang-notes/scripts/validate.py --links` | 系统 `python3` |
| 算法域文档契约 | `python3 .dsh/skills/mindspring-lab/scripts/validate.py` | 系统 `python3` |
| 算法域测试 | `cd algorithms && .venv/bin/python -m pytest -q`（575 项） | `uv sync --extra dev` |
| Agent 运行时 | [`python-agent-runtime/scripts/verify.sh`](engineering/ai-platform/agent-platform/agent-service/python-agent-runtime/scripts/verify.sh)（pytest / ruff / docstring） | 该目录 `uv sync` |
| 语言域文档站 | `cd languages/website && npm install && npm run build` | Node + 网络 |

> 各域 pytest 配置互斥：根 [`pytest.ini`](pytest.ini) 只收 `algorithms/`（`--import-mode=importlib`），
> `python-agent-runtime` 自带 `[tool.pytest.ini_options]`（prepend 模式，服务同目录导入）。
> **不要用一条 `pytest` 跨域收集**——会在收集期直接失败。详见 [`verify.sh`](verify.sh)。
> 算法域需 Python ≥ 3.11（`algorithms/pyproject.toml` 的 `requires-python`；系统 `python3` 可能是 3.9）。

`engineering/` 两个平台的**设计文档**当前无自动化脚本（规范自述「不带校验脚本」），按
[`.dsh/skills/engineering-docs/`](.dsh/skills/engineering-docs/) 的场景 D 完成度清单人工核对。

## 边界

`languages/` 承载**语义与教学**（"应该怎么做、为什么"），`engineering/` 的目标是**真实系统与真实指标**（"跑起来是什么样"）。同一个概念在两处出现时，前者讲清纪律，后者交付可运行的实现与实测数字——不重复造文档。

当前 `engineering/` 两域都还没到"跑起来"：`ai-platform/` 为设计阶段（0/11，D8 进行中：Part 1 资料完成，运行时代码未开始），`data-platform/` 为设计文档（0/13，路线 v48，未实现）。**状态以各域 README / 设计文档头部标注为准；未实现的不按"已跑通"叙述。**

## 为什么叫 Mosaic

三块各自独立的图块拼成一张完整图景：语言、算法、工程。每块可以单独看，合起来才是全貌。
