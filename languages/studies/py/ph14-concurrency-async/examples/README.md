# examples —— 并发、并行与异步阶段完整示例

> 每个示例对应主文档 `14-concurrency-async.md` 相关小节（3.x / 4.x / 6 章）的完整可运行版。验证环境：Python 3.13.9（macOS arm64，14 核）；第三方依赖：aiohttp 3.13.2、httpx 0.28.1、fastapi 0.139.1、uvicorn 0.50.0（全部本机已装并实测）；其余为标准库。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-threading-io.py` | threading：线程基础（start/join、输出顺序不定）、IO 密集串行 vs 线程池实测、竞争条件与 Lock（主文档 3.1/3.2/4.1） | `python3 ex01-threading-io.py`（离线） |
| `ex02-multiprocessing-cpu.py` | multiprocessing：CPU 密集串行 vs 多进程实测、GIL 反例（线程无加速）（主文档 3.3/4.1/4.3） | `python3 ex02-multiprocessing-cpu.py`（离线） |
| `ex03-concurrent-futures.py` | concurrent.futures：map / submit+as_completed 统一接口、按任务类型选 Executor（主文档 3.4） | `python3 ex03-concurrent-futures.py`（离线） |
| `ex04-asyncio-gather.py` | asyncio：串行 await vs gather 并发实测、time.sleep 阻塞事件循环反例、return_exceptions（主文档 3.5/3.6/4.4） | `python3 ex04-asyncio-gather.py`（离线） |
| `ex05-aiohttp-httpx.py` | aiohttp / httpx async：并发请求本地 HTTP 服务实测、Semaphore 限速（主文档 3.7/4.4） | `python3 ex05-aiohttp-httpx.py`（本地起服自测，测完自动关闭） |
| `ex06-async-fastapi.py` | 异步 FastAPI：进程内 uvicorn 并发压测、time.sleep 阻塞端点反例（主文档 3.8/4.6） | `python3 ex06-async-fastapi.py`（进程内起服自测，测完自动退出） |
| `pyproject.toml` | 本目录 ruff 校验基准（line-length 100、select E/F/I/UP/B） | 被 `ruff check` 命令自动读取 |

说明：

- **产物纪律**：ex05/ex06 起的本地服务都在**进程内**（后台线程 / asyncio 任务），测完自动 `shutdown`/`should_exit` 关闭，**不残留进程**；ex01~ex04 只向 stdout 输出、不落盘——运行后用 `git status` 可确认工作区干净。
- **依赖状态**：aiohttp 3.13.2、httpx 0.28.1、fastapi 0.139.1、uvicorn 0.50.0 本环境已装并实测（`python3 -c "import aiohttp, httpx, fastapi, uvicorn"` 通过）；**pytest-asyncio 未安装**——练习与项目的异步测试用标准 `asyncio.run` 包装（主文档 3.9）。
- **耗时标注**：所有耗时数字为本机（macOS arm64，14 核，Python 3.13.9）实测，**随机器与负载波动 ±10~20%**；「串行 vs 并发」的对比关系（并发 ≈ 单任务耗时）稳定，绝对秒数仅供参考。

验证状态（全部在本环境实际运行，已验证）：

- `ex01`：两次运行打印顺序不同（T0/T3/T4/T1/T2 vs T0/T2/T4/T1/T3，如实标注顺序不定）；IO 密集实测串行 **1.087s** vs 线程池(8) **0.163s**（约 6.7 倍）；竞争条件无锁 **501/4000**（丢 3499）、加锁 **4000/4000**
- `ex02`：CPU 密集实测串行 **2.357s** vs 多进程(4) **0.739s**（约 3.2 倍）vs 线程(4) **2.304s**（GIL 反例：无加速）
- `ex03`：as_completed 按完成顺序 b@0.05s → c@0.10s → d@0.16s → a@0.21s（与各自延迟一致）；map 接口线程池/进程池完全一致
- `ex04`：串行 await **1.020s** vs gather **0.051s**（约 20 倍）；gather+time.sleep 反例 **1.073s**（阻塞抹平并发）；return_exceptions 正确返回异常对象
- `ex05`：aiohttp 串行 **1.098s** vs gather **0.059s**（约 19 倍）vs httpx **0.065s**；Semaphore=2 限速 **0.537s**（= 20/2 × 0.05s，线性）；服务器已关闭
- `ex06`：async 端点串行 **1.051s** vs 并发 **0.067s**（约 16 倍）；blocked 端点并发 **1.154s**（≈ 20 × 0.05s，阻塞反例）；uvicorn 已退出
