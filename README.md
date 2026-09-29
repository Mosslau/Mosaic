# Mosaic

**通用数据平台 + AI 平台数据中心。**

把三件事放进同一个仓库：**怎么造语言工具**、**怎么让机器变聪明**、**怎么把系统真正跑起来**。

## 三部分

| 部分 | 目录 | 内容 | 规模 | 状态 |
|---|---|---|---|---|
| ① 开发语言部分 | [`languages/`](languages/) | 学（多语言阶段式学习路线）/ 析（语言设计解剖）/ 合（Tenet 语言与编译器） | 6 语言 × 126 阶段 | 已建成（正文 + 示例 + 文档站） |
| ② 算法部分 | [`algorithms/`](algorithms/) | 手写算法 vs 框架对照实验，五个学科族 | 23 个实验 | 进行中（1/23 完成，以 [`algorithms/README.md`](algorithms/README.md) 索引表为准） |
| ③ 工程系统部分 | [`engineering/`](engineering/) | [`ai-platform/`](engineering/ai-platform/)（AI 平台，7 个项目）+ [`data-platform/`](engineering/data-platform/)（通用数据平台，1 套设计） | 7 个项目 + 1 套设计 | 规划 / 设计阶段：ai-platform 未开工（`P5-agent-nest` 🚧），data-platform 仅设计文档（未实现） |

## 跨域支撑

| 路径 | 用途 |
|---|---|
| [`roadmap/`](roadmap/) | 路线图：算法演进路线 + 两条职业路线 + 语言学习路线 |
| [`roadmap/books/`](roadmap/books/) | 计算机书单 |
| [`.dsh/skills/`](.dsh/skills/) | 写作与验证规范（16 个 skill + `_design` 设计笔记） |

## 校验

```bash
# ① 语言域：章节契约 + 悬空链接 + 构建产物纪律
python3 .dsh/skills/tenetlang-notes/scripts/validate.py --links

# ② 算法域：索引/状态/章节锚定/模板结构/违禁 import，以及单元测试
python3 .dsh/skills/mindspring-lab/scripts/validate.py
python3 -m pytest -q

# ③ 语言域文档站
(cd languages/website && npm run build)
```

## 边界

`languages/` 承载**语义与教学**（"应该怎么做、为什么"），`engineering/` 的目标是**真实系统与真实指标**（"跑起来是什么样"）。同一个概念在两处出现时，前者讲清纪律，后者交付可运行的实现与实测数字——不重复造文档。

当前 `engineering/` 两域都还没到"跑起来"：`ai-platform/` 是待做清单（除 `P5-agent-nest` 外未开工），`data-platform/` 是设计文档（v35，未实现）。**状态以各域 README / 设计文档头部标注为准；未实现的不按"已跑通"叙述。**

## 为什么叫 Mosaic

三块各自独立的图块拼成一张完整图景：语言、算法、工程。每块可以单独看，合起来才是全貌。
