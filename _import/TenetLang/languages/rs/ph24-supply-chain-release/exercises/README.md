# exercises —— Rust 安全、供应链与发布阶段练习

四题与 roadmap 第 24 节练习一一对应：练习 1 =「对项目跑 cargo audit/deny」（sol-01），练习 2 =「整理许可证清单」（sol-02），练习 3 =「编写 CHANGELOG 和 release notes」（sol-03），练习 4 补充「必会概念」中的可复现构建（sol-04）。每题一个参考实现文件 `sol-NN-*`，**先自己做，做完再看**。每题标注难度（★~★★★）。

**本阶段铁律（贯穿全部练习）**：不虚构工具输出——每一条写进答案的 audit/deny/package 输出要么来自你本机实跑、要么来自 examples/ 标注「已验证」的实测（引用要写明来源）；这正是 roadmap 验收「能为依赖漏洞制定处理策略」「能让发布包内容可审查」的训练形态。

验证环境：rustc/cargo **1.92.0**、cargo-audit **0.22.2**、cargo-deny **0.20.2**、cargo-sbom **0.10.0**（安装命令见 examples/README）。构建产物统一落 `/tmp`（`CARGO_TARGET_DIR`），仓库零二进制残留。

## 练习 1：audit + deny 实战（★★）

**目标**：对一个含漏洞依赖的小工程完整走一遍「扫雷 → 配门禁 → 修复 → 转绿」闭环（roadmap 练习「对项目跑 cargo audit/deny」）。

**要求**：用本仓库 `examples/ex01-cargo-audit/vulndemo/`（依赖锁在 `time = "=0.1.35"`）当练习对象：
1. 先 `cargo audit`，读出命中公告的 ID、受影响版本、修复版本（Solution）；
2. 写一份 deny.toml（四段齐全，参考 `examples/ex02-cargo-deny-config/deny.toml` 但**自己写**），分别跑 `cargo deny check advisories` 与 `check bans`；
3. 修复：把 `Cargo.toml` 的 time 依赖改到已修复版本区间（提示：0.2.23+ 或 0.3），`cargo update` 后重跑 audit，确认命中消失；
4. 顺手跑一次 `cargo deny list`，把输出按「许可证 → crate」整理进答案。

**提示**：audit/deny 的对象是 Cargo.lock，改完 manifest 必须 `cargo update` 让 lock 跟上；deny 的 db 拉取可复用 audit 缓存（`db-path = "~/.cargo/advisory-db"`）；deny.toml 的 `yanked`/`multiple-versions` 是 LintLevel 字符串不是布尔（examples/ex02 踩坑实录）。

**验收**：答案包含——① audit 命中公告的完整字段（ID/Version/Severity/Solution）；② 自己写的 deny.toml 全文；③ 修复前 deny advisories 非零退出、修复后 audit 与 deny 双双转绿的**真实输出**；④ `cargo deny list` 的输出。禁止复制 examples/ex02 的 README 输出冒充自己的运行结果。

参考实现：`sol-01-audit-deny-practice.md`。

## 练习 2：整理许可证清单（★★）

**目标**：对一个含真实三方依赖的工程整理出可用的「许可证 → crate」SPDX 清单，并给出合规判定（roadmap 练习「整理许可证清单」）。

**要求**：
1. 对 `examples/ex01-cargo-audit/vulndemo/`（time 0.1.35 依赖链含 libc/winapi/kernel32-sys）跑 `cargo deny list`（或 ex03 的 `check-licenses.sh`）；
2. 手工整理一张 SPDX 表：每行一个许可证，列出使用它的全部 crate（含版本），标注每个 crate 的 license 声明是「标准 SPDX 标识」「老式写法（如 MIT/Apache-2.0 斜杠）」「缺失」中的哪一种；
3. 对照「内部应用」「闭源商业分发」两种 allow 集合（主文档 3.4 表格），分别判定这张清单**是否通过**、卡在哪个 crate、行动项是什么。

**提示**：winapi 系是历史包袱常客；「缺失 license」与「老式写法」的包在 deny 下行为不同（unlicensed error vs OR 命中）；根包自己没写 license 也会被标 Unlicensed（这正是发布前要补的）。

**验收**：答案含一张完整 SPDX 表（许可证 × crate × 声明类型）+ 两种分发模式各自的判定结论与行动项。判定的「行动项」要具体（如「给根包 Cargo.toml 补 license = …」），不是泛泛而谈。

参考实现：`sol-02-license-inventory.md`。

## 练习 3：发布前检查清单 + CHANGELOG 编写（★★★）

**目标**：为一次「0.1.0 → 0.2.0」发布编写全套发布文案并执行发布演练（roadmap 练习「编写 CHANGELOG 和 release notes」）。

**要求**：假设 `examples/ex07-publish-preview/`（ph24-pkgdemo）要发布 0.2.0，新增功能 `fn checksum(data: &[u8]) -> u64`，并把最低 rustc 从 1.75 提到 1.85（MSRV 提升 = 破变更，主文档 3.11）：
1. 写出 0.2.0 的 CHANGELOG 小节（keep-a-changelog 格式，含 Breaking 标注），并把 0.1.0 的历史正确归档；
2. 写出该版本的 release notes（面向使用者的公告文体，引用 CHANGELOG 对应节）；
3. 在 ex07 目录实跑 `cargo package --list`，逐行审查哪些文件会随包发布、有没有遗漏（如 CHANGELOG 忘了加进发布物？license 文件在不在？），把审查结论写成发布前 checklist（≥8 项）；
4. 说明为什么版本 bump 用 minor（0.1.0 → 0.2.0）而不是 patch——把 semver 决策写清楚。

**提示**：发布的「破变更」不一定要动 API——MSRV 提升对下游同样是破变更（0.x 下升 minor）；CHANGELOG 的 `## [Unreleased]` 小节在发版时归档后要重建空的 Unreleased；`cargo package --list` 在 git 仓库内会多一个 `.cargo_vcs_info.json`（examples/ex07 实测）。

**验收**：答案含——① 0.2.0 CHANGELOG 小节与归档后的完整 CHANGELOG 骨架；② release notes 全文（≤150 字，面向使用者）；③ 实跑 `cargo package --list` 的真实输出 + 逐行审查结论 + ≥8 项发布前 checklist；④ semver 决策说明。实跑输出来自本机，写明验证环境。

参考实现：`sol-03-changelog-release-notes.md`。

## 练习 4：可复现构建验证（★★）

**目标**：亲手验证「同一 commit 两次干净构建产物逐字节一致」，并破坏一个输入观察哈希变化（补充题，对应必会概念「可复现构建」）。

**要求**：
1. 对 `examples/ex04-reproducible-build/`（零依赖 bin）用两个独立 `CARGO_TARGET_DIR` 各 `cargo build --release` 一次，对比产物 `shasum -a 256`——记录两条哈希；
2. **破坏实验 A**：改 `Cargo.toml` 的 `version`（如 1.2.3 → 1.2.4），重跑双目录构建，观察哈希是否变化、为什么；
3. **破坏实验 B**：在 `Cargo.toml` 加 `[profile.release] codegen-units = 16`，重跑双目录构建，观察哈希变化——说明 profile 为什么是可复现性的输入参数；
4. 把三个实验的哈希与结论整理成一张对照表。

**提示**：破坏实验前把原始 `Cargo.toml` 备份（做完记得还原，别把 examples/ 里的文件留在破坏状态——仓库不允许 git 操作之外的修改遗留）；构建要「干净」才有说服力——两个 target 目录互不共享缓存就是这个目的。

**验收**：答案含三张哈希对照（基线/改 version/改 profile）+ 每张的结论。能解释「为什么改 version 哈希会变、变在哪」加分（提示：二进制里通常不嵌版本，想清楚再答——真实答案可能是「不变」！那就如实写不变并解释）。

参考实现：`sol-04-reproducible-build.md`。

做完四题后，「扫雷 → 配门禁 → 修漏洞 → 整理许可 → 写发布文案 → 验证可复现」六件发布前必做的手艺都过了一遍——去 `project/` 把它们合体成一条 release-check 流水线。
