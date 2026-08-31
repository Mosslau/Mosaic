# exercises —— 生命周期 Lifetime 阶段练习

完成顺序建议：按 1~5 顺序完成，对应主文档第 6 章示例 1~5 的主题。参考实现在 `sol-*` 文件中，**先自己做，做完再看**。

## 练习 1：为返回引用的函数添加生命周期（★）

- **目标**：修复 E0106，并理解"输出只绑定一个输入"与"绑定所有输入"的差别
- **要求**：
  - 以下函数无法编译（`error[E0106]: missing lifetime specifier`），在不改变函数体的前提下补上生命周期标注：
    ```rust
    fn longer(x: &str, y: &str) -> &str {
        if x.len() >= y.len() { x } else { y }
    }
    ```
  - 再写一个 `fn first(x: &str, y: &str) -> &str`，让返回值**只绑定第一个输入**（`y` 仅用于比较），使下面的调用合法——外层作用域在 `s2` 被 drop 后仍能使用返回值：
    ```rust
    let s1 = String::from("alpha");
    let r;
    {
        let s2 = String::from("b");
        r = first(&s1, &s2);
    }
    println!("{r}"); // 要求这里能编译
    ```
  - 用 `longer` 做同样的嵌套调用，把返回值用在 `s2` 存活期内（逃出作用域的版本保持注释，标注会报 E0597）
- **验收**：`rustc --edition 2021 sol-01-add-lifetime.rs -o /tmp/sol01 && /tmp/sol01` 编译零警告；`first` 的返回值在 `s2` drop 后仍可打印 `alpha`；`longer` 输出较长者

## 练习 2：写一个持有引用的结构体并实现方法（★★）

- **目标**：掌握 `struct S<'a>` / `impl<'a> S<'a>` 的写法，体会方法上的省略规则
- **要求**：
  - 定义 `struct LineView<'a> { text: &'a str, number: usize }`：借用它指向的那行文本，零拷贝
  - 实现 `new(text: &'a str, number: usize) -> Self`、`text(&self) -> &str`、`number(&self) -> usize`、`first_word(&self) -> &str`（返回该行首个单词，空行返回 `""`，用 `unwrap_or` 不用裸 `unwrap`）
  - 方法签名**不写**显式生命周期（依赖省略规则第 3 条），体会"结构体定义必须写 `<'a>`、方法几乎不用写"的不对称
  - main 中对一段多行文本逐行构造 `LineView` 并打印行号与首个单词
- **验收**：`rustc --edition 2021 sol-02-line-view.rs -o /tmp/sol02 && /tmp/sol02` 编译零警告；输出每行的行号与首个单词；结构体不持有任何 `String`

## 练习 3：整理含泛型和生命周期的 where 子句（★★）

- **目标**：把生命周期约束 `'a: 'b` 与 trait bound 同时收进 where 子句，保持签名可读
- **要求**：
  - 实现 `fn echo_longest<'a, 'b, T>(x: &'a str, y: &'b str, tag: T) -> &'b str`：打印 `tag` 后返回 `x`、`y` 中较长者的引用，返回类型绑定较短的 `'b`
  - `<>` 中只保留参数名（`<'a, 'b, T>`），**全部约束**（`'a: 'b`、`T: Display`）写进 where 子句——想清楚为什么需要 `'a: 'b` 才能把 `&'a str` 当 `&'b str` 返回
  - main 中演示：`x` 在外层作用域、`y` 在内层作用域，返回值只能用在 `y` 存活期内（逃出作用域的版本保持注释，标注会报 E0597）
- **验收**：`rustc --edition 2021 sol-03-where-clause.rs -o /tmp/sol03 && /tmp/sol03` 编译零警告；约束全部位于 where 子句；内层打印较长者，外层打印 `done`

## 练习 4：把不必要的引用字段改成拥有字段（★★）

- **目标**：体会"拥有数据可简化生命周期"——`&'a str` 字段改 `String` 后生命周期参数整体消失
- **要求**：
  - 给定引用字段版本（保留为注释作对照）：
    ```rust
    struct Server<'a> { host: &'a str, endpoint: &'a str }
    ```
  - 改造成拥有字段 `String` 版本，实现 `new(host: &str, endpoint: &str) -> Self` 与 `host()` / `endpoint()` 访问器（返回 `&str`）
  - 改造前版本作为注释保留在文件里，并用注释标出 `<'a>` 共从几个位置消失（结构体定义、impl 块、每个使用处）
  - main 中证明改造收益：把多个 `Server` 存进 `Vec`，再把 `Vec` **move 进**一个函数统计数量——引用字段版本在这种所有权转移下需要处处携带 `<'a>`
- **验收**：`rustc --edition 2021 sol-04-owned-fields.rs -o /tmp/sol04 && /tmp/sol04` 编译零警告；`Vec<Server>` 成功 move 进函数并输出数量；代码中无生命周期参数

## 练习 5：制造并修复一个 E0597（★★★）

- **目标**：走通"复现 → 定位 → 三种方向修复"的完整套路
- **要求**：
  - 先写出无法编译的错误版本（返回局部值的引用），保留为注释，**首行注释必须写明"故意不通过编译"**：
    ```rust
    fn make_tag(id: u64) -> &str {
        let tag = format!("tag-{id}");
        &tag // error[E0597]
    }
    ```
  - 用三种方向各写一个修复版本：数据是新建的 → 返回拥有值 `String`；内容恒定 → 返回 `&'static str`；数据是传入的 → 返回输入切片（单输入，用省略规则即可，不写显式生命周期）
  - main 中分别调用三个修复版本并打印；代码中**不用裸 `unwrap`**（用 `unwrap_or` 或 `match`）
  - 在注释里用一句话说明每个修复版本"数据属于谁"
- **验收**：`rustc --edition 2021 sol-05-fix-e0597.rs -o /tmp/sol05 && /tmp/sol05` 编译零警告；三个修复版本输出正确；错误版本保持注释且首行标注"故意不通过编译"

> **提示**：练习 1~5 与主文档示例 1~5 一一对应（示例是"看"，练习是"做"）。卡壳时先回读主文档 3.x 对应小节（3.3 显式标注、3.4 结构体、3.6 where 子句、3.8 错误修复），最后再看 `sol-*`。
