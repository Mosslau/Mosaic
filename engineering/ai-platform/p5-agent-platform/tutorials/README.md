# 📚 AgentNest 教学轨道（Tutorials）

> **从零手写一个 Agent Harness**——不依赖任何框架，逐章实现 harness 的每个机制。
>
> 核心理念：*Agency comes from the model. An Agent Product = Model + Harness.*
> 模型提供智能，harness 提供工具 / 知识 / 权限 / 上下文；Agent 循环永不改变，变的只是环绕它的机制。

本目录是 [../README.md](../README.md) 中"Part 1 沉淀"的教程部分，与 [../research/](../research/) 的方法论一一对应。

## 双轨道

| 轨道 | 目录 | 语言 | 形式 | 定位 |
|:--|:--|:--|:--|:--|
| **Python** | [python/](python/) | Python 3 | 每章一个 `code.py`（单文件，开箱即跑） | **权威参考轨道**，机制讲解最完整，含三语 README（中 / 英 / 日）与 SVG 图解 |
| **Rust** | [rust/](rust/) | Rust | Cargo workspace，每章一个独立 binary crate | 生产化重写轨道，与 Python 章节一一对应，测试驱动（`cargo test --workspace` 全绿） |

> 想快速理解某个机制：看 Python 轨道的 `code.py` + 图解；想看工程化、类型安全、测试完备的版本：对照 Rust 轨道。

## 章节地图（s01–s20）

两轨道完全对齐，逐章递进——**每章只新增一个机制**，测试最新一章 = 回归全部已有机制：

| 阶段 | 章节 | 核心机制 |
|:--|:--|:--|
| 基础循环 | s01–s05 | Agent Loop → 工具调用 → 权限闸门 → Hooks → 规划（todo） |
| 上下文与记忆 | s06–s10 | 子代理 → Skill 加载 → 上下文压缩 → 持久记忆 → System Prompt 组装 |
| 生产化 | s11–s14 | 错误恢复 → 任务系统 → 后台任务 / 并发 → Cron 调度 |
| 多代理与隔离 | s15–s18 | Agent 团队 → 团队协议 / 审批 → 自治代理 → Worktree 隔离 |
| 集成与综合 | s19–s20 | MCP 插件 → 全机制综合（完结章） |

各章目录：`python/sXX_*/` 与 `rust/sXX_*/` 一一对应。

## 快速开始

**Python**（`code.py` 单文件直跑，见各章 README）：

```bash
cd python
python s01_agent_loop/code.py
```

**Rust**（workspace，`cargo run -p <crate>`）：

```bash
cd rust
cargo run -p s01_agent_loop      # 运行某一章
cargo test --workspace           # 全量回归（2775 个测试）
```

## 配套内容

- **技能（skills/）**：两轨道各含 `agent-builder` / `code-review` / `mcp-builder` / `pdf` 四个 skill 示例（s07 起使用）
- **Python 测试**：`python/tests/`（冒烟 + 机制专项，见 `python/README.md`）
- **Rust 测试手册**：`rust/TEST.md`（T1–T17 端到端手工测试路径）
- **Rust 示例**：`rust/example/`（含五子棋 `gomoku-js` crate）
- **环境变量**：各轨道各自的 `.env`（见 [python/.env.example](python/.env.example) 与 [rust/.env.example](rust/.env.example)）

## 文档语言约定

- **Python 轨道**：每章 README 提供 `README.md`（英）/ `README.zh.md`（中）/ `README.ja.md`（日）三语
- **Rust 轨道**：单语 `README.md`（中文为主）

## 维护说明

- 新增章节：两轨道同步新增 `sXX_*/` 目录，并在此地图登记
- 改章节名 / 路径：同步本地图与顶层 [../README.md](../README.md) 及 [../research/](../research/) 的引用
- 重命名后跑一次全库死链检查（grep 旧路径名）

---

**下一步（见顶层路线）**：Part 1 门禁——方案评审定稿，选定 Part 2 首个落地对象（agent-core mock-LLM 最小闭环 / agentscope 适配器实证）。
