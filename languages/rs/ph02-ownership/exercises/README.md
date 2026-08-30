# ph02 所有权 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：rustc 1.92.0，单文件直接用 `rustc sol-XX-*.rs -o solXX` 编译。
> 本阶段只用 std 标准库，不引入第三方 crate。

## 练习 1：move 改借用（★）

**目标**：把会移动所有权的函数改成借用参数，调用后原变量仍可用。

**要求**：下面两个函数会吃掉传入的 `String`，导致调用方无法继续使用。改写签名与调用，使 `main` 里 `text` 在两个调用之后还能打印：

```rust
// 待改写（编译能过，但 main 里第二次使用 text 会报 E0382）
fn shout(s: String) -> String {
    s.to_uppercase()
}

fn len_of(s: String) -> usize {
    s.len()
}
```

- `shout` 改为返回**新** `String`、参数只借用
- `len_of` 改为纯只读借用
- 不允许使用 `.clone()`

**验收**：编译零警告；输出包含大写串、长度、以及调用后仍能打印的原始 `text`。

## 练习 2：String / &str / slice 转换（★★）

**目标**：练习 `String`、`&str`、`&[T]` 之间的零拷贝视图与拥有值转换。

**要求**：

- 写 `first_word(s: &str) -> &str`：返回第一个空格之前的切片（无空格则返回整个串），不分配新内存
- 写 `swap_to_owned(s: &str) -> String` 与 `as_view(s: &String) -> &str`：展示两种方向的转换
- 写 `tail(nums: &[i32]) -> &[i32]`：返回去掉首元素的子切片（空切片则返回空切片）

**验收**：编译零警告；`first_word("hello world")` 返回 `"hello"`；`tail(&[1, 2, 3])` 返回 `[2, 3]`；全程不出现 `clone`。

## 练习 3：修复借用检查错误（★★）

**目标**：读懂并修复两个最典型的借用检查错误。

**要求**：以下两段代码分别触发 E0382（move 后使用）和 E0502（不可变借用期间申请可变借用），在不改变程序意图的前提下修复它们：

```rust
// 错误 A：E0382
fn main() {
    let s = String::from("ownership");
    let t = s;
    println!("{} {}", s, t); // borrow of moved value
}
```

```rust
// 错误 B：E0502
fn main() {
    let mut v = vec![1, 2, 3];
    let first = &v[0];
    v.push(4); // cannot borrow as mutable
    println!("{} {:?}", first, v);
}
```

- 错误 A：优先用借用而非 `clone`
- 错误 B：优先缩短借用作用域（利用 NLL），而不是复制数据

**验收**：两个修复版本都编译零警告并输出预期结果；能口述每处错误「谁在哪一行借用了谁、冲突在哪」。

## 练习 4：去 clone 重写（★★★）

**目标**：把一个频繁 clone 的函数改写为借用版本，对比改动前后的所有权流向。

**要求**：下面的 `join_words` 每处理一个单词就 clone 一次，堆分配与拷贝次数都是 O(n²) 量级：

```rust
fn join_words(words: Vec<String>) -> String {
    let mut out = String::new();
    for w in words {
        let w = w.clone(); // 多余的 clone
        if !out.is_empty() {
            out.push_str(&w.clone()); // 又一次多余的 clone
            out.push(' ');
        }
        out.push_str(&w);
    }
    out
}
```

- 改写为 `fn join_words(words: &[String]) -> String`（或更通用的 `&[&str]`），全程不 clone
- 调用方保留 `words` 的 ownership，调用后还能打印它
- 在注释里写出改动前后「`words` 与每个 `String` 的 ownership 流向」对比（谁 move、谁借用、堆数据被复制几次）

**验收**：编译零警告；`join_words` 对 `["a", "bb", "ccc"]` 输出 `"a bb ccc"`；调用后 `words` 仍可用；函数体内不出现 `clone`。
