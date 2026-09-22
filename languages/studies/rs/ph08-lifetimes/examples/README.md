# examples —— 生命周期 Lifetime 阶段完整示例

对应主文档 `08-lifetimes.md` 第 6 章示例 1~5 的完整可运行版本。全部为单文件、零第三方依赖。验证环境：rustc 1.92.0（macOS arm64）。

| 文件 | 对应示例 | 说明 | 编译 | 运行 |
|------|---------|------|------|------|
| `ex01-longest.rs` | 示例 1 | 返回引用的函数加生命周期：两个输入 + 一个输出时省略规则失效（E0106），`longest<'a>` 显式绑定输出归属 | `rustc --edition 2021 ex01-longest.rs -o /tmp/ex01` | `/tmp/ex01` |
| `ex02-config-view.rs` | 示例 2 | 结构体持有引用：`ConfigView<'a>` 零拷贝借用配置原文，`from_text(&'a str) -> ConfigView<'a>` 绑定输入生命周期 | `rustc --edition 2021 ex02-config-view.rs -o /tmp/ex02` | `/tmp/ex02` |
| `ex03-where-lifetime.rs` | 示例 3 | 生命周期 + 泛型组合：`'a: 'b` 生命周期约束与 `T: Display` trait bound 同处 where 子句 | `rustc --edition 2021 ex03-where-lifetime.rs -o /tmp/ex03` | `/tmp/ex03` |
| `ex04-owned-fields.rs` | 示例 4 | 引用字段改拥有字段：`&'a str` → `String` 后 `<'a>` 从结构体、impl 块、所有使用处整体消失 | `rustc --edition 2021 ex04-owned-fields.rs -o /tmp/ex04` | `/tmp/ex04` |
| `ex05-fix-e0597.rs` | 示例 5 | 修复 E0597 的三种方向：返回拥有值 / 返回 `&'static str` / 返回输入切片（错误版本已注释，仅作对照） | `rustc --edition 2021 ex05-fix-e0597.rs -o /tmp/ex05` | `/tmp/ex05` |

## 关于"故意出错"的代码

- `ex01-longest.rs`、`ex03-where-lifetime.rs` 中各有一行被注释掉的 `println!`，取消注释会触发 E0597——这是故意保留的对照，请勿取消注释后指望编译通过。
- `ex05-fix-e0597.rs` 文件头部的"错误版本"块整体被注释，取消注释无法通过编译（E0597），仅用于与修复版本对照。

## 运行产物

编译产物输出到 `/tmp/`，验证后已删除，仓库内不留任何二进制文件。

五个示例均已在本环境编译零警告并运行验证（已验证：rustc 1.92.0，`rustc --edition 2021` 单文件编译）。
