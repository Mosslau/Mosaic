# 04 · Option/Result 错误处理

> demo: `cargo run --bin 04_option_result`

## 1. 设计动机

C 用错误码（容易漏检查），C++/Java/Python 用异常（隐式控制流，性能有争议，
出错路径不清晰）。Rust 的命题：**错误是返回值的一部分，类型系统强迫你处理**。

## 2. 机制拆解

两个枚举撑起整个错误处理体系：

```rust
enum Option<T> { None, Some(T) }      // 可能没有值（替代 null）
enum Result<T, E> { Ok(T), Err(E) }   // 可能失败（替代异常）
```

**关键设计**：`Option`/`Result` 是**普通类型**，不是语言特性——
`match` 必须穷尽所有分支，所以"忘记处理 None/Err"是编译错误，不是运行时事故。

```rust
fn parse(s: &str) -> Result<i64, String> {
    s.parse().map_err(|_| format!("不是数字: {s}"))
}
```

**`?` 运算符**：错误向上传播的语法糖——`Err` 直接 return，`Ok` 解包继续：

```rust
fn read_and_parse(path: &str) -> Result<i64, String> {
    let s = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    parse(&s)?                     // 两处失败都在这里一行搞定
}
```

**没有 null**：`Option` 让"空值"显式化——不会出现解引用 null 的崩溃。

## 3. 代码验证（demos/04_option_result.rs）

demo 演示：`Option` 消除空值恐慌、`Result` + `?` 链式传播错误、
`match` 穷尽性强迫处理。

## 4. 代价与取舍

| 代价 | 说明 |
|------|------|
| 样板代码 | 每个调用都要处理 Ok/Err（? 已大幅缓解） |
| 心智负担 | 错误类型要设计（自定义 Error 类型） |
| 与异常互操作 | FFI 时和抛异常的代码对接别扭 |

**换来的**：错误路径显式、可静态追踪；不会漏检查；无异常开销。

## 5. 对 Tenet 的启示

- ✅ **吸收"错误是显式的、可追踪的"**：Tenet 的解释器错误（`TenetError`）贯穿
  词法→语法→解释→代码生成全链路，错误带 `[行:列]` 位置——这就是
  "错误是值、不是意外"思想的体现
- ✅ **吸收"失败要带上下文"**：Rust 的 `map_err` 文化（包装错误信息）对应
  Tenet 的 `期望 X，但遇到 Y` 式报错
- ❌ **拒绝把错误处理语法引入语言**：教学阶段 `print` 内建 + 运行时错误足够；
  若未来加 IO/文件，再引入 Result 风格
- 💡 Tenet 的 `error.rs` / `error.py` / `error.hpp` 三端错误类型，
  正是"错误即值"的最小实践

**一句话**：Rust 让错误处理从"异常黑盒"变成"类型系统里的显式值"；
Tenet 用它最小的形态（统一错误类型 + 位置信息）继承了这个思想。
