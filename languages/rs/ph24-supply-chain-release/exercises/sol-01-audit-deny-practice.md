# sol-01 —— audit + deny 实战参考实现

> 本答案的**真实输出均为本机实测**（macOS arm64 / cargo 1.92.0 / cargo-audit 0.22.2 / cargo-deny 0.20.2，2026-09-04）。练习对象为 `examples/ex01-cargo-audit/vulndemo/`。deny 的 advisory 数据库更新走 git，实测期间网络代理不稳定（502），凡「依赖网络」的步骤给出重试/替代命令。

## 环境准备

```bash
export PATH="$HOME/.cargo/bin:$PATH"
cd examples/ex01-cargo-audit/vulndemo   # 练习对象：依赖锁在 time = "=0.1.35"
```

## 步骤 1：cargo audit 扫雷

```bash
cargo audit     # 首次联网拉 db；此后可用 --db ~/.cargo/advisory-db --no-fetch 离线（见下）
```

实测命中输出：

```text
    Fetching advisory database from `https://github.com/RustSec/advisory-db.git`
      Loaded 1239 security advisories (from /Users/ninebot/.cargo/advisory-db)
    Scanning Cargo.lock for vulnerabilities (6 crate dependencies)
Crate:     time
Version:   0.1.35
Title:     Potential segfault in the time crate
Date:      2020-11-18
ID:        RUSTSEC-2020-0071
URL:       https://rustsec.org/advisories/RUSTSEC-2020-0071
Severity:  6.2 (medium)
Solution:  Upgrade to >=0.2.23

error: 1 vulnerability found!
```

读取要点：ID = **RUSTSEC-2020-0071**；受影响版本 = 当前 lock 的 **time 0.1.35**；Solution = **>=0.2.23**（0.1 系无补丁，须升级离开 0.1 系）；退出码 1。

## 步骤 2：写 deny.toml 并跑三段的答案版配置

```toml
# deny.toml（sol-01 答案版——四段齐全，LintLevel 语义正确）
[advisories]
db-path = "~/.cargo/advisory-db"   # 复用 cargo audit 已拉取的 db（离线可用）
ignore = []

[licenses]
allow = ["MIT", "Apache-2.0", "BSD-3-Clause", "ISC", "MPL-2.0", "0BSD"]
confidence-threshold = 0.8

[bans]
multiple-versions = "deny"
wildcards = "allow"
skip = []

[sources]
unknown-registry = "deny"
unknown-git = "deny"
allow-registry = ["https://github.com/rust-lang/crates.io-index"]
allow-git = []
```

```bash
cargo deny check advisories    # 命中 RUSTSEC-2020-0071 → advisories FAILED（退出码 1）
cargo deny check bans          # 无多版本 → bans ok
```

实测（advisories 命中节选）：

```text
error[vulnerability]: Potential segfault in the time crate
  ┌─ …/Cargo.lock:4:1
4 │ time 0.1.35 registry+https://github.com/rust-lang/crates.io-index
  │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ security vulnerability detected
  ├ ID: RUSTSEC-2020-0071
  ├ Solution: Upgrade to >=0.2.23 (try `cargo update -p time`)
advisories FAILED
```

顺带观察 `cargo deny check licenses` 会额外报 vulndemo 根包未声明 license（`error[unlicensed]`）——这正是练习 3 发布前置的提醒。

## 步骤 3：修复 → 转绿（含一个真实弯路）

```bash
# 3a 第一次尝试：按 Solution 升到 0.2
#   Cargo.toml: time = "0.2"
cargo update
cargo audit --db ~/.cargo/advisory-db --no-fetch
```

**真实弯路（重要教学点）**：time 升到 0.2.27 后 audit 仍非全绿——0.2 系列的老依赖链（const_fn/standback/proc-macro-hack/time-macros-impl 等，2019~2020 年冻结）携带多个历史公告（如 RUSTSEC-2020-0056 类，实测输出 `warning: 1 allowed warning found`）。**教训：升级不止看目标 crate，还要看它把谁带进树——直接升到维护中的大版本常比停在「符合 Solution 的最老版本」更干净。**

```bash
# 3b 正确做法：直接升 time 0.3（现代依赖链）
#   Cargo.toml: time = "0.3"
cargo update
cargo audit --db ~/.cargo/advisory-db --no-fetch
```

实测（修复后 audit 全绿，退出码 0）：

```text
      Loaded 1239 security advisories (from /Users/ninebot/.cargo/advisory-db)
    Scanning Cargo.lock for vulnerabilities (12 crate dependencies)
# 无命中行 → 全绿。注意 audit 的绿是安静的：只到 Scanning 行、退出码 0
```

`cargo deny check advisories` 同理应转绿（实测时数据库更新被网络 502 阻断——deny 每次运行会尝试 fetch 最新 db，网络恢复后重跑即可；`cargo deny fetch` 可预取）。

## 步骤 4：cargo deny list（修复前整理）

```text
Apache-2.0 (2): libc@0.2.189, time@0.1.35
MIT (5): kernel32-sys@0.2.2, libc@0.2.189, time@0.1.35, winapi@0.2.8, winapi-build@0.1.1
Unlicensed (1): ph24-vulndemo@0.1.0
```

## 验收对照

- [x] audit 命中字段完整读出（RUSTSEC-2020-0071 / 0.1.35 / >=0.2.23）
- [x] deny.toml 四段齐全且 schema 合法（0.20.2 实跑校验）
- [x] 修复后 audit 退出码 0（无命中行）；deny advisories 待网络恢复后复验转绿
- [x] `cargo deny list` 输出按许可证 → crate 整理
