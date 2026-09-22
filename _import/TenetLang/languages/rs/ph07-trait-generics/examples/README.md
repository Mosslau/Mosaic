# examples —— Trait 与泛型阶段完整示例

对应主文档 `07-trait-generics.md` 第 6 章示例 1~5 的完整可运行版本。全部为单文件、零第三方依赖。验证环境：rustc 1.92.0（macOS arm64）。

| 文件 | 对应示例 | 说明 | 编译 | 运行 |
|------|---------|------|------|------|
| `ex01-encode-trait.rs` | 示例 1 | 为 LogRecord / IndexMeta / VectorRecord 实现统一的 `Encode` trait（含默认实现），泛型函数 `dump_all<T: Encode>` 通吃三种类型 | `rustc ex01-encode-trait.rs -o /tmp/ex01` | `/tmp/ex01` |
| `ex02-generic-fn.rs` | 示例 2 | 把重复的 `max_score` / `max_ts` 改造成泛型 `max_of<T: Ord + Copy>`，再用 `max_by_key` 与 `sum` 演示 bound 组合 | `rustc ex02-generic-fn.rs -o /tmp/ex02` | `/tmp/ex02` |
| `ex03-where-clause.rs` | 示例 3 | where 子句约束复杂泛型：`group_and_sum<K, V>` 三组约束 + 泛型结构体 `Counter<K>` 的 impl 块 where | `rustc ex03-where-clause.rs -o /tmp/ex03` | `/tmp/ex03` |
| `ex04-impl-trait.rs` | 示例 4 | impl Trait 返回位置：`impl Iterator<Item = u32>` 隐藏迭代器链具体类型、`impl Fn(i32) -> i32` 返回闭包 | `rustc ex04-impl-trait.rs -o /tmp/ex04` | `/tmp/ex04` |
| `ex05-derive-hash.rs` | 示例 5 | derive 版 `DocId`（逐字段 PartialEq/Hash）对比自定义版 `ShardKey`（只按 shard 判定相等与哈希） | `rustc ex05-derive-hash.rs -o /tmp/ex05` | `/tmp/ex05` |

## 运行产物

编译产物输出到 `/tmp/`，验证后已删除，仓库内不留任何二进制文件。

五个示例均已在本环境编译零警告并运行验证（已验证：rustc 1.92.0）。
