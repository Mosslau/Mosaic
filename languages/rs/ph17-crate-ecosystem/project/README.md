# ph17 阶段项目：依赖评审报告（fetch-cli 选型实录）

对应 roadmap ph17 推荐项目「依赖评审报告：列出核心 crate、用途、风险和替代方案」。落地为**文档型项目**：以「命令行下载工具 fetch-cli」为真实场景，产出 `REPORT.md`（核心 crate 一览 + 六维评审 + 风险与替代方案 + 决策记录）+ `check-deps.sh`（配套依赖体检脚本）+ `lib-skeleton/`（若未来拆成可复用库的 Cargo.toml 特性设计骨架，可选）。

## 需求

1. 场景真实：fetch-cli——`fetch-cli <url> [-o 保存路径]` 下载文件、显示进度、可并发下载多个 URL、失败重试 2 次。
2. 报告完整：列出每个核心 crate 的**用途、版本区间、风险、替代方案**（roadmap 原文要求），并按主文档 3.2 六维清单逐项给出判据。
3. 可执行配套：check-deps.sh 把报告里的体检命令脚本化，任何成员 clone 后一条命令复跑。
4. 延伸落地：给出「若 fetch-cli 的核心拆成库供别的工具复用」时的特性设计骨架（默认特性最小化、feature 语义遵循主文档 3.9）。

## 功能清单

- [ ] `REPORT.md`：场景与需求 → 依赖一览表（crate/用途/版本区间/风险/替代方案）→ 六维评审细节 → 整体风险与缓解 → 决策记录模板
- [ ] `check-deps.sh`：`cargo tree --depth 2` / `-d` / `-i reqwest` / `cargo audit`（缺失自动跳过）/ `cargo deny check licenses`（可选）
- [ ] `lib-skeleton/`：Cargo.toml 特性骨架 + 一句 lib.rs 说明（可选扩展）
- [ ] 依赖版本区间一律写主版本（serde 1 / tokio 1 / reqwest 0.12 …），不钉死小版本（锁定交给 Cargo.lock，策略见 ph16）

## 验收标准

- REPORT.md 覆盖 roadmap 要求的四要素（核心 crate / 用途 / 风险 / 替代方案），每个核心 crate 至少 1 条风险与 1 个替代方案
- 六维评审里至少 3 个维度给出「判据 + 取证方式」而非空话（如依赖树膨胀给出预期 `cargo tree` 观察点）
- check-deps.sh 在联网环境可完整跑通；工具缺失时优雅跳过并提示安装命令
- 报告结论可辩护：每个「引入」决定都能指回某条判据（验收对应 roadmap「能在引入依赖前说明理由」）

## 扩展方向（可选）

- 把 REPORT.md 的「决策记录」升级为 ph16 project/ 的「依赖引入约定」登记表格式，双向引用（本阶段承接 ph16 伏笔，见 ph16 project README 第 71 行）
- 把 check-deps.sh 挂进 CI 成为 `cargo audit` 门禁——完整供应链门禁体系属 ph24 安全、供应链与发布阶段
- 给 fetch-cli 真的写代码：HTTP 层选型结论见 exercises/sol-01 与 sol-03（reqwest），下载/重试/进度逻辑可作 ph12/ph13 的复习练习

> 验证环境：rustc/cargo 1.92.0（macOS arm64，rustup 1.28.2）；lib-skeleton 需联网拉取 crate，标注「未在本环境验证」；`cargo tree`/`cargo audit` 输出以你在联网环境实测为准。
