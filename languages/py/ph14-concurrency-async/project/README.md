# ph14 阶段项目：异步遥测采集服务（async-telemetry-collector）

> 对应 roadmap 第 14 节「推荐项目」第一个「异步采集服务」——把本阶段的并发武器（aiohttp 并发、Semaphore 限速、指数退避重试、事件循环心智）完整落进一个「起模拟服务器 → 并发采集 → 汇总统计 → CSV 报表」的采集服务；另一个推荐项目「并发日志处理器」作为扩展方向（见文末）。

## 需求

车联网场景里，平台要从成百上千辆车**周期采集遥测数据**（车速、电量），采集端面对的是「大量、慢、会失败」的 HTTP 接口。本项目做一个**异步采集服务**：进程内起一个模拟遥测服务器（可注入延迟与失败率），用 **aiohttp 并发采集**（`asyncio.Semaphore` 限速、指数退避重试），统计成功/失败/耗时，输出 CSV 报表——把「大量并发网络 IO 用 asyncio」「不要阻塞事件循环」两条必会概念变成可运行、可测试的代码。

## 功能清单

- [x] `collector.simserver.TelemetrySimulator`：进程内模拟遥测服务器（aiohttp web），提供车辆列表与单车辆遥测接口；延迟/失败率可注入、随机数可播种（同一 seed 完全可复现）
- [x] `collector.fetcher.collect`：aiohttp 并发采集，`asyncio.Semaphore` 把同时在途请求压到 `max_concurrency`；`fetch_one` 非 200 / 网络异常 → 指数退避重试，耗尽 `max_retries` 记为失败；`ClientSession` 复用 TCP 连接
- [x] `collector.stats`：按车辆分组汇总（`summarize`）+ 总体统计（`overall`：总数/成功/失败/平均耗时/成功率）
- [x] `collector.report.write_csv`：确定性覆盖写 CSV 报表（按车辆排序、失败行留空、可安全重跑）
- [x] `cli.py` 命令行入口：`--vehicles/--concurrency/--max-retries/--fail-rate/--latency-ms/--output-dir/--seed` 参数化 + `--demo` 离线自检
- [x] `tests/` 16 个 pytest 用例：模拟服务器行为、采集正确性（全成功/全失败/混合重试）、并发上限不影响结果、统计与报表纯函数测试
- [x] 质量门禁：`pyproject.toml` 统一配置；`ruff check .` 与 `ruff format --check .` 全绿

## 验收标准

- `python3 -m pytest` → **16 passed**（simserver 5 + fetcher 4 + stats 4 + report 3，本机实测）
- `ruff check .` → `All checks passed!`；`ruff format --check .` → 10 files already formatted（本机实测）
- `python3 cli.py --demo` → 自检通过：10/10 采集成功、无重试、遥测值完整（本机实测）
- `python3 cli.py` → 默认 20 辆车、10% 失败率、20ms 延迟：约 **0.12s** 采完，成功率 100%（重试兜底），平均耗时约 21.7ms（本机实测，**随机器与负载波动 ±10~20%**）
- 高失败率演示：`python3 cli.py --vehicles 30 --fail-rate 0.5 --concurrency 8` → 30 辆车约 0.27s 采完，25 成功 / 5 失败（重试耗尽），CSV 中失败行 `status` 为空、`attempts=3`（本机实测）
- **并发代码怎么测**（主文档 3.9 的落地）：所有测试用**标准 pytest + `asyncio.run` 包装**，不需要 pytest-asyncio——每个用例在 `asyncio.run` 里起模拟服务器、跑采集、断言、`finally` 关闭

> **依赖状态如实标注**：aiohttp 3.13.2 本环境已装并实测；pytest 8.4.2、ruff 0.12.0 已装并实测；**pytest-asyncio 未安装**——测试用标准 `asyncio.run` 包装实现（见 `tests/`）。模拟服务器跑在**进程内**，`stop()`/`runner.cleanup()` 保证无残留端口占用——运行后 `git status` 工作区干净（报表输出到 `/tmp`）。

## 扩展方向

- **并发日志处理器**（roadmap 另一个推荐项目）：把「采集」换成「读取大日志文件」，IO 读入用线程/异步、按行分片交给多进程统计（正则解析、分组计数）——本项目 `tests/` 的「异步 + 断言」测法直接复用
- 采集到的数据落库：接 ph11 数据库阶段的 `aiosqlite`（异步驱动），把 `write_csv` 换成异步写入
- 包成服务：接 ph10 异步 FastAPI 阶段，把「触发一次采集」暴露为 HTTP 接口（`async def` 端点 + 后台任务），uvicorn 多 worker 横向扩展
- 限速策略升级：从固定 Semaphore 升级为令牌桶（按 QPS 平滑限速），`fetch_one` 的退避策略可参数化
- 失败补偿：把重试耗尽的上报进死信队列，配合后续消息队列主题（roadmap 第 18 节车联网方向阶段，目录待建）
