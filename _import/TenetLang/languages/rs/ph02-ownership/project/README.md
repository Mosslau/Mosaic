# ph02 阶段项目：文本统计器

## 需求

对应 Roadmap「Rust 所有权 Ownership 阶段」推荐项目。实现一个文本统计器：从标准输入读取多行文本，统计行数、单词数、最长单词，**全程零 clone**——统计函数只借用 `&str`，最长单词返回指向输入文本的切片，不分配新内存。核心逻辑附带 `#[test]` 单元测试。

## 功能清单

- [x] 从标准输入读取多行文本（EOF 结束，支持管道喂入）
- [x] 统计行数（`str::lines`）
- [x] 统计单词数（按空白分割）
- [x] 找出最长单词并输出其长度，空输入输出 `N/A`
- [x] 统计函数全部接受 `&str` / 返回 `&str`，不调用 `.clone()`
- [x] `analyze` 汇总为 `Stats` 结构体，`longest` 字段借用输入文本（零拷贝视图）
- [x] 核心逻辑有单元测试覆盖（9 个用例）

## 验收标准

- `cargo test` 全部通过
- `printf 'hello world\nrust ownership\n' | cargo run` 输出 `lines: 2`、`words: 4`、`longest: ownership (len=9)`
- 空输入（直接 EOF）输出 `lines: 0`、`words: 0`、`longest: N/A`，不 panic
- 多余空白（连续空格、空行）不影响单词计数
- 源码中不出现 `.clone()`

## 扩展方向（可选）

- 支持从文件路径读取（`std::fs::read_to_string` + 命令行参数解析，可在学完 ph06 Cargo 与模块化后实现）
- 统计字符数、字节数、每个单词出现频率（需要 `HashMap`，属于 ph03/ph09 的内容）
- 把统计逻辑拆成 lib crate + bin crate —— 属于 ph06 模块化与 Cargo 阶段

## 验证环境

rustc/cargo 1.92.0，edition 2021。构建：`cargo build`；运行：`cargo run < input.txt`；测试：`cargo test`。已在本环境验证：9 个单元测试全部通过，管道输入的统计结果符合验收标准。
