# 🔬 Python 语言设计分析（analysis/py）

> 一步步分析 Python 的语言设计，每篇主题配一个可直接运行的 demo。
> 分析结论汇总到 [`Tenet`](../../tenet/Tenet架构设计.md)，作为 Tenet 语言设计的输入。

> 🧭 **定位**：本目录是「设计解剖」——讲*为什么*这么设计。
> 对应的「学习笔记」（讲*怎么学*）在 [`languages/studies/py/`](../../studies/py/)，建议先学后析。

Python 的核心设计命题：**"简单、可读、快速上手"优先于性能与严谨**——
动态类型、一切皆对象、鸭子类型、解释执行。它是"语言设计要服务开发者体验"的最佳样本，
也是"性能与严谨"的反面教材。

## 分析路线

| # | 主题 | 核心问题 | Demo |
|---|------|---------|------|
| 01 | [动态类型与鸭子类型](notes/01-dynamic-typing.md) | 类型检查推迟到运行时，换来什么、失去什么？ | `python3 demos/01_dynamic_typing.py` |
| 02 | [数据模型（魔术方法）](notes/02-data-model.md) | 运算符和内置函数怎么映射到对象方法？ | `python3 demos/02_data_model.py` |
| 03 | [装饰器与闭包](notes/03-decorators.md) | 函数是一等公民能玩出什么花样？ | `python3 demos/03_decorators.py` |
| 04 | [生成器与迭代器](notes/04-generators.md) | 惰性求值怎么省内存？ | `python3 demos/04_generators.py` |
| 05 | [上下文管理器](notes/05-context-managers.md) | `with` 语句怎么自动清理资源？ | `python3 demos/05_context_managers.py` |

## 快速开始

```bash
cd analysis/py
python3 demos/01_dynamic_typing.py   # 依次运行 01~05
```

## 分析方法

每篇笔记的结构：

1. **设计动机**——这个设计解决什么问题
2. **机制拆解**——语法/语义/运行时规则
3. **代码验证**——最小 demo 亲眼看到机制
4. **代价与取舍**——牺牲了什么
5. **对 Tenet 的启示**——值得吸收 / 应该拒绝（输入 Tenet架构设计.md（完整文档 §1 设计溯源））
