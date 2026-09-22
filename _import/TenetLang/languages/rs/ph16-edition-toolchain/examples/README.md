# examples —— Edition、工具链与版本管理阶段完整示例

对应主文档 `16-edition-toolchain.md` 第 6 章示例 1~5。本阶段的「代码」大部分是**命令与配置**而不是 Rust 源文件——五个示例里四个是 shell 演练脚本（自带工作目录、可重复运行、产物全部落在 `/tmp/`）。

验证环境：rustc/cargo 1.92.0（macOS arm64，rustup 1.28.2 管理的 stable-aarch64-apple-darwin）；涉及 crates.io 依赖的示例（ex04/ex05）经 rsproxy 国内镜像拉取。

## 示例清单

| 文件 | 对应示例 | 说明 | 运行命令 | 验证状态 |
|------|---------|------|---------|---------|
| `ex01-toolchain-file/` | 示例 1 | rust-toolchain.toml 实战：目录级 override 生效观察（`rustup show` 显示 overridden by） | 见下 | 已验证（channel="stable" 路径） |
| `ex02-edition-diff.sh` | 示例 2 | Edition 差异实测矩阵：同一代码在 2015/2018/2021/2024 四个 edition 下的编译结果 | `bash ex02-edition-diff.sh` | 已验证 |
| `ex03-cargo-fix-migration.sh` | 示例 3 | cargo fix --edition 迁移演练：2015 → 2018 → 2021 → 2024 全流程 | `bash ex03-cargo-fix-migration.sh` | 已验证 |
| `ex04-msrv-check.sh` | 示例 4 | MSRV：resolver v3 的 MSRV 感知实测 + 依赖 rust_version 提取 + cargo-msrv | `bash ex04-msrv-check.sh` | 已验证（verify 子命令除外，见下） |
| `ex05-cargo-lock.sh` | 示例 5 | Cargo.lock 策略：应用提交/库不提交、升级回退、`--locked` 守门 | `bash ex05-cargo-lock.sh` | 已验证 |

## 示例 1：rust-toolchain.toml 实战（ex01-toolchain-file/）

`ex01-toolchain-file/` 里放了一份真实的 `rust-toolchain.toml`（`channel = "stable"` + 组件 rustfmt/clippy）和一个最简 `hello.rs`。在该目录下：

```bash
# 1. 观察 override 生效
rustup show
# 2. 确认 rustc 走该文件选中的通道
rustc --version
# 3. 编译运行（产物落 /tmp）
rustc --edition 2021 -D warnings hello.rs -o /tmp/ph16-ex01-hello
/tmp/ph16-ex01-hello
```

实测输出（rustc 1.92.0）：`rustup show` 的 active toolchain 一节显示

```text
active toolchain
----------------
name: stable-aarch64-apple-darwin
active because: overridden by '<...>/examples/ex01-toolchain-file/rust-toolchain.toml'
```

`hello` 运行输出 `hello from the toolchain pinned by rust-toolchain.toml` / `1 + 1 = 2`。

> ⚠️ `rust-toolchain.toml` 是「目录级开关」：凡是放在仓库里的该文件，对所有进入该目录执行 cargo/rustc 的人生效。本示例故意用 `channel = "stable"`（任何装了 rustup 的机器都有）；若钉精确版本号（如 `"1.92.0"`），rustup 会在缺失时联网下载——下载行为在本环境因沙箱禁写 `~/.rustup` 未实测，语义以 rustup 官方文档为准。

## 示例 2：Edition 差异实测矩阵（ex02-edition-diff.sh）

脚本在 `/tmp/ph16-ex02-edition-diff` 生成四个演示文件，分别用 `--edition 2015/2018/2021/2024` 编译（同一条 rustc 1.92.0，`-D warnings`），打印矩阵与失败案例的首条错误原文。实测矩阵：

| 案例 | 2015 | 2018 | 2021 | 2024 | 关键错误（实测原文） |
|------|------|------|------|------|---------------------|
| a_closure_capture（move 闭包字段捕获） | 失败 | 失败 | 通过 | 通过 | `error[E0382]: borrow of moved value: cfg` |
| b_array_into_iter（数组 into_iter 按值） | 失败 | 失败 | 通过 | 通过 | `error[E0308]: mismatched types`（expected `i32`, found `&{integer}`） |
| c_gen_keyword（`gen` 变量名） | 通过 | 通过 | 通过 | 失败 | `error: expected identifier, found reserved keyword \`gen\`` |
| d_unsafe_extern（裸 extern 块） | 通过 | 通过 | 通过 | 失败 | `error: extern blocks must be unsafe` |

最后脚本用 2021 edition 编译通过版并运行：`host = localhost` / `port = 8080` / `10 20 30` / `42` / `3`。

## 示例 3：cargo fix --edition 迁移演练（ex03-cargo-fix-migration.sh）

脚本在 `/tmp/ph16-ex03-migdemo` 建一个 edition 2015 的 crate（`try!` 宏、裸 trait object `Box<Fn>`、变量名 `gen`），逐步执行迁移。实测流程与关键观察：

```text
0. 起点：edition = "2015"，cargo build 只有警告（bare_trait_objects 等）
1. cargo fix --edition --allow-no-vcs   → Fixed src/main.rs (1 fix)：try! → r#try!
   ⚠️ 打印 "Migrating Cargo.toml from 2015 edition to 2018" 但【实测不改写 Cargo.toml】，
      edition 字段必须手工 bump
2. cargo fix --edition（2018→2021）     → Box<Fn(&str)> → Box<dyn Fn(&str)>
   手工：r#try! → ?（cargo fix 不做，只报 deprecated 警告）；bump edition = "2021"
3. cargo fix --edition（2021→2024）     → Fixed src/main.rs (2 fixes)：let gen → let r#gen
   手工：bump edition = "2024"
4. 终验：RUSTFLAGS="-D warnings" cargo build 零警告；运行输出 [log] port = 8080 / gen = 1
```

`--allow-no-vcs` 仅因演练目录不在 git 仓库里；真实项目中 cargo fix 要求工作区干净，用 git 状态当迁移前快照。

## 示例 4：MSRV 检查（ex04-msrv-check.sh）

脚本在 `/tmp/ph16-ex04-msrv` 建两个 crate 做 resolver 对照实验，再提取依赖 MSRV。实测输出要点：

1. **resolver v3（edition 2024 默认）MSRV 感知**：项目声明 `rust-version = "1.85"`，依赖 `home = "0.5"` 的最新版 0.5.12 要求 Rust 1.88 —— cargo 输出 `Locking 11 packages to latest Rust 1.85 compatible versions` + `Adding home v0.5.11 (available: v0.5.12, requires Rust 1.88)`，自动选中兼容的 0.5.11。
2. **resolver v2（edition 2021 默认）无感知**：同样的依赖直接锁到 0.5.12（在 Rust 1.85 的机器上会编译失败）。
3. **依赖 MSRV 提取**：`cargo metadata --format-version 1` + python3 打印每个包的 `rust_version`（实测：`home 0.5.11 → 1.81`、`windows-sys 0.59.0 → 1.60`、`windows-targets 0.52.6 → 1.56`）。
4. **cargo-msrv**（本环境已装 0.19.3，`cargo install cargo-msrv --locked` 经 rsproxy）：`cargo msrv show` 输出 `MSRV is Rust 1.85.0`（读本 crate 的 rust-version）；`cargo msrv list` 表格列出各依赖的 MSRV。

> ⚠️ 未在本环境验证：`cargo msrv verify`（逐版本安装旧工具链实测最低可编译版本）——它需要 rustup 联网装工具链，本环境沙箱禁写 `~/.rustup`。真实环境直接 `cargo msrv verify` 即可。

## 示例 5：Cargo.lock 策略演示（ex05-cargo-lock.sh）

脚本在 `/tmp/ph16-ex05-lockdemo` 建一个应用 crate 和一个库 crate（都依赖 itoa），实测：

- **锁文件格式**：`version = 4`（v4 锁格式）；头部两行注明「自动生成，勿手改」；每个包记录 name/version/source/checksum。
- **应用 vs 库**：应用的 `.gitignore` 只有 `/target`（Cargo.lock 提交）；库的 `.gitignore` 多一行 `Cargo.lock`（不提交——库本地构建也会生成锁文件，但它只是本地产物，下游应用的锁文件才算数）。
- **升级与回退**：`cargo update -p itoa --precise 1.0.14` 实测输出 `Downgrading itoa v1.0.18 -> v1.0.14`；`cargo update -p itoa` 升回 `Updating itoa v1.0.14 -> v1.0.18`。
- **`--locked` 守门**：把 Cargo.toml 改成 `itoa = "=1.0.14"`（与锁里的 1.0.18 失配）后，`cargo build --locked` 报错 `error: the lock file ... needs to be updated but --locked was passed to prevent this`——CI 用它防止「锁文件没跟上 Cargo.toml」。

## 运行注意事项

- 四个脚本都会先 `rm -rf` 自己在 /tmp 的工作目录再重建，可重复运行；全部编译产物经 `CARGO_TARGET_DIR` 落在 /tmp，仓库零二进制残留。
- ex04/ex05 首次运行需要联网拉取 crates（脚本内置 rsproxy 镜像配置；海外网络删除 `/tmp/ph16-cargo-home/config.toml` 即用默认 crates.io）。
- ex03 的迁移步进输出措辞随 cargo 版本可能微调，文档记录的是 cargo 1.92.0 实测值。

## 验证状态汇总

- ex01：rust-toolchain.toml override（`rustup show` 显示 overridden by）+ hello 编译运行——已验证。
- ex02：四案例 × 四 edition 编译矩阵与错误原文——已验证（rustc 1.92.0）。
- ex03：2015→2018→2021→2024 迁移全流程（含「cargo fix 不改 Cargo.toml」的实证）——已验证（cargo 1.92.0）。
- ex04：resolver v3/v2 对照、cargo metadata 提取、cargo msrv show/list（0.19.3）——已验证；`cargo msrv verify` 未验证（需 rustup 安装旧工具链，沙箱禁写 ~/.rustup）。
- ex05：锁文件格式、升级/回退、`--locked` 拒绝失配——已验证（cargo 1.92.0，itoa 1.0.18，rsproxy）。
