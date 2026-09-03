# ph16 阶段项目：团队模板仓库（team-template）

对应 roadmap ph16 推荐项目「团队模板仓库：包含工具链文件、CI、格式化、lint 和 README 约定」。落地为一个**零依赖、clone 即用**的 cargo 工程模板：新成员 clone 后不需要问「装哪个版本、用什么格式化配置、CI 跑什么」——答案全部在仓库文件里。

## 需求

1. 工具链钉死：`rust-toolchain.toml` 声明 channel 与组件，rustup 自动选择/补齐。
2. 版本治理：`Cargo.toml` 声明 `rust-version`（MSRV），锁文件提交、`--locked` 守 CI。
3. 质量闸门：rustfmt 约定文件 + clippy 严格档（all + pedantic，`-D warnings`）。
4. CI：格式化 / lint / 测试（stable + MSRV 双工具链矩阵）/ 锁文件构建四道闸。
5. README 约定：依赖引入流程写明，零依赖起步。

## 功能清单

- [x] `rust-toolchain.toml`（channel = stable + rustfmt/clippy 组件）——`rustup show` 实测显示 overridden by
- [x] `Cargo.toml`：`edition = "2021"`、`rust-version = "1.85"`、`[lints.rust] unsafe_code = "deny"`、`[lints.clippy] all/pedantic = "warn"`
- [x] `Cargo.lock` 提交（version = 4 格式），`cargo build --locked` 通过
- [x] `rustfmt.toml`（只含 stable 选项），`cargo fmt --all --check` 零差异
- [x] clippy `--all-targets -- -D warnings` 零警告（含 pedantic）
- [x] `src/lib.rs`（领域逻辑 + 3 个单元测试）+ `src/main.rs`（薄入口）
- [x] `.github/workflows/ci.yml` 四 job（fmt / clippy / test 矩阵 stable+1.85.0 / locked-build）
- [x] 模板自带 README：快速开始 + 团队约定表 + 依赖引入登记表

## 构建与运行

```bash
# 1. 构建（锁文件守门）与测试
cd project/team-template
cargo build --locked
cargo test
# 2. lint 与格式化（与 CI 同闸门）
cargo clippy --all-targets -- -D warnings
cargo fmt --all --check
# 3. 运行
cargo run -- rust
# 4.（可选）确认 MSRV 声明被工具识别：cargo install cargo-msrv --locked 后
cargo msrv show
```

验证环境：rustc/cargo 1.92.0（macOS arm64，rustup 1.28.2）；零依赖、无需联网；CARGO_TARGET_DIR 指向 /tmp 时仓库零二进制残留。**已验证**（cargo msrv show 输出 `MSRV is Rust 1.85.0`，cargo-msrv 0.19.3）。

> ⚠️ 未在本环境验证：`.github/workflows/ci.yml`（本地无 GitHub Actions 运行环境）；CI 中 MSRV job 的 `1.85.0` 工具链安装（沙箱禁写 `~/.rustup`）。两者均为通行写法，语法遵循 GitHub Actions 与 dtolnay/rust-toolchain 官方文档。

## 实测输出

```text
$ cargo test
running 3 tests
test result: ok. 3 passed; 0 failed; ...

$ cargo clippy --all-targets -- -D warnings
    Finished `dev` profile ... （零警告）

$ cargo run -- rust
hello, rust!
template MSRV: Rust 1.85（见 Cargo.toml rust-version）
```

## 验收标准

- `cargo build --locked` / `cargo test` / `cargo clippy --all-targets -- -D warnings` / `cargo fmt --all --check` 全部通过（已验证）
- `rustup show` 显示工具链由 `rust-toolchain.toml` override（已验证）
- `cargo msrv show` 识别 `rust-version = "1.85"`（已验证，cargo-msrv 0.19.3）
- CI 四道闸与本地命令一一对应（CI 本身未在本环境验证）

## 扩展方向（可选）

- 把模板改成 workspace（`[workspace]` + 多 crate），观察 rust-toolchain.toml 对整个 workspace 生效——工作区组织属 ph06 已讲，这里只体会「一份工具链文件管全部」
- 给 CI 加依赖审计 job（cargo-deny / cargo-audit）——**供应链安全属于 ph24 安全、供应链与发布阶段（roadmap 第 24 节，目录待建）**，这里只留扩展位
- 用 examples/ex03 的流程把模板升到 edition 2024，记录迁移 diff——注意 `[lints]` 与 rust-version 在 2024 下的 resolver v3 行为（主文档 3.6 已实测）
- crate 选型与依赖树膨胀控制是下一阶段 [ph17 Crate 生态选择与常用库阶段](../../ph17-crate-ecosystem/17-crate-ecosystem.md) 的主题，模板的「依赖引入约定」表即为其伏笔
