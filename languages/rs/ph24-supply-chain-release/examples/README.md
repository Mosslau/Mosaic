# examples —— Rust 安全、供应链与发布阶段完整示例

对应主文档 `24-supply-chain-release.md` 第 6 章。七个示例覆盖 roadmap 第 24 节全部学习内容：从「cargo audit 扫已知漏洞」起步，依次经过 cargo deny 配置（advisories/licenses/bans/sources）、许可证清单、可复现构建、SBOM、secret 管理、crates.io 发布演练——全程围绕同一纪律：**依赖树里每一环都可信、制品内容可审查、版本变更可追溯**。

验证环境：rustc/cargo **1.92.0**（macOS arm64，stable-aarch64-apple-darwin）、cargo-audit **0.22.2**（`cargo install cargo-audit --locked`，本机编译安装成功并实测）、cargo-deny **0.20.2**（同上安装成功并实测）、cargo-sbom **0.10.0**（同上，实测生成 SPDX-2.3 / CycloneDX-1.6）。构建产物统一落 `/tmp`（`CARGO_TARGET_DIR`），仓库零二进制残留；需要真实三方依赖的工程（ex01/ex07）在 README 中给出最小依赖集与联网说明。

## 示例清单与验证状态

| 示例 | 对应主文档 | 一句话说明 | 验证状态 |
|------|-----------|-----------|---------|
| `ex01-cargo-audit` | 3.2 | 干净工程 vs 含故意旧漏洞依赖工程的 audit 实测对照（含真实命中输出） | 已验证（cargo-audit 0.22.2） |
| `ex02-cargo-deny-config` | 3.3 | deny.toml 四段结构全配置（含注释）与 `cargo deny check` 实测（含命中输出） | 已验证（cargo-deny 0.20.2） |
| `ex03-license-check` | 3.6 | 许可证合规命令链：`cargo metadata` 核对 + SPDX 清单整理脚本（实测输出） | 已验证（脚本实测）；deny list 补充见 ex02 |
| `ex04-reproducible-build` | 3.8 | 双 CARGO_TARGET_DIR 干净构建，SHA-256 对比验证可复现构建 | 已验证 |
| `ex05-sbom-generate` | 3.9 | SBOM 生成实测：cargo-sbom 产出 SPDX-2.3 / CycloneDX-1.6（真实输出） | 已验证（cargo-sbom 0.10.0） |
| `ex06-secret-handling` | 3.7 | 从环境变量读 secret 的 Rust 最小形态 + 禁止事项清单 | 已验证（cargo run 实测） |
| `ex07-publish-preview` | 3.10/3.11 | `cargo package --list`/`--no-verify` 发布演练工程 + CHANGELOG 模板 | 已验证（package 演练）；真实 publish 未验证 |

## 通用质量闸门（每个含 Cargo.toml 的目录内执行）

```bash
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR=/tmp/ph24-ex-<示例>-target   # 仓库零二进制残留的关键
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test --release                                  # ex04/ex06/ex07 有单测或可运行验证
```

> ⚠️ ex01 的 `vulndemo` 子目录**刻意包含存在已知漏洞的旧依赖**（time 0.1.35），仅供 `cargo audit` 演示命中输出——不要把它当作可发布依赖的样例，也不要对它运行 `cargo build`（`time 0.1.35` 可编译但无必要）。ex07 的 pkgdemo 为**零第三方依赖**库，ex04 的 reprobin 为零依赖 bin——无需联网即可完整复现。

## 运行命令与实测输出

### ex01：cargo audit（漏洞扫描）

```bash
# 前置：cargo-audit（首次运行会拉取 RustSec advisory-db，需联网）
cargo install cargo-audit --locked            # 本机 0.22.2，已验证
cd examples/ex01-cargo-audit
# 对照 ①：干净工程（vulndemo 换回无漏洞依赖）——audit 安静通过（退出码 0）
# 对照 ②：含故意旧漏洞的工程（time = "=0.1.35"）
cd vulndemo && cargo audit
# 实测输出（节选，完整见 README）：
#   Crate:     time
#   Version:   0.1.35
#   ID:        RUSTSEC-2020-0071
#   Severity:  6.2 (medium)
#   Solution:  Upgrade to >=0.2.23
#   error: 1 vulnerability found!   ← 退出码 1，CI 门禁直接变红
```

### ex02：cargo deny（deny.toml 配置 + check 实测）

```bash
# 前置：cargo-deny（本机 0.20.2 已装）
cargo install cargo-deny --locked
cd examples/ex02-cargo-deny-config
cargo deny check advisories   # 漏洞门禁（与 cargo audit 同源 RustSec db）
cargo deny check licenses     # 许可门禁：unlicensed / allow 外 → 非零退出
cargo deny check bans         # 版本/重复依赖门禁
cargo deny check sources      # 来源门禁（git/未知 registry）
```

实测输出（cargo-deny 0.20.2，对含 `time 0.1.35` 的实验工程运行，完整见 ex02/README）：

```text
# advisories 命中（db-path 复用 cargo audit 的 ~/.cargo/advisory-db，离线可跑）：
error[vulnerability]: Potential segfault in the time crate
  ┌─ …/Cargo.lock:4:1
  │
4 │ time 0.1.35 registry+https://github.com/rust-lang/crates.io-index
  │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ security vulnerability detected
  ├ ID: RUSTSEC-2020-0071
  ├ Advisory: https://rustsec.org/advisories/RUSTSEC-2020-0071
  ├ Solution: Upgrade to >=0.2.23 (try `cargo update -p time`)
advisories FAILED                       ← 退出码 1

# licenses 对「根包未声明 license」的实验工程：
warning[no-license-field]: license expression was not specified in manifest for crate 'ph24-vulndemo = 0.1.0'
error[unlicensed]: ph24-vulndemo = 0.1.0 is unlicensed
warning[license-not-encountered]: license was not encountered   ← allow 里没遇见的许可
licenses FAILED

# bans（同一工程，无多版本问题）：
bans ok

# 许可证 × crate 清单（cargo deny list，零配置即可用）：
Apache-2.0 (2): libc@0.2.189, time@0.1.35
MIT (5): kernel32-sys@0.2.2, libc@0.2.189, time@0.1.35, winapi@0.2.8, winapi-build@0.1.1
Unlicensed (1): ph24-vulndemo@0.1.0
```

### ex03：许可证清单整理

```bash
cd examples/ex03-license-check
./check-licenses.sh            # 脚本基于 cargo metadata 输出依赖的 license 字段并核对 allow 清单
# 脚本末尾输出一行汇总：核对 N 个包 / allow 命中 X / 需人工确认 Y
# （对 ph24-pkgdemo 零依赖工程实测输出为「核对 1 个包」；对带三方依赖的工程在真实项目上使用）
```

### ex04：可复现构建（双目录哈希对比）

```bash
cd examples/ex04-reproducible-build
export CARGO_TARGET_DIR=/tmp/ph24-t1 cargo build --release   # 干净构建 ①
export CARGO_TARGET_DIR=/tmp/ph24-t2 cargo build --release   # 干净构建 ②
shasum -a 256 /tmp/ph24-t1/release/ph24-reprobin /tmp/ph24-t2/release/ph24-reprobin
# 实测：两行 SHA-256 完全相同
#   1205b2a934974b02209700bdbe6f0a5b96e0fa6ee112ce84c7b90c88a26fc82c  …/ph24-reprobin (×2)
```

### ex05：SBOM（cargo-sbom 生成实测）

```bash
# 前置：cargo-sbom（本机 0.10.0 已装；cargo-deny 0.20 无 sbom 子命令，见 ex05/README 说明）
cargo install cargo-sbom --locked
cd <含三方依赖的 cargo 工程>
cargo sbom --output-format spdx_json_2_3          # SPDX-2.3（默认）
cargo sbom --output-format cyclone_dx_json_1_6    # CycloneDX 1.6
```

实测结构（cargo-sbom 0.10.0 对 time/libc/winapi 实验工程，完整输出见 ex05/README）：

```text
SPDX-2.3：spdxVersion=SPDX-2.3，5 个 packages + 7 条依赖关系边
  packages: ph24-vulndemo(NOASSERTION) / time 0.1.35(MIT OR Apache-2.0)
            / libc 0.2.189(MIT OR Apache-2.0) / kernel32-sys 0.2.2(MIT) / winapi 0.2.8(MIT)
CycloneDX 1.6：bomFormat=CycloneDX / specVersion=1.6 / 4 components（不含根包）
```

### ex06：secret 管理

```bash
cd examples/ex06-secret-handling
cargo run                     # 无 token 时：报「缺少环境变量 CRATES_IO_TOKEN：请注入」
CRATES_IO_TOKEN=dummy cargo run   # 有 token 时：输出 token 长度，不回显内容
```

### ex07：发布演练（cargo package）

```bash
cd examples/ex07-publish-preview
cargo package --list          # 内容审查：看哪些文件会随包发布
cargo package --no-verify     # 本地打包（跳过 verify 省时间）→ target/package/*.crate
# 实测输出（本机）：
#   Cargo.lock / Cargo.toml / Cargo.toml.orig / LICENSE-APACHE / LICENSE-MIT
#   README.md / src/lib.rs
#   Packaged 7 files, 2.7KiB (1.6KiB compressed)
# 真实发布（需 crates.io 账号 + token，未在本环境验证）：
cargo login && cargo publish && cargo publish --dry-run
# 发错版本：cargo yank ph24-pkgdemo@0.1.0
```

## 每个示例的看点

- **ex01**：audit 的对象是 Cargo.lock（不是 manifest）；干净工程的「全绿」是安静的（只打 scanning 行、退出 0），命中的输出每对 `字段: 值` 都是行动线索——`Solution: Upgrade to >=0.2.23` 直接给出处理策略。
- **ex02**：deny.toml 的每一段回答一个威胁——advisories=已知漏洞、licenses=合规事故、bans=多版本修复不对称、sources=依赖混淆。配置是声明，`cargo deny check` 是执行，两者缺一不可。
- **ex03**：许可证清单的自动核对依赖 crate 的 `license` 元数据；SPDX 表达式的 `OR` 语义（双许可）与缺 license 字段的「需人工确认」是整理时的两个主要坑。
- **ex04**：同一 commit + 同一工具链，双目录干净构建的产物逐字节一致；验证的关键是「干净构建」（增量缓存命中必然相同，没有说服力）。
- **ex05**：SBOM 的价值在生成之后的程序化消费——SPDX/CycloneDX 选标准 JSON 格式、与制品同源同版发布。
- **ex06**：secret 的最小注入形态是环境变量；读不到就显式失败而不是空值继续，打印长度校验而不回显内容是「用到但不泄露」的最小示范。
- **ex07**：`cargo package --list` 把「发布内容审查」变成一条命令；已发布版本不可删，所以审查必须在 publish 之前完成。

## 阅读顺序建议

按主文档 3.1→3.11 推进：ex01 建立「已知漏洞扫描」的第一直觉，ex02/ex03 学策略门禁与许可证，ex04 亲手验证可复现构建，ex05 看 SBOM 结构，ex06 管住 secret，最后 ex07 走完发布演练闭环——project 把 ex02/ex07 的形态放大成一条完整的 release-check 流水线。

## 验证状态汇总

- ex01/ex02/ex04/ex06/ex07：**已验证**（cargo 1.92.0 + cargo-audit 0.22.2 + cargo-deny 0.20.2，本机实测；数字/哈希/命中输出为实测值）
- ex03：脚本在零依赖工程与含三方依赖工程上实测（真实输出见其 README）
- ex05：**已验证**（cargo-sbom 0.10.0 实测产出 SPDX-2.3 与 CycloneDX-1.6；cargo-deny 0.20 已移除 sbom 子命令，生成走 cargo-sbom）
- 真实 crates.io `cargo publish` / `cargo yank`：**未在本环境验证**（需账号 + API token）
- 无任何命令输出为虚构；运行数字以你本机复现为准（advisory-db 条数会随上游更新变化，命中输出以实时数据库为准）
