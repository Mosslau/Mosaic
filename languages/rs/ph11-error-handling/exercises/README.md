# exercises —— 错误处理与工程质量阶段练习

完成顺序建议：按 1~5 顺序完成，对应主文档第 6 章示例 1~5 与第 3 章 3.1~3.6 的主题。参考实现在 `sol-*` 文件中，**先自己做，做完再看**。每题标注难度（★~★★★）。全部为单文件、零第三方依赖（错误处理全在 `std`，不依赖 cargo 联网），统一用 `rustc --edition 2021 -D warnings` 单文件编译（练习 5 加 `--test`）。

## 练习 1：Option/Result 组合子重构（★）

- **目标**：把「嵌套 match 分支」改写成组合子链（`map`/`and_then`/`or_else`/`ok_or_else`/`?`），理解组合子是"把错误处理写进数据流"
- **要求**：
  - 实现 `parse_key_value(line) -> Result<(&str, &str), String>`：用 `split_once` + `ok_or_else` + `?`（不许手写 `match`）
  - 实现 `lookup(lines, key) -> Result<&str, String>`：用 `find_map` + `match` 只做"key 是否匹配"判断，坏行忽略，找不到返回错误消息
  - 实现 `parse_port(line) -> Result<u16, String>`：用 `and_then` 链式「先解析行、再解析数字」；用 `or_else` 给失败提供默认端口 3000
  - 用 `assert_eq!` 断言关键结果；不写裸 `unwrap` 之外的 panic 路径
- **验收**：`rustc --edition 2021 -D warnings sol-01-combinator-refactor.rs -o /tmp/sol01 && /tmp/sol01` 编译零警告；输出含 `lookup host -> 127.0.0.1`、`lookup nope -> ERR 配置项 "nope" 不存在`、`parse_port ok -> 8080`、`parse_port fallback -> 3000`、`全部断言通过`

## 练习 2：为解析模块定义错误枚举（★★）

- **目标**：掌握自定义错误枚举的「三步走」（`Display` + `Error` + `From`），让 `?` 自动转换标准库错误，错误消息定位到行
- **要求**：
  - 定义 `ConfigError` 枚举，至少含：`Io(io::Error)`、`MissingEquals { line, text }`、`Parse { line, source: ParseIntError }`、`DuplicateKey(String)`
  - 手写 `Display`（每条消息含行号/文件名）、`Error`（`source()` 对包装底层错误的变体返回 `Some`）、`From<io::Error>`
  - `load_config(path) -> Result<HashMap<String, u32>, ConfigError>`：`io::Error` 走 `From` 自动转换；行内数字手动 `map_err`（要携带行号）
  - 打印正常路径与三种异常路径的 Display 消息与错误链（`source()` 逐层遍历），`assert_eq!`/`matches!` 断言
- **验收**：`rustc --edition 2021 -D warnings sol-02-config-error-enum.rs -o /tmp/sol02 && /tmp/sol02` 编译零警告；输出含 `场景 A: 第 2 行不是合法数字: invalid digit found in string`（链 2 层）、`场景 B: 读取配置失败: No such file or directory (os error 2)`（链 2 层）、`场景 C: 第 2 行缺少 '=' 分隔符: "no-equals-here"`、`场景 D: pool=16 retries=3`、`全部断言通过`

## 练习 3：为 I/O 错误添加上下文（★★）

- **目标**：掌握 `Box<dyn Error>`（开集错误）的上下文包装——`map_err` 把「哪个文件/哪一行」逐层包进消息，层间 `?` 直接传播
- **要求**：
  - `load(path) -> Result<String, Box<dyn Error>>`：`map_err` 把文件名包进上下文（`format!(...).into()` 装箱）
  - `parse_report(path) -> Result<Vec<u32>, Box<dyn Error>>`：逐行解析，`map_err` 带行号；`load` 的错误经 `?` 原样上传
  - 打印「内容不合法」与「文件不存在」两种场景的完整错误消息与错误链；`assert!` 断言
  - **思考题（写进注释）**：`String` 装箱的 `Box<dyn Error>` 没有 `source()` 层——为什么错误链只有一层？要多层链需要什么？（提示：自定义 `Error` 类型或 anyhow，见主文档 3.3/3.5）
- **验收**：`rustc --edition 2021 -D warnings sol-03-io-error-context.rs -o /tmp/sol03 && /tmp/sol03` 编译零警告；输出含 `场景 A（内容错误）: 解析 /tmp/ph11-sol03-data.csv 第 3 行不是数字: invalid digit found in string`、`场景 B（文件不存在）: 读取报告文件 /tmp/ph11-sol03-missing.csv 失败: No such file or directory (os error 2)`、`全部断言通过`

## 练习 4：panic 与 recover 边界（★★★）

- **目标**：理解 panic 与 Result 的分工——panic 是「不可恢复的不变量破坏」，recover 手段是 `catch_unwind` 与 `Mutex` 中毒恢复
- **要求**：
  - `catch_unwind` 截获一个 `panic!`，用 `downcast_ref::<&str>()` 拿回 payload 并 `assert_eq!` 断言消息
  - 开一个线程：持锁时 `panic!`（guard 存活到 panic），主线程 `m.lock()` 应得到 `Err`；打印中毒消息，用 `PoisonError::into_inner()` 取回 `MutexGuard` 并断言数据完好
  - 先绑定 `let lock_result = m.lock();` 再 `match`——体会为什么（临时值生命周期，E0597 的坑，见示例 5）
  - 在注释中写明：运行本文件时 stderr 会打印 2 行 panic 消息（panic hook 即使被捕获也会输出），退出码为 0
- **验收**：`rustc --edition 2021 -D warnings sol-04-panic-poison-recover.rs -o /tmp/sol04 && /tmp/sol04` 编译零警告；stdout 输出 `catch 到 panic: 服务启动失败: 端口被占用`、`锁中毒: poisoned lock: another task failed inside`、`into_inner 取回数据: [1, 2, 3]`、`全部断言通过`；stderr 有 2 行 panic 钩子输出，程序退出码 0

## 练习 5：补充正常路径和异常路径测试（★★★）

- **目标**：用 `rustc --test`（无需 cargo）为解析模块补单元测试，覆盖正常路径、异常路径、panic 契约，掌握 `Result` 返回测试与 `#[should_panic]`
- **要求**：
  - 实现 `parse_line` / `parse_config`（返回 `Result`，错误枚举 `ParseError` 实现 `Display` + `Error` + `PartialEq, Eq`）与便捷入口 `parse_config_checked`（非法输入按契约 `expect` panic）
  - `#[cfg(test)] mod tests` 至少 6 个测试：正常路径 ×2（单行、多行含空行）、异常路径 ×2（缺 `=`、重复 key）、`Result` 返回测试 ×1、`#[should_panic]` ×1
  - 测试通过 `assert_eq!` 对比错误枚举值与 `to_string()` 消息
- **验收**：`rustc --edition 2021 -D warnings --test sol-05-parser-tests.rs -o /tmp/sol05 && /tmp/sol05` 编译零警告；输出 `test result: ok. 6 passed; 0 failed`

> **提示**：练习 1~5 覆盖主文档第 6 章示例 1~5 的主题（示例是"看"，练习是"做"）。卡壳时先回读主文档 3.x 对应小节（3.1 组合子、3.2 自定义错误三步、3.3 Error trait 与 source、3.4 Box\<dyn Error\> 上下文、3.6 panic 与 recover），最后再看 `sol-*`。
