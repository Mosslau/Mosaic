# ph12 阶段项目：异步采集器（std 版）

对应 roadmap ph12 推荐项目「异步采集器：并发拉取多个数据源状态，超时重试并汇总结果」。在主文档示例 1~3（线程 + 通道 + 锁）的基础上，落地为带**全局超时 + 每源重试 + 汇总报告 + 单元测试**的完整程序。**纯 std、单文件**（`rustc` 直接编译，零第三方依赖）；数据源用「延迟 + 故障注入」模拟（真实网络 I/O 的系统化编程属 ph13 文件、网络与系统编程阶段；tokio 异步网络版见 `examples/tokio/src/bin/ex09-tokio-tcp-echo.rs`，已验证 tokio 1.53.1）。

## 需求

5 个模拟数据源（`db-primary` / `cache-node` / `search` / `metrics` / `legacy-billing`），每个源有独立的**延迟**与**故障模式**（`fail_until`：前 N 次探测都失败）。程序并发启动全部源的采集线程，每个源**最多重试 `RETRIES` 次**，主线程按**全局超时**（380ms）收集结果，最后汇总为三档：成功 / 重试耗尽失败 / 超时未返回。

## 功能清单

| 功能 | 说明 |
|------|------|
| 模拟数据源 | `Source { name, latency_ms, fail_until }`：延迟模拟网络往返，`fail_until` 注入前 N 次失败 |
| 单次采集 | `fetch`：sleep 延迟后按 `attempt <= fail_until` 返回 `Err` 或 `Ok(状态文本)` |
| 每源重试 | `collect_one`：最多 `retries` 次重试，成功即发回 `Ok`，耗尽发回 `Err`（携带最后一次错误） |
| 并发启动 | 每个源一个 `thread::spawn`，结果经 `mpsc` 通道回传（多生产者模式） |
| 全局超时 | 主线程按剩余时限递减 `recv_timeout`，到点整体放弃，未返回的源计入 `timed_out` |
| 汇总报告 | `summarize` 三档归类 + 总耗时；`print_report` 打印 ✔/✘/⏱ 报告 |
| 单元测试 | `#[cfg(test)]` 6 个用例：fetch 成功/失败、重试成功/耗尽、汇总归类、全量采集（latency 0 + 宽松时限，不依赖真实计时） |

## 验收标准

- [ ] `rustc --edition 2021 -D warnings src/main.rs -o /tmp/proj` 编译零警告
- [ ] `rustc --edition 2021 -D warnings --test src/main.rs -o /tmp/proj_test && /tmp/proj_test` 全部测试通过（`test result: ok. 6 passed; 0 failed`，实测）
- [ ] 正常运行输出（实测，总耗时约 381ms ≈ 全局超时 380ms）：
  - `成功 3 个 / 重试耗尽失败 0 个 / 超时未返回 2 个`
  - `✔ metrics` / `✔ cache-node` / `✔ db-primary`（db-primary 重试 2 次后成功）
  - `⏱ search`（重试 1 次后成功但 400ms > 时限）与 `⏱ legacy-billing`（一直失败且 450ms > 时限）计入超时
- [ ] 重试语义可解释：`db-primary` 前 2 次失败第 3 次成功（实测在成功列表）；`legacy-billing` 重试耗尽（fail_until=99）但未及返回即超时
- [ ] 全程安全代码：无 `unsafe`；`collect_one` 对已放弃的通道用 `let _ = tx.send(...)` 忽略发送错误（主线程超时后不再接收）

## 扩展方向（可选）

- 把模拟源换成真实网络请求：每源一个 `TcpStream`/HTTP 客户端，全局超时 + 重试逻辑原样复用（属 ph13 文件、网络与系统编程阶段）
- 升级为 tokio 版：`tokio::spawn` 任务 + `tokio::time::timeout` + `JoinSet` 管理任务（tokio 1.53.1 已验证，见 examples/tokio/）
- 增加「部分成功」语义：超时的源按最近一次探测结果降级上报（如返回 `degraded` 而非丢弃）
- 采集结果落盘/上报，配合结构化日志（衔接 ph11 的 tracing 讲解）

## 验证环境

- rustc 1.92.0（macOS arm64），零第三方依赖
- 编译：`rustc --edition 2021 -D warnings src/main.rs -o /tmp/proj`
- 运行：`/tmp/proj`
- 测试：`rustc --edition 2021 -D warnings --test src/main.rs -o /tmp/proj_test && /tmp/proj_test`
- 验证状态：已验证（编译零警告，6 个单元测试全部通过，运行输出为实测）
