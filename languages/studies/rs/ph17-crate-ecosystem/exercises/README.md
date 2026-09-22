# exercises —— Crate 生态选择与常用库阶段练习

完成顺序建议：按 1~4 顺序完成，对应主文档 3.5 / 3.10 / 3.2 / 3.9。参考实现在 `sol-*` 文件中，**先自己做，做完再看**。每题标注难度（★~★★★）。

四题与 roadmap 练习/验收一一对应：练习 1 = 「为 HTTP 客户端比较 reqwest 与 hyper」，练习 2 = 「用 cargo tree 观察依赖树」，练习 3 = 「为某场景选型并写理由」（要求先完成「检查 crate 最近发布和 issue 状态」的取证），练习 4 = 「控制 feature 范围」（对应阶段验收「能控制 feature 范围」）。

验证环境：rustc/cargo 1.92.0（macOS arm64，rustup 1.28.2 管理）；需联网拉取 crate（国内配 rsproxy 镜像）。所有 sol 参考实现标注「未在本环境验证」——命令语义以 cargo 官方文档为准。

## 练习 1：比较 reqwest 与 hyper（★★）

- **目标**：为一个「需要控制 HTTP/1.1 连接复用细节的下载器」判断该用 reqwest 还是 hyper，写出一页能说服人的对比（roadmap 练习「为 HTTP 客户端比较 reqwest 与 hyper」）
- **要求**：
  - 不写代码，输出一份对比：定位差异、API 风格差异、各自依赖成本（提示：跑 `cargo tree` 看两边依赖面）、TLS 后端问题
  - 给出**判据问题**：什么信号下选 reqwest、什么信号下选 hyper（提示：你在写业务还是写库？连接管理是你要控制的还是框架替你控制的？）
  - 各给出 1 个反例（选错了会怎样）
- **验收**：对比表覆盖定位/风格/依赖/异步四个维度；判据至少 2 条；反例各 1 条（参考实现 `sol-01-reqwest-vs-hyper.md`）

## 练习 2：用 cargo tree 观察依赖树（★★）

- **目标**：对一个含传递依赖的小工程，用 cargo tree 回答「依赖树长什么样、有没有膨胀、有没有重复版本」（roadmap 练习「用 cargo tree 观察依赖树」）
- **要求**：
  - 建一个演示 crate，依赖 `serde`（features = ["derive"]）与 `serde_json`（参考 examples/ex05 的起点 Cargo.toml，或自选两个有传递依赖的 crate）
  - 依次运行并记录输出：`cargo tree`、`cargo tree --depth 2`、`cargo tree -e features`、`cargo tree -d`、`cargo tree -i <某依赖>`
  - 用文字回答：① 深度 2 内有哪些直接依赖的传递依赖？② `-e features` 里 serde 实际开了哪些 feature、为什么有 std？③ `-d` 是否有输出、意味着什么？
- **验收**：五个命令的输出与三个问题的文字回答齐全；能解释「-d 无输出 = 版本对齐良好」（参考实现 `sol-02-cargo-tree.sh`）

## 练习 3：为「天气查询 CLI」选型并写理由（★★★）

- **目标**：为一个假想工程写一份选型报告，核心是 HTTP 层选型，且**先取证再下结论**（roadmap 练习「检查 crate 最近发布和 issue 状态」+ 阶段验收「能在引入依赖前说明理由」）
- **场景**：天气查询 CLI——`weather <城市>` 调用某天气 API（HTTPS + JSON），输出温度与体感；单文件起步，未来可能加缓存与多数据源
- **要求**：
  - 用 crates.io API（`curl -s https://crates.io/api/v1/crates/<crate>`）或 GitHub 页面，对候选（reqwest、ureq、hyper）各记录：最近发布、更新时间、近 90 天下载量、issue 响应迹象——把「取证结果」写进报告
  - 给出你的选型结论 + 至少三条理由（结合：同步 vs 异步、TLS 后端、依赖成本、维护活跃度）
  - 明确「什么条件下你会改选另一个」
- **验收**：报告含取证数据表（3 个候选 × 至少 2 个活跃度指标）+ 结论 + ≥3 条理由 + 改选条件（参考实现 `sol-03-selection-report.md`）

## 练习 4：控制 feature 范围（★★★）

- **目标**：把一个「默认特性全开」的 Cargo.toml 改造成「关默认 + 精开」，并解释 feature 统一对结果的影响（阶段验收「能控制 feature 范围」）
- **起点**（原样照抄到你的工程里，先 `cargo build` 观察依赖面）：

  ```toml
  [dependencies]
  reqwest = "0.12"                    # 默认开 native-tls / 一堆用不到的特性
  tokio = { version = "1", features = ["full"] }   # full = 全家桶
  ```

- **要求**：
  - 改造后目标：HTTP 客户端用纯 Rust TLS（rustls）；tokio 只开当前工程用到的组（rt-multi-thread + macros）
  - 改前改后各跑一次 `cargo tree --depth 1` 与 `cargo tree -e features | grep -E "tokio|reqwest"`，对比差异并写进答案（提示：native-tls → openssl-sys；full → 数十个 feature）
  - 加一问：如果工程里另一个 crate 强制要求 `tokio/rt`，你关掉的 `rt` 还会不会出现？为什么？（提示：主文档 3.9 语义点 2）
- **验收**：改造后的 Cargo.toml 正确（关默认、精开、无 full）；前后依赖面对比记录存在；最后一问解释正确（参考实现 `sol-04-feature-control/`，内附改动前后对照说明）

提示：练习 1 练「同类库的定位思维」，练习 2 练「依赖树可观测」，练习 3 练「取证 + 理由」的完整评审闭环，练习 4 练「feature 是编译期契约」——四题做完覆盖 roadmap 必会概念（维护活跃度 / API 稳定性 / 依赖树膨胀 / 许可证兼容）中的前三项与验收三项；许可证与 unsafe 面的动手在 project/ 的 REPORT.md 与 examples/ex01。
