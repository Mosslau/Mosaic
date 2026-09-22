# team-template —— 团队 Rust 项目模板

> 一句话：clone 即用——工具链、格式化、lint、CI、锁文件策略全部就位，新成员第一天不用问「该装什么版本」。

## 快速开始

```bash
# 1. 进入目录，rustup 自动按 rust-toolchain.toml 选择工具链并补齐 rustfmt/clippy
rustup show
# 2. 构建 / 测试 / lint / 格式化检查（与 CI 四道闸完全一致）
cargo build --locked
cargo test
cargo clippy --all-targets -- -D warnings
cargo fmt --all --check
```

## 团队约定（本模板的 README 约定部分）

| 约定 | 落点 | 说明 |
|------|------|------|
| 工具链钉死 | `rust-toolchain.toml` | 跟随 stable；发布审计期改精确版本号并全队同步 |
| MSRV 声明 | `Cargo.toml` 的 `rust-version = "1.85"` | CI 矩阵跑 stable + 1.85.0 双工具链；改动 MSRV 必须同 PR 改 CI |
| 格式化 | `rustfmt.toml` + `cargo fmt --all --check` | 只允许 stable 选项；PR 必须先过 fmt |
| lint | `Cargo.toml` 的 `[lints]` 表 | clippy all+pedantic；误报用 `#[allow]` 点杀并写理由；`unsafe_code = "deny"` |
| 锁文件 | 提交 `Cargo.lock`，CI 用 `--locked` 守门 | 应用型仓库；改库型时在 `.gitignore` 加 `Cargo.lock` |
| 依赖引入 | 本节下方登记 | 加依赖前在 PR 描述写「用途 / 维护活跃度 / 替代品」三行 |

### 依赖引入约定

当前依赖：无（零依赖起步）。

新增依赖时在 PR 中填写：

```text
- crate 名 + 版本：
- 用途：
- 维护活跃度（最近发布 / issue 响应）：
- 替代品与放弃它们的理由：
- MSRV 影响（其 rust-version 是否高于 1.85）：
```

## 目录结构

```text
team-template/
├── Cargo.toml                 # 包清单 + rust-version + [lints] 集中声明
├── Cargo.lock                 # 锁文件（提交！应用可复现构建的根基）
├── rust-toolchain.toml        # 工具链开关（channel + components）
├── rustfmt.toml               # 格式化约定（stable 选项）
├── .gitignore                 # /target；不忽略 Cargo.lock
├── .github/workflows/ci.yml   # CI：fmt / clippy / test(stable+MSRV) / --locked build
└── src/
    ├── lib.rs                 # 领域逻辑（可测试）
    └── main.rs                # 入口（只做参数解析与打印）
```
