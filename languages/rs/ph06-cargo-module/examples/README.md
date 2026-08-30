# examples —— 模块化与 Cargo 阶段完整示例

对应主文档 `06-cargo-module.md` 第 6 章示例 1~5 的完整可运行版本。验证环境：rustc 1.92.0 + cargo 1.92.0。所有命令在对应子目录内执行。

| 目录 | 对应示例 | 说明 | 构建 | 运行 | 测试 |
|------|---------|------|------|------|------|
| `log-analyzer/` | 示例 1 | 单文件拆分为 lib.rs + 多模块文件（model/parser/service 三层 + bin 入口），含 5 个单元测试 | `cargo build` | `cargo run` | `cargo test` |
| `pub-api/` | 示例 2 | pub API 设计与可见性控制（pub / pub(crate) / 私有字段 / pub use 重导出），含 3 个单元测试 | `cargo build` | `cargo run` | `cargo test` |
| `json-cfg/` | 示例 3 | 添加第三方 crate 并固定版本（serde_json `=1.0.108` 精确锁定），含 2 个单元测试 | `cargo build` | `cargo run` | `cargo test` |
| `feat-demo/` | 示例 4 | features 特性开关（可选依赖 + `dep:` 语法 + 纯开关），含 2 个单元测试 | `cargo build` | `cargo run` | `cargo test` |
| `log-workspace/` | 示例 5 | workspace 管理多 crate（虚拟清单 + crates/ + path 依赖），含 3 个单元测试 | `cargo build --workspace` | `cargo run -p log-cli` | `cargo test --workspace` |

## 依赖说明

- 示例 1/2/5：纯标准库，零第三方依赖。
- 示例 3/4：需从 crates.io 拉取 serde / serde_json（本环境已验证网络可用，拉取成功）。

## feat-demo 特性组合命令对照

```bash
# 1. 默认构建（含 json 特性）
cargo build
# 2. 零依赖模式（关闭全部默认特性）
cargo run --no-default-features
# 3. 叠加 pretty 纯开关
cargo run --features pretty
# 4. 全开
cargo run --all-features
# 5. 查看特性开启来源
cargo tree -e features
```

## 运行产物

cargo 构建产物在各自 `target/` 目录，验证后已 `rm -rf target` 清理，不入仓库。

五个示例均已在本环境编译零警告、测试通过并运行验证（已验证，rustc 1.92.0）。
