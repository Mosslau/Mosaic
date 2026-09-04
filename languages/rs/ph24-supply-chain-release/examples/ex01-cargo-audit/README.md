# ex01-cargo-audit —— 已知漏洞扫描实测

对应主文档 3.2。本示例用**两相对照**演示 cargo audit：干净工程（零漏洞）的「安静全绿」vs 含故意旧漏洞依赖工程的「响亮命中」。核心教学点：audit 的对象是 **Cargo.lock 里的点版本**（不是 manifest 区间），退出码即可做 CI 门禁。

## 验证状态

- **已验证**（本机 macOS arm64 / rustc/cargo 1.92.0 / cargo-audit **0.22.2**，2026-09-04）
- 首次运行需联网拉取 RustSec advisory-db；本机实测数据库条数为 `Loaded 1239 security advisories`（该数字随上游更新变化，以你复现为准）
- 干净对照工程的 audit 在本机零依赖工程 ph24-pkgdemo 上实测（输出见下）

## 目录结构

```text
ex01-cargo-audit/
├── README.md          # 本文件
└── vulndemo/          # 含故意旧漏洞依赖的实验工程（time = "=0.1.35"，可 cargo audit 命中）
```

> ⚠️ `vulndemo` **刻意锁定存在 RustSec 公告的 time 0.1.35**——仅供 audit 命中演示，勿当作依赖样例；不必 `cargo build` 它（audit 只需 Cargo.lock，离线可扫）。

## 运行命令与实测输出

```bash
export PATH="$HOME/.cargo/bin:$PATH"

# ① 安装 cargo-audit（独立子命令；本机已装 0.22.2）
cargo install cargo-audit --locked

# ② 在 vulndemo 内跑 audit（本地已带 Cargo.lock，若 db 已缓存则全程离线）
cd ex01-cargo-audit/vulndemo
cargo audit
```

实测输出（本机真实输出，2026-09-04）：

```text
    Fetching advisory database from `https://github.com/RustSec/advisory-db.git`
      Loaded 1239 security advisories (from /Users/ninebot/.cargo/advisory-db)
    Updating crates.io index
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

- 退出码 **1**（`echo $?` 验证）——CI 里该命令非零即拦
- `Solution: Upgrade to >=0.2.23` 就是处理策略「升级」的直接答案；执行 `cargo update -p time --precise 0.2.23`（在非精确锁定的工程上为 `cargo update -p time`）后再 audit 应转绿

**对照实验（干净工程）**：用零依赖工程（本仓库 ex07 的 pkgdemo 即可）跑同版本 cargo audit：

```text
    Scanning Cargo.lock for vulnerabilities (1 crate dependencies)   ← 只有 scanning 行
# 退出码 0；cargo audit 的「全绿」不打印 "No vulnerabilities" 结论行 —— 安静的绿，命中的红
```

## 输出解读速查

| 命中行字段 | 读法 |
|-----------|------|
| `Crate` / `Version` | 你锁定（lock 里）的包与版本 |
| `ID` / `URL` | RustSec 公告号与原文链接（检索 details/影响函数用） |
| `Severity` | CVSS 严重度与数值（本命中 6.2 medium） |
| `Solution` | 修复版本区间/动作——处理策略的第一候选 |

## 处理策略对照

升级（`cargo update` 到 Solution 版本）→ 补丁/规避（无修复版时锁定 unaffacted 区间）→ 替换依赖（上游停更）→ 接受并登记（不可达路径，CI 配 ignore + 理由）。详见主文档 3.2 策略表。
