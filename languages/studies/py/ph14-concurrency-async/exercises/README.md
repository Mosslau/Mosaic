# exercises —— 并发、并行与异步阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。与 roadmap「练习」小节对应：并发下载文件（练习 1）、多进程处理大计算（练习 2，roadmap 的「多进程处理大文件」由它覆盖——把「大文件按行分片」替换为「大计算按区间分片」，切分思想一致）、并发请求 API（练习 3）、异步爬虫（练习 5，aiohttp 并发抓取本地接口）；练习 4（混合任务 + as_completed）对应「学习内容」里的 concurrent.futures。

完成顺序建议：按 1~5 顺序完成（逐步叠加：线程 → 进程 → 异步 → 统一接口 → 真实 HTTP 客户端）。

## 依赖与验证方式

- 依赖：练习 1/2/3/4 只用**标准库**（零安装）；练习 5 需要 `pip install aiohttp`（本环境 3.13.2 已装）
- 运行：`python3 sol-XX-*.py`（每个 sol 是独立脚本，内含正确性断言，断言失败会报错退出）
- 耗时标注：所有耗时数字为本机（macOS arm64，14 核，Python 3.13.9）实测，**随机器与负载波动 ±10~20%**；对比关系（并发 ≈ 单任务耗时、多进程 ≈ 串行/核数）稳定，绝对秒数仅供参考
- 产物纪律：练习 5 起的本地服务器在**进程内**（后台线程），测完自动 `shutdown`/`close`，**不残留进程**——运行后 `git status` 工作区干净
- 参考实现文件头带**验证块**：环境、运行命令、实测输出（耗时/计数为本机实际运行结果）

## 练习 1：并发下载文件（★）

- **目标**：用线程池并发「下载」一批文件，体会 IO 密集任务用 threading 的收益（对应 roadmap「并发下载文件」）
- **要求**：
  - 实现 `download_file(i)`：模拟下载第 i 个文件（`time.sleep(0.05)` + 返回 `{"id": i, "size": 1024*(i+1)}`）
  - 串行下载 20 个文件并计时；再用 `ThreadPoolExecutor(max_workers=4)` 并发下载并计时
  - 断言两种方式结果完全一致（一个文件都不能丢、不能错）
- **验收**：脚本跑通并输出两段实测耗时；**把实测数字（串行 vs 并发秒数、文件数、总字节）写进你 sol 文件头的验证块**；能说清「为什么 IO 等待时线程能重叠」（等待释放 GIL）

## 练习 2：多进程处理大计算（★★）

- **目标**：把大计算按区间分片交给多进程，体会 CPU 密集任务必须用 multiprocessing（对应 roadmap「多进程处理大文件」的切分思想）
- **要求**：
  - 实现 `count_primes(lo, hi)`：统计 `[lo, hi)` 内质数个数（简单试除法即可）
  - 把 `[2, 1_000_000)` 切成 4 段，串行统计并计时；再用 `ProcessPoolExecutor(max_workers=4)` 分片统计并计时；**加一组 `ThreadPoolExecutor` 对照组**（体会 GIL 反例）
  - 断言三种方式质数总数一致
- **验收**：脚本跑通并输出三组实测耗时与质数总数；**把实测数字写进验证块**；能解释「为什么进程池要写在 `if __name__ == "__main__":` 保护内」（spawn 子进程会重新导入主模块）

## 练习 3：异步并发请求 API（★★）

- **目标**：用 `asyncio.gather` 并发请求一批 API，并演示「不要在协程里用 `time.sleep`」（对应 roadmap「并发请求 API」）
- **要求**：
  - 实现 `async def fetch_api(i)`：`await asyncio.sleep(0.05)` 模拟请求，返回 `{"id": i, "data": ...}`
  - 串行 `await` 20 个请求并计时；`asyncio.gather` 并发并计时；**再加一组「协程里用 `time.sleep`」的 gather 反例**并计时（预期并发被抹平）
  - 用 `return_exceptions=True` 处理「第 5 个请求抛 TimeoutError」的场景，断言 9/10 成功
- **验收**：脚本跑通并输出三组实测耗时；**把实测数字写进验证块**；能说清「`await` 让出控制权」与「阻塞调用卡死事件循环」的区别

## 练习 4：混合任务流式收集（★★★）

- **目标**：同一批任务里 IO 密集的进线程池、CPU 密集的进进程池，用 `submit + as_completed` 流式收集（对应「学习内容」concurrent.futures）
- **要求**：
  - 实现 `io_job(i)`（`time.sleep(0.05)`）与 `cpu_job(i)`（平方和计算）
  - 串行跑 16 个任务（12 IO + 4 CPU）计时
  - 混合并发：`ThreadPoolExecutor(6)` 收 IO 任务、`ProcessPoolExecutor(4)` 收 CPU 任务，`as_completed` 边完成边收集，计时
  - 断言：IO/CPU 两类任务数量一个不少、结果总数正确
- **验收**：脚本跑通并输出串行 vs 混合并发实测耗时；**把实测数字写进验证块**；能说清「IO 与 CPU 两组任务为什么能在总耗时里重叠」

## 练习 5：aiohttp 并发抓取 + 限速 + 重试（★★★）

- **目标**：写一个带**限速与重试**的异步抓取客户端，跑在本地模拟接口上（对应 roadmap「异步爬虫」的最小闭环）
- **要求**：
  - 起一个本地 HTTP 服务（stdlib `ThreadingHTTPServer`，后台线程）：`GET /api/fetch/{i}` 睡 0.02s 后返回 200 JSON；**`i%5==0` 的端点恒返 503**（确定性失败，供重试演示）
  - 实现 `fetch_with_retry(session, base, i, max_retries)`：非 200 / 网络异常 → 指数退避重试；耗尽 `max_retries` 记为失败；返回 `FetchResult`（id / ok / attempts / status / elapsed_ms）
  - 串行抓 20 个端点计时；`asyncio.Semaphore(4)` 限速并发抓取并计时
  - 断言：成功 16 个（`i%5!=0`）、失败 `[0,5,10,15]`（attempts=3）、其余 attempts=1
  - 测完 `shutdown`/`server_close` 关闭服务器（不残留进程）
- **验收**：脚本跑通并输出串行 vs 并发实测耗时与成功/失败清单；**把实测数字与 attempts 分布写进验证块**；能说清「Semaphore 把并发压到 4 后耗时为什么会近似 `20/4 × 0.02s`」

> **提示**：练习 1~5 与主文档 3.x 小节一一对应（3.1 threading、3.3 multiprocessing、3.5 asyncio、3.4 concurrent.futures、3.7 aiohttp/httpx、3.9 并发代码怎么测）；做完后对照 `sol-*` 参考实现复盘——先独立完成，再看答案。
