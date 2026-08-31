# examples —— 集合、迭代器与函数式写法阶段完整示例

对应主文档 `09-collections-iterators.md` 第 6 章示例 1~6 的完整可运行版本。全部为单文件、零第三方依赖。验证环境：rustc 1.92.0（macOS arm64）。

| 文件 | 对应示例 | 说明 | 编译 | 运行 |
|------|---------|------|------|------|
| `ex01-rewrite-stats.rs` | 示例 1 | 用迭代器重写 for 循环统计：命令式 vs `filter`+`count`/`sum` vs 单次遍历的 `fold`（同时算及格人数与平均分） | `rustc --edition 2021 ex01-rewrite-stats.rs -o /tmp/ex01` | `/tmp/ex01` |
| `ex02-collect-word-freq.rs` | 示例 2 | collect 到 Vec 和 HashMap：分词、长度映射、`entry` API 词频统计、按词频排序输出 | `rustc --edition 2021 ex02-collect-word-freq.rs -o /tmp/ex02` | `/tmp/ex02` |
| `ex03-fold-aggregate.rs` | 示例 3 | 用 fold 实现聚合：一个 `fold` 同时求最大/最小/个数、`fold` 构建 HashMap（词频）、`sum` 只是 `fold` 的特例 | `rustc --edition 2021 ex03-fold-aggregate.rs -o /tmp/ex03` | `/tmp/ex03` |
| `ex04-log-aggregator.rs` | 示例 4 | 日志数据聚合器：过滤异常记录 + 错误分布 + 延迟分档 + 来源统计（roadmap 推荐项目核心实现） | `rustc --edition 2021 ex04-log-aggregator.rs -o /tmp/ex04` | `/tmp/ex04` |
| `ex05-closure-capture.rs` | 示例 5 | 闭包捕获三种模式 Fn/FnMut/FnOnce：三个泛型函数把 trait 约束钉死，观察编译行为与意外移动 | `rustc --edition 2021 ex05-closure-capture.rs -o /tmp/ex05` | `/tmp/ex05` |
| `ex06-borrow-conflict.rs` | 示例 6 | 迭代器与借用冲突（E0502）：复现"边遍历边 push"的错误，给出三种安全解法（先收集后修改 / `iter_mut` / `retain`） | `rustc --edition 2021 ex06-borrow-conflict.rs -o /tmp/ex06` | `/tmp/ex06` |

## 关于"故意出错"的代码

- `ex06-borrow-conflict.rs` 文件头部的 E0502 复现块是**故意不通过编译**的：块内首行注释已写明运行前提（取消注释会报 `error[E0502]: cannot borrow ... as mutable because it is also borrowed as immutable`），请勿取消注释指望编译通过。
- `ex05-closure-capture.rs` 中有一行被注释掉的 `println!("{tag2}")`，取消注释会触发 E0382（use of moved value）——这是故意保留的对照，演示闭包意外移动。
- 两个文件均可正常编译运行（错误行保持注释状态），其余四个示例无故意出错代码。

## 运行产物

编译产物输出到 `/tmp/`，验证后已删除，仓库内不留任何二进制文件。

六个示例均已在本环境编译零警告并运行验证（已验证：rustc 1.92.0，`rustc --edition 2021` 单文件编译）。
