# ph24 阶段项目：安全发布流水线 relpipe

对应 roadmap 第 24 节推荐项目「安全发布流水线：自动测试、审计、构建、打包和生成发布说明」。落地为完整 cargo 工程 `relpipe/`：**演示 crate（带一个最小第三方依赖）+ deny.toml + release-check.sh（本地 9 步流水线）+ .github/workflows/release.yml（CI 形态参考）**——把本阶段「扫雷 → 门禁 → 打包审查 → 版本一致性」四件事收进一条命令。

## 需求

「发布一个可信 crate」需要回答四个问题，流水线逐题回答：

1. **代码可信吗** → fmt / clippy `-D warnings` / test `--locked`（ph21 门禁 + ph16 锁文件纪律）
2. **依赖可信吗** → `cargo audit` 扫已知漏洞（3.2）+ `cargo deny check` 做许可/版本/来源门禁（3.3~3.5）
3. **发布物可审查吗** → `cargo package --list` 逐行人审 + `--no-verify` 本地打包（3.10）
4. **版本可追溯吗** → CHANGELOG 与 Cargo.toml version 一致性校验（3.11）

演示 crate 刻意只带 **hex**（零传递依赖、MIT OR Apache-2.0）——有真实的依赖树供 audit/deny/licenses 检查，又不臃肿。

## 目录与功能清单

```text
relpipe/
├── Cargo.toml            # 发布元数据完整（description/license/readme/repository/keywords/categories）
├── Cargo.lock            # 提交 lock（发布演练与 audit 的对象）
├── CHANGELOG.md          # keep-a-changelog：[Unreleased] + [0.1.0] 归档
├── LICENSE-MIT / LICENSE-APACHE   # 双许可文件（与 license 字段一致）
├── deny.toml             # 四段门禁（schema 经 cargo-deny 0.20.2 实跑校验）
├── README.md             # crate 说明（crates.io 首页渲染源）
├── release-check.sh      # 本地 9 步发布检查（./release-check.sh 一条命令）
├── .github/workflows/release.yml   # CI 形态参考（tag 触发 → check → publish → SBOM → release）
└── src/lib.rs            # crc8 / sum_bytes / checksum_hex（3 个单测 + hex 依赖）
```

- [x] release-check.sh 9 步全部**本机实测跑通**（cargo 1.92.0 / cargo-audit 0.22.2 / cargo-deny 0.20.2）
- [x] deny.toml schema 合法：licenses/bans 离线全绿；advisories 依赖网络 db 更新（网络差时降级警告——已知漏洞硬性覆盖由 audit step 承担）
- [x] `cargo package` 演练：11 files / LICENSE 齐全 / 无 target 残留（`CARGO_TARGET_DIR` 落 /tmp）
- [x] 真实审查发现已处理：初版漏放 LICENSE 文件，被 step 7 的 `package --list` 人审流程抓出后补上
- [ ] CI workflow 未在本环境运行（无 GitHub runner），YAML 为静态形态参考

## 验证环境

cargo/rustc **1.92.0**（macOS arm64）、cargo-audit **0.22.2**、cargo-deny **0.20.2**、cargo-sbom **0.10.0**（CI publish job 用）；hex **0.4.3**（唯一第三方依赖）。全部本地命令本机实测；**真实 `cargo publish` 未在本环境验证**（需 crates.io 账号 + token）。

## 验收标准

在 `project/relpipe/` 目录内执行：

```bash
export PATH="$HOME/.cargo/bin:$PATH"
./release-check.sh
# 期望：9 个 step 逐个输出明确结果，末尾打印
#   ==== release-check 通过：v0.1.0 可以进入 cargo publish ====
```

**本机实测输出摘要（2026-09-04，完整跑通）：**

| step | 检查 | 实测结果 |
|------|------|---------|
| 1/9 | `cargo fmt --check` | fmt: OK |
| 2/9 | `cargo clippy --all-targets -- -D warnings` | 0 warnings |
| 3/9 | `cargo test --release --locked` | 3 passed（单测）+ doc 0 |
| 4/9 | `cargo audit`（离线复用缓存 db） | 无命中（2 crate dependencies 扫描） |
| 5/9 | `cargo deny check licenses / bans` | licenses ok / bans ok；advisories 因 db fetch 网络 502 降级警告 |
| 6/9 | `cargo deny list` | `Apache-2.0 (2): hex, ph24-relpipe`；`MIT (2): hex, ph24-relpipe` |
| 7/9 | `cargo package --list` | 11 files 逐行审查：LICENSE/README/CHANGELOG 在列 |
| 8/9 | `cargo package --no-verify` | Packaged 11 files, 12.3KiB (6.1KiB compressed) |
| 9/9 | CHANGELOG ↔ version 校验 | [0.1.0] 已归档：OK |

**验收口径（对应 roadmap 验收「能为依赖漏洞制定处理策略」「能让发布包内容可审查」「能让版本号和变更说明一致」）：** 交付物必须能本地一键跑出上述 9 步、每步输出明确结果；未验证步骤（CI workflow、真实 publish）如实标注；网络受限时（advisory db fetch 502）流程以警告降级而非崩溃——因为已知漏洞硬性覆盖已由 `cargo audit --no-fetch`（step 4）承担，deny advisories 是第二道同源检查。

## 扩展方向

- **换被测对象**：把 `src/lib.rs` 换成你的真实 crate（ph25 的 KV/LSM 组件将直接以本模板起步，roadmap 第 25 节，目录待建）——本工程的 deny.toml/release-check.sh/CI 模板原样可搬
- **收紧发布物**：step 7 的 `package --list` 人审目前能发现 deny.toml/release-check.sh 混入发布包——可给 `Cargo.toml` 配 `include`/`exclude` 让流水线脚本不进 `.crate`
- **SBOM 进发布**：CI 的 publish job 已预留 `cargo sbom` 生成 SPDX 并 attach 到 release（3.9）
- **yank 演练**：发布后事故流程（`cargo yank` + 立即发修复版）可在本地用 `cargo yank --dry-run` 语义演示（真实 yank 需 token，未验证）
- **MSRV 门禁**：加 `cargo msrv` 或 CI 矩阵低版本构建，把「rust-version 声明 ≠ 实际可编译」的坑也收进流水线
