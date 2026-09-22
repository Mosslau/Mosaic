# ex02-cargo-deny-config —— cargo deny 门禁配置与实测

对应主文档 3.3~3.5。提供一份**带注释的 deny.toml 全配置**，覆盖四段：`advisories`（已知漏洞）、`licenses`（许可证策略）、`bans`（版本/重复依赖）、`sources`（依赖来源）。配置与运行输出均已用 cargo-deny **0.20.2** 实测。

## 验证状态

- **已验证**（本机 macOS arm64 / cargo 1.92.0 / cargo-deny 0.20.2，2026-09-04）：`check advisories` / `check licenses` / `check bans` 均对「含 time 0.1.35 旧漏洞依赖的实验工程」实测，真实输出见下
- **deny.toml schema 曾写错过一次并已被实跑纠正**：`yanked`/`multiple-versions` 在 0.20 是 LintLevel（`"deny"`/`"warn"` 字符串）不是布尔；licenses `allow` 数组每项是单个 SPDX 标识符（不接受 `OR` 表达式——双许可靠「把两侧都 allow」实现）；`confidence` 键实际叫 `confidence-threshold`——**这正是「配置必须实跑」的教训**
- `advisories` 的 db 拉取走 git（首次需联网）；实测遇网络代理 502，改用 `db-path = "~/.cargo/advisory-db"` **直接复用 cargo audit 已拉取的 RustSec 库**，离线可用（见下实测输出）——这也是 audit 与 deny 共享数据库的务实姿势

## 目录结构

```text
ex02-cargo-deny-config/
├── deny.toml        # 四段全配置（schema 经 0.20.2 校验，注释写明「踩坑」点）
└── README.md        # 本文件
```

## 安装与运行

```bash
export PATH="$HOME/.cargo/bin:$PATH"
cargo install cargo-deny --locked        # 本机 0.20.2（cargo-audit 装好后依赖多已缓存，编译约 2 分钟）
cd examples/ex02-cargo-deny-config

cargo deny check                 # 全部段（= advisories licenses bans sources）
cargo deny check advisories      # ① 已知漏洞（与 cargo audit 同源 RustSec db）
cargo deny check licenses        # ② 许可证：unlicensed / allow 外 → 非零退出
cargo deny check bans            # ③ 多版本/版本约束
cargo deny check sources         # ④ 来源：git/未知 registry
cargo deny list                  # （0.20 新增）许可证 × crate 清单，零配置即用
```

## 实测输出（cargo-deny 0.20.2）

以下均对 `/tmp` 下的实验工程运行（依赖 `time = "=0.1.35"`，故意含旧漏洞）：

**① `cargo deny check advisories`——命中 RUSTSEC-2020-0071（退出码 1）：**

```text
error[vulnerability]: Potential segfault in the time crate
  ┌─ …/Cargo.lock:4:1
  │
4 │ time 0.1.35 registry+https://github.com/rust-lang/crates.io-index
  │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ security vulnerability detected
  │
  ├ ID: RUSTSEC-2020-0071
  ├ Advisory: https://rustsec.org/advisories/RUSTSEC-2020-0071
  ├ …（公告正文，含 Impact/Patches/Workarounds 全文）
  ├ Solution: Upgrade to >=0.2.23 (try `cargo update -p time`)
  ├ time v0.1.35
    └── ph24-vulndemo v0.1.0
advisories FAILED
```

**② `cargo deny check licenses`——根包未声明 license 被拦（退出码非零）：**

```text
warning[no-license-field]: license expression was not specified in manifest for crate 'ph24-vulndemo = 0.1.0'
 ├ ph24-vulndemo v0.1.0
warning[unlicensed]: a valid license expression could not be retrieved for the crate
error[unlicensed]: ph24-vulndemo = 0.1.0 is unlicensed
 ├ ph24-vulndemo v0.1.0 (*)
warning[license-not-encountered]: license was not encountered    ← allow 清单里没遇见的许可
   ┌─ deny.toml:26:6
   │
26 │     "BSD-3-Clause",
   │      ━━━━━━━━━━━━ unmatched license allowance
licenses FAILED
```

**③ `cargo deny check bans`——无多版本问题即全绿：**

```text
bans ok
```

**④ `cargo deny list`——许可证 × crate 逆查清单（发布前整理许可证矩阵最顺手）：**

```text
Apache-2.0 (2): libc@0.2.189, time@0.1.35
MIT (5): kernel32-sys@0.2.2, libc@0.2.189, time@0.1.35, winapi@0.2.8, winapi-build@0.1.1
Unlicensed (1): ph24-vulndemo@0.1.0
```

## 输出解读

| 段 | 防什么 | 命中时的信号 | 行动 |
|----|--------|------------|------|
| `advisories` | 已知漏洞进 CI | `error[vulnerability]` + RUSTSEC-ID + `Solution` | 按 Solution 升级（`cargo update -p <crate>`），重跑转绿 |
| `licenses` | 合规事故 | `error[unlicensed]`（缺 license）/ `unknown`（识别不出）；`license-not-encountered`（allow 冗余） | 补 license 字段 / 加 allow / 从 allow 删除未遇见的项（保持配置干净） |
| `bans` | 多版本修复不对称 | `error[multiple-versions]` | `cargo update -p <crate> --precise` 合并，或 `skip` 带理由 |
| `sources` | 依赖混淆 / git 失控 | `unknown-registry`/`unknown-git` | 白名单内部 registry / 移除 git 依赖 |

> ⚠️ `warning[license-not-encountered]` 不是错误，但值得认真对待：allow 清单里躺着从没遇到的许可是「清单漂移」，说明配置比实际依赖宽——定期用 `cargo deny list` 对照清理。

## 与本阶段其它示例的关系

- `advisories` 段与 ex01 的 cargo audit **同源**（RustSec advisory-db）；本配置的 `db-path` 直接复用 audit 缓存库
- `licenses` 段 allow 清单与 ex03 脚本的 `ALLOW_LICENSES` 保持同一集合（按分发模式裁剪，主文档 3.4 三档表格）
- 把本 deny.toml 复制进 project/ 的演示 crate，配 `release-check.sh` 即成完整流水线
