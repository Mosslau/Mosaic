# 01 · 所有权与借用（Ownership & Borrowing）

> demo: `cargo run --bin 01_ownership`

## 1. 设计动机

C 语言把内存安全完全交给程序员：`malloc` 后忘 `free` 就泄漏，`free` 后再用就悬垂。
C++ 用 RAII + 智能指针缓解，但**裸指针仍然合法**，悬垂/use-after-free 依旧是 UB。
Rust 的命题是：**能不能让"谁拥有这块内存、谁可以访问它"成为编译期规则，从源头消灭这类 bug？**

## 2. 机制拆解

三条规则，编译器强制执行：

```text
1. 每个值有且只有一个 owner（所有者）
2. owner 离开作用域，值被自动释放（无 GC，无手动 free）
3. 可以借用（& 不可变借用 / &mut 可变借用），但同一时刻：
   - 要么任意多个不可变借用
   - 要么只有一个可变借用
   - 不能同时存在
```

**move 语义**：把值赋给另一个变量 = 所有权转移，旧变量失效：

```rust
let s = String::from("tenet");
let t = s;          // 所有权 move 给 t
// println!("{s}"); // 编译错误！s 已失效（use of moved value）
println!("{t}");    // t 是现在的 owner
```

**借用**：只想"看一眼"不需要拥有：

```rust
fn len(s: &String) -> usize { s.len() }   // 不可变借用
let s = String::from("tenet");
println!("{}", len(&s));                   // 借完还能用
println!("{}", s);                         // s 仍有效
```

## 3. 代码验证（demos/01_ownership.rs）

demo 里演示了 move、借用、可变借用，以及**注释掉的编译错误**——把注释打开，
`cargo build` 会拒绝编译，亲眼看到 borrow checker 在工作。

## 4. 代价与取舍

| 代价 | 说明 |
|------|------|
| 学习曲线陡 | 概念密度高，初学被 borrow checker 反复教育 |
| 表达受限 | 自引用结构、图结构很难写（需要 unsafe 或间接层） |
| 代码啰嗦 | 生命周期、Rc/Arc、clone 的噪音 |
| 编译器复杂 | 借用检查是 rustc 里最复杂的部分之一 |

**换来的**：悬垂指针、use-after-free、double-free、迭代器失效这类 bug
在 C/C++ 里能潜伏多年，在 Rust 里是编译错误。

## 5. 对 Tenet 的启示

- ✅ **吸收"值有明确生命周期"的思想**：Tenet 目前用引用计数式的环境（Rc）管理作用域，
  没有裸指针，天然无悬垂问题——这是"最小语言"下所有权思想的最简实现
- ✅ **吸收"可变性默认收敛"的精神**：Tenet 的变量可重新赋值，但**没有指针**，
  从根上避免别名与修改的冲突
- ❌ **拒绝完整借用检查**：对教学语言，borrow checker 的复杂度远超收益；
  Tenet 用「无指针 + 值语义」绕过了整个问题域
- 💡 未来若加 struct + 引用，需要重新评估是否引入借用规则

**一句话**：Rust 用「所有权」把 C 时代的运行时 bug 变成编译错误；
Tenet 用「没有指针」把同一类 bug 变成不可能。
