# Rust 安全、供应链与发布阶段

> 面向「交付物可信」的方向：从供应链攻击史出发，认识「依赖树里的每一环都可能是入口」；然后逐个点亮把关工具——cargo audit 扫已知漏洞、cargo deny 做许可/版本/来源门禁、SBOM 让发布物自带成分清单、secret 管理堵住凭据泄露、可复现构建让「同一个 commit 长出同一个制品」成为可验证事实，最后走通 crates.io 的发布流程与 semver 纪律——全程回答同一句话：**别人凭什么相信你发布的这个包，和你凭什么相信你依赖的那些包**。

## 1. 概述

本阶段对应 roadmap 第 24 节，目标是**能发布可信 Rust 软件，并管理依赖、漏洞和制品**。它是学习路线中「从能写到能交付」的最后一块拼图：ph16 已把「Cargo.lock 提交、工具链固定」立为工程惯例，ph17 已把「引入依赖前的六维评审」与 `cargo tree/audit/deny/diet` 的第一层用法交给读者，ph21 已把 fmt/clippy/test 的质量门禁沉淀成 CI 模板并留下 audit/deny 的「预留注释位」，ph23 刚把 FFI 的 unsafe 审查止步于「每个 unsafe 写清 soundness 前提」的纪律层——本阶段把这些线头织成一张**从「代码没错」到「交付物可信」的完整流水线**：已知漏洞有数据库对照（cargo audit）、许可与来源有策略门禁（cargo deny）、制品有成分清单（SBOM）、凭据有注入纪律（secret 管理）、构建可复现、发布可审查（cargo package → cargo publish）、版本变更可追溯（semver + CHANGELOG）。ph23 的 cdylib/pyo3 制品与 ph21 的 CI 模板在这里进入审计、打包与发布流水线；ph17 预告的「完整供应链安全体系（SBOM、签名、发布完整性）」在此兑现——其中**制品签名**环节留到正文按工具链现状说明（见 3.10 与基线说明的验证口径）。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 供应链风险模型 | 直接/传递依赖的信任边界、typosquatting、恶意包与投毒手法、事件史（event-stream/left-pad/SolarWinds/Log4j 的供应链维度）（3.1） |
| cargo audit | RustSec advisory-db、漏洞扫描、CVE/CVSS 解读、漏洞处理策略（升级/补丁/规避/替换）（3.2） |
| cargo deny | deny.toml 四段结构（advisories/licenses/bans/sources）、各段策略与解读（3.3~3.5） |
| 许可证合规 | SPDX 标识、license 字段写法、双许可 Apache-2.0 OR MIT 惯例、常见许可证矩阵、copyleft 边界（3.6） |
| secret 管理 | 最小权限、不用 env 明文/不 commit .env、CI secret 注入、`cargo login` token 与凭证存储、SOPS/密钥库概念（3.7） |
| 可复现构建 | Cargo.lock 提交、`--locked`、vendoring/离线、构建确定性、双目录哈希对比实测（3.8） |
| SBOM | SPDX/CycloneDX 概念、生成与校验、发布物附 SBOM 的实践（3.9） |
| crates.io 发布流程 | `cargo package --list` 内容审查、`--no-verify`/`--dry-run` 演练、cargo publish 前置条件、yank 与版本回滚（3.10） |
| 版本发布策略 | semver 纪律、Rust 生态 1.0 前惯例、预发布版本、feature 门控、CHANGELOG/release notes（3.11） |
| 底层原理 | cargo 依赖解析与 Cargo.lock 精确锁定、RustSec advisory 结构与版本匹配、crates.io 校验与 yank 机制（4） |
| 场景与练习 | 库作者 vs 内部应用分级 + npm/Gradle/Go 供应链对照；examples/exercises/project 四层配套（5~7） |

这个阶段只涉及**依赖与发布维度的信任链建设**（漏洞审计、许可/来源门禁、SBOM、secret 注入纪律、可复现构建、crates.io 发布流程、版本策略），**不涉及 Rust 数据基础设施组件的运行时安全与加密存储**（KV/LSM 组件的 WAL 校验、加密、权限模型与 Agent 工具后端的权限/审计/可观测性属于 [ph25 Rust 数据基础设施专项阶段](../ph25-data-infrastructure/25-data-infrastructure.md)，届时本阶段的 deny.toml/audit job 会被 ph25 的工程直接拿去用）；**不重复 ph23 FFI 阶段已讲透的跨语言 unsafe 审查细节**（`extern "C"` 导出的 soundness 前提、panic 护栏、谁分配谁释放的纪律是 ph23 的内容，本阶段只从「制品进入审计与发布流水线」的视角引用其 cdylib/pyo3 产物形态，不再重讲边界安全写法）。同时与相邻知识划清边界：**unsafe/FFI 的语言级安全模型**（ph14 Unsafe 阶段与 ph23 已覆盖，这里的「安全」指供应链与依赖信任，不是内存安全）；**依赖选择与评审清单**（ph17 Crate 生态阶段已讲六维评审与 `cargo tree`，这里默认会看依赖树，只讲「评审之后怎么用策略与门禁持续把关」）；**Edition/工具链固定的一般知识**（ph16 已讲 rust-toolchain.toml 与 Cargo.lock 策略，本阶段 3.8 在其上深化可复现构建的验证方法）。

上一阶段的预告在本阶段逐条兑现，它就是本阶段的验收骨架：

| 预告来源 | 预告点 | 兑现位置 |
|---------|--------|---------|
| ph17 主文档 3.2/3.10/7 章 | 「把评审沉淀成 CI 门禁、SBOM、发布签名等完整供应链体系属于 ph24」；「SBOM 生成、依赖签名验证、发布完整性、私仓镜像、cargo vendor 离线供应链属于 ph24」 | 3.3~3.5 的 deny.toml 门禁、3.9 的 SBOM、3.8 的 vendor/离线、3.10 的发布完整性、project 的 release-check.sh |
| ph17 主文档 3.10 | cargo-diet「打包体检：cargo package 会带上哪些文件」衔接发布 | 3.10 的 `cargo package --list` 实测 + ex07-publish-preview |
| ph21 project 扩展方向 | CI 模板「按预留位加 cargo audit / cargo deny、许可证与 secret 检查——ph24」 | 3.2/3.3/3.7 + project/.github/workflows/release.yml 的完整 step |
| ph23 主文档「下一阶段」 | 「把 FFI 的 unsafe 审查纪律升级为『怎么让交付物可信』：届时本阶段的 cdylib/pyo3 制品将进入审计、签名与发布流水线，跨语言边界的系统化安全审查在那里补完」 | 3.2/3.3 对 ph23 制品形态的引用、3.9 的 SBOM、5 节对跨语言边界的供应链化审查说明（制品级而非边界语法级） |

## 2. 来源与演变

供应链安全的叙事起点不是「某一天有了审计工具」，而是一串**发生在真实世界的失败**。这些事件分两类：一类是**上游被攻破或投毒**（别人的恶意进到你的构建里），另一类是**下游被你牵连**（你的包被别人依赖时成了攻击跳板）。Rust 生态的供应链故事写在 crates.io、RustSec advisory-db 与 cargo 工具链的演进里，下面按时间线收束成几条主线。

**事件史给了工具出现的理由。** 2016 年 npm 的 left-pad 事件（作者撤回一个 11 行的小包，大量项目因依赖它而构建失败）首先教会生态一件事：**依赖越细碎、越容易被上游的任意动作击穿**——它本质是「可用性被依赖绑架」。2018 年 npm 的 event-stream 事件升级为真正的投毒：攻击者获得维护者账号后向 event-stream 注入针对特定钱包的窃密代码，**下载量最大的包之一成为木马分发渠道**——它教会生态第二件事：**维护者身份与代码审查是两回事，信任一个包 = 信任它的维护历史、账号安全与审查过程**。依赖混淆（dependency confusion）攻击则利用「私有包名与公共注册表同名、解析器优先取了公共源」的配置错误，让攻击者把一个同名恶意包「顶替」进内部构建。2020 年的 SolarWinds 供应链攻击（构建系统被入侵、合法签名的更新被植入后门）把攻击面推到了**构建与签名环节本身**——合法软件签名不再等于可信软件。2021 年 Log4j（CVE-2021-44228）则展示了另一个维度：一个被全世界无数服务间接依赖的库爆出可远程利用漏洞后，**修复的扩散速度取决于每个下游团队的依赖可见性**——看不见自己依赖了什么，就无法知道自己是否受影响。**设计哲学一句话加粗：供应链安全的工具不是在发现处设卡，而是把「信任」拆成可自动核验的清单——漏洞有数据库对照、许可有策略门禁、依赖有锁文件锁定、成分有 SBOM 声明、发布有审查演练。**

Rust 侧的回应沿着同一条逻辑展开：cargo 用 **Cargo.lock 精确锁定**每个依赖版本（ph16 已讲其策略）；**RustSec advisory-db**（rustsec/advisory-db，GitHub 维护，2024 年起在 Rust Foundation 治理下）把已知漏洞公告成机器可读的 `advisory.toml`，**cargo-audit**（2018 年出现）对照 Cargo.lock 扫出「已知雷」；**cargo-deny**（约 2020 年，Embark Studios 发起）把许可、漏洞、重复依赖、来源限制四类检查合一成可进 CI 的门禁；**SBOM（软件物料清单）** 概念在 2021 年美国第 14028 号行政令后从政府合规要求变成工程惯例，SPDX 与 CycloneDX 两种格式（见 3.9）成为主流；crates.io 的发布侧则从「用户名密码可发布」演进到 **API token + 作用域**（见 3.10），cargo 1.77+ 与 1.92 之间又陆续收紧发布元数据与包校验。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| npm left-pad 撤回事件 | 2016 | 单个小包撤回导致海量构建失败——「可用性被依赖绑架」，依赖审计意识的早期催化剂 |
| npm event-stream 投毒事件 | 2018 | 维护者账号被接管、流行包植入窃密代码——「信任维护者 ≠ 代码安全」，JS 生态引入完整供应链审查 |
| RustSec advisory-db + cargo-audit | 2018 | rustsec/advisory-db 成立，cargo-audit 让「已知漏洞扫描」进入 Rust 日常工作流 |
| crates.io 转向 API token | 2019~2021 | 发布从密码认证演进为 API token（2021 起强制），为最小权限与 credential 轮换铺路 |
| cargo-deny | 约 2020 | Embark Studios 发起：advisories/licenses/bans/sources 四合一许可与依赖门禁，deny.toml 声明式策略 |
| SolarWinds / Log4j 事件 | 2020~2021 | 构建链投毒 + 全局传递依赖漏洞——「信任签名」「看不见的依赖面」两大教训进入主流工程叙事 |
| SBOM 制度化（SPDX/CycloneDX） | 2021~ | 美 14028 行政令推动 SBOM 合规；SPDX（许可证/组件，Linux Foundation）与 CycloneDX（漏洞/依赖图，OWASP）成两大格式 |
| crates.io 恶意包治理 | 2022~ | RustSec advisory-db 增设恶意包（malicious）类公告，crates.io 上线包名保留与举报机制，生态把「投毒包」当作独立威胁类型公告 |
| cargo 发布侧收紧 | 2023~ | cargo package 校验更严（readme/license/描述缺失即警告到报错），`--locked`/`--dry-run` 语义完善，发布演练成本下降 |
| cargo-audit 0.20+/cargo-deny 0.16+ 迭代 | 2024~ | cargo-audit 引入 `--fix` 类建议、RustSec db 进 Rust Foundation 治理；cargo-deny 扩展 `cargo deny sbom`、`check source` 等子命令 |

本文示例以 **rustc/cargo 1.92.0（stable-aarch64-apple-darwin，rustc ded5c06cf 2025-12-08 / cargo 344c4567c 2025-10-21）** 为基线（与 ph17/ph21/ph23 及本仓库全部 rs/ 代码层一致）。**验证工具链与本环境实测口径**：cargo-audit **0.22.2**、cargo-deny **0.20.2**、cargo-sbom **0.10.0** 均在本机 `cargo install` 编译安装成功并实测（`cargo audit`/`cargo deny check`/`cargo sbom` 的输出见 3.2/3.3/3.9 与 examples 各 README，标「已验证」）；其中 cargo-deny 的 advisory 数据库更新走 git、实测曾因网络代理 502 中断——deny 通过 `db-path = "~/.cargo/advisory-db"` 复用 cargo audit 已拉取的缓存库（命中输出见 3.3 与 examples/ex02），网络不可用时的降级口径见 project/README 验收表；`cargo package --list` / `cargo package --no-verify` / 双目录可复现构建哈希对比在本机实测通过（3.8/3.10，标「已验证」）；crates.io **真实发布未验证**（需账号与 API token，本环境无凭据，只做 `cargo package` 本地演练，真实 `cargo publish` 语义按官方文档说明并标「未在本环境验证」）；**制品签名**（发布包 GPG/signing 生态）未在本环境验证，属 ph17 预告中「按工具链现状」的部分。**这个阶段是「把别人写好的检查工具接到自己的工程流程里」**——语法点极少，难的是读懂每件工具防什么攻击、把策略写成声明式配置、并让输出成为可行动的决策。学习重点是建立「每次发布前我凭什么信这套依赖树」的清单式直觉。

## 3. 语法与参数

本章按 roadmap 第 24 节学习内容展开：供应链风险模型 → cargo audit → cargo deny（配置总览 → licenses → bans/sources）→ 许可证合规 → secret 管理 → 可复现构建 → SBOM → crates.io 发布流程 → 版本发布策略。核心心法是每件工具都回答三问——**它防什么攻击、怎么配、怎么解读输出**。全部命令的完整工程形态见 [`examples/`](./examples/)，练习见 [`exercises/`](./exercises/)，综合项目见 [`project/`](./project/)。

### 3.1 供应链风险模型：你的依赖树里有几道信任缺口

Rust 程序的安全边界不止是「我的代码」，而是 **`cargo tree` 展开后整棵依赖树**——直接依赖（你在 `Cargo.toml` 里写的）与传递依赖（依赖的依赖，你往往没读过它的源码）共同构成「被信任面」。ph17 讲过引入前评审，本阶段补上**持续性的信任模型**：依赖一旦进入 `Cargo.lock`，它带来的风险不是一次性的，而是随上游发布、随你的使用方式持续变化。

```text
你的 crate
 ├── 直接依赖 A（你选过、评审过）           ← 第一道信任决策（ph17 六维评审）
 │    └── 传递依赖 A1 / A2                    ← 你可能没看过（审计工具的射程）
 ├── 直接依赖 B（含 build.rs / proc-macro）   ← 构建期执行任意代码的面
 └── dev-dependencies（只进测试与 example）   ← 常被忽略，恶意代码也能跑
```

风险按攻击手法分类，Rust 生态里能落地成「工具可拦」的威胁如下：

| 威胁 | 手法 | 谁受害 | 工具怎么拦 |
|------|------|--------|-----------|
| 已知漏洞（CVE） | 上游库存在已公告漏洞且未修复/未升级 | 所有依赖它的下游 | cargo audit 对照 RustSec db 扫 Cargo.lock |
| typosquatting（仿冒名） | 注册与热门包一字之差的包名（如 `tokio-rs`、`serde_yaml` 的仿冒变体）诱导误装 | 手滑复制错误包名的开发者 | cargo deny `sources` 限定来源 + 安装前 `cargo info` 核对包名/作者/repository |
| 投毒包（malicious） | 上传功能正常但含后门的包，或收购停更包后植入代码 | 引入该包的工程 | RustSec db 恶意包公告 + 引入前评审（ph17）+ 供应链可见性 |
| 依赖混淆 | 私有 registry 包名与公共 crates.io 同名，解析器取错源 | 使用私有 registry 的企业 | deny.toml `sources` 段白名单/黑名单源 |
| 构建期代码执行 | `build.rs` / proc-macro 在构建机任意执行 | CI 与构建机 | 最小依赖面（ph17）、vendor 后源码审查、受控构建环境 |
| 上游被攻破/版本被劫持 | 维护者账号泄露后发布恶意新版本 | 升级到该版本的工程 | `cargo update` 后立刻 audit、锁定 + 升级评审、发布签名（成熟生态才有） |
| 许可证不合规 | 引入 copyleft 或禁商用许可的库 | 分发商业软件的团队 | cargo deny `licenses` 段 allow 清单 |

**为什么这样设计**：供应链威胁的共性是**受害方把信任投给了自己不完整了解的对象**。工具不消除信任，而是把「信任」从不可见变成可核验：锁文件让你知道依赖的精确版本（Cargo.lock），advisory db 让你知道这些版本有没有已知漏洞（cargo audit），策略文件让你预先声明「什么许可/来源可接受」（deny.toml）。RustSec advisory-db 自 2022 年起对 crates.io 上被公告的投毒包给出 **malicious 类公告**（此类包建议直接规避或替换）——**具体包名单随数据库实时变化，本笔记不固化过期清单**，需要时用 3.2 的检索命令现查。

> 本阶段把「恶意代码、已知漏洞」当作可自动核验的对象；**语言级的内存安全（unsafe/FFI 的 soundness）是 ph14/ph23 的审查对象**，这里不做运行时漏洞分析——工具管「依赖关系是否可信」，编译器管「代码本身是否安全」。

### 3.2 cargo audit：对照 RustSec advisory-db 扫已知漏洞

cargo-audit 是**已知漏洞扫描器**：它解析 `Cargo.lock`，把每个依赖的精确版本与 RustSec advisory-db（机器可读公告库，托管于 GitHub，受 Rust Foundation 治理）里的 `advisory.toml` 匹配，命中即报。它不分析代码、不评估逻辑漏洞——它回答一个窄而确定的问题：**当前锁定的版本集合里，有没有已公告的漏洞**。安装与运行：

```bash
# 安装（独立 cargo 子命令，非 rustup 组件）：
export PATH="$HOME/.cargo/bin:$PATH"
cargo install cargo-audit --locked        # 需联网拉 crates.io 编译（较久）

# 运行（首次会拉取 RustSec advisory-db，之后增量更新）：
cd <你的 crate 工程>
cargo audit                                # 全量扫描 Cargo.lock
cargo audit -f json                        # 机器可读输出（CI 解析用）
cargo audit --fix                          # 尝试把受影响的依赖升到已修复版本（会自动 cargo update）
cargo audit database update                # 手动更新本地 advisory db 缓存
```

**cargo audit 报告怎么读**——命中一个漏洞时输出含以下字段（examples/ex01 的「含故意旧依赖」实验工程给出了本机真实输出）：

| 输出字段 | 含义 | 行动含义 |
|---------|------|---------|
| `RUSTSEC-2020-0071` 类 ID | RustSec 公告号（`RUSTSEC-年份-序号`），唯一标识 | 检索原文与影响细节用 |
| `CVE-2020-…` / `GHSA-…`（alias） | 跨库关联编号（NVD/GitHub） | 查通用信息源 |
| `Title` / `Date` | 漏洞标题与公告日期 | 判断时效与热度 |
| `CVSS` 分数 | 严重度量化（0~10，含向量串） | 优先级排序参考 |
| `Version` / `Patched` / `Unaffected` | 你锁定的版本 / 已修复版本 / 不受影响版本 | 决策核心 |
| 受影响的依赖链（`Dependency tree`） | 谁直接依赖了它（可能有多级） | 定位升级点与影响面 |

**漏洞处理策略**（roadmap 验收「能为依赖漏洞制定处理策略」）按优先级排列：

| 策略 | 动作 | 何时用 |
|------|------|--------|
| 升级（首选） | `cargo update -p <crate>` 升到 `Patched` 版本，重跑 test | 上游已发布修复版且无破坏性变更（ph17 的 semver 升级评审在此复用） |
| 补丁/降级规避 | 若 `Patched` 不可用，评估 `Unaffected` 版本区间或临时锁定 | 上游未修或修复版不兼容当前 API |
| 替换依赖 | 用同功能替代 crate 移除受影响者 | 漏洞长期无解 / 上游停更多年（ph17「依赖树膨胀」评审的升级版） |
| 接受并登记 | 漏洞在不可达路径（如仅 Windows 触发而你只发 Linux），写进风险登记 | 需要理由充分且可审计；CI 里配置 ignore 例外并注明理由 |
| 切断入口 | 减少传递依赖或关闭触发 feature | 漏洞在被 `default-features` 拖入的无关能力上 |

**常见错误**：
- 以为 `cargo audit` 全绿 = 依赖安全：它只查「已公告」，查不了未公开漏洞与恶意逻辑——audit 全绿只说明「已知漏洞集合内干净」，ph17 的引入前评审与最小依赖面仍是第一道防线；
- 没有 Cargo.lock 就 audit：库工程（ph16 策略：库不提交 lock）在 CI 里要用 `cargo generate-lockfile` 或临时锁文件才能扫——**audit 的对象是 lock 不是 manifest**；
- 命中漏洞就立刻 `cargo update --all`：盲升可能引入 breaking change（0.x 生态尤其），升级后必须过 test + ph17 的 changelog 评审；
- 忽略「仅某平台受影响」信息：`cargo audit` 会标注平台相关漏洞，Windows 专用漏洞不影响 Linux 产物，但仍建议登记而非忽略。

本机实测（cargo-audit **0.22.2**）的真实输出——实验工程 ph24-vulndemo 故意把依赖锁在存在公告的 `time 0.1.35`（`time = "=0.1.35"`），`cargo audit` 命中 RUSTSEC-2020-0071 且退出码非零：

```text
$ cargo audit        # 在 /tmp/ph24-exp/vulndemo 内执行（依赖 time 0.1.35）
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
# 退出码 1 —— CI 里 audit 直接让门禁变红
```

对照解读：命中行的每对 `字段: 值` 对应上表的解读列——`Solution: Upgrade to >=0.2.23` 就是处理策略「升级」的直接答案；干净工程（零依赖的 ph24-pkgdemo）同版本 audit 输出只有前四行（fetch/loaded/updating/scanning）且退出码 0，不打印「No vulnerabilities」结论行——**audit 的"全绿"是安静的，命中才是响亮的**。完整实验命令见 [`examples/ex01-cargo-audit`](./examples/ex01-cargo-audit/README.md)。

### 3.3 cargo deny：deny.toml 四段结构的策略门禁

cargo-deny 把四类检查合成**一个可进 CI 的门禁**：`advisories`（漏洞，与 audit 同源 RustSec db）、`licenses`（许可证 allow/deny 清单）、`bans`（版本限制与重复依赖）、`sources`（依赖来源白/黑名单）。与 cargo audit 的区别是**策略先行**：audit 只报告「有没有」，deny 让你先声明「什么可接受」，然后 `cargo deny check` 对任何违背策略的依赖树返回非零退出码——门禁天然可挂在 CI 的 `-D` 语义上。

```bash
# 安装与运行：
cargo install cargo-deny --locked          # 独立子命令（本机 0.20.2 安装成功，已验证）
cargo deny init                            # 生成默认 deny.toml
cargo deny check                           # 全部检查（等价 check advisories licenses bans sources）
cargo deny check advisories                # 只查漏洞
cargo deny check licenses                  # 只查许可证
cargo deny check bans                      # 只查版本/重复
cargo deny check sources                   # 只查来源
```

**deny.toml 的结构（roadmap 示例「deny.toml 片段」的完整形态，来自 [`examples/ex02-cargo-deny-config/deny.toml`](./examples/ex02-cargo-deny-config/deny.toml)）**：

```toml
# examples/ex02-cargo-deny-config/deny.toml —— 四段结构总览（cargo-deny 0.20.2 实测校验）
[advisories]                       # 段 1：已知漏洞（与 cargo audit 同源 RustSec db）
db-path = "~/.cargo/advisory-db"   # 复用 cargo audit 已拉取的缓存库（实测离线可用）
# 注意：0.20 无 yanked 布尔键；被 yank 的版本由 ignore 条目（"crate@version"）管理
ignore = []                        # 例外清单：仅当接受并登记时填 RUSTSEC-ID + 理由

[licenses]                         # 段 2：许可证策略（3.4 详解）
allow = ["MIT", "Apache-2.0"]      # 白名单：每项是单个 SPDX 标识符（0.20 不接受 OR 表达式
                                   # —— "MIT OR Apache-2.0" 声明的包靠 MIT+Apache 都在 allow 内命中）
# 0.20 无 default 键；allow 名单收口 + unlicensed 即报错
confidence-threshold = 0.8         # SPDX 识别置信度阈值（0.20 键名；低于即判 unknown 需人工）

[bans]                             # 段 3：版本与重复依赖（3.5 详解）
multiple-versions = "deny"         # LintLevel 字符串（0.20 语义；非布尔）
wildcards = "allow"                # 依赖声明允许通配（库工程常见）
skip = []                          # 对无害的版本重复放行（记录理由）
skip-tree = []                     # 放行某棵子树内的重复

[sources]                          # 段 4：依赖来源（3.5 详解）
unknown-registry = "deny"          # 未知 registry 默认拒绝
unknown-git = "deny"               # git 依赖默认拒绝（发布 crate 不该有）
allow-registry = ["https://github.com/rust-lang/crates.io-index"]  # crates.io 白名单
allow-git = []                     # 白名单 git 源（如公司内部仓库）
```

**它防什么攻击**：`advisories` 防「已知漏洞进 CI」；`licenses` 防「无许可/不兼容许可/错误 SPDX 标识的包混进商业分发」（3.6）；`bans` 防「同 crate 多版本并存导致修了 A 链没修 B 链、或 lock 失控」；`sources` 防「依赖混淆（私有 registry 被公共源顶替）与发布物偷偷依赖 git 源」。

**常见错误**：
- 以为 deny.toml 写了就生效：它**不会自动生效**，必须跑 `cargo deny check`（本地或 CI）——配置是声明、check 是执行；
- 按旧版教程写 `[licenses] default = "deny"` / `confidence = 0.8`：cargo-deny **0.20 已无 default 键**（allow 名单收口 + unlicensed 即报错）、置信度键名是 `confidence-threshold`——deny.toml schema 随版本演进，**写配置前用 `cargo deny init` 生成权威模板对照**（examples/ex02 的实测踩坑实录）；
- 把 `yanked = true` / `multiple-versions = true` 当布尔写：0.20 中这些是 **LintLevel**（`"deny"`/`"warn"` 字符串）——schema 错误会让 deny 直接拒绝解析配置（实测报 `expected LintLevel`）；
- `allow` 只含 `MIT` 而依赖声明 `MIT OR Apache-2.0`：0.20 的 allow 每项是单个 SPDX 标识符，**双许可可靠「把 OR 两侧都 allow」命中**，不必也不可把 `"MIT OR Apache-2.0"` 整串写进 allow（实测报 `expected a WITH here`）；
- 把 git 依赖的 crate 发布上 crates.io：cargo publish 会拒绝含 git 依赖的库（3.10），deny 的 `sources.unknown-git = "deny"` 在本地就把这类问题拦下。

> cargo-deny **0.20 已移除 `sbom` 子命令**（可用命令 check/fetch/init/list），SBOM 生成走独立工具 **cargo-sbom 0.10.0**（本机实测，见 3.9 与 examples/ex05）；`cargo deny list`（0.20 新增）输出「许可证 × crate」清单，是 3.4 之外整理许可证矩阵的另一入口（examples/ex02 实测）。

### 3.4 cargo deny：licenses 许可证检查的 allow/deny 清单

`[licenses]` 段是**许可证门禁**——cargo-deny 会读取依赖树里每个 crate 的 `license` 元数据（SPDX 表达式），与 allow/deny 清单比对。这是「软件成分合规」里最容易自动化的一环，也是商业分发前必须过的一关（3.6 讲许可证本身的语义）。**它防的攻击不是恶意代码，而是合规事故**：把 GPL 系代码混进闭源商业产物、把无许可声明的包带进交付物、或依赖树里混入你根本不知道存在但带传染性许可的传递依赖。

**allow 清单怎么配**——常见做法按你的分发模式分三档：

| 分发模式 | 建议 allow | 理由 |
|---------|-----------|------|
| 内部应用（不对外分发代码） | `["MIT", "Apache-2.0", "BSD-3-Clause", "ISC", "MPL-2.0", "Unicode-3.0", "Zlib", "0BSD"]` | 宽松许可几乎都不影响内部使用，宽松集合减小误伤 |
| 商业闭源分发（不提供源码） | 上档 + 谨慎评估后补个例；`default = "deny"` 强制逐例评估 | MPL-2.0（文件级 copyleft）需逐文件看；GPL/AGPL 一般不允 |
| 开源发布 | 上档 + 明示项目自身许可的兼容集 | 若项目 MIT/Apache 双许可，GPL 依赖会污染再分发条款，需团队决策 |

**SPDX 表达式在配置里的正确写法**——注意 allow 列表的语法在 cargo-deny 0.20 中的边界（实测：允许单个 SPDX 标识符与 `WITH` 例外，**不接受 `OR`/`AND` 组合整串**）：

```toml
[licenses]
allow = [
    "MIT",                                 # 单个 SPDX 标识符（包声明 OR/AND 组合时，
    "Apache-2.0",                          # 只要表达式各成分都落在 allow 内即命中——双许可不用写 OR 整串）
    "Apache-2.0 WITH LLVM-exception",      # WITH 例外：可以出现在 allow 里
]
```

**常见错误**：
- 把 `"MIT OR Apache-2.0"` 整串写进 allow：cargo-deny 0.20 实测报 `expected a WITH here`——OR/AND 是**包声明侧**的表达式，配置侧只需把各成分分别 allow（表达式真值语义由 deny 处理：命中任一支即合规，`AND` 要求各成分都合规）；
- 忽略 `license` 字段缺失的包：老 crate 常没写 license 或写了 `license-file`，deny 报 `unlicensed`/`unknown`——正确动作是补查其仓库的 LICENSE 文件后用 `[[licenses.clarify]]` 人工指定或登记，而不是直接 allow-all；
- 许可证「漏网」只靠 `cargo deny check licenses` 一次排查：包一旦升级，`license` 元数据可能变化——门禁要挂 CI，随每次构建检查（project 的 release-check.sh 把这一步做成了流水线 step）。

本机实测输出：`cargo deny check licenses` 对 `examples/ex02` 的 deny.toml 与含真实三方依赖的样例工程运行——命中「根包未声明 license」时报 `error[unlicensed]` 并使 `licenses FAILED`，同时对 allow 里未遇见的许可给出 `warning[license-not-encountered]`（真实输出见 [`examples/ex02`](./examples/ex02-cargo-deny-config/README.md)，标「已验证」）。

### 3.5 cargo deny：bans 版本限制 / sources 来源限制

**bans 段防两类问题**——「同一 crate 的多个版本并存」（版本分叉）与「声明了不该有的版本约束」：

```toml
[bans]
multiple-versions = "deny"     # LintLevel 字符串（0.20 语义）：同 crate 多版本 → 报错
# 但生态现实是：传递依赖常各自锁版本，多版本在 lock 里很常见——
# 用 skip 给出有理由的放行（理由=注释，可审计；0.20 的 skip 条目形如 "crate@version"）
skip = [
    # "time@0.1.35",            # 例：time 0.1 与 0.3 并存是历史遗留，0.1 仅被 log 0.4 的旧链使用
]
# 或用 skip-tree 放行某个依赖整棵子树（如 bindgen 的 libloading 链）
# skip-tree = ["criterion@0.5"]
```

多版本并存的危害是**修复不对称**：cargo audit 报了 time 0.1 的漏洞，你升了 0.3 链，但 0.1 的副本还在 lock 里——`multiple-versions` 把这种「视觉上修好、实际上没修干净」的状态变成报错。真正消除分叉靠 `cargo update -p <crate> --precise <版本>`（把不同要求合并到同一版本）或改直接依赖的版本区间（ph17 的 `cargo tree -d` 定位谁引入了第二份）。

**sources 段防依赖混淆与来源失控**：

```toml
[sources]
unknown-registry = "deny"    # 只信 crates.io（与私有 registry 白名单）
unknown-git = "deny"         # 发布 crate 不得含 git 依赖
allow-git = []               # 内部仓库的 git 源在此列白（记理由）
```

**它防什么**：私有 registry 的企业场景里，若私有包名与 crates.io 公共包重名，解析器可能取错源（依赖混淆）；把 `unknown-registry` 设为 deny 并白名单自家 registry，就杜绝了「公共同名包顶替内部包」。`unknown-git = "deny"` 则守护发布物：git 依赖没有版本语义、不可审计复现，crates.io 上也不允许（3.10），在门禁层提前拦截比发布时被 cargo 拒绝便宜。

**常见错误**：
- 一出多版本报错就无脑 `skip`：skip 只该用于「真实无害」的并存（如构建期工具链隔离），多数情况应 `--precise` 合并或升级直接依赖来消除；
- 允许任意 git 源：git 依赖绕过 semver、无不可变版本，允许一个就打开了「依赖指向可变的 commit」的口子——即使要放行也应 `allow-git` 精确列源。

### 3.6 许可证合规：SPDX 标识、常见矩阵与双许可惯例

许可证是「发布包会长期携带的法律元数据」，比代码本身更难改。Rust 侧的工程形态是三层：**每个 crate 在 `Cargo.toml` 声明 SPDX 标识 → cargo package/publish 校验其存在 → cargo deny 在依赖树侧按策略把关**。SPDX（Software Package Data Exchange）是许可证的标准化短标识符系统（由 Linux Foundation 维护），`license = "MIT"`、`license = "Apache-2.0"` 都是 SPDX 标识符；`OR`/`AND`/`WITH` 构成表达式表达组合许可与例外条款。

**为什么 crate 作者要写 license**：crates.io 的包在被别人依赖时，`license` 字段是下游合规工具（cargo deny、scancode 等）唯一自动可读的许可证信息。缺 license 字段的包会直接挡在 `default = "deny"` 门禁外，等于把自己从商业生态里排除。Rust 社区的默认答案是**双许可 Apache-2.0 OR MIT**——两个宽松许可互补（Apache-2.0 含专利授权条款、MIT 更简短通用），使用者任选其一即合规，这也是 ph17 提到的 crates.io 上最主流的库许可模式。

**常见许可证矩阵**（ph17 已给判断维度，这里给可直接对照的语义表）：

| SPDX 标识 | 类别 | 分发闭源产物 | 修改后闭源再分发 | 一句话直觉 |
|-----------|------|:---:|:---:|-----------|
| `MIT` | 宽松 | 允许 | 允许 | 最简宽许，保留版权声明即可 |
| `Apache-2.0` | 宽松 | 允许 | 允许 | MIT + 专利授权，大厂偏好 |
| `BSD-3-Clause` | 宽松 | 允许 | 允许 | 与 MIT 近似，禁止用作者名义背书 |
| `ISC` | 宽松 | 允许 | 允许 | MIT 的简化变体，OpenBSD 传统 |
| `0BSD` | 公共领域式 | 允许 | 允许 | 连版权声明都不要求 |
| `MPL-2.0` | 弱 copyleft | 允许（文件级） | 修改的该文件需开源 | 文件级传染：改了什么文件，什么文件开源 |
| `LGPL-2.1/3.0` | 弱 copyleft | 允许（动态链接） | 库本体修改需开源 | 静态链接/修改库要提供对应源码 |
| `GPL-3.0` | 强 copyleft | **不允许**（除非整体开源） | 不允许 | 传染到整个再分发产物 |
| `AGPL-3.0` | 强 copyleft + 网络 | **不允许** | 不允许 | GPL + 网络服务视为分发（SaaS 陷阱） |
| `Unlicense`/`CC0-1.0` | 放弃版权 | 允许 | 允许 | 公共领域；CC0 在部分司法区有争议但 Rust 生态接受 |

```toml
# Cargo.toml —— 作者侧怎么写（ph24-pkgdemo 实测样例）
[package]
name = "ph24-pkgdemo"
version = "0.1.0"
license = "MIT OR Apache-2.0"     # SPDX 表达式：双许可
# 若用 license-file（非标准标识），cargo publish 会警告——首选 license 字段
# description / readme / repository / keywords / categories 见 3.10 的发布前置检查
```

**常见错误**：
- 只写 `license = "MIT"` 却同时放了两个 LICENSE 文件：元数据与文件不一致，下游按元数据判断会漏掉 Apache 选项——要么改表达式要么删多余文件；
- 把「自己项目的许可」误当「依赖的许可约束」：项目本身 GPL 不代表不能依赖 MIT 包（MIT 允许被 GPL 项目使用），反向（MIT 项目依赖 GPL 包）才是问题——判断方向是**依赖的许可 ⊂ 你产物的分发约束**；
- 直接拷贝网上模板代码而不知其许可：代码片段级风险不体现在 Cargo.toml，但在商业交付物里同样真实——ph17 评审清单的延伸。

### 3.7 secret 管理：最小权限、注入纪律与密钥库概念

secret（API token、数据库口令、签名私钥）是供应链里**最容易被「顺手」泄露**的一环：进 git 历史就永远删不干净，进依赖发布物就随包分发。Rust 工程的 secret 管理围绕三条纪律：**不入库、不硬编码、最小权限注入**。

**三条纪律的最小落地**：

```bash
# 1. 不入库：.env / 密钥文件进 .gitignore（且确认从未 commit）
printf '.env\n*.pem\n*.key\n' >> .gitignore
# 若已误 commit：立即轮换该 secret（git 历史里的旧值视为已泄露），别指望 git rm 能抹掉

# 2. 不硬编码：代码里只读环境变量（见下方 Rust 示例）
# 3. 最小权限注入：CI/部署平台的 secret 只授予需要的 job，按环境隔离
```

```rust
// examples/ex06-secret-handling —— 从环境变量读 secret 的最小形态（已验证，见该目录）
// secret 不落代码、不落 Cargo.toml、不落日志；读不到就显式失败而非用空值继续
use std::env;

fn load_secret(name: &str) -> Result<String, String> {
    env::var(name).map_err(|_| format!("缺少环境变量 {name}：请在运行环境注入，不要写进代码"))
}

fn main() -> Result<(), String> {
    let token = load_secret("CRATES_IO_TOKEN")?;  // cargo login 场景的模拟
    // 只在本进程内使用，绝不 println!/dbg! 打印
    let _len = token.len();                        // 演示「用到但不泄露」
    Ok(())
}
```

**cargo 侧的 secret 形态是 `cargo login` 的凭证存储**：

```bash
cargo login                      # 交互式输入 API token
cargo logout                     # 删除本地存储的 token
# 本地凭证落点：~/.cargo/credentials.toml（cargo 1.68+ 默认即该文件），
# 权限 600，绝不 commit；CI 里改用环境变量注入（见下）
```

CI 场景把 token 通过平台 secret 注入环境变量、再喂给 cargo：

```yaml
# project/.github/workflows/release.yml 片段（发布 job 最小权限形态）
- name: Publish to crates.io
  env:
    CARGO_REGISTRY_TOKEN: ${{ secrets.CRATES_IO_TOKEN }}   # 平台 secret，永不进日志
  run: cargo publish
```

**它防什么攻击**：防「代码仓库泄露 → 凭据被爬取 → 攻击者以你的身份发布恶意版本（供应链投毒的最上游入口）」。event-stream 类事件里，维护者 token 泄露正是投毒起点——**secret 纪律保护的不是你自己的账号，是所有依赖你包的工程**。

**为什么这样设计**：环境变量注入而不是代码内置，是因为环境是「运行时才存在」的边界——同一份代码在开发/CI/生产不同环境拿不同 secret，代码本身零秘密。最小权限原则（principle of least privilege）在这里的工程形态是：**token 只给需要的 job、只给需要它的 crate、按环境隔离、可单独轮换**。crates.io 的 API token 自 2021 年起支持**作用域**（只读/发布、限具体 crate、限过期时间）——给 CI 一个「只能发布 ph24-pkgdemo 且 90 天过期」的 token，比给全权 token 安全一个量级。

**进阶（概念层，本阶段不实现）**：团队级 secret 用 **SOPS**（把 secret 加密后仍放 git，解密靠 KMS/age 密钥）或 **Vault/云 KMS**（运行时取用、可审计轮换）管理——原理不变：**加密/保管与使用分离，使用侧永远只有最小权限**。本仓库不演示真实密钥操作，涉及命令见 examples/ex06 的说明。

**常见错误**：
- 把 token 写进 `Cargo.toml`、`build.rs` 或文档示例：任何进 git 的文本都默认已泄露；
- `echo $TOKEN` 打到 CI 日志：cargo 与平台通常自动脱敏，但自定义 step 打印环境变量会直接暴露；
- 给 CI 配「全权永不过期」的 token：违背最小权限，一次 CI 配置泄露 = 账号级泄露；
- 用 `.env` 却忘了它进了 `.gitignore` 之前的历史：`.env` 一旦 commit，轮换优于删除。

### 3.8 可复现构建：同一 commit 长出同一个制品

「可复现构建」（reproducible/deterministic build）指：**给定同一份源码（同一 commit）与同一工具链，任何时间、任何干净环境下构建出的制品字节一致**。它是供应链信任的基石——如果同一个 commit 今天构建的包和三个月前不一样，你无法判断「发布的那份」是不是就是「审查过的那份」。Rust 的可复现构建分三层：**依赖锁定（lock）→ 工具链固定（toolchain）→ 构建确定性（确定性编译）**。

| 层 | 手段 | 管什么 | 出处 |
|----|------|--------|------|
| 依赖锁定 | 应用提交 `Cargo.lock` + CI 用 `--locked` | 依赖版本精确到哈希级，`cargo build` 不漂移 | ph16（策略）+ 本层（验证） |
| 工具链固定 | `rust-toolchain.toml` 声明 channel/components | rustc/cargo 版本一致（编译器不同产物可不同） | ph16 |
| 构建确定性 | rustc 同输入同输出的确定性编译 | 同一工具链+依赖下产物逐字节一致 | 本层（实测验证） |

**锁文件的两种工程口径**（ph16 已给策略，这里补命令形态）：应用与可发布产物**提交 Cargo.lock**，一切构建带 `--locked`（lock 与 manifest 不符即失败）；库工程 lock 不入库，但发布前用临时 lock 跑审计与 package 演练（3.10）。`cargo vendor` 把依赖树源码下载进本地目录（`cargo vendor` 生成 vendor/ 与 `.cargo/config.toml` 的 source 替换配置），实现**离线可复现构建**——CI/内网构建机用它摆脱对 crates.io 的实时依赖（ph17 预告的「cargo vendor 离线供应链」）。

**构建确定性怎么验证（本机实测，标「已验证」）**：本环境用两个完全独立的 `CARGO_TARGET_DIR` 对同一 commit 各做一次干净 `cargo build --release`，对比产物哈希（完整命令与输出见 [`examples/ex04-reproducible-build`](./examples/ex04-reproducible-build/README.md)）：

```bash
# 同一源码同一工具链，两个独立 target 目录各构建一次
CARGO_TARGET_DIR=/tmp/ph24-t1 cargo build --release
CARGO_TARGET_DIR=/tmp/ph24-t2 cargo build --release
shasum -a 256 /tmp/ph24-t1/release/ph24-reprobin /tmp/ph24-t2/release/ph24-reprobin
# 实测输出（两行哈希完全相同 = 产物可复现）：
# 1205b2a934974b02209700bdbe6f0a5b96e0fa6ee112ce84c7b90c88a26fc82c  /tmp/ph24-t1/release/ph24-reprobin
# 1205b2a934974b02209700bdbe6f0a5b96e0fa6ee112ce84c7b90c88a26fc82c  /tmp/ph24-t2/release/ph24-reprobin
```

**可复现的边界（哪些差异会破坏哈希一致）**：
- **平台/CPU 差异**：跨 macOS/Linux/Windows 的产物天然不同（不同链接器、平台元数据）——可复现构建的正确比较域是「同平台同工具链」；
- **profile 差异**：`debug` vs `release`、`lto`/`codegen-units` 等 profile 参数不同产物即不同（ph22 讲过 profile 的影响）；
- **环境变量嵌入**：`build.rs` 若把路径/时间戳编进产物，确定性即破——保持 build.rs 纯函数化是库作者责任；
- **非 rustc 环节**：链接器版本、系统库差异——严格复现需容器级环境固定（CI 的 rust-cache 键就绑 rustc 版本 + lock hash，ph21 已用）。

**常见错误**：
- 库不提交 lock 就声称「可复现」：库的可复现性只能通过消费者锁文件体现，发布物要可复现得在发布流程里用锁定环境打包（3.10 的 `cargo package` 用当前 lock）；
- 只在有增量缓存的目录里比哈希：增量命中必然相同，验证确定性必须干净构建（双目录或清 target）；
- 把「同机器重编一致」当可复现：真正的可复现要经得起不同时间/不同干净环境（CI 与本地互证），这需要 lock + toolchain + 确定性三件事齐全。

### 3.9 SBOM：让发布物自带「成分清单」

SBOM（Software Bill of Materials，软件物料清单）是**随软件交付的成分声明**：列出制品包含哪些组件、各自版本与许可证。它的价值不在生成那一刻，而在下游——**当一个新的 CVE 公告出现时，持有 SBOM 的团队能在几分钟内回答「我是否受影响」，而不是翻遍每个仓库**（Log4j 事件的教训：影响面不可见时，修复无从扩散）。SBOM 因此常被比作「食品配料表」或「集装箱货物清单」。

**两种主流格式**：

| 格式 | 维护方 | 侧重 | 形态 |
|------|--------|------|------|
| SPDX | Linux Foundation | 许可证合规、组件与版权信息 | 支持 tag-value/JSON/RDF；Rust 生态默认出口 |
| CycloneDX | OWASP | 依赖图、漏洞引用（含 BOM-Link） | JSON/XML；偏安全分析流水线 |

**Rust 侧怎么生成**——cargo-deny **0.20 已移除 sbom 子命令**（可用命令 check/fetch/init/list），SBOM 生成走独立工具 **cargo-sbom**（本项目实测 0.10.0）；另一社区工具 cargo-spdx 也可选。命令形态（实测）：

```bash
# cargo-sbom 生成 SPDX-2.3（默认格式；本机 0.10.0 实测通过，标「已验证」）
cargo install cargo-sbom --locked
cd <含 Cargo.lock 的 cargo 工程>
cargo sbom --output-format spdx_json_2_3 > sbom.spdx.json          # SPDX-2.3
cargo sbom --output-format cyclone_dx_json_1_6 > sbom.cdx.json     # CycloneDX 1.6
```

实测结构（cargo-sbom 0.10.0 对依赖 time 0.1.35 链的实验工程；完整 JSON 见 [`examples/ex05-sbom-generate/sample-spdx-2.3.json`](./examples/ex05-sbom-generate/sample-spdx-2.3.json)）：SPDX 侧生成 `spdxVersion: SPDX-2.3`、5 个 packages（根包 license 为 NOASSERTION——它把「未声明许可」如实写进物料单）+ 7 条 DEPENDS_ON 关系；CycloneDX 侧 4 个 components（不含根包）且每个带 `license.expression`。两格式选型与差异见 ex05 README。

**SBOM 里有什么**（以 SPDX 为例，逻辑结构而非具体字段拼写）：

```jsonc
{
  "spdxVersion": "SPDX-2.3",
  "name": "ph24-pkgdemo-0.1.0",
  "packages": [
    { "name": "ph24-pkgdemo", "versionInfo": "0.1.0",
      "licenseConcluded": "MIT OR Apache-2.0" }
    // …依赖树的每个 crate 一项：包名 + 版本 + 许可证 + 下载来源
  ],
  "relationships": [ /* 依赖关系边：ph24-pkgdemo DEPENDS_ON … */ ]
}
```

**发布物附 SBOM 的实践**：把 SBOM 与制品一起归档（release asset 或 crate 包旁的校验附件），CI 在打包产物生成后立即生成 SBOM，保证成分声明与制品同源同版。**检查 SBOM 是否有有效成分清单，需要一批真实第三方依赖**——零依赖 crate 生成的是「只有自己一项」的最小 SBOM；要看到「有内容的清单」，examples/ex05 用含三方依赖的实验工程生成了样例（project 的 relpipe 带一个 hex 依赖，release.yml 的 publish job 示范了 SBOM attach release）。

> **SBOM 与 ph17 供应链章节的关系**：ph17 的依赖评审是「引入前」的个体判断，SBOM 是「引入后」的集体可见性——前者决定某个依赖该不该进，后者让全树依赖在漏洞公告时能被程序化筛查。两者互补，SBOM 不替代评审，评审也不产生可见性。

**常见错误**：
- 生成一次就归档再也不更新：SBOM 必须与每次发布同步生成（依赖一变清单即过期）；
- 把 SBOM 当「合规交差」的文档：它的自动化价值在于**能被下游工具解析**——选 JSON/标准格式、固定版本（如 SPDX-2.3），比 PDF 式报告有用得多；
- 零依赖 crate 就跳过：最小 SBOM 也是基线（至少声明了自己与许可），养成「发布=制品+SBOM+校验」的固定姿势，到了有几十个依赖的项目才不会漏。

### 3.10 crates.io 发布流程：从 package 演练到 publish

发布是把 crate 变成「别人可以依赖的公共制品」的动作。crates.io 上**已发布的版本不可变、不可删**——所以发布流程的核心是**发布前的审查演练**，把「发出去就收不回」的后果前置到本地可检查。真实 `cargo publish` 需要 crates.io 账号与 API token（本环境无凭据，标「未在本环境验证」），但流程的每一步（内容审查、打包、校验）都可在本地演练。

**发布前置检查（发布前 checklist 的核心）**：

```text
□ Cargo.toml 元数据完整：name/version/edition/description/license/readme
   （发布库必需：description、license、readme；repository/keywords/categories 推荐）
□ 版本号正确（semver，3.11），Cargo.lock 当前（package 会把 lock 一并带上）
□ README 与文档存在（readme 字段指向的文件会被渲染成 crates.io 首页）
□ 无 git/路径依赖（crates.io 拒绝；Cargo.lock 里 origin 必须都是 crates.io）
□ cargo package --list 审查：要发布的文件集合符合预期、无 target/ 与秘密文件混入
□ cargo test / clippy / audit 全绿（ph21 门禁 + 本阶段审计）
□ CHANGELOG 已更新、版本号与变更一致（3.11）
```

**本地演练三连（本机实测，标「已验证」）**：

```bash
cd ph24-pkgdemo
cargo package --list            # ① 只列将打包的文件（不发包）——内容审查入口
cargo package --no-verify       # ② 本地打包成 .crate（跳过 verify 以省时间）→ 生成 target/package/
cargo package                   # ③ 完整打包（含 verify：编译+测试通过才打包成功）
```

本机实测 `cargo package --list` 与 `--no-verify` 的真实输出（在 /tmp 非 VCS 目录打包，7 文件；**同一工程放 git 仓库内打包会多出 `.cargo_vcs_info.json` 与随包加入的 CHANGELOG 等 = 9 文件**，examples/ex07 README 记录的是仓库内版本）：

```text
$ cargo package --list            # 非 VCS 目录（/tmp）实测
Cargo.lock
Cargo.toml
Cargo.toml.orig
LICENSE-APACHE
LICENSE-MIT
README.md
src/lib.rs
$ cargo package --no-verify
   Packaging ph24-pkgdemo v0.1.0 (/private/tmp/ph24-exp/pkgdemo)
    Packaged 7 files, 2.7KiB (1.6KiB compressed)
```

**package 输出怎么审**：核对每一行——`src/` 下是不是只有该发布的源码（`Cargo.toml.orig` 是 cargo 生成的 manifest 快照，正常）；LICENSE/README 有没有随包（缺了会在 crates.io 显示为无许可/无说明）；有没有把测试夹具、`.env`、`target/` 之类不该发布的东西打进去（cargo 默认排除 target 与 gitignore 文件，但 `include`/`exclude` 字段的误配置可能放行秘密文件）。

**发布与回滚**：

```bash
# 真实发布（需账号 + token，本环境未验证）：
cargo login                        # 存 API token（3.7）
cargo publish                      # 发布当前版本（先跑上面的本地演练，publish 自带 verify）
cargo publish --dry-run            # 只做预检不实际上传（语义与 package 演练重叠）

# 发错版本后的补救（已发布版本不可删，只能 yank）：
cargo yank ph24-pkgdemo@0.1.1      # 从 crates.io 撤回：阻止新工程依赖它
cargo yank --undo ph24-pkgdemo@0.1.1   # 反撤回（如误 yank）
```

**yank 语义（重要）**：yank **不删除** 已下载的 `.crate`，也不破坏已有工程的构建（`Cargo.lock` 已锁定的版本照常可用）——它只阻止**新的依赖解析**选到该版本。所以「发错版本」的正解是：yank 坏版本 + 立即发布修正版本 + 在 release notes 里声明。**为什么不能删版本**：crates.io 上每个 `.crate` 都被依赖它的工程与缓存引用，删除会制造连锁的不可复现构建——不可变性是发布生态的信任基础（4.3）。

**常见错误**：
- 跳过 `cargo package --list` 直接 publish：把不该发布的文件（或漏了 LICENSE）发出去才发现不可收回；
- 把 `[dev-dependencies]` 或本地路径依赖带进发布物：cargo 会拒绝路径依赖的库发布，但 `[dev-dependencies]` 不影响发布、不会进最终包（cargo test 才需要）；
- 忘记更新版本号就 publish：同一版本重复发布会被拒（`cargo publish` 对已存在版本报错），正确流程是先 `cargo publish` 失败 → 意识到要 bump → 改 version → CHANGELOG → 重发；
- 发布后想「删掉重来」：没有这条路，只有 yank + 新版本——**发布前 checklist 的价值全在这里**。

### 3.11 版本发布策略：semver 纪律与变更可见性

semver（语义化版本）在 ph17 讲过「依赖声明的版本区间」，这里从**发布者**视角看：版本号是给下游的信号——`major.minor.patch` 的每一位 bump 都承诺了一类兼容性变化。Rust 生态有两条社区惯例让「承诺」可执行：

| 惯例 | 内容 | 为什么 |
|------|------|--------|
| **0.x 中 minor = breaking** | `0.1→0.2` 视同 major（可含破坏性变更），`0.1.x` 只做向后兼容 | Rust 生态 1.0 前大量库长期 0.x；cargo 的版本区间语义对 0.x 特殊处理（`^0.1.2` 只允许 `0.1.x`，不允许 0.2） |
| **破变更必须升 major（或 0.x 的 minor）** | patch 只含 bugfix、minor 只做向后兼容新增 | 下游 `cargo update` 在区间内自动升级，破变更混进 patch/minor 会悄悄破坏下游构建 |

**发布者视角的 semver 决策表**：

```text
修改类型                                → 版本动作
修复 bug（行为修正，不破坏 API）          → patch bump（0.1.3 → 0.1.4）
新增 API/功能（向后兼容）                → minor bump（0.1.4 → 0.2.0 或 1.2 → 1.3）
破坏性 API 变更 / MSRV 提升 / 行为大变   → major bump（0.x 时 minor；1.x 时 major）
发布候选 / 预览                          → 预发布后缀（0.3.0-alpha.1、1.0.0-rc.1）
```

**预发布版本**（`-alpha`/`-beta`/`-rc`）在 semver 里**排序在正式版之前**且**不会被 `^` 区间自动选中**——这是发布流程的关键工具：把候选版本标成 `1.0.0-rc.1` 发布，下游不会误用，你自己可以先拿真实发布流程验证（yank 演练、docs.rs 渲染、依赖方冒烟），确认无误再发 `1.0.0`。**feature 门控**与版本策略配合：新 API 先藏在新 feature 后（`[features] experimental = []`，ph17 讲过 feature 纪律），默认特性下 API 面不变，让 minor bump 的「向后兼容」承诺更可信。

**变更可见性：CHANGELOG 与 release notes**。roadmap 验收「能让版本号和变更说明一致」，工程形态是「CHANGELOG.md 跟踪 unreleased → 发版时归档 + git tag + release notes」：

```markdown
# CHANGELOG（keep-a-changelog 风格，完整模板见 examples/ex07）

## [0.2.0] - 2026-09-04
### Added
- `sum_bytes`：批量字节和计算（供集成测试与发布演练）
### Changed
- 最低支持 rustc 升至 1.85（MSRV 策略见 README）

## [0.1.0] - 2026-08-20
### Added
- 首个发布：`crc8` 逐字节校验
```

**发布策略的工程闭环**（release-check.sh 的检查项，project 落地）：bump 版本号 → 更新 CHANGELOG（把 Unreleased 归档）→ 跑质量门禁 + 审计 → `cargo package --list` 审查 → `cargo publish` → git tag `v0.2.0` → 在 tag 上写 release notes（引用 CHANGELOG 对应节）→ 附 SBOM。每一步要么本地可跑、要么在 CI 里不可跳过——**版本策略不是写文档，是让「版本号、CHANGELOG、git tag、发布物」四者永远一致的过程纪律**。

**常见错误**：
- 破变更只升 patch：下游 `^0.1.x` 区间内自动升级即崩——这是 Rust 生态最常见的版本事故；
- CHANGELOG 记录「改了啥」却不标注 Breaking：release notes 面向使用者，要明确写「升级到本版本前请阅读 BREAKING」；
- 发布后才补 CHANGELOG：变更列表依赖记忆，必然遗漏——养成「PR 合入即记 Unreleased」的习惯；
- `1.0.0` 前频繁预发布却不发正式版：`-alpha` 会被 `^` 区间跳过，长期只发预发布等于下游永远无法稳定依赖你（ph17 评审里「大版本 0 天升仓」的反面是「永远停在 0.x 预发布」）。

## 4. 底层原理

### 4.1 cargo 依赖解析：Cargo.lock 精确锁定与 semver 兼容范围

供应链工具（audit/deny/SBOM/package）全部围绕同一个事实工作：**cargo 能精确回答「当前这棵树长什么样」**——这个能力来自 Cargo.lock 与依赖解析器的配合。ph17 4.1 讲过「cargo 在 semver 契约内求一个满足全图的解」的决策面，这里补上**锁文件在信任链里的机制角色**。

```text
Cargo.toml（声明需求区间）            Cargo.lock（锁定精确版本）
serde = "^1.0"          ──resolver──▶  serde = "1.0.219"
tokio = { version = "1", … }            tokio = "1.49.0"
                    生成/更新时求解         ├── tokio-macros = "2.6.0"   ← 传递依赖一并锁定
```

机制要点：**需求是区间，锁定是点**。`cargo build` 优先读 lock——只要 lock 里的版本仍满足 manifest 的区间，就用 lock 的精确版本，不重新求解；`cargo update -p <crate>` 才在区间内寻找新解。这把「语义化区间」的解析自由度收敛成「不可变快照」，供应链工具于是有了稳定的审计对象：audit 扫的是 lock 里的**点版本**（不是区间），SBOM 列的是 lock 里的**点版本**，`cargo package` 带走的是 lock 里的**点版本**。**没有 lock，同一份 manifest 在不同时间构建出不同的树**——审计、SBOM、可复现全部失去锚点。这也是为什么库的发布物（`.crate` 携带 Cargo.lock）能复现：`.crate` 里锁定的树就是消费者拿到的树（消费者有自己的 lock 时以其为准，但 `.crate` 里的 lock 保证「打包时的树」可审）。

**锁定与升级的边界**（ph16 的锁文件策略在此得到机制解释）：应用锁文件进 git，锁定的树随代码一起评审；库不锁，因为库的「树」要由消费者的锁来决定——但库发布物里的临时 lock 承担「打包一刻的审计快照」。`--locked` 让 CI 拒绝「lock 与 manifest 不一致」，防止构建悄悄用了与评审不同的树。

### 4.2 RustSec advisory 的结构与匹配机制

cargo audit 的「准」来自 advisory-db 的结构化公告。每个公告是一个 `advisories/<类别>/RUSTSEC-YYYY-NNNN.toml`（如 `advisories/RUSTSEC-2020-0071.toml`），内容约含：

```toml
# advisory 结构示意（真实字段，非真实公告全文；examples/ex01 给完整实测输出）
[advisories]
id = "RUSTSEC-2020-0071"
package = "time"
date = "2020-11-18"
url = "https://rustsec.org/advisories/RUSTSEC-2020-0071"
title = "Potential segfault in the time crate"
[versions]
patched = [">= 0.2.23"]
affected = [">= 0.2.7, < 0.2.23"]   # 或：unaffected = [...]
[affected]
functions = { "time::…" = ["< 0.2.23"] }   # 可选：精确到受影响函数
```

**匹配机制**：cargo-audit 把 Cargo.lock 里每个包版本与公告的 `[versions]` 范围做 semver 区间比较——版本落入 `affected` 区间（或 `unaffected` 之外）即命中；`patched` 给出修复版本号。**关键认识：匹配的是「范围」不是「等号」**，所以同一个公告能覆盖该包全系受影响版本；而 `cargo audit --fix` 就是读 `patched` 后执行 `cargo update -p <pkg> --precise <patched 版本>` 的自动化。公告还带 `categories`（`code-execution`/`memory-corruption`/`crypto-failure`…）与 `cvss` 向量，`yanked`/`malicious` 标记区分「普通漏洞」与「投毒包」——处理策略随类别不同（3.2 的策略表按此分流）。

**为什么用 git 仓库存公告**：advisory-db 是公开 git 仓库（`git clone https://github.com/rustsec/advisory-db`），本地缓存即一份完整历史——扫描**离线可做**、审计过程可复现（缓存到某 commit 的 db 结果可固定）。这比「每次查中心化 API」更符合供应链信任模型：数据库本身也可被审查与固定版本。

### 4.3 crates.io 校验与 yank 机制：为什么版本不可删

crates.io 发布物是一份 **`.crate` 文件（tar.gz）**，其信任链建立在「上传内容 = 你本地打包内容」的校验上：`cargo publish` 上传前，本地 `cargo package` 先生成 `.crate`（内含所有文件的 SHA-256 checksum 清单，记录在 `.cargo_vcs_info.json` 与 cargo 的 package 校验文件里），crates.io 端对上传包做同样校验（`cargo publish` 每次上传带的校验由 cargo 与 crates.io 服务端共同核对）。**发布后 .crate 不可变**——crates.io 不提供删除 API，版本只能 yank。

**yank 的机制定位**：yank 在 crates.io 索引里把该版本标记为 `yanked`，cargo 的解析器（4.1）在**求解新依赖图**时跳过 yanked 版本，但**已有 lock 的工程不受影响**（lock 里的版本照常从本地缓存/稀疏索引取用）。所以：

```text
                    ┌─ 新工程 cargo add ph24-pkgdemo ──▶ 解析器跳过 yanked 的 0.1.1，选 0.1.2
yank 0.1.1 ─────────┤
                    └─ 已锁定 0.1.1 的工程 cargo build ─▶ lock 里有点版本，照常构建（不联网也可）
```

**为什么这套设计是对的**：可复现性要求「过去能构建的将来还能构建」——如果删除版本，所有锁住它的工程瞬间不可复现（`cargo build --locked` 直接失败）。yank 在「阻止新依赖」与「保护旧构建」之间取平衡：坏版本不再扩散，但既有的信任不被破坏。这也解释了发布者为什么把 **yank + 立即发修正版** 当标准事故流程（3.10），而不是试图抹掉历史。

**校验链的工程延伸**：对依赖方，「我拿到的 .crate 与作者发布的一致吗」由 crates.io 的 checksum 与 HTTPS 保证；对更严格的分发（内网镜像、离线供应链），`cargo vendor` + 本地 registry 校验和锁定（ph17 预告的「cargo vendor 离线供应链」）把整条拉取链收进可控范围。

## 5. 使用场景

**供应链体系不是越全越好，是按暴露面分级投入。** 关键分界是「你的产物被谁消费」：

| 角色 | 典型形态 | 需要的最小体系 | 可暂缓的 |
|------|---------|--------------|---------|
| 个人学习/一次性脚本 | 本地 cargo 工程，用完即弃 | `cargo audit` 跑一下 | deny 门禁、SBOM、发布流程 |
| 内部应用（库） | 公司内部依赖，不对外发布 | Cargo.lock + `--locked`（ph16）、CI 一道 audit/deny、secret 不落库 | SBOM（无外部消费方）、crates.io 发布 |
| 内部应用（二进制） | 部署到生产环境的服务 | 上者 + 可复现构建（双目录验证）、依赖升级评审（ph17） | SBOM（合规要求时补） |
| 开源库作者 | crates.io 发布，被未知工程依赖 | **完整体系**：audit/deny 进 CI、许可证元数据与 SPDX、CHANGELOG/semver、package 审查、发布物附 SBOM | 制品签名（生态工具仍在演化） |
| 商业分发（闭源/SaaS） | 面向客户的产物 | 完整体系 + 许可证合规门禁（3.6 矩阵）+ 依赖漏洞 SLA | 同左列——许可证矩阵是硬门槛 |

**关键判断**：库作者与内部应用的分水岭是**不可变性与暴露面**——发布到 crates.io 的版本不可删（4.3），影响不可见的下游，所以库的每个环节都要在发布前闭环；内部应用的影响面可控，可复现与审计仍是底线，但 SBOM 与发布流程的收益递减。**什么时候不需要**：原型期（ph21 对探索性代码的同一立场）、无第三方依赖的纯 std 工具（audit 空转，但保留流程习惯）。

**与其他语言生态的供应链工具对照**（为 analysis/ 与 Tenet 合成积累素材）：

| 维度 | Rust | npm/JS | Java（Gradle） | Go |
|------|------|--------|---------------|-----|
| 漏洞审计 | cargo audit（RustSec advisory-db） | npm audit（与 advisory db 联动） | dependency-check（NVD）/ OWASP | govulncheck（Go vuln db） |
| 许可门禁 | cargo deny `licenses` | license-checker / `npx license-checker` | License Gradle Plugin | `go-licenses` |
| 依赖锁定 | Cargo.lock（提交与否按 ph16 策略） | package-lock.json（默认提交） | Gradle lockfiles（`--write-locks`，可选） | go.sum + go.mod（模块哈希必锁） |
| SBOM | cargo deny sbom / cargo-spdx | CycloneDX npm plugin | CycloneDX Gradle plugin | syft / trivy |
| 来源限制 | cargo deny `sources` | npm scope/registry 配置 | 私有仓库配置 | GOPROXY 私有代理 |
| 恶意包防护 | RustSec malicious 公告 + 生态治理 | npm 恶意包扫描（发布即检）+ 审计 | 依赖扫描服务 | 模块代理校验 |

跨生态读出的规律：**五门语言的供应链工具收敛到同一组能力——锁文件/锁机制、漏洞数据库对照、许可证策略、SBOM 出口——差异在「谁默认开启」与「谁可信」**：npm 生态恶意包面最大所以 npm audit 默认最激进；Go 把「模块哈希校验」（go.sum）做成语言强制，来源信任靠代理；Rust 把「锁文件策略」交给工程决策（ph16 的应用/库分野）而把漏洞与许可交给独立工具。**对 Tenet 的启示候选：供应链可信的最小可执行集合 = 不可变锁文件 + 机器可读漏洞库 + 声明式许可/来源策略 + 可复现构建验证；其中「锁文件的提交策略按产物角色分档」与「许可策略按分发模式分档」是两处值得借鉴的工程分层**。这些观察在 analysis/ 设计解剖时再深化，本阶段只收集素材。

## 6. 代码示例

本节展示示例的关键形态，完整工程与运行命令在 [`examples/`](./examples/)。验证环境：rustc/cargo **1.92.0**（macOS arm64）；cargo-audit **0.22.2**、cargo-deny **0.20.2**、cargo-sbom **0.10.0** 均本机安装并实测；cargo/rustc 原生能力（`cargo package`/`cargo build`/双目录哈希对比）本机实测。七个示例的验证状态逐项标注：

| 示例 | 对应主文档 | 一句话说明 | 验证状态 |
|------|-----------|-----------|---------|
| [`examples/ex01-cargo-audit/`](./examples/ex01-cargo-audit/) | 3.2 | 干净工程与含旧漏洞依赖工程两相对照的 audit 实测（含真实命中输出） | 已验证（cargo-audit 0.22.2） |
| [`examples/ex02-cargo-deny-config/`](./examples/ex02-cargo-deny-config/) | 3.3 | deny.toml 四段结构全配置（schema 经 0.20.2 校验）+ cargo deny check 实测（含命中输出） | 已验证（cargo-deny 0.20.2） |
| [`examples/ex03-license-check/`](./examples/ex03-license-check/) | 3.6 | 许可证合规命令链：SPDX 声明检查 + 清单整理脚本（实测输出） | 已验证（脚本实测）；deny list 补充见 ex02 |
| [`examples/ex04-reproducible-build/`](./examples/ex04-reproducible-build/) | 3.8 | 双 target 目录干净构建，SHA-256 比对演示可复现构建 | 已验证 |
| [`examples/ex05-sbom-generate/`](./examples/ex05-sbom-generate/) | 3.9 | SBOM 生成实测：cargo-sbom 产出 SPDX-2.3 / CycloneDX-1.6（真实输出） | 已验证（cargo-sbom 0.10.0） |
| [`examples/ex06-secret-handling/`](./examples/ex06-secret-handling/) | 3.7 | 从环境变量读 secret 的 Rust 最小形态 + 禁止清单 | 已验证（cargo run 实测） |
| [`examples/ex07-publish-preview/`](./examples/ex07-publish-preview/) | 3.10/3.11 | cargo package --list/--no-verify 发布演练 + CHANGELOG 模板 | 已验证（package 演练）；真实 publish 未验证 |

```rust
// examples/ex06-secret-handling/src/main.rs —— secret 注入最小形态（已验证）
// 验证环境：rustc/cargo 1.92.0；运行：CRATES_IO_TOKEN=dummy cargo run
use std::env;

fn load_secret(name: &str) -> Result<String, String> {
    env::var(name).map_err(|_| format!("缺少环境变量 {name}：请注入，不要写进代码"))
}

fn main() -> Result<(), String> {
    let token = load_secret("CRATES_IO_TOKEN")?;   // 读环境，读不到显式失败
    println!("token 已就绪（长度 {}，内容不回显）", token.len());
    Ok(())
}
```

```bash
# examples/ex04-reproducible-build —— 可复现构建验证（已验证，哈希为实测值，完整输出见 3.8 与 ex04/README）
export PATH="$HOME/.cargo/bin:$PATH"
CARGO_TARGET_DIR=/tmp/ph24-t1 cargo build --release   # 干净构建 ①
CARGO_TARGET_DIR=/tmp/ph24-t2 cargo build --release   # 干净构建 ②
shasum -a 256 /tmp/ph24-t1/release/ph24-reprobin /tmp/ph24-t2/release/ph24-reprobin
# 实测：两行 SHA-256 完全相同（1205b2a934…），同一 commit 双目录产物逐字节一致
```

examples/ex07 的 `cargo package --list`/`--no-verify` 实测输出已在 3.10 展示，CHANGELOG 模板在 3.11 展示；完整工程形态见 [`examples/ex07-publish-preview/`](./examples/ex07-publish-preview/README.md)。

## 7. 总结

### 关键要点

- **供应链风险模型的中心是依赖树，不是单个依赖**：直接依赖要评审（ph17），传递依赖与构建期代码（build.rs/proc-macro）要靠工具持续扫——威胁分已知漏洞/投毒包/typosquatting/依赖混淆四类，各有对应工具与策略（3.1）
- **cargo audit 是「已知漏洞」的唯一自动防线**：解析 Cargo.lock 对照 RustSec advisory-db，命中输出 RUSTSEC-ID/受影响版本/修复版本（实测 RUSTSEC-2020-0071），退出码即门禁；全绿是安静的成功，别误读为「依赖安全」（3.2/4.2）
- **cargo deny 是策略门禁，audit 是报告**：deny.toml 四段（advisories/licenses/bans/sources）先声明「什么可接受」再 `cargo deny check` 把关——licenses 防合规事故、bans 防多版本修复不对称、sources 防依赖混淆（3.3~3.5）
- **许可证按分发模式分级**：内部/闭源/开源的 allow 集合不同；SPDX 表达式（`OR`/`AND`/`WITH`）有真值语义；`MIT OR Apache-2.0` 双许可是 Rust 库默认（3.6）
- **secret 三纪律：不入库、不硬编码、最小权限注入**：环境变量是最小注入形态，`cargo login` 凭证落 `~/.cargo/credentials.toml`，CI token 用作用域+过期，event-stream 类投毒的上游入口就是 token 泄露（3.7）
- **可复现构建 = lock + toolchain + 确定性**：三件齐全后同一 commit 的产物逐字节一致（实测双目录 SHA-256 相同）；比较域限定在同平台同 profile（3.8/4.1）
- **SBOM 让影响面可见**：SPDX/CycloneDX 随制品发布，CVE 公告时用程序化筛查代替翻仓库；发布=制品+SBOM 要成固定姿势（3.9）
- **发布流程的精华是发布前的 package 演练**：已发布版本不可删，`cargo package --list` 内容审查 + `--no-verify` 本地打包把不可收回的后果前置；坏版本只能 yank（阻止新依赖、不破坏旧构建）（3.10/4.3）
- **semver 纪律 + CHANGELOG 是发布者的契约**：0.x 的 minor 即 breaking、预发布版本不被 `^` 自动选中、PR 合入即记 Unreleased——让「版本号/CHANGELOG/tag/发布物」永远一致（3.11）

### 阶段验收清单

- [ ] 能对任意 Rust 工程跑 `cargo audit` 并读懂命中输出（RUSTSEC-ID/受影响版本/Solution），能为漏洞制定「升级/补丁/规避/替换/接受登记」之一并给出理由（roadmap 验收「能为依赖漏洞制定处理策略」）（3.2/ex01）
- [ ] 能写一份 deny.toml（advisories/licenses/bans/sources 四段）并说明每段防什么攻击、`cargo deny check` 各子命令的职责（3.3~3.5/ex02）
- [ ] 能为一个工程整理出可用的许可证清单（SPDX 表），并判断「依赖的许可 ⊂ 我的分发约束」方向（3.6/ex03）
- [ ] 能说明 secret 管理的三条纪律与最小权限在 cargo/CI 场景的落点，能指出仓库里「不该 commit」的文件类型（3.7/ex06）
- [ ] 能用一个可执行实验验证「同一 commit 两次干净构建产物一致」（双 CARGO_TARGET_DIR + SHA-256 对比），并说出哪些因素会破坏确定性（3.8/ex04）
- [ ] 能走完 `cargo package --list` → 审查 → `--no-verify` 的发布演练，说明 yank 为什么是「阻止新依赖」而不是「删除版本」（3.10/ex07）
- [ ] 能解释版本策略：为什么 0.x 的 minor bump 视同 breaking、预发布版本为什么不被自动选中、CHANGELOG 为什么要在发布前归档（roadmap 验收「能让版本号和变更说明一致」）（3.11）
- [ ] 能说清本阶段工具防的攻击类型与各自边界：audit 只查已知漏洞、deny 是策略门禁、SBOM 提供影响面可见性——三者叠加仍不替代 ph17 的引入前评审（3.1~3.9）

### 跨语言对比

- 五门语言（Rust/npm/Java/Go/Python 系）的供应链工具收敛到「锁文件、漏洞库对照、许可策略、SBOM」四件套，差异在默认开启度与信任模型：Go 用 go.sum 强制模块哈希、npm 靠生态强制 audit、Rust 把锁文件策略交给工程决策而把漏洞/许可交给独立工具（为 analysis/ 与 Tenet 合成积累素材，详见 5 节对照表）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。四题与 roadmap 第 24 节练习一一对应：练习 1 =「对项目跑 cargo audit/deny 实战」（sol-01：配 deny.toml 并跑全命令链），练习 2 =「整理许可证清单」（sol-02：SPDX 表 + 自动核对命令），练习 3 =「编写 CHANGELOG 和 release notes」（sol-03：版本发布文案全套），练习 4 =「可复现构建验证」（sol-04：双目录哈希实验）。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**安全发布流水线 release-pipeline**——roadmap 第 24 节推荐项目「安全发布流水线：自动测试、审计、构建、打包和生成发布说明」的落地：一个带真实依赖的演示 crate + deny.toml + `release-check.sh`（本地可跑：fmt → clippy `-D warnings` → test `--locked` → audit → license 清单 → `cargo package --list` 审查 → CHANGELOG 校验）+ `.github/workflows/release.yml` 形态参考。验收标准为「每一步在本地可执行并输出明确结果，未验证步骤如实标注」。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（本机跑出 `release-check.sh` 全链路输出）

### 下一阶段

[**ph25 Rust 数据基础设施专项阶段**](../ph25-data-infrastructure/25-data-infrastructure.md)（roadmap 第 25 节——Rust 路线最后一个阶段，现已建成）——本阶段把「交付物可信」的流水线立起来了；下一阶段进入数据基础设施实现：WAL/MemTable/SSTable、Bloom Filter 与 Compaction、Mini Raft、HNSW 向量检索与 Agent 工具服务——届时 ph24 沉淀的 deny.toml、audit job 与 release-check.sh 会被 KV/LSM 工程直接拿去用（KV 组件的运行时安全与加密存储、Agent 后端的权限/审计/可观测性也在那里展开），「安全地写出来」与「可信地发出去」在 ph25 汇合成「安全可信的数据基础设施」。





