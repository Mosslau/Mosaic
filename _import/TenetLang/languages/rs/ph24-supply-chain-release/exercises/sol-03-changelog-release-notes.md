# sol-03 —— 发布前检查清单 + CHANGELOG 编写参考实现

> 场景：`examples/ex07-publish-preview/`（ph24-pkgdemo）发布 0.2.0。新增 `checksum` 函数；MSRV 1.75 → 1.85（破变更）。发布演练的 `cargo package --list` 输出为本机实测（2026-09-04，macOS arm64 / cargo 1.92.0）。真实 publish 需账号，未验证。

## ① CHANGELOG 0.2.0 小节（keep-a-changelog）

```markdown
# CHANGELOG

## [Unreleased]
### Added
- （空：0.2.0 归档后重建的占位）

## [0.2.0] - 2026-09-04
### Added
- `checksum(data: &[u8]) -> u64`：新增数据块校验和（对外 API 增加，向后兼容）
### Changed
- **BREAKING**：最低支持 rustc 从 1.75 升至 1.85（MSRV 提升，0.x 下视同破变更，升 minor）
### Removed
- （如本版本删除了任何 API，在此列出；0.2.0 无）

## [0.1.0] - 2026-08-20
### Added
- 首个发布版本：`crc8` 逐字节校验（含 doc 示例与单测）
- `sum_bytes` 字节和（含单测）

## License
MIT OR Apache-2.0
```

**写法要点**：
- `## [Unreleased]` 在发版时**归档**成 `## [0.2.0] - 日期`，同时重建一个空的 Unreleased 承接下一轮 PR；
- Breaking 变化显式标 `**BREAKING**` 并把内容写清（这里 MSRV 提升是 0.x 生态里最常见的「没改 API 却破了构建」的破变更）；
- Added/Changed/Removed 分节（keep-a-changelog 的约定），用户能一眼看到升级要小心什么。

## ② release notes（面向使用者，≤150 字）

```text
ph24-pkgdemo v0.2.0 发布

新增：
- checksum()：对字节切片计算校验和。

⚠️ 破坏性变更：
- 最低 rustc 版本升至 1.85。请先升级工具链再升级本 crate：
    rustup update stable

完整变更见 CHANGELOG.md 0.2.0 小节。
```

## ③ `cargo package --list` 实测与逐行审查

实测输出（git 仓库内打包，CARGO_TARGET_DIR=/tmp/ph24-ex07-target）：

```text
.cargo_vcs_info.json      # cargo 自动附加（记录 commit；非 VCS 目录无此文件）→ 正常
CHANGELOG.md              # 发布物应带变更历史 → 应在
Cargo.lock                # 发布演练锁文件 → 应在（库的 .crate 携带 lock 作发布一刻的快照）
Cargo.toml                # 应在
Cargo.toml.orig           # cargo 生成的 manifest 快照 → 正常
LICENSE-APACHE            # 应在（双许可另一半）
LICENSE-MIT               # 应在
README.md                 # 应在（crates.io 首页渲染源）
src/lib.rs                # 应只有它（无多余模块/夹具）
```

**逐行审查结论**：9 个文件全部符合预期；`src/` 下只有 `lib.rs`；LICENSE/README/CHANGELOG 三件套齐全。可疑项：**无**。

## ④ 发布前 checklist（≥8 项，0.2.0 视角）

```text
□ 1. Cargo.toml version 已 bump 到 0.2.0（与 CHANGELOG/tag 一致）
□ 2. Cargo.toml 元数据完整：description / license / readme / repository / keywords / categories
□ 3. CHANGELOG 的 [Unreleased] 已归档为 [0.2.0]，Breaking 已显式标注
□ 4. cargo test / clippy -D warnings / fmt --check 全绿（ph21 门禁）
□ 5. cargo audit（或 deny advisories）无命中（本阶段防线）
□ 6. cargo package --list 逐行审查过：无 .env/密钥/target/多余文件混入
□ 7. cargo package --no-verify 本地打包成功（产物 .crate 可检查）
□ 8. license 与 LICENSE 文件与 Cargo.toml 声明一致（MIT OR Apache-2.0）
□ 9. release notes 已按 CHANGELOG 0.2.0 小节写好（发布到 tag 时用）
□ 10. semver 决策已记录：为何 0.1.0 → 0.2.0 而非 0.1.1（见下）
```

## ⑤ semver 决策说明

0.2.0 含 **MSRV 提升**（1.75 → 1.85）。按 Rust 生态惯例（主文档 3.11），MSRV 提升会让下游「还在 1.75 的工程」构建失败，等价于破变更——因此即使 API 全部向后兼容，也不能只升 patch（0.1.1）：0.x 系列中 **minor bump 承担 breaking 语义**（`0.1.0 → 0.2.0`）。若该 crate 已 1.x，则应升 major。`checksum` 是纯新增、不破坏现有调用，本身只够 minor——它不与 MSRV 提升冲突：两者同发时取更高级别（minor），不必为两个理由发两个版本。

## 验收对照

- [x] CHANGELOG 0.2.0 小节 + 归档骨架 + Breaking 标注
- [x] release notes ≤150 字面向使用者
- [x] `cargo package --list` 真实输出 + 逐行审查结论 + ≥8 项 checklist
- [x] semver 决策（MSRV 提升为何升 minor）写清
