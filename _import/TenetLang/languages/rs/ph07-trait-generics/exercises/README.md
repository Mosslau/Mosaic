# exercises —— Trait 与泛型阶段练习

完成顺序建议：按 1~5 顺序完成，对应主文档第 6 章示例 1~5 的主题。参考实现在 `sol-*` 文件中，**先自己做，做完再看**。

## 练习 1：为多个结构体实现同一个 trait（★）

- **目标**：定义一个 `Summarize` trait，为 `Article`、`Comment`、`Tweet` 三个结构体分别实现
- **要求**：
  - `Summarize` 含一个必须实现的方法 `fn summarize(&self) -> String` 和一个默认实现 `fn headline(&self) -> String`（基于 summarize 包装）
  - `Article`（字段：title、author）、`Comment`（字段：user、body）、`Tweet`（字段：user、content）各自实现 `summarize`
  - `Comment` 覆盖默认的 `headline`，另两个用默认实现
  - 写一个泛型函数 `print_all<T: Summarize>(items: &[T])` 打印三种类型的切片
- **验收**：`rustc sol-01-summarize-trait.rs -o /tmp/sol01 && /tmp/sol01` 编译零警告并输出三种类型的摘要与 headline；覆盖默认实现的 Comment 输出与另两个不同

## 练习 2：把重复函数改造成泛型函数（★★）

- **目标**：把三个几乎相同的函数合并为一个泛型函数
- **要求**：以下三个函数只有元素类型不同——
  ```rust
  fn max_i32(items: &[i32]) -> Option<i32> { items.iter().copied().max() }
  fn max_f64(items: &[f64]) -> Option<f64> { items.iter().copied().max() }
  fn max_char(items: &[char]) -> Option<char> { items.iter().copied().max() }
  ```
  - 改造成一个 `fn largest<T>(items: &[T]) -> Option<T>`，用最小必要的 trait bound（想清楚：i32/f64/char 共有什么能力）
  - 空切片返回 `None`，调用方用 `match` 或 `if let` 处理（**不用 unwrap**）
  - main 中用三种类型各调用一次，并演示空切片返回 None
- **验收**：`rustc sol-02-largest-generic.rs -o /tmp/sol02 && /tmp/sol02` 编译零警告；三种类型输出各自最大值；空切片输出 `None`；代码中无 unwrap/expect

## 练习 3：where 子句约束复杂泛型（★★）

- **目标**：写一个"按键分组计数"的泛型函数，约束多到必须用 where 子句
- **要求**：
  - `fn count_by<T, K, F>(items: &[T], key_fn: F) -> HashMap<K, usize>`：对 `items` 中每个元素用 `key_fn` 提取 key，统计每个 key 出现次数
  - 约束：`F` 是接收 `&T` 返回 `K` 的闭包；`K` 必须能作为 HashMap 的 key
  - 约束用 **where 子句**写（不准内联到 `<>` 里），保持签名可读
  - main 中演示两种用法：对 `&["INFO", "WARN", "INFO"]` 按原值计数；对一组 `(name, level)` 元组按 level 计数
- **验收**：`rustc sol-03-count-by.rs -o /tmp/sol03 && /tmp/sol03` 编译零警告；`INFO` 计数为 2；按 level 分组计数正确

## 练习 4：用 impl Trait 改写返回迭代器的函数（★★）

- **目标**：体会返回位置 `impl Iterator` 隐藏具体类型的价值
- **要求**：
  - 写 `fn evens_squared(limit: u32) -> impl Iterator<Item = u64>`：返回 `[0..=limit]` 中偶数的平方（`u64` 防止溢出）
  - 再写 `fn multiples_of(base: u32, limit: u32) -> impl Iterator<Item = u32>`：返回 `[1..=limit]` 中 `base` 的所有倍数
  - main 中 `collect` 两种迭代器并打印；再演示把 `evens_squared(10)` 的结果 `sum()` 求和
  - **思考（不写在代码里）**：如果不用 impl Trait，返回类型的完整签名有多长？
- **验收**：`rustc sol-04-impl-iterator.rs -o /tmp/sol04 && /tmp/sol04` 编译零警告；`evens_squared(10)` collect 后为 `[0, 4, 16, 36, 64, 100]`；`multiples_of(3, 10)` 为 `[3, 6, 9]`

## 练习 5：自定义 PartialEq 与 Hash 的一致性（★★★）

- **目标**：手写 PartialEq + Hash，理解"相等即同哈希"的一致性约束
- **要求**：
  - 定义 `struct CaseInsensitiveKey(String)`：比较与哈希都**忽略大小写**（`"Info" == "info" == "INFO"`）
  - 手写 `PartialEq`、`Eq`、`Hash` 三个 impl（提示：比较和哈希都用转小写后的值，保证一致）
  - 用 `HashMap<CaseInsensitiveKey, u64>` 聚合：插入 `"INFO"`、`"info"`、`"Warn"` 各一次计数，查询时用任意大小写组合都应命中
  - main 中验证：`get("INFO")`、`get("info")`、`get("Info")` 返回相同结果（**不用 unwrap**，用 `match` 或 expect 带说明文字）
- **验收**：`rustc sol-05-case-insensitive-key.rs -o /tmp/sol05 && /tmp/sol05` 编译零警告；`info` 键总计数为 2；三种大小写查询结果一致；代码中无裸 unwrap

> **提示**：练习 1~5 与主文档示例 1~5 一一对应（示例是"看"，练习是"做"）。卡壳时先回读主文档 3.x 对应小节，最后再看 `sol-*`。
