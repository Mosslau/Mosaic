# exercises —— 宏与元编程阶段练习

完成顺序建议：按 1~4 顺序完成，对应主文档第 3 章 3.1~3.6 与第 6 章示例的主题。参考实现在 `sol-*` 文件中，**先自己做，做完再看**。每题标注难度（★~★★★）。

对应 roadmap 练习的说明：练习 1 = roadmap「写一个生成日志字段的 macro_rules 宏」，练习 4 = roadmap「用 serde derive 生成序列化代码」；roadmap 练习 3「用 cargo expand 观察宏展开」是观察性任务（不需要写独立代码），已在 [examples/crates/README 的 cargo expand 一节](../examples/README.md) 实测落地，练习区不重复出题。练习 2/3 把「必会概念」卫生性与「匹配规则/递归」做成动手题。

- 练习 1~3 为纯 std 单文件，`rustc --edition 2021 -D warnings` 编译（产物输出 `/tmp/`）。
- 练习 4 需要 serde（cargo 工程 `crates/`，rsproxy 拉取，Cargo.lock 已锁定）。

## 练习 1：生成日志字段的宏 log_fields!（★★）

- **目标**：写一个 `log_fields!` 声明宏，把「事件名 + 任意多个字段」输出成一行行 `event = <名>` / `  <字段名> = <值>` 的日志块（roadmap 练习「写一个生成日志字段的 macro_rules 宏」）
- **要求**：
  - 调用形如 `log_fields!("login", user = user, port = port, ok = true)`：字段是 `$k:ident = $v:expr` 成对出现，字段名打印 token 原样（`stringify!`），字段值用 `{:?}` 打印（兼容字符串/数字/布尔）
  - 支持 0 个以上字段、可尾逗号（`$(,)?`）
  - 宏展开只生成 `println!` 语句，不产生返回值；用 `{{ }}` 包住展开体防止与外部语句粘连
- **验收**：`rustc --edition 2021 -D warnings sol-01-log-fields-macro.rs -o /tmp/sol01 && /tmp/sol01` 编译零警告；输出含两段日志块（`login` 与 `purchase`，字段值 `"ada"`/`8080`/`true`、`"rs-book"`/`3`）与「断言通过：log_fields! 与手写 println 输出一致」

## 练习 2：swap_vars! 与卫生性（★★）

- **目标**：写一个 `swap_vars!(a, b)` 宏交换两个调用方变量，并用「宏内临时变量与调用方同名变量并存」实测卫生性（对应必会概念 hygiene；参考 examples/ex04）
- **要求**：
  - `swap_vars!` 接收两个 `ident`（`$a:ident, $b:ident`），展开体内**必须用显式临时变量**完成交换（`let tmp = $a; $a = $b; $b = tmp;`）
  - 调用方声明 `left = 1, right = 2`，**再额外声明一个 `tmp = 99`**——若宏内临时变量不卫生，两处 `tmp` 会冲突
  - 交换后断言 `(left, right) == (2, 1)` 且调用方 `tmp` 仍是 99；再交换回来断言 `(1, 2)`
- **验收**：`rustc --edition 2021 -D warnings sol-02-swap-hygiene.rs -o /tmp/sol02 && /tmp/sol02` 编译零警告；输出含 `left = 2, right = 1`、`调用方 tmp 仍是 99` 与「断言全部通过」

## 练习 3：递归声明宏（★★★）

- **目标**：用「剥一个 + 递归剩余」（tt muncher）写两个递归声明宏，理解 macro_rules! 的递归只靠结构收敛、不做算术（对应 3.2/3.3 匹配规则）
- **要求**：
  - `sum_args!`：变参求和。递归终点是「只剩一个参数」的臂 `($x:expr) => { $x }`；递归臂剥掉第一个、把剩余整体递归：`sum_args!(1, 2, 3, 4) == 10`、`sum_args!(1..=10) == 55`
  - `last_arg!`：递归丢弃第一个直到只剩一个：`last_arg!("a", "b", "c") == "c"`；单参数直接命中终点
  - 在注释里说明（不启用）：为什么「数值递归」（如 `down_from!($n - 1)` 想从 3 减到 0）会一路展开到 `recursion limit reached`——宏按 token 匹配、不会先求值
- **验收**：`rustc --edition 2021 -D warnings sol-03-recursion-macros.rs -o /tmp/sol03 && /tmp/sol03` 编译零警告；输出含 `sum_args!(1, 2, 3, 4) = 10`、`sum_args!(1, 2, 3, 4, 5, 6, 7, 8, 9, 10) = 55`、`last_arg!("a", "b", "c") = c` 与「断言全部通过」

## 练习 4：用 serde derive 生成序列化代码（★★）

- **目标**：为「页面分析事件」建模并 derive 序列化/反序列化（roadmap 练习「用 serde derive 生成序列化代码」）
- **要求**（在 `crates/` 工程里新建 `src/bin/sol-04-serde-derive.rs`，或先自己写再看参考实现）：
  - `struct PageView { user_id: u64, page: String, duration_ms: u32, #[serde(default)] referrer: String }`，结构体级 `#[serde(rename_all = "snake_case")]`
  - `enum Event { PageView(PageView), Signup { user_id: u64, plan: String } }`，同样 `rename_all`——观察**外标签（externally tagged）**形态：variant 名做 JSON 外层键
  - 三个事件（两个 PageView + 一个 Signup）序列化为 JSON 并逐行打印；第一个 JSON 反序列化回 `Event` 断言往返一致；构造缺 `referrer` 的 JSON 断言 `default` 生效
- **验收**：`cd crates && CARGO_TARGET_DIR=/tmp/ph15-exercises-target cargo run --bin sol-04-serde-derive` 编译零警告；输出三行 JSON（`"page_view"` 含 4 个键 / `"signup"` 形态）+「往返一致 = true」+ 缺失 referrer 为 `""` + 「断言通过」（完整实测输出见 sol-04 文件头验证块）

> **提示**：练习 1 练 repetition 与 `stringify!`，练习 2 练卫生性，练习 3 练递归匹配，练习 4 练 derive——四题做完覆盖 roadmap 必会概念（编译期代码生成 / token tree / 宏展开 / 卫生性）与两条编码类练习；cargo expand 观察见 examples/crates README。
