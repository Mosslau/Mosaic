# exercises —— 模块化与 Cargo 阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。

完成顺序建议：按 1~5 顺序完成。练习 1/2/5 对应 roadmap 承诺的三个练习（把单文件项目拆成 model/parser/service、添加第三方 crate 并固定版本、创建 workspace 管理多个 crate），练习 3/4 进阶到单元测试与质量门禁、features 可选能力——覆盖主文档第 3.9 节 cargo 工作流。

练习 1/2 为单 crate 多文件、练习 3/4 为单 crate、练习 5 为 workspace，均用 cargo 组织，sol-* 参考实现以子目录形式给出完整 cargo 项目。

## 练习 1：把单文件项目拆成 model、parser、service（★★）

**目标**：把给定单文件程序拆成 model / parser / service 三层多文件结构，行为完全不变

**要求**：
- 起点代码在 [`ex01-single-source.rs`](./ex01-single-source.rs)：一个完整可运行的"温度记录统计"程序，解析 `ts\tcity\ttemp` 制表符分隔的日志行，按城市统计平均温度
- 用 `cargo new temp-stats` 建项目，拆成 `src/model.rs`（数据模型）、`src/parser.rs`（解析）、`src/service.rs`（聚合统计）、`src/lib.rs`（模块树入口）、`src/main.rs`（入口）
- 模块依赖方向：`main → service → parser → model`，model 不依赖任何人
- 为 parser 与 service 各写至少 2 个单元测试（`#[cfg(test)] mod tests`）

**验收**：`cargo run` 输出与单文件版本一致；`cargo test` 全部通过；`src/model.rs` 中不出现 `use crate::parser` / `use crate::service`（依赖方向正确）。

## 练习 2：添加第三方 crate 并固定版本（★★）

**目标**：用 `cargo add` 引入 serde_json 并把版本精确锁定，理解 Cargo.lock 才是真正的版本锁

**要求**：
- `cargo new json-user-db`，用 `cargo add serde_json@1.0.108` 添加依赖（精确版本）
- 解析一个 JSON 用户列表 `{"users":[{"name":"alice","age":30},{"name":"bob","age":25}]}`：输出用户数、按年龄排序后的名字列表
- 用 `cargo tree` 观察依赖树，确认 serde_json 版本为 1.0.108

**验收**：`Cargo.lock` 中 `serde_json` 精确版本为 `1.0.108`；`cargo run` 输出用户数与排序后的名字；`cargo tree` 能显示 serde_json 依赖链。

## 练习 3：为库 crate 编写单元测试并跑通质量门禁（★★）

**目标**：给库 crate 补齐 `#[cfg(test)]` 单元测试，并跑通 `cargo fmt --check` / `cargo clippy -- -D warnings` / `cargo test` 质量门禁三连

**要求**：
- `cargo new int-stats --lib`，实现四个函数：`sum(&[i64]) -> i64`、`avg(&[i64]) -> Option<i64>`（空输入返回 `None`）、`min(&[i64]) -> Option<i64>`、`max(&[i64]) -> Option<i64>`
- 为每个函数写测试：正常输入、单元素、空输入（`None`）、负数
- 修好所有 `cargo clippy -- -D warnings` 报出的问题（提示：`avg` 用整数除法前先想好语义）

**验收**：`cargo test` 全部通过；`cargo fmt --check` 零输出；`cargo clippy -- -D warnings` 零警告；空输入调用 `avg/min/max` 返回 `None` 而不是 panic。

## 练习 4：用 features 给项目加一个可选能力（★★★）

**目标**：用 features + optional 依赖 + `#[cfg(feature = "...")]` 给命令行工具加"JSON 输出"可选能力

**要求**：
- `cargo new fmt-out`，实现一个简单的表格格式化工具：`format_table(&[(String, i32)]) -> String` 输出两列文本表格
- 加特性：`default = ["text"]`、`text` 纯开关、`json = ["dep:serde_json"]`（optional 依赖 `serde_json = { version = "1.0.108", optional = true }`）
- `#[cfg(feature = "json")]` 下新增 `format_json(&[(String, i32)]) -> serde_json::Result<String>`，输出 JSON 对象数组
- main 按启用特性输出不同格式

**验收**：`cargo run`（默认）输出文本表格；`cargo run --features json` 输出 JSON；`cargo run --no-default-features` 不依赖 serde_json 也能编译运行；`cargo tree -e features` 能看到 json 特性的开启来源。

## 练习 5：创建一个 workspace 管理多个 crate（★★★）

**目标**：从零创建 workspace：一个库 crate + 一个二进制 crate，用 path 依赖协作

**要求**：
- 根 `Cargo.toml` 虚拟清单（`[workspace]` + `members`），成员放 `crates/` 目录
- `crates/word-count-core`：库，`count_words(&str) -> usize`（按空白分词，跳过空串）
- `crates/word-count-cli`：二进制，path 依赖 core，读入嵌入文本输出"单词数: N"
- 继承根清单元数据（`version.workspace = true` / `edition.workspace = true`）
- 给 core 写单元测试

**验收**：`cargo build --workspace` 一次构建全部成员；`cargo run -p word-count-cli` 输出正确单词数；`cargo test --workspace` 全绿；根目录只有一份 `Cargo.lock`。

> **提示**：练习 1/2/5 与主文档第 6 章示例 1/3/5 主题一致但实现不同（温度统计 vs 日志解析、用户列表 vs 配置解析、单词统计 vs 日志聚合）——先独立完成，再对照 `examples/` 查漏。`sol-*` 为参考实现（目录内头注释已注明对应练习），做完再看。
