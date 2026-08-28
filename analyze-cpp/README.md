# 🔬 C++ 语言设计分析（analyze-cpp）

> 一步步分析 C++ 的语言设计，每篇主题配一个可编译运行的 demo。
> 分析结论汇总到 [`Tenet设计溯源`](../tenet/Tenet设计溯源.md)，作为 Tenet 语言设计的输入。

> 🧭 **定位**：本目录是「设计解剖」——讲*为什么*这么设计。
> 对应的「学习笔记」（讲*怎么学*）在 [`lang-cpp/`](../lang-cpp/)，建议先学后析。

C++ 的核心设计命题：**在"零成本抽象"的前提下，把尽可能多的范式塞进一门语言**——
过程式、面向对象、泛型、模板元编程、函数式并存。它的伟大与混乱都源于此。

## 分析路线

| # | 主题 | 核心问题 | Demo |
|---|------|---------|------|
| 01 | [RAII 资源管理](notes/01-raii.md) | 资源（内存/文件/锁）怎么自动释放？ | `make && ./demos/01_raii` |
| 02 | [移动语义与右值引用](notes/02-move-semantics.md) | 怎么零拷贝地传递大对象？ | `make && ./demos/02_move` |
| 03 | [多范式设计](notes/03-multiparadigm.md) | 一门语言能同时容纳几种编程范式？ | `make && ./demos/03_multiparadigm` |
| 04 | [STL 设计](notes/04-stl-design.md) | 容器/迭代器/算法怎么解耦？ | `make && ./demos/04_stl` |
| 05 | [constexpr 编译期计算](notes/05-constexpr.md) | 计算能提到编译期吗？ | `make && ./demos/05_constexpr` |

## 快速开始

```bash
cd analyze-cpp/demos
make          # 编译全部 5 个 demo
./01_raii     # 依次运行
```

## 分析方法

每篇笔记的结构：

1. **设计动机**——这个设计解决什么问题
2. **机制拆解**——语法/语义/编译期规则
3. **代码验证**——最小 demo 亲眼看到机制
4. **代价与取舍**——牺牲了什么
5. **对 Tenet 的启示**——值得吸收 / 应该拒绝（输入 design-notes.md）
