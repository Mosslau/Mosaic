# Mosaic

**通用数据平台 + AI 平台数据中心。**

把三件事放进同一个仓库：**怎么造语言工具**、**怎么让机器变聪明**、**怎么把系统真正跑起来**。

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
| [`.dsh/skills/`](.dsh/skills/) | 写作与验证规范（15 个 skill + `_desgin` 设计笔记） |

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

## 边界

`languages/` 承载**语义与教学**（"应该怎么做、为什么"），`engineering/` 承载**真实系统与真实指标**（"跑起来是什么样"）。同一个概念在两处出现时，前者讲清纪律，后者交付可运行的实现与实测数字——不重复造文档。

## 为什么叫 Mosaic

三块各自独立的图块拼成一张完整图景：语言、算法、工程。每块可以单独看，合起来才是全貌。
