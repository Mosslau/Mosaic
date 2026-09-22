# ph03 基础数据结构 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：rustc 1.92.0（无第三方依赖）。编译统一用 `rustc <文件>.rs -o /tmp/<名>`，运行 `/tmp/<名>`。

## 练习 1：定义业务实体结构体（★）

**目标**：用 struct 表达 User、Device、Order 三类业务实体，理解 derive 宏省去 boilerplate。

**要求**：

- 定义 `User { id: u32, name: String, email: String }`，derive `Debug` + `Clone`
- 定义 `Device { id: u32, name: String, online: bool }`，derive `Debug` + `Clone` + `PartialEq`
- 定义 `Order { id: u32, product: String, amount: u32 }`，derive `Debug` + `Clone` + `PartialEq`
- 在 main 中：各创建一个实例，用 `clone()` 生成副本，用 `assert_eq!` / `println!` 验证

**验收**：

- `rustc sol-01-entities.rs -o /tmp/sol01 && /tmp/sol01` 编译零警告、运行无 panic
- 三个结构体都能 `{:?}` 打印
- `Device` 与 `Order` 的 clone 副本与原值 `==` 相等（`assert_eq!` 不触发）

## 练习 2：用 Vec 保存记录并排序过滤（★★）

**目标**：掌握 Vec 的三种遍历语义、`sort_by` 排序、`iter().filter` 过滤。

**要求**：

- 定义 `Order { id: u32, product: String, amount: u32, shipped: bool }`，derive `Debug`
- 用 Vec 保存至少 5 条订单
- 用 `for o in &mut orders` 把所有订单 amount +10
- 用 `sort_by` 按 amount 降序排序
- 用 `iter().filter` 过滤出未发货（`shipped == false`）的订单

**验收**：

- 排序后列表按 amount 降序
- 过滤结果只含 `shipped == false` 的订单
- 提示：`for x in v` 会消耗 v（之后不可再用，报 E0382），本题用 `&` / `&mut` 遍历避免 move

## 练习 3：用 HashMap 分组统计（★★）

**目标**：掌握 entry API 做分组统计——一次哈希查找完成「判断 + 更新」。

**要求**：

- 定义 `Order { product: String, amount: u32, category: String }`，derive `Debug` + `Clone`
- 给定固定订单列表（至少 5 条，含重复 product / category）
- 用 `HashMap<&str, u32>` 按 product 分组统计总金额
- 用 `HashMap<&str, u32>` 按 category 分组统计订单数量
- 必须用 entry API（`and_modify` + `or_insert` 或 `entry().or_insert`），不准 `contains_key` + `insert` 两步走

**验收**：

- 输出分组统计结果与预期一致（如 product 为 widget 的总金额 = 各条 widget 订单 amount 之和）
- 编译零警告

## 练习 4：订单分析器（★★★）

**目标**：综合 struct + Vec + HashMap，写一个小的订单分析工具，并用断言验证（不靠肉眼比对）。

**要求**：

- 定义 `Order { product: String, amount: u32, category: String }`，derive `Debug` + `Clone` + `PartialEq`
- 写函数 `analyze(orders: &[Order]) -> Analysis`，`Analysis` 结构体含三个字段：
  - `by_category: HashMap<String, usize>`：按 category 分组的订单数量
  - `total_by_product: HashMap<String, u32>`：按 product 分组的销售总额
  - `sorted: Vec<Order>`：按 amount 降序排序的订单副本
- 在 main 中构造订单列表，调用 `analyze`，用 `assert_eq!` 验证数量、金额、排序都正确

**验收**：

- `rustc sol-04-order-analyzer.rs -o /tmp/sol04 && /tmp/sol04` 编译零警告、断言全部通过
- 排序用 `sort_by`，分组用 entry API
