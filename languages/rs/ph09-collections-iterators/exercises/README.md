# exercises —— 集合、迭代器与函数式写法阶段练习

完成顺序建议：按 1~5 顺序完成，对应主文档第 6 章示例 1~6 的主题。参考实现在 `sol-*` 文件中，**先自己做，做完再看**。每题标注难度（★~★★★）。

## 练习 1：用迭代器重写 for 循环统计（★）

- **目标**：把"for 循环 + 可变累加器"的统计代码改写成迭代器链，体会命令式与声明式的差异
- **要求**：
  - 给定 `let scores = vec![72, 88, 95, 41, 60, 100, 33];`，统计及格（≥60）人数与平均分
  - 先写出命令式版本（for 循环 + `mut` 累加器），**再替换成迭代器版本并保留命令式版本为注释对照**
  - 迭代器写两个版本：① `filter` + `count`/`sum`；② 单个 `fold` 同时算人数与总分（只遍历一次）
  - 用 `assert_eq!` 断言两个迭代器版本结果一致
- **验收**：`rustc --edition 2021 sol-01-rewrite-stats.rs -o /tmp/sol01 && /tmp/sol01` 编译零警告；输出 `及格 5 人, 平均 83.0`；命令式版本以注释形式保留

## 练习 2：练习 collect 到 Vec 和 HashMap（★）

- **目标**：掌握 `collect` 的目标类型由标注决定，区分裸 collect 与 `entry` API 的适用场景
- **要求**：
  - 给定 `let text = "the quick brown fox jumps over the lazy dog the fox";`
  - ① 分词后 `collect` 到 `Vec<&str>`；② 把每个词映射成 `(词, 长度)` 后 `collect` 到 `HashMap<&str, usize>`
  - ③ 词频统计：**不要用裸 collect 做重复键聚合**（会覆盖），用 `entry(key).or_insert(0) += 1`
  - ④ 把词频表转成可排序的 `Vec`，按词频**降序**输出 `词: 次数`
- **验收**：`rustc --edition 2021 sol-02-collect-map.rs -o /tmp/sol02 && /tmp/sol02` 编译零警告；`the: 3`、`fox: 2` 居首，其余词 1 次；长度表为 `HashMap<&str, usize>`

## 练习 3：用 fold 实现聚合（★★）

- **目标**：掌握 `fold(初始值, |acc, x| 新acc)` 的三要素，理解累加器可以是元组或集合
- **要求**：
  - 给定 `let nums = [3, 1, 4, 1, 5, 9, 2, 6];`，用**单个 `fold`** 同时求最大值、最小值、个数（累加器为三元组）
  - 用 `fold` 构建 `HashMap<&str, u32>` 做词频统计（输入 `["rust", "go", "rust", "c", "rust", "go"]`），体会"闭包必须返回 `acc`"
  - 再写一行代码证明 `sum` 只是 `fold(0, |acc, n| acc + n)` 的特例
  - 不用裸 `unwrap`（用 `or_insert`/`or_insert(0)`）
- **验收**：`rustc --edition 2021 sol-03-fold-aggregate.rs -o /tmp/sol03 && /tmp/sol03` 编译零警告；输出 `max=9 min=1 count=8`、`{"rust": 3, "go": 2, "c": 1}`、`sum via fold: 31`

## 练习 4：闭包捕获三种模式与意外移动（★★）

- **目标**：区分 Fn / FnMut / FnOnce 三种捕获模式，能避免"闭包意外移动"（E0382）
- **要求**：
  - 写三个泛型函数把约束钉死：`run_once<F: FnOnce() -> String>`、`run_mut<F: FnMut()>`（内部调用两次）、`run_fn<F: Fn() -> u32>`（内部调用两次并相加）
  - 用 `run_once(|| tag2)` 演示意外移动：调用后 `tag2` 的所有权被移出，**错误版本（`println!("{tag2}")`）保持注释，首行标注"故意不通过编译（E0382）"**
  - 用 `run_mut(|| counter += 1)` 演示可变捕获；用 `run_fn(|| base + 1)` 演示只读捕获，并证明只读闭包也能传给 `run_once`
  - 不写裸 `unwrap`
- **验收**：`rustc --edition 2021 sol-04-closure-capture.rs -o /tmp/sol04 && /tmp/sol04` 编译零警告；输出 `v2`、`counter = 2`、`run_fn: 202`、`run_once: tag-100`、`base = 100`（base 未被移动）

## 练习 5：迭代器与借用冲突（复现 E0502 并修复）（★★★）

- **目标**：走通"复现 → 理解 → 三种解法"的完整套路，理解迭代器持有借用期间不能做结构性修改
- **要求**：
  - 先写出无法编译的错误版本（for 循环里 `nums.push(*n)`），**保留为注释，块内首行标注"故意不通过编译（E0502）"**（实测报 `error[E0502]`，不要把错误码标成别的）
  - 用三种解法各写一个可运行版本：① 先 `collect` 出要加的数据、循环结束后再 `extend`；② 原地修改用 `iter_mut`；③ 按条件删除用 `retain`
  - 不写裸 `unwrap`
- **验收**：`rustc --edition 2021 sol-05-borrow-conflict.rs -o /tmp/sol05 && /tmp/sol05` 编译零警告；三行输出分别为 `[1, 2, 3, 4, 5, 6, 10, 20, 30, 40, 50, 60]`、`[2, 3, 4, 5, 6, 7, 11, 21, 31, 41, 51, 61]`、`["bb", "ccc"]`

> **提示**：练习 1~5 覆盖主文档第 6 章示例 1~6 的主题（示例是"看"，练习是"做"；示例 4 的日志聚合器是阶段项目核心）。卡壳时先回读主文档 3.x 对应小节（3.2 适配器、3.3 消费器、3.4 闭包捕获、3.6 collect、3.8 借用冲突），最后再看 `sol-*`。
