# examples —— Crate 生态选择与常用库阶段完整示例

对应主文档 `17-crate-ecosystem.md` 第 6 章示例 1~5。本阶段的「代码」分两类：**shell 演练脚本**（ex01/ex05，自带命令流水线，产物落 `/tmp/`，可重复运行）与 **cargo 工程**（ex02/ex03/ex04，完整 Cargo.toml + src/main.rs）。

验证环境：rustc/cargo 1.92.0（macOS arm64，rustup 1.28.2 管理）；涉及 crates.io 依赖的示例（ex02/ex03/ex04/ex05）需**联网拉取 crate**，国内网络可在命令前配置 rsproxy 镜像（`export CARGO_HOME=...` + `[source.crates-io] replace-with = "rsproxy"`，写法见 ph16 examples 的 ex04/ex05 注释）。**验证说明**：ex02 已在 cargo 1.92.0 本机实测构建+运行通过并标注「已验证」；其余示例标注「未在本环境验证」（依赖 crate 未入本机缓存，需联网拉取），命令在联网环境按序执行即可复现。

## 示例清单

| 文件 | 对应主文档 | 说明 | 运行命令 | 验证状态 |
|------|-----------|------|---------|---------|
| `ex01-crate-review.sh` | 示例 1 / 3.2 | 六维评审命令流水线：crates.io API 活跃度 + cargo tree + cargo audit | `bash ex01-crate-review.sh <crate名>` | 未在本环境验证 |
| `ex02-serde-basics/` | 示例 2 / 3.3 | serde derive + 字段属性 + 枚举标签 + Value 动态解析 | `cd ex02-serde-basics && cargo run` / `cargo test` | 已验证（本机实测构建+运行） |
| `ex03-clap-cli/` | 示例 3 / 3.6 | clap 4 derive：flag / 选项 / 子命令 + 单元测试 | `cd ex03-clap-cli && cargo run -- --help` | 未在本环境验证 |
| `ex04-tracing-log/` | 示例 4 / 3.7 | tracing span/event/结构化字段 + EnvFilter + instrument | `cd ex04-tracing-log && RUST_LOG=ph17_demo=debug cargo run` | 未在本环境验证（需访问 example.com） |
| `ex05-cargo-tree-features.sh` | 示例 5 / 3.9/3.10 | cargo tree 四用法 + feature 并集对照实验 | `bash ex05-cargo-tree-features.sh` | 未在本环境验证 |

## 示例 1：crate 六维评审流水线（ex01-crate-review.sh）

脚本把主文档 3.2 的六维清单翻译成可执行的命令序列，输入一个 crate 名，依次产出：**① 维护活跃度**（crates.io API：最近版本/更新时间/下载量）→ **③ 依赖树膨胀**（`cargo tree --depth 2` 与 `-d` 重复版本）→ **⑤ 已知漏洞**（`cargo audit`）→ **④ 许可证**（`cargo deny check licenses`，可选）。⑥ MSRV 维度由 `cargo metadata` 承接（见 ph16 sol-02），脚本在末尾提示补查。

```bash
# 1. 完整评审流水线（建议在临时空 crate 目录执行，先 cargo init）
bash examples/ex01-crate-review.sh serde
# 2. 只跑前半段（不装 cargo-audit/cargo-deny 也能跑：脚本对缺失工具自动跳过）
```

## 示例 2：serde 序列化教学（ex02-serde-basics/）

一个小工程演示 3.3 的四个点：**derive 序列化/反序列化、字段属性（default / rename）、枚举标签（tag + rename_all）、Value 动态解析**。内嵌 1 个 round-trip 单元测试。

```bash
cd examples/ex02-serde-basics
cargo run     # 打印 pretty JSON、round-trip 断言、枚举标签 JSON、Value 读取
cargo test    # 1 个测试：序列化 → 反序列化 → 相等
```

预期输出形态（crate 版本不同输出可能微调，结构不变）：`{ "name": "serde", "stars": 10000, ... }` → `round-trip ok` → `{"type":"push","branch":"main"}`。

## 示例 3：clap CLI 教学（ex03-clap-cli/）

演示 clap 4 derive 的三件套：flag（`--verbose`）、选项（`--count`，带默认值）、子命令（`greet` / `show`）。`--help` 自动生成，非法参数自动报错退出。

```bash
cd examples/ex03-clap-cli
cargo run -- --help
cargo run -- greet world
cargo run -- --count 3 --verbose greet rust
cargo run -- show --json
cargo test    # 2 个解析测试
```

## 示例 4：tracing 日志教学（ex04-tracing-log/）

演示 3.7 的核心：`tracing_subscriber::fmt` + `EnvFilter` 订阅、`#[instrument]` 自动开 span、结构化字段、`.instrument(span)` 把 span 绑到 future。

```bash
cd examples/ex04-tracing-log
RUST_LOG=ph17_demo=debug cargo run   # 需联网（示例请求 https://example.com）
# 期望看到带 span 上下文（job_id=42）与结构化字段（url / bytes / len）的日志行
```

## 示例 5：feature flags 与依赖治理命令演示（ex05-cargo-tree-features.sh）

脚本在 `/tmp/ph17-ex05-features` 建演示 crate，跑 `cargo tree -e features` / `-d` / `-i`，再做一次「关默认特性」对照实验，观察 **feature 统一**（serde_json 依赖 serde 的 std，所以你自己关了 serde 默认特性，最终并集里 std 依然在）。

```bash
bash examples/ex05-cargo-tree-features.sh
```

## 运行注意事项

- ex01/ex05 是 shell 脚本，会在自己的 /tmp 工作目录里操作，可重复运行；ex01 建议在空 crate 里跑，ex05 自带建 crate 步骤
- ex02/ex03/ex04 首次构建需联网拉取 crate（国内网络配 rsproxy）；ex04 运行本身还要访问 `https://example.com`
- ex01 的 `cargo audit` / `cargo deny` / `cargo semver-checks` 为可选子命令，未安装时脚本跳过并提示；它们的安装与行为以各自仓库 README 为准

## 验证状态汇总

- ex01：评审命令流水线——未在本环境验证（crates.io API 与 cargo audit 需联网）。
- ex02：serde 教学工程——已验证（cargo 1.92.0 本机实测构建+运行通过）。
- ex03：clap 教学工程——未在本环境验证（需 cargo 联网拉 clap）。
- ex04：tracing 教学工程——未在本环境验证（需拉 tokio/reqwest/tracing + 访问 example.com）。
- ex05：cargo tree 演示脚本——未在本环境验证（需 cargo 联网拉 serde/serde_json/itoa 等演示依赖）。
