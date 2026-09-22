# examples —— 错误处理与工程质量阶段完整示例

对应主文档 `11-error-handling.md` 第 6 章示例 1~5 的完整可运行版本。全部为单文件、零第三方依赖（错误处理全在 `std`，不依赖 cargo 联网）。验证环境：rustc 1.92.0（macOS arm64），统一用 `rustc --edition 2021 -D warnings` 单文件编译（零警告）。

| 文件 | 对应示例 | 说明 | 编译 | 运行 |
|------|---------|------|------|------|
| `ex01-option-result-combinators.rs` | 示例 1 | Option/Result 组合子：`map`/`and_then`/`or_else`/`ok_or_else`/`?`，含 "key=value" 配置行解析（实测输出已写入注释） | `rustc --edition 2021 -D warnings ex01-option-result-combinators.rs -o /tmp/ex01` | `/tmp/ex01` |
| `ex02-custom-error-from.rs` | 示例 2 | 自定义错误类型三步走（Display + Error + From）：`PortError` 枚举、`?` 的 From 自动转换、Debug 输出与 source 链遍历（实测） | `rustc --edition 2021 -D warnings ex02-custom-error-from.rs -o /tmp/ex02` | `/tmp/ex02` |
| `ex03-error-trait-source.rs` | 示例 3 | Error trait 实现（Display + source）：`ScoreError` 两个变体都暴露底层原因，错误链逐层打印（场景 A 带行号、场景 B 带文件名，实测） | `rustc --edition 2021 -D warnings ex03-error-trait-source.rs -o /tmp/ex03` | `/tmp/ex03` |
| `ex04-box-dyn-error-context.rs` | 示例 4 | 错误上下文包装（`Box<dyn Error>`）：`map_err` 把「哪个文件/哪一行」包进上下文，层间 `?` 直接传播；`--fail` 模式演示 `main -> Result` 的退出行为（退出码 1） | `rustc --edition 2021 -D warnings ex04-box-dyn-error-context.rs -o /tmp/ex04` | `/tmp/ex04`（或 `/tmp/ex04 --fail`） |
| `ex05-panic-recover-boundary.rs` | 示例 5 | panic 与 recover 边界：`catch_unwind` 截获 panic、`unwrap` 的 panic 消息、`Mutex` 中毒（poisoned）与 `PoisonError::into_inner()` 恢复（panic/中毒消息均实测） | `rustc --edition 2021 -D warnings ex05-panic-recover-boundary.rs -o /tmp/ex05` | `/tmp/ex05` |

## 关于「故意出错 / 故意运行会 panic」的代码

- `ex04-box-dyn-error-context.rs`：带 `--fail` 运行时**故意让 `main` 返回 `Err`**——程序以退出码 1 结束，stderr 打印一行 `Error: "读取 ... 失败: No such file or directory (os error 2)"`（这是 Rust 对 `main -> Result` 失败时的标准输出，实测文本）。普通运行（不带参数）全部场景成功/失败都打印在 stdout，退出码 0。
- `ex05-panic-recover-boundary.rs`：文件内三处 panic 都不会让程序崩溃——前两处被 **`catch_unwind` 捕获**，第三处（子线程内）由**线程边界（spawn/join）收容**；但注意运行本文件时 **stderr 会打印 3 行 panic 消息**（panic hook 即使被捕获也会输出）：
  - `配置缺失: app.toml`
  - `called `Result::unwrap()` on an `Err` value: "parse failed"`
  - `持锁线程 panic`
  程序退出码为 0，正常继续——panic 消息文本为实测结果。

## 关于生态讲解（thiserror / anyhow / tracing）

本目录全部示例只用标准库。`thiserror`/`anyhow`/`tracing` 属于主文档 3.5/3.7 的生态讲解内容（roadmap 学习内容），本环境未安装验证，一律标注「未在本环境验证（需第三方 crate）」，不在本目录提供示例文件。

## 运行产物

编译产物输出到 `/tmp/`，验证后已删除，仓库内不留任何二进制文件。

五个示例均已在本环境编译零警告并运行验证（已验证：rustc 1.92.0，`rustc --edition 2021 -D warnings` 单文件编译）。ex05 的 panic 消息文本、ex02/ex03 的错误链遍历输出、ex04 的 `--fail` 退出行为均为实测结果。
