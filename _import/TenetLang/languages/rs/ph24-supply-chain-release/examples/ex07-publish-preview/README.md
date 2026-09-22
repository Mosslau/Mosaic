# ex07-publish-preview —— crates.io 发布演练与 CHANGELOG

对应主文档 3.10/3.11。发布流程的精华是**发布前的 package 演练**：`cargo package --list` 审查「哪些文件会随包发布」，`cargo package --no-verify` 本地打包出 `.crate`。真实 `cargo publish` 需要 crates.io 账号 + API token，本示例只做本地可复现的演练部分（标「已验证」），真实发布命令给出但标「未在本环境验证」。

## 验证状态

- **已验证**（本机 macOS arm64 / rustc/cargo 1.92.0，2026-09-04）：fmt / clippy `-D warnings` / test 2 单测 + 1 doc 测试 / `cargo package --list` / `--no-verify` 全实测
- 真实 `cargo publish` / `cargo yank`：**未在本环境验证**（需 crates.io 账号与 API token，本环境无凭据）

## 目录结构

```text
ex07-publish-preview/
├── Cargo.toml        # 发布库元数据完整：name/version/edition/description/license/readme/repository/keywords/categories
├── Cargo.lock        # 应用提交 lock（pkgdemo 是库，此处 lock 供发布演练与 audit 使用）
├── CHANGELOG.md      # keep-a-changelog 风格（3.11 版本变更可见性）
├── LICENSE-MIT / LICENSE-APACHE   # 双许可 Apache-2.0 OR MIT 的文件形态
├── src/lib.rs        # crc8 / sum_bytes（含 doc 示例与单测）
└── 本文件（ex07 的说明 README；pkgdemo 自身的 README.md 是发布物的一部分）
```

> ⚠️ 本目录在 git 仓库内打包时，`cargo package --list` 会**自动附加 `.cargo_vcs_info.json`**（记录 commit 信息）——与无 VCS 的临时目录打包（7 files）不同，这是 cargo 的既定行为，不是异常（详见下方输出解读）。

## 运行命令与实测输出

```bash
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR=/tmp/ph24-ex07-target   # 打包产物落 /tmp，仓库零残留
cd ex07-publish-preview

# ① 质量闸门（发布前置）
cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test --release
# 实测：fmt OK / clippy 零告警 / 2 passed（单测）+ 1 passed（doc）

# ② 内容审查：哪些文件会随包发布
cargo package --list
# 实测输出（本仓库内，git VCS 环境）：
#   .cargo_vcs_info.json      ← cargo 自动附加（记录 commit；非 VCS 目录无此文件）
#   CHANGELOG.md
#   Cargo.lock
#   Cargo.toml
#   Cargo.toml.orig           ← cargo 生成的 manifest 快照
#   LICENSE-APACHE
#   LICENSE-MIT
#   README.md
#   src/lib.rs

# ③ 本地打包（跳过 verify 省时间）
cargo package --no-verify
# 实测输出：
#    Packaging ph24-pkgdemo v0.1.0 (…/examples/ex07-publish-preview)
#     Packaged 9 files, 3.3KiB (2.0KiB compressed)
# 产物：$CARGO_TARGET_DIR/package/ph24-pkgdemo-0.1.0.crate

# ④ 完整打包（含 verify：编译 + 测试通过才成功）——发布前最后一关
cargo package        # 实测：Finished + Packaged 成功
```

**输出怎么审**：逐行核对 `--list` 的每一行——`src/` 下是否只有该发布的源码、LICENSE/README/CHANGELOG 有没有随包、有没有把不该发布的东西（`.env`、测试夹具、`target/`）打进去。cargo 默认排除 target 与 gitignore 文件，但 `include`/`exclude` 配置错误可能放行秘密文件——**发布前逐行读一遍，是「不可收回」的唯一防线**。

## 真实发布与 yank（未在本环境验证）

```bash
cargo login                        # 存 API token（3.7：作用域 + 过期 + 权限 600）
cargo publish                      # 真实发布（自带 verify；重复版本会被拒）
cargo publish --dry-run            # 预检不实际上传

# 发错版本后的补救（版本不可删，只能 yank）
cargo yank ph24-pkgdemo@0.1.0            # 阻止新依赖解析选中它（旧 lock 不受影响）
cargo yank --undo ph24-pkgdemo@0.1.0     # 反撤回
```

## 版本变更可见性（3.11）

`CHANGELOG.md` 的写法约定：PR 合入即记 `## [Unreleased]`，发版时把条目归档到新版本小节、bump `Cargo.toml` 的 version、打 `git tag v0.2.0`、在 tag 上写 release notes 引用对应小节。版本号、CHANGELOG、tag、发布物四者必须一致——roadmap 验收「能让版本号和变更说明一致」的工程形态。
