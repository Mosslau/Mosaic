# 依赖评审报告：fetch-cli（命令行下载工具）

> 场景：`fetch-cli <url> [-o 保存路径]`——下载文件、显示进度、支持多 URL 并发、失败自动重试 2 次。
> 本报告回答 roadmap ph17 推荐项目的四要素：**每个核心 crate 的用途、风险、替代方案**，并补上主文档 3.2 的六维判据与整体风险缓解。
> 验证环境：rustc/cargo 1.92.0（macOS arm64，rustup 1.28.2）；版本区间以 crates.io 写作时状态为参照（serde 1 / tokio 1 / reqwest 0.12 / clap 4 / tracing 0.1）。**未在本环境验证**：文中 `cargo tree`/`cargo audit` 的观察点描述为预期行为，请在联网环境用 `check-deps.sh` 复跑取证。

## 1. 场景与需求拆解

| 需求 | 它要求的依赖能力 |
|------|-----------------|
| 解析 `fetch-cli <url> -o <path>` 参数 | CLI 解析（flag/选项/位置参数 + `--help`） |
| HTTPS 下载 + 进度显示 | HTTP 客户端 + 流式读取（进度 = 已读字节 / Content-Length） |
| 多 URL 并发 | 并发任务 + 超时控制 |
| 失败重试 2 次 | 错误类型化 + 重试策略（delay + 次数上限） |
| 日志与排障 | 结构化日志（成功/失败/重试事件） |

## 2. 核心 crate 一览（roadmap 四要素）

| crate | 版本区间 | 用途 | 风险 | 替代方案 |
|-------|---------|------|------|---------|
| clap | 4（features = ["derive"]） | 参数解析三件套（flag/选项/子命令）+ 自动 `--help` | 大而全，若只用子集则 API 冗余；derive 路线依赖过程宏（编译时间） | builder 路线（同 crate，少过程宏）；`lexopt`（极简手写风格，需自维护 help） |
| tokio | 1（default-features = false，rt-multi-thread + macros + time） | 多 URL 并发的运行时 + 重试 delay 定时 | 引入 async 心智与 Send 约束；feature 并集受全图影响（主文档 3.9）；若未来需求证明并发无益则白付复杂度 | `std::thread`（并发量小、下载是 I/O 密集时线程也够）；纯同步栈用 ureq + 线程 |
| reqwest | 0.12（default-features = false，rustls-tls + json） | HTTPS 下载、流式 body、超时 | 底层 hyper 升级会随 0.x 语义漂移（0.x 无 semver 硬承诺，主文档 3.9）；TLS 后端选错会把 openssl 拖进依赖树 | ureq（纯同步、轻）；hyper（写库才考虑，见 sol-01） |
| tracing | 0.1 + tracing-subscriber 0.3（env-filter） | span/event 结构化日志（每个下载任务一个 span） | 生态较年轻（0.1），API 偶有迁移；subscriber 配置是应用层责任 | log + env_logger（老生态，无 span/结构化）；先不引，用 println（原型期够用） |
| serde + serde_json | 1 / 1 | 进度元数据 / 配置的序列化（可选） | 若 fetch-cli 不需要配置持久化则纯冗余依赖 | 不需要就不引（忍住原则，主文档 5 使用场景） |

**不引入清单（评审后放弃）**：`indicatif`（进度条——需求只要求「显示进度」，println 百分比即可，避免引终端渲染依赖）；`anyhow`（错误处理：重试策略需要结构化错误判定，thiserror 更贴合，且 ph11 已教过分工——重试需要的「错误可分型」用 thiserror 表达更准）。两处都是「5% 能力需求不引大 crate」的实例。

## 3. 六维评审细节（主文档 3.2）

| 维度 | 判据 | 取证方式（跑命令） | 结论 |
|------|------|-------------------|------|
| ① 维护活跃度 | 四个 crate 最近 publish < 1 年 | crates.io API：`curl -s https://crates.io/api/v1/crates/<crate>`（examples/ex01 步骤 1） | 均为活跃第一梯队（tokio/reqwest/serde 由大型组织维护） |
| ② API 稳定性 | serde/tokio 主版本 1（semver 硬承诺）；reqwest 0.12（0.x，minor 可破坏） | docs.rs 版本列表 + CHANGELOG | reqwest 是唯一需盯升级的：升级 0.x minor 前跑 changelog + 测试 |
| ③ 依赖树膨胀 | 干「下载」的活不应拖出预期之外的大件 | `bash check-deps.sh`（`cargo tree --depth 2` / `-d`） | 预期：tokio/reqwest(rustls)/hyper 在 depth 1~2；openssl-sys **不应出现**（rustls 路线）；`-d` 无输出 |
| ④ 许可证兼容 | 全部 MIT OR Apache-2.0 双许可，无 Copyleft | `cargo deny check licenses` | 兼容（Apache-2.0 产品可安全引入） |
| ⑤ unsafe 面 | rustls/hyper 的 unsafe 集中在 FFI/性能边界且有封装；reqwest 应用层无 unsafe | docs.rs 源码抽查 + `cargo geiger`（可选） | 可接受：unsafe 面集中且是生态反复审计过的核心件 |
| ⑥ MSRV | 目标 rust-version 1.85；四者均 ≤ 1.85（写作时） | `cargo metadata` 提取（ph16 sol-02 脚本） | 兼容；CI 用 ph16 的 MSRV 矩阵守门 |

## 4. 整体风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| reqwest 0.x 升级破坏（hyper 大版本切换曾发生） | 中 | 升级前跑 sol-02 式依赖树对照 + 全套测试；报告决策记录留档 |
| async 复杂度白付（若并发需求萎缩） | 中 | 架构上把「下载单文件」写成与运行时无关的纯函数（async 只留在编排层），未来可切线程模型 |
| rustls 证书策略差异（不读系统根证书默认行为需显式配置） | 低 | 使用 `reqwest` 默认 rustls 根证书行为，README 记录企业代理场景的配置开关 |
| tracing-subscriber 配置随版本演进 | 低 | 订阅者代码集中在 main 一处，升级只改一处 |

## 5. 决策记录（供后续新增依赖时复制续写）

```text
- crate 名 + 版本区间：<如 reqwest 0.12>
- 用途：<一句话>
- 六维判据引用：<第 3 节哪个维度/判据>
- 风险登记：<第 4 节哪条 + 缓解>
- 替代方案与放弃理由：<1~2 个>
- MSRV 影响：<是否高于 1.85>
- 评审日期 / 评审人：
```

（此格式即 ph16 project/ 的「依赖引入约定」登记表扩展版——ph16 模板的三行字段（用途/维护活跃度/替代品）+ MSRV 影响，本报告补成六维引用与风险登记。）
