# ph21 阶段项目：Rust CI 模板工程（ci-template）

对应 roadmap 第 21 节推荐项目「Rust CI 模板：可复用于 CLI、服务端和库项目」。把本阶段学到的**全部质量设施**合成一份可复用的模板工程：复制 `ci-template/` 到新项目，改三个名字即可拥有完整的「本地门禁 + CI 矩阵/缓存 + lint 策略 + 可复现构建」底座——它正是 ph20 主文档「### 下一阶段」预告里说的「第一个接入 CI 的样板工程」，也是 ph22/ph25 各阶段项目接入 CI 时的起点。

## 需求

为「CLI / 服务端 / 库」三类 Rust 项目提供统一的 CI 模板：质量门禁（fmt/clippy/test）进 GitHub Actions，带 **toolchain×OS 矩阵**、**cargo 缓存**、**`--locked` 可复现构建**与 **lint 例外纪律配置**；同时内置一个「故意带 lint 问题 → 治理后全绿」的演示 crate，让使用者能亲眼看到门禁红→绿的完整流程，理解每条配置在干什么之后再改。

## 功能清单

- [x] **workspace 骨架**：根 `Cargo.toml` 声明成员 `demo-app`；`[workspace.lints.rust]` 禁 `unsafe_code`、`[workspace.lints.clippy]` 保持默认组 warn / pedantic 不开（lint 策略单一事实来源，主文档 3.4）
- [x] **质量门禁**：`scripts/check.sh`（`set -euo pipefail`；fmt → clippy `-D warnings` → test `--locked`）——与 CI 三条 run 逐条一致，本地/CI 结果可互证
- [x] **GitHub Actions**：`.github/workflows/ci.yml`——push / PR / 手动触发、`concurrency` 取消旧 run、OS × 工具链矩阵（含 MSRV 成员）、Swatinem/rust-cache、`--locked`；预留 ph22（性能回归）/ ph24（audit/deny）注释位（主文档 3.5/3.6）
- [x] **工具链与阈值配置**：`rust-toolchain.toml`（stable + rustfmt/clippy 组件）、`clippy.toml`（too-many-arguments-threshold）
- [x] **可复现构建**：`Cargo.lock` 提交 + `cargo test --locked`（应用项目约定，ph16/主文档 3.6）；`.gitignore` 只忽略 `/target`
- [x] **演示 crate（故意带 lint → 治理后全绿）**：`demo-app/src/main.rs` 为全绿基线；`demo-app/before/linty_main.rs` 故意携带 needless_range_loop / ptr_arg / manual_map（主文档 3.3 实测全在 style 组默认 warn）——复制进 `src/` 即复现「门禁红」

## 目录布局

```text
ci-template/
├── Cargo.toml              # workspace + [workspace.lints]（lint 策略）
├── Cargo.lock              # 应用模板：提交（可复现构建）
├── clippy.toml             # 阈值类配置
├── rust-toolchain.toml     # 工具链钉版（stable + fmt/clippy）
├── .gitignore              # /target
├── .github/workflows/ci.yml# 矩阵 + 缓存 + --locked 三连门禁
├── scripts/check.sh        # 本地门禁（与 CI 逐条一致）
└── demo-app/
    ├── Cargo.toml          # [lints] workspace = true
    ├── src/main.rs         # 全绿基线（治理后）
    └── before/linty_main.rs# 故意带 lint 的整文件（治理前，门禁红材料）
```

## 验收标准

在 `ci-template/` 目录内执行（`./scripts/check.sh` 已验证：bash 3.2+、cargo 1.92.0、rustfmt 1.8.0）：

```bash
export PATH="$HOME/.cargo/bin:$PATH"
cd project/ci-template
./scripts/check.sh                       # ① 治理后全绿：退出 0（已验证 green=0）
cp demo-app/before/linty_main.rs demo-app/src/main.rs
./scripts/check.sh                       # ② 故意带 lint → 门禁红：clippy 步骤失败（已验证红态非零退出）
git checkout -- demo-app/src/main.rs     # ③ 恢复全绿基线（模板部署进真实 git 仓库后）
./scripts/check.sh                       # ④ 再绿（已验证 restored=0）
```

- `ci.yml` 静态可解析（Ruby psych 实测通过），结构符合验收清单：三个门禁拆 step、矩阵含 OS × 工具链、缓存使用 rust-cache、测试带 `--locked`
- **验证说明**：`scripts/check.sh` 与 demo-app 三态已本机实测（上表括号内）；`ci.yml` **未在本环境实际运行验证**（GitHub Actions 需远端 runner），但其三条 `run` 与本地脚本逐条一致，本地全绿即 CI 预期行为
- 把模板用于真实项目时：改成员名 → 跑 `scripts/check.sh` 确认本地绿 → 推仓库后看远端 workflow 跑绿

## 扩展方向（可选）

- **MSRV 矩阵调优**：把 `ci.yml` 的 `rust: ["stable", "1.85"]` 改为你的 `rust-version`；库项目可只留 Linux 上的 MSRV 组合省成本（主文档 3.6）
- **perf 回归 job**：按 `ci.yml` 预留位接 criterion `--save-baseline` 阈值判红——ph22 性能优化与 Profiling 阶段（roadmap 第 22 节，目录待建）
- **供应链 step**：按预留位加 `cargo audit` / `cargo deny`、许可证与 secret 检查——ph24 安全、供应链与发布阶段（roadmap 第 24 节，目录待建）
- **换被测对象**：ph25 的 KV/LSM crate 直接以本模板起步，把 `demo-app` 换成真实组件（roadmap 第 25 节，目录待建）
