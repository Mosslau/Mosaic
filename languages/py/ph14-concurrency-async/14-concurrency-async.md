# Python 并发、并行与异步阶段

> 面向「怎么让程序同时干很多事」，本阶段从「选型口诀」出发（ph06 已埋下：IO 用线程、CPU 用进程、海量网络 IO 用 asyncio），用**实测数据**把 threading / multiprocessing / asyncio / concurrent.futures / aiohttp·httpx / 异步 FastAPI 逐项验证、讲透机制——回答「为什么这样选、不这样选会怎样」。

## 1. 概述

Python 并发、并行与异步阶段的目标是：**处理 IO 密集和 CPU 密集任务**（roadmap 第 14 节目标）。它是学习路线的「吞吐量」一站，承接两条线索：ph06 标准库阶段已做三种并发模型的**选型概览**（其 3.10 表格：IO 用线程、CPU 用进程、海量网络 IO 用 asyncio）与 **GIL 铺垫**（4.4：「多线程不等于多核并行」）；ph10 Web 后端阶段已做 **async def 入门**（3.12：事件循环并发、异步依赖、`httpx.ASGITransport` 实测并发 ≈ 0.30s）。本阶段把这两条线索升级为**「选型口诀 + 实测数据 + 机制理解」三合一**：每个结论都有本机跑出来的耗时对比，每个机制都拆到「为什么」——这是从「会用」走向「会选、会判、会防坑」的分水岭。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 线程（threading） | Thread 创建与 join、输出顺序不定、IO 密集串行 vs 线程池实测、竞争条件与 Lock |
| 进程（multiprocessing） | Process / ProcessPoolExecutor、CPU 密集串行 vs 多进程实测、GIL 反例（线程无加速）、spawn 与 `__main__` 保护 |
| 统一接口（concurrent.futures） | `map` / `submit` + `as_completed`、线程池与进程池的同一套 Executor 接口、按任务类型选池 |
| 协程（asyncio） | `async def`/`await`、事件循环、`asyncio.run`/`create_task`/`gather`、串行 vs 并发实测 |
| 事件循环纪律 | `time.sleep` 阻塞事件循环的反面实测、正确做法（异步库 / `run_in_executor`） |
| 异步网络（aiohttp / httpx） | ClientSession 复用连接、并发请求实测、Semaphore 限速 |
| 异步 FastAPI | 承接 ph10 async def 入门，进程内 uvicorn 并发压测、阻塞端点反例 |
| 并发代码测试 | 标准 pytest + `asyncio.run` 包装的最小测法（project 落地），pytest-asyncio 仅提及 |

这个阶段只涉及**单机并发 / 并行 / 异步**——threading、multiprocessing、asyncio、concurrent.futures、aiohttp / httpx async、异步 FastAPI，以及「并发代码怎么测」的最小测法，**不涉及分布式消息队列与跨机集群并发（Kafka / MQ、百万级连接架构——ph10/ph11 曾预告此项属本阶段，这里明确边界：本阶段覆盖单机 asyncio 的万级并发网络 IO，消息队列属更大的架构主题，见 roadmap 第 18 节车联网 / 数据平台方向阶段，目录待建）、并发 / 异步测试的框架体系（pytest-asyncio 等——本阶段用标准 pytest + `asyncio.run` 演示最小测法，完整框架属生态工程实践，测试方法论本身是 ph13 测试与工程质量阶段的内容）和数据分析 / AI 训练中的并行（NumPy 的 SIMD 向量化、PyTorch 的 GPU 并行——ph09 数据分析阶段 / ph15 AI 与机器学习阶段的内容）**。本阶段承接 ph06 标准库阶段（选型口诀与 GIL 铺垫）与 ph10 Web 后端阶段（async def 入门），把「选型口诀」升级为「实测数据 + 机制理解」；ph13 测试与工程质量阶段承诺的「怎么测并发与异步代码」也在本阶段落地（3.9 与 project）。本阶段四层交付物已就位：主文档 + [`examples/`](./examples/) + [`exercises/`](./exercises/) + [`project/`](./project/)，入口见第 6、7 章。

## 2. 来源与演变

Python 的并发史是一条「**GIL 阴影下的妥协与突围**」主线。**1992 年 Guido van Rossum 为支持多线程引入 GIL（Global Interpreter Lock，全局解释器锁）**——用一把锁保证解释器状态（尤其引用计数）的线程安全，换来「多线程安全」的实现简单；代价是同一时刻只有一个线程执行 Python 字节码，纯计算多线程无法利用多核。此后二十年，CPython 在 GIL 内做并发：**threading**（高层线程封装，随 Python 1.5.2/2.0 进入标准库，1998-2000）适合 IO 密集——等待时释放 GIL；**multiprocessing**（PEP 371，Python 2.6，2008，Jesse Noller & Richard Oudkerk）用「多进程绕过 GIL」解决 CPU 密集；**concurrent.futures**（PEP 3148，Python 3.2，2011，Brian Quinlan，受 Java Executor 框架启发）把「提交任务、拿 Future、按完成顺序取结果」的接口统一到线程池与进程池之上。**asyncio**（PEP 3156，2012 年 Guido 设计，参考 Twisted / Tornado，Python 3.4 引入）则跳出「线程」赛道：单线程事件循环 + 协程，用「一个线程里让出控制权」实现海量并发网络 IO——2015 年 PEP 492 引入 `async`/`await` 关键字把它变成一等语法，2018 年 Python 3.7 的 `asyncio.run` 让「跑一个协程」只需一行。异步生态同期成熟：**aiohttp**（2012-2013，Nikolay Kim）是纯 asyncio 的 HTTP 客户端 + 服务端一体库；**uvicorn**（2017 前后，仓库 2017 年建、2018 年 4 月首个 PyPI 发布）是 ASGI 服务器参考实现；**httpx**（2019，Tom Christie）提供同步/异步双接口并兼容 ASGI；FastAPI（2018）的 async 能力即构建在 uvicorn + Starlette 之上（其历史详见 ph10 Web 后端阶段，这里不重复）。2024 年 10 月 Python 3.13 发布**实验性 free-threaded 构建**（无 GIL 的 CPython，2023 年只是 PEP 703 提案年），但标准构建仍带 GIL——本阶段的结论在标准构建上全部成立。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| GIL 引入 | 1992 | Guido 为支持多线程引入全局解释器锁，代价是纯计算无法并行 |
| threading 进标准库 | 1998-2000 | `thread` 低层模块（1.5.2）→ `threading` 高层封装（2.0） |
| multiprocessing（PEP 371） | 2008（2.6） | 多进程绕过 GIL，CPU 密集的真并行方案 |
| concurrent.futures（PEP 3148） | 2011（3.2） | 线程池/进程池统一 Executor 接口（受 Java Executor 启发） |
| asyncio（PEP 3156） | 2014（3.4） | 单线程事件循环 + 协程，海量并发网络 IO |
| `async`/`await`（PEP 492） | 2015（3.5） | 协程成为一等语法；`asyncio.run` 于 3.7（2018） |
| aiohttp | 2012-2013 | 纯 asyncio 的 HTTP 客户端 + 服务端一体库 |
| uvicorn | 2016 | ASGI 服务器参考实现，FastAPI 的运行时 |
| httpx | 2019 | 同步/异步双接口、HTTP/2、兼容 ASGI 的 HTTP 客户端 |
| Python 3.13 free-threaded 实验 | 2024（3.13） | 无 GIL 的实验构建（3.13.0 起）；标准构建仍带 GIL |

本文示例以 **Python 3.13.9** 为基线（本机验证工具链实测版本），第三方依赖 **aiohttp 3.13.2 + httpx 0.28.1 + fastapi 0.139.1 + uvicorn 0.50.0**（全部本机已装并实测，`python3 -c "import aiohttp, httpx, fastapi, uvicorn"` 通过）；**pytest-asyncio 未安装**——并发代码的测试用标准 pytest + `asyncio.run` 包装（3.9 与 project/tests）。本阶段的核心 API（threading / multiprocessing / asyncio / concurrent.futures）自 3.7 起十余年未变，是这个语言里最稳定的部分——「IO 用线程、CPU 用进程、海量网络 IO 用 asyncio」的选型在标准构建上长期成立。

## 3. 语法与参数

### 3.1 threading：线程基础与 IO 密集实测

**线程是「进程内的执行流」**：`threading.Thread(target=fn, args=(...))` 创建，`start()` 让它排队执行，`join()` 等它跑完，`daemon=True` 标记守护线程（主线程结束时被强制终止）。线程共享进程内存，创建开销远小于进程——但它由操作系统调度，**执行顺序不确定**：`start()` 只是「排上队」，谁先拿到 CPU 谁先跑。

```python
# examples/ex01-threading-io.py —— 线程基础：两次运行输出顺序不同（完整版见示例 1，本机已验证）
def shout(name: str) -> None:
    time.sleep(0.001)                    # 让出 CPU，放大顺序不确定性
    print(f"{name} 完成")

for _ in range(2):
    threads = [threading.Thread(target=shout, args=(f"T{i}",)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()                         # join：等该线程跑完再继续主流程
```

实测输出（两次运行顺序不同，如实标注）：第一次 `T0 / T3 / T4 / T1 / T2`，第二次 `T0 / T2 / T4 / T1 / T3`——**多线程输出顺序不定是常态，不是 bug**，依赖顺序的代码必须用锁或队列显式同步（3.2）。

**IO 密集实测：threading 为什么有效**。IO 密集任务（下载、读文件、调接口）绝大部分时间在「等」，而 CPython 在线程**等待时释放 GIL**（4.1），于是多个线程的等待可以重叠。ex01 用 20 个 0.05s 的模拟 IO 任务对比：

| 方式 | 本机实测 | 说明 |
|------|---------|------|
| 串行 | 1.087s | 20 × 0.05s，一个等完再等下一个 |
| 线程池(8) | 0.163s（≈ 6.7 倍） | 8 个线程的等待互相重叠，总耗时 ≈ 20/8 × 0.05s |

**选型口诀第一条：threading 适合 IO 密集**（roadmap 必会概念）——等待时释放 GIL 让线程能重叠；**CPU 密集用线程是反模式**（GIL 反例见 3.3 实测）。本阶段只涉及线程的基础用法与锁，**Barrier / Event / 线程局部存储等进阶同步原语超出本阶段**，用到时查 `threading` 文档即可。

### 3.2 线程安全与锁：竞争条件

**共享可变状态是线程的头号陷阱**。多个线程同时「读-改-写」同一个变量，中间被插队就会丢更新。ex01 用 8 个线程 × 500 次「读 → 让出 → 写」制造竞争窗口，实测（无锁版）**501/4000，丢了 3499 次**；加锁版恒为 **4000/4000**：

```python
# examples/ex01-threading-io.py —— 竞争条件：无锁丢计数、加锁分毫不差（完整版见示例 1，本机已验证）
def incr() -> None:
    for _ in range(LOOP_ITERS):
        v = counter["n"]          # 读
        time.sleep(0.000001)      # 让出 CPU，制造切换窗口
        counter["n"] = v + 1      # 写（若期间别人写过，这里会覆盖 → 丢计数）
```

**Lock 把「读-写」包成临界区**：`with lock:` 进入时阻塞等待、退出时释放，同一时刻只有一个线程能进——`counter` 从「可能丢 3500 次」变成「分毫不差」。竞争条件的修复三件套：**加锁（Lock/RLock）、原子数据结构（`queue.Queue` 生产者-消费者天然线程安全）、不可变数据（只读共享无需锁）**。

> ⚠️ **本环境（Python 3.13 标准构建）裸 `counter += 1` 的竞争很难复现**——GIL 切换间隔默认 5ms，紧循环里线程几乎不切换，`+=` 在实测中「看起来原子」。这正是 GIL 的「双刃」证据：它让简单计数侥幸安全（安全但慢），也让竞争测试难以复现——ex01 特意用「读 → 让出 → 写」制造确定性的切换窗口。**不要依赖这种侥幸**：GIL 不保证任何复合操作的原子性，共享可变状态必须显式加锁。

### 3.3 multiprocessing：CPU 密集与 GIL 反例

**进程是「独立的程序实例」**：`multiprocessing.Process` 创建子进程，`ProcessPoolExecutor` 提供进程池。进程间**内存隔离**（不共享变量，靠 pickle 序列化传数据、Queue/Pipe 通信，4.3），创建开销远大于线程——但每个进程有自己的 GIL，**真并行**。ex02 用 4 个 2000 万次平方和任务实测：

| 方式 | 本机实测 | 结论 |
|------|---------|------|
| 串行 | 2.357s | 4 × 0.59s |
| 多进程(4) | 0.739s（≈ 3.2 倍） | 4 个核同时算，加速比 ≈ 核数 |
| 线程(4) | 2.304s（≈ 串行） | **GIL 反例**：线程轮流抢锁执行字节码，无加速 |

```python
# examples/ex02-multiprocessing-cpu.py —— CPU 密集：多进程真并行、线程无加速（完整版见示例 2，本机已验证）
def cpu_task(_: int) -> int:
    return sum(i * i for i in range(LIMIT))   # 纯计算，不释放 GIL

with ProcessPoolExecutor(max_workers=4) as ex:
    results = list(ex.map(cpu_task, range(N_TASKS)))   # 4 个进程各占一个核
```

**`if __name__ == "__main__":` 保护是硬规则**（教学增量）：macOS / Windows 默认用 **spawn** 启动子进程——子进程会**重新导入主模块**，若模块顶层直接创建进程池，会无限递归创建进程直接报错（`RuntimeError: An attempt has been made to start a new process...`）。所有进程池代码必须放进 `main()`、由 `if __name__ == "__main__":` 守卫（ex02、练习 2 都如此）。

**选型口诀第二条：multiprocessing 适合 CPU 密集**（roadmap 必会概念）——绕过 GIL 真并行；**代价是进程隔离与序列化开销**：传参/回传要 pickle（lambda、局部闭包不可序列化——练习 2 若把任务写成 lambda 或局部闭包，会报 `Can't pickle <function <lambda>>`），大对象传输慢。任务小到「进程创建 + 序列化」成本超过并行收益时，串行反而更快——**加速比 ≈ 核数，但只有任务足够大才值得**。

### 3.4 concurrent.futures：统一 Executor 接口

**concurrent.futures 把「线程池」和「进程池」抽象成同一个 Executor 接口**（受 Java Executor 框架启发）：`ThreadPoolExecutor` 与 `ProcessPoolExecutor` 提供完全相同的三个方法——`map(fn, *iterables)` 按序收集结果、`submit(fn, *args)` 单个提交返回 **Future**（占位符，稍后 `future.result()` 取结果）、`as_completed(futures)` 谁先完成先处理谁。**选池只改一行**（ex03 的 `choose_executor` 助手演示了这一点）：

```python
# examples/ex03-concurrent-futures.py —— 统一接口：IO 用线程池、CPU 用进程池（完整版见示例 3，本机已验证）
def choose_executor(kind: str):
    if kind == "io":
        return ThreadPoolExecutor(max_workers=8)     # IO 密集 → 线程池
    if kind == "cpu":
        return ProcessPoolExecutor(max_workers=4)    # CPU 密集 → 进程池
    raise ValueError(f"未知任务类型: {kind!r}")

with choose_executor("io") as ex:
    r_io = list(ex.map(io_task, ["x", "y"], [0.05, 0.08]))
```

`as_completed` 的「流式消费」在 ex03 的实测中很直观——4 个延迟不同的任务按完成顺序返回：**b(0.05s) → c(0.10s) → d(0.16s) → a(0.21s)**（完成时刻与各自延迟一致，同一延迟内顺序不定）。混合场景（练习 4）演示了两池协同：IO 任务进线程池、CPU 任务进进程池，`as_completed` 边完成边收集，**两组任务在总耗时里互相重叠**（串行 0.94s → 混合并发 0.16s，≈ 5.9 倍）。

| 场景 | 选哪个池 | 原因 |
|------|---------|------|
| 下载 / 网络 / 等待 | `ThreadPoolExecutor` | 等待时释放 GIL，可重叠 |
| 计算 / 解析 / 压缩 | `ProcessPoolExecutor` | 独立进程真并行，绕过 GIL |
| 任务量小、切换频繁 | 串行 | 池的创建与调度开销超过收益 |

### 3.5 asyncio：协程、事件循环与 gather

**asyncio 是「单线程内的并发」**：一个事件循环（event loop）跑一堆**协程**（`async def` 定义的函数），每个协程在 `await` 处把控制权让回事件循环，等待期间其他协程插队执行。三个入口：`asyncio.run(coro)` 一键「建循环 → 跑 → 关」、`asyncio.create_task(coro)` 把协程挂为后台任务、`asyncio.gather(*coros)` 一批协程并发跑、全部完成一起返回。ex04 用 20 个 0.05s 模拟 IO 实测：

| 方式 | 本机实测 | 说明 |
|------|---------|------|
| 串行 await | 1.020s | `[await task(i) for i in ...]`，一个等完再等下一个 |
| gather 并发 | 0.051s（≈ 20 倍） | 20 个协程同时「等」，总耗时 ≈ 单任务耗时 |

```python
# examples/ex04-asyncio-gather.py —— gather 并发：20 个任务 ≈ 单任务耗时（完整版见示例 4，本机已验证）
async def async_io_task(i: int) -> int:
    await asyncio.sleep(IO_WAIT)     # await 让出控制权：等待期间其他任务插队
    return i * 2

results = await asyncio.gather(*(async_io_task(i) for i in range(20)))
```

**`gather(..., return_exceptions=True)`** 让单个协程的异常不拖垮整批——ex04 实测：5 个任务里第 3 个抛 `ValueError`，结果为 `[0, 1, 2, ValueError('任务 3 挂了'), 4]`（异常对象原位返回，其余照常）。这与 ph13 的「mock 隔离外部依赖」是同一心智：**让失败成为可检查的返回值，而不是整个程序崩溃**。

**选型口诀第三条：asyncio 适合大量并发网络 IO**（roadmap 必会概念）——线程池扛几千个连接要几千条线程（每条线程约 8MB 栈内存 + 调度开销），asyncio 一条线程就能扛上万协程（每个协程只是几十字节的状态对象）；代价是**代码必须全程 `async`**——同步阻塞调用会卡死整个事件循环（3.6 反例实测）。

### 3.6 不要阻塞事件循环（必会概念的反面演示）

**事件循环是单线程的，一个协程阻塞 = 所有人阻塞**。`time.sleep` / `requests.get` / 同步文件 IO 这类**阻塞调用**在协程里会占住整个事件循环，其他协程全部排队。ex04 用「协程里写 `time.sleep`」的 gather 反例实测：**1.073s ≈ 串行**——并发被彻底抹平。ex06 在真实 FastAPI 服务上复现同一现象（3.8 的 blocked 端点）。

| 写法 | 效果（ex04 实测） |
|------|------------------|
| `await asyncio.sleep(0.05)` | 0.051s（并发，≈ 20 倍） |
| `time.sleep(0.05)`（在协程里） | 1.073s（阻塞，退回串行） |

**正确做法三条**：① 用**异步库**替代同步库（`asyncio.sleep` 替代 `time.sleep`、aiohttp/httpx 替代 requests、aiosqlite 替代 sqlite3——ph10 的「异步接口要配套异步依赖」即此）；② 绕不开的同步 CPU/阻塞代码用 `asyncio.to_thread(fn, ...)` / `loop.run_in_executor` 丢到线程池；③ 混用框架时记住 FastAPI 会把普通 `def` 端点自动丢进线程池（3.8）——**同步业务代码写在 `def` 端点里反而安全**。

> ⚠️ **判断一段代码会不会阻塞事件循环的直觉**：它是不是「等」？`await asyncio.sleep` 是「让出等」、`time.sleep` 是「占着等」；凡是 CPU 密集或同步 IO 的调用在 async 上下文里都要警惕。这是 roadmap 必会概念「不要阻塞事件循环」的量化版本——反例的 1.07s 与正例的 0.05s 就是 20 倍的差距。

### 3.7 aiohttp / httpx async：异步 HTTP 客户端

**aiohttp 与 httpx 是 asyncio 世界的两个 HTTP 客户端**，共同点是 `async with` 管理连接（`ClientSession` / `AsyncClient`，类比 requests 的 `Session`：复用 TCP 连接、批量请求更省开销）、`await client.get(url)` 发出请求。ex05 在本地起一个模拟服务（20 个端点、每个 0.05s 延迟）实测：

| 方式 | 本机实测 | 说明 |
|------|---------|------|
| aiohttp 串行 | 1.098s | 一个等完再发下一个 |
| aiohttp gather 并发 | 0.059s（≈ 19 倍） | 20 个请求同时「等」，≈ 单请求耗时 |
| httpx 并发 | 0.065s | 同一套 gather 写法，接口不同 |

```python
# examples/ex05-aiohttp-httpx.py —— 并发请求本地服务（完整版见示例 5，本机已验证）
async with aiohttp.ClientSession() as session:          # ClientSession 复用连接
    responses = await asyncio.gather(*(get_resp(u) for u in urls))   # get_resp：GET + 读体（连接可复用）

async with httpx.AsyncClient() as client:               # httpx：同一套 gather 写法
    responses = await asyncio.gather(*(hx_get(u) for u in urls))
```

**限速用 `asyncio.Semaphore`**：给并发加上限，防止把对端打爆（爬虫、采集的刚需）。ex05 实测：Semaphore(2) 时 20 个 0.05s 请求耗时 **0.537s ≈ 20/2 × 0.05s**——限速把并发压成「2 路并行 + 排队」，耗时按 并发上限 线性增长，关系完全可预测。

**aiohttp vs httpx 选型**（ph08 第三方库阶段已做选型铺垫，这里补并发视角）：httpx 提供**同步/异步双接口**（`httpx.Client` 与 `httpx.AsyncClient`，同一套 API，ph08 的同步脚本可直接平移）、支持 HTTP/2、兼容 ASGI；aiohttp 是**纯 asyncio 的客户端 + 服务端一体库**（`aiohttp.web`，本项目用它起模拟服务器），生态里和 asyncio 绑定最紧。**爬虫/采集/API 客户端用 httpx 更顺手；纯 asyncio 项目或需要内嵌 HTTP 服务用 aiohttp**。

### 3.8 异步 FastAPI：事件循环上的 Web 服务

**FastAPI 的 `async def` 端点跑在 uvicorn 的事件循环上**（ph10 3.12 已入门：await 让出、异步依赖、`ASGITransport` 并发 ≈ 0.30s）。本阶段补上**真实服务的并发压测**：ex06 在进程内起 uvicorn（端口 0 = 系统分配，测完 `should_exit` 优雅退出），用 httpx 压 20 个 0.05s 慢请求：

| 场景 | 本机实测 | 结论 |
|------|---------|------|
| `async def` 端点 串行 20 请求 | 1.051s | 20 × 0.05s |
| `async def` 端点 并发 20 请求 | 0.067s（≈ 16 倍） | 事件循环在 `await` 处切换请求 |
| `time.sleep` 阻塞端点 并发 20 请求 | 1.154s（≈ 20 × 0.05s） | **阻塞反例**：事件循环被卡死，并发失效 |

```python
# examples/ex06-async-fastapi.py —— async 端点与阻塞反例（完整版见示例 6，本机已验证）
@app.get("/slow/{n}")
async def slow(n: int) -> dict:
    await asyncio.sleep(0.05)          # await 让出：等待期间处理其他请求
    return {"n": n, "ok": True}

@app.get("/blocked/{n}")
async def blocked(n: int) -> dict:
    time.sleep(0.05)                   # 错误示范：阻塞整个事件循环
    return {"n": n, "ok": True}
```

**结论与 ph10 的「异步接口要配套异步依赖」完全一致，且有了量化证据**：`async def` 端点的价值全在 `await`——IO 密集业务（查库、调外部 API）写成 async 端点，一个进程就能扛大量慢请求；**同步业务（CPU 密集、同步库）写普通 `def` 端点**，FastAPI 自动丢进线程池，反而不会卡事件循环。**判断标准不是「端点写了 async 就快」，而是「await 的 IO 等待能不能重叠」**。

### 3.9 并发代码怎么测（ph13 承诺的落地）

ph13 测试与工程质量阶段承诺「怎么测并发与异步代码」留到本阶段。**最小测法不需要任何新框架**：测试函数用标准 pytest，内部用 `asyncio.run()` 包装异步场景——起进程内模拟服务器 → 跑采集 → 断言 → `finally` 关闭（project/tests 的完整示范）：

```python
# project/tests/test_fetcher.py —— 标准 pytest + asyncio.run 包装（project 落地，本机已验证）
def test_collect_all_success():
    async def _t() -> None:
        sim = TelemetrySimulator(n_vehicles=10, fail_rate=0.0, seed=1)
        await sim.start()
        try:
            results = await collect(sim.base_url, sim.vehicle_ids, max_concurrency=5)
            assert len(results) == 10
            assert all(r.ok for r in results)          # 断言的是「结果」而非「并发过程」
            assert all(r.attempts == 1 for r in results)
        finally:
            await sim.stop()                           # 测完必关，不残留端口

    asyncio.run(_t())
```

**测并发的三条纪律**（project 的 16 个用例全部遵守）：① **测结果，不测过程**——断言「成功数、失败集合、重试次数、结果一致性」，不断言「哪个线程先跑」（输出顺序不定，断言它会随机挂）；② **让失败确定性**——模拟服务器注入 `fail_rate=0.0`（全成功）/ `1.0`（全失败）/ 固定 seed（混合），同一 seed 完全可复现（project 的 `test_same_seed_is_deterministic` 专门验证）；③ **进程内起服务、测完必关**——不依赖外部服务、不残留端口。**pytest-asyncio 本环境未安装**，它把 `asyncio.run` 包装变成 `@pytest.mark.asyncio` 装饰器（体验更好），原理与本阶段的最小测法一致——需要时装 `pip install pytest-asyncio` 即可，本阶段不引入。

## 4. 底层原理

### 4.1 GIL：为什么线程不能并行 CPU

CPython 解释器本身不是线程安全的——**引用计数**（对象回收的机制）在多线程下会竞争。GIL 用一把进程级大锁保证「同一时刻只有一个线程执行 Python 字节码」，让引用计数操作天然安全。关键在**锁的持有时机**：执行纯计算时线程**一直持有 GIL**（谁也插不进来，多线程 = 轮流执行，无并行）；执行 IO 时线程**释放 GIL 等待**（其他线程趁机执行，等待可重叠）。这就是 3.1/3.3 两组实测的机制根源：IO 密集线程池 6.7 倍加速（等待重叠）、CPU 密集线程池 0 加速（轮流抢锁，差异在 ±10~20% 波动内）。**GIL 反例的 2.304s ≈ 串行的 2.357s，就是「轮流执行」的实证**。

### 4.2 线程调度：OS 线程与 GIL 切换

Python 线程是**操作系统线程**（macOS/Windows 下由内核调度），线程切换（上下文切换：保存/恢复寄存器、栈、缓存）有真实开销。GIL 之上还有一层**解释器级切换**：CPython 按**时间间隔**切换 GIL（默认 **5ms**——Python 3.2 起为时间间隔制，3.2 前才是指令计数制；`sys.getswitchinterval()` 可查、`sys.setswitchinterval()` 可调）就尝试让出 GIL，让其他线程有机会执行——ex01 的「读 → 让出 → 写」竞争正是靠 `time.sleep(0.000001)` 制造切换窗口才稳定复现（3.2 的注意块）。两层切换叠加，线程多的场景调度开销不可忽视——**这是「任务太小用线程不如串行」的机制解释**。

### 4.3 进程模型：隔离、spawn 与 pickle

`multiprocessing` 的子进程是**独立的内存空间**（进程级隔离）：不共享变量、不共享 GIL，靠 **pickle 序列化**在进程间传参数与结果、靠 **Queue / Pipe** 做进程间通信（IPC）。macOS / Windows 默认 **spawn** 启动方式：父进程「重新导入主模块 + 运行指定的入口函数」来孵化子进程——这解释了 3.3 的两条硬规则：**进程池代码必须受 `if __name__ == "__main__":` 保护**（否则 spawn 时无限递归），**传给进程池的函数与参数必须可 pickle**（模块级函数可以，lambda / 局部闭包会报 `Can't pickle <function <lambda>>`——练习 2 若写成 lambda 就会踩这个坑）。大对象（如几十 MB 的 DataFrame）序列化成本可能吃掉并行收益——**大数据量场景优先考虑「分段传 + 每段独立结果」，而不是整体传来传去**。

### 4.4 事件循环：await 让出与非阻塞 IO

asyncio 的底层是**非阻塞 IO + 事件通知**：socket 请求发出后不阻塞等待，而是注册「有数据到了叫我」（macOS 用 kqueue、Linux 用 epoll，标准库 `selectors` 模块统一）；事件循环就是「**注册 → 等待通知 → 分发回调**」的无限循环。协程的 `await` 让这一模型有了语法级表达：`await` 处把「当前协程挂起 + 注册完成回调」，控制权回到事件循环；事件到达时循环把结果交回协程继续执行。**Task 是「协程 + 状态 + 回调」的包装**，`gather` 内部就是「建 N 个 Task、全部完成后一起返回」。所以：

```text
事件循环（单线程）
  │
  ├─ 协程 A ──await──▶ 注册回调 ──▶ 等 socket ──▶ 事件到达 ──▶ 唤醒 A
  ├─ 协程 B ──await──▶ 注册回调 ──▶ 等 socket ──▶ 事件到达 ──▶ 唤醒 B
  └─ 就绪队列：谁的事件先到谁先跑（协作式调度，无抢占）
```

**为什么 `time.sleep` 会卡死它**：`time.sleep` 是**阻塞系统调用**，不经过事件循环的「注册-通知」机制——协程 A 调它，整个线程睡死，就绪队列里 B/C/D 全部饿死（3.6/3.8 的 1.07s、1.15s 反例）。**asyncio 的并发是协作式的：每个人都自觉在 `await` 处让出，一个人赖着不走，所有人陪等**。

### 4.5 三种并发模型对比

```text
┌───────────────────┐      ┌─────────────────────────┐      ┌─────────────────┐
│ 线程（threading） │      │ 进程（multiprocessing） │      │ 协程（asyncio） │
│ 共享内存          │      │ 内存隔离                │      │ 单线程共享      │
│ 共享 GIL          │      │ 各自 GIL                │      │ 无 GIL 争抢     │
│ OS 调度           │      │ OS 调度                 │      │ 事件循环调度    │
│ 开销：中          │      │ 开销：大                │      │ 开销：最小      │
│ 适用：IO 密集     │      │ 适用：CPU 密集          │      │ 适用：海量网络  │
└───────────────────┘      └─────────────────────────┘      └─────────────────┘
```

三者不是替代关系而是**组合关系**（练习 4 的混合场景、project 的采集服务都是组合）：IO 用线程/协程重叠等待，CPU 用进程真并行，海量网络 IO 用协程省资源。

### 4.6 FastAPI / uvicorn 的 ASGI 事件循环

FastAPI 跑在 **ASGI** 之上（ph10 4.1 已讲：应用是接收 `(scope, receive, send)` 的异步可调用对象），uvicorn 启动一个 asyncio 事件循环：**每个请求是一条协程任务，不是一条线程**。`async def` 端点的 `await` 让出控制权，事件循环去处理别的请求——「一个进程扛成千上万个慢请求」的原理；普通 `def` 端点由 Starlette 自动丢进**线程池**执行。ex06 的 16 倍并发实测就是这个模型的量化验证；而 blocked 端点的 1.154s 则量化了「同步阻塞代码放进 async 端点」的代价——**20 个请求全部排队，事件循环形同虚设**。这正是 ph10「异步接口要配套异步依赖」的机制底层：依赖链上任何一环是同步阻塞，整条链的并发就归零。

### 4.7 并发代码评审清单（写对并发的最后一道闸）

把 3.1~3.9 的教训收敛成合入前逐项过一遍的清单——**并发 bug 大多不在"会不会写"，而在"写的时候没问这几句"**：

- [ ] 共享可变状态有没有被锁/原子结构/不可变数据保护？（3.2——无锁丢 3499 次的教训）
- [ ] CPU 密集任务是不是错用了线程？（3.3——GIL 反例：≈ 串行）
- [ ] async 上下文里有没有同步阻塞调用（`time.sleep`/`requests`/同步文件 IO）？（3.6——1.07s 反例）
- [ ] 池/会话用完有没有关闭？（`with` 块或显式 `shutdown`——`ClientSession`/Executor 不关会泄漏）
- [ ] 并发任务的异常会被吞掉还是可检查？（`return_exceptions`/`future.result()` 显式处理，3.5）
- [ ] 并发代码有没有可复现的测试？（seed + 注入失败率，断言结果不断言过程，3.9）

清单外的第一原则：**先想"要不要并发"，再想"用哪种并发"**——任务小到并发基础设施开销都回不来时，串行是对的选择（3.4/5 章选型表）。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 批量下载 / 并发抓取 / 调外部 API | threading + 线程池（3.1）、aiohttp / httpx async（3.7）、练习 1/3/5、project |
| 大量并发网络 IO（爬虫、采集、监控上报） | asyncio + gather + Semaphore 限速（3.5/3.7）、project |
| 解析大文件 / 批量计算 / 数据预处理 | multiprocessing + 进程池（3.3）、练习 2/4 |
| 混合任务（既有等待又有计算） | concurrent.futures 双池 + as_completed（3.4）、练习 4 |
| 共享计数 / 生产者消费者 / 任务队列 | Lock / `queue.Queue`（3.2） |
| Web 服务的慢 IO 接口（查库、调第三方） | 异步 FastAPI async 端点（3.8）、ex06 |
| 异步代码的正确性验证 | pytest + `asyncio.run` 包装（3.9）、project/tests |
| 限速防封（爬虫礼貌抓取） | `asyncio.Semaphore`（3.7、练习 5） |

**选型决策**（roadmap 必会概念的落地版）：

| 任务类型 | 首选 | 为什么 | 反面 |
|---------|------|--------|------|
| IO 密集（等网络/磁盘） | threading / asyncio | 等待重叠，asyncio 更省资源 | multiprocessing 的进程开销白付 |
| CPU 密集（纯计算） | multiprocessing | 真并行 | threading 被 GIL 卡死（实测无加速） |
| 海量并发网络 IO（千级以上） | asyncio | 单线程扛万级协程 | threading 的线程数撑不住 |
| 规模小、切换频繁 | 串行 | 并发基础设施开销超过收益 | 为了并发而并发 |

**不适合此阶段的事项**：

- 分布式消息队列与跨机集群并发（Kafka / MQ、百万级连接架构）：roadmap 第 18 节车联网 / 数据平台方向阶段（目录待建）或团队工程实践——ph10/ph11 曾把「大规模异步与消息」预告到 ph14，本阶段明确其边界：**单机 asyncio 覆盖万级并发网络 IO，消息队列是跨机架构话题**，不在此展开
- 并发 / 异步测试的框架体系（pytest-asyncio 等）：本阶段用标准 pytest + `asyncio.run` 演示最小测法（3.9），框架属生态工程实践
- 数据分析与 AI 训练中的并行（NumPy SIMD 向量化、PyTorch GPU 并行）：ph09 数据分析阶段 / [ph15 AI 与机器学习阶段](../ph15-ai-ml/15-ai-ml.md)（深度学习与 GPU 训练超出 ph15 可验证范围，仅概念层）
- 分布式计算框架（ray、dask）：超出本路线的阶段划分
- async 数据库驱动的深入（asyncpg / aiomysql 等）：ph10/ph11 已用到 aiosqlite 的最小用法，本阶段不展开

**与其他语言同类机制的对比**（一句话级，为 analysis/ 与 Tenet 合成积累素材）：Go 的 **goroutine** 把「轻量线程」内置进语言（几 KB 栈、运行时调度器 M:N 调度，`go func()` 即并发，channel 做同步）——Python 的线程是 OS 线程（贵、受 GIL 限制），asyncio 是库不是语言特性；Node.js 与 Python asyncio 同源（单线程事件循环），但 JS 的异步是语言内置（Promise/async-await），Python 是标准库演化而来；Rust 的 **tokio** 把「零成本异步」做进类型系统（所有权保证跨线程安全、编译期杜绝数据竞争），Python 的线程安全靠运行时锁与开发者自觉；Java 2023 年的 **虚拟线程（Loom）** 把「百万线程」变成 JVM 内置能力，用阻塞式代码获得并发——**Python 的独特之处是「三种模型并存、按任务类型选型」**：没有一种机制通吃，选型能力本身就是 Python 并发编程的核心技能。

**并发反模式自查表**（每一条都能在本文的实测里找到代价）：

| 反模式 | 实测代价（转述自 3.x） | 修法 |
|--------|----------------------|------|
| CPU 密集用线程 | 2.304s ≈ 串行 2.357s——GIL 卡死，无加速 | `ProcessPoolExecutor`（3.3） |
| 以为 GIL 让计数天然安全 | "看似原子"只是 GIL 切换间隔（5ms）的侥幸，复合操作不保证 | 共享状态显式加锁（3.2） |
| async 协程里塞 `requests.get`/`time.sleep` | 1.07s/1.15s ≈ 串行——并发被阻塞抹平 | 异步库 / `asyncio.to_thread`（3.6/3.8） |
| 一个 Executor 通吃所有任务 | IO 任务被进程池的序列化拖慢、CPU 任务在线程池零加速 | 按任务类型选池，混合用双池 + `as_completed`（3.4/练习 4） |
| 并发无上限 | 打爆对端/本地（连接、内存失控） | `asyncio.Semaphore` 限速（3.7） |
| 并发写完不测 | 竞态偶发、难复现难回归 | seed + 注入失败率，断言结果不断言过程（3.9） |

## 6. 代码示例

本节展示完整可运行示例的关键片段，完整文件（含文件头验证环境与运行命令）在 [`examples/`](./examples/) 目录，对照 [`examples/README.md`](./examples/README.md) 逐条运行。验证环境：Python 3.13.9（macOS arm64，14 核）+ aiohttp 3.13.2 + httpx 0.28.1 + fastapi 0.139.1 + uvicorn 0.50.0（全部本机已装并实测）。全部示例**离线可跑**：ex05/ex06 起的本地服务都在进程内，测完自动关闭**不残留进程**；ex01~ex04 只向 stdout 输出、不落盘。**所有耗时数字为本机实测，随机器与负载波动 ±10~20%**——对比关系（并发 ≈ 单任务耗时、多进程 ≈ 串行/核数）稳定，绝对秒数仅供参考。

### 示例 1：threading（线程基础 + IO 密集实测 + 竞争条件）

呼应 3.1/3.2/4.1：线程直接创建（输出顺序不定）、IO 密集串行 vs 线程池、竞争条件无锁 vs 加锁。完整文件 `examples/ex01-threading-io.py`。

```python
# examples/ex01-threading-io.py —— threading 三件套（离线可跑，已验证）
def io_task(i: int) -> int:
    time.sleep(IO_WAIT)                # 模拟 IO 等待：等待时释放 GIL
    return i * 2

t0 = time.perf_counter()
serial = [io_task(i) for i in range(N_TASKS)]          # 串行
t0 = time.perf_counter()
with ThreadPoolExecutor(max_workers=8) as ex:
    pooled = list(ex.map(io_task, range(N_TASKS)))     # 线程池
```

实测输出：两次运行打印顺序不同（`T0/T3/T4/T1/T2` vs `T0/T2/T4/T1/T3`）；IO 密集串行 **1.087s** vs 线程池(8) **0.163s**（≈ 6.7 倍）；竞争条件无锁 **501/4000**（丢 3499）、加锁 **4000/4000**。

### 示例 2：multiprocessing（CPU 密集实测 + GIL 反例）

呼应 3.3/4.1/4.3：串行 vs 多进程 vs 线程的 CPU 密集三方实测。完整文件 `examples/ex02-multiprocessing-cpu.py`。

```python
# examples/ex02-multiprocessing-cpu.py —— CPU 密集三方对比（离线可跑，已验证）
def cpu_task(_: int) -> int:
    return sum(i * i for i in range(LIMIT))            # 纯计算，不释放 GIL

with ProcessPoolExecutor(max_workers=4) as ex:         # 4 个进程各占一个核
    results = list(ex.map(cpu_task, range(N_TASKS)))
```

实测输出：串行 **2.357s** / 多进程(4) **0.739s**（≈ 3.2 倍）/ 线程(4) **2.304s**（GIL 反例：无加速，差异在 ±10~20% 波动内）。

### 示例 3：concurrent.futures（统一 Executor 接口）

呼应 3.4：map 双池一致、submit + as_completed 按完成顺序消费、按任务类型选池。完整文件 `examples/ex03-concurrent-futures.py`。

```python
# examples/ex03-concurrent-futures.py —— 统一接口（离线可跑，已验证）
with ThreadPoolExecutor(max_workers=4) as ex:
    futures = {ex.submit(io_task, name, delay): name for name, delay in IO_DELAYS.items()}
    for fut in as_completed(futures):                  # 谁先完成先处理谁
        print(f"  {futures[fut]} 完成 -> {fut.result()}")
```

实测输出：as_completed 完成时刻 **b@0.05s → c@0.10s → d@0.16s → a@0.21s**（与各自延迟一致）；map 接口线程池/进程池完全一致。

### 示例 4：asyncio（gather 并发 + 阻塞反例）

呼应 3.5/3.6/4.4：串行 await vs gather 并发、time.sleep 反例、return_exceptions。完整文件 `examples/ex04-asyncio-gather.py`。

```python
# examples/ex04-asyncio-gather.py —— gather 与阻塞反例（离线可跑，已验证）
async def async_io_task(i: int) -> int:
    await asyncio.sleep(IO_WAIT)       # await 让出控制权
    return i * 2

async def blocking_io_task(i: int) -> int:
    time.sleep(IO_WAIT)                # 阻塞！事件循环被卡住
    return i * 2

results = await asyncio.gather(*(async_io_task(i) for i in range(20)))
```

实测输出：串行 await **1.020s** / gather **0.051s**（≈ 20 倍）/ gather+time.sleep **1.073s**（阻塞抹平并发）；`return_exceptions=True` 返回 `[0, 1, 2, ValueError('任务 3 挂了'), 4]`。

### 示例 5：aiohttp / httpx（异步 HTTP 客户端 + 限速）

呼应 3.7/4.4：本地 HTTP 服务上并发请求实测、Semaphore 限速。完整文件 `examples/ex05-aiohttp-httpx.py`（本地起服自测，测完自动关闭）。

```python
# examples/ex05-aiohttp-httpx.py —— 并发请求本地服务（本地起服自测，已验证）
async with aiohttp.ClientSession() as session:
    responses = await asyncio.gather(*(get_resp(u) for u in urls))   # get_resp：GET + 读体（连接可复用）
sem = asyncio.Semaphore(2)                              # 限速：并发压到 2
async def limited(u: str):
    async with sem:
        return await get_resp(u)
```

实测输出：aiohttp 串行 **1.098s** / gather **0.059s**（≈ 19 倍）/ httpx **0.065s**；Semaphore=2 限速 **0.537s**（= 20/2 × 0.05s，线性）；服务器已关闭（无残留进程）。

### 示例 6：异步 FastAPI（进程内 uvicorn 压测 + 阻塞反例）

呼应 3.8/4.6：async 端点串行 vs 并发、time.sleep 阻塞端点反例。完整文件 `examples/ex06-async-fastapi.py`（进程内起 uvicorn 自测，测完优雅退出）。

```python
# examples/ex06-async-fastapi.py —— async 端点与阻塞反例（进程内起服自测，已验证）
@app.get("/slow/{n}")
async def slow(n: int) -> dict:
    await asyncio.sleep(0.05)          # await 让出：等待期间处理其他请求
    return {"n": n, "ok": True}
```

实测输出：async 端点串行 **1.051s** / 并发 **0.067s**（≈ 16 倍）；blocked 端点（`time.sleep`）并发 **1.154s**（≈ 20 × 0.05s，阻塞反例）；uvicorn 已退出（无残留进程）。

## 7. 总结

### 关键要点

1. **threading 适合 IO 密集**（必会概念）：等待时释放 GIL，线程的等待可重叠——ex01 实测 20×0.05s 从 1.087s 压到 0.163s（≈ 6.7 倍）；**共享可变状态必须加锁**（无锁丢 3499 次、加锁分毫不差，3.1/3.2）
2. **multiprocessing 适合 CPU 密集**（必会概念）：进程各自有 GIL、真并行——ex02 实测 ≈ 3.2 倍加速；线程跑纯计算被 GIL 卡死（2.304s ≈ 串行）；`if __name__ == "__main__":` 保护与「可 pickle」是两条硬规则（3.3/4.3）
3. **asyncio 适合大量并发网络 IO**（必会概念）：单线程事件循环 + 协程，`await` 让出控制权——ex04 实测 20 任务从 1.020s 压到 0.051s（≈ 20 倍）；aiohttp/httpx 并发请求 ≈ 单请求耗时（3.5/3.7）
4. **不要阻塞事件循环**（必会概念）：`time.sleep` 在协程里把并发抹平——ex04 反例 1.073s、ex06 阻塞端点 1.154s，与正例的 0.05s/0.07s 是 15~20 倍差距；正确做法：异步库 / `asyncio.to_thread` / FastAPI 的 `def` 端点（3.6/3.8）
5. **concurrent.futures 是统一入口**：线程池与进程池同一套 `map`/`submit`/`as_completed` 接口，按任务类型选池只改一行（3.4/练习 4）
6. **Semaphore 限速**：并发上限与耗时成线性关系（ex05 实测 20/2 × 0.05s = 0.537s），采集/爬虫防打爆对端的刚需（3.7/练习 5）
7. **测并发测结果不测过程**：pytest + `asyncio.run` 包装、失败确定性（seed 注入）、进程内服务测完必关——project 16 个用例全绿（3.9）
8. **先想"要不要并发"，再想"用哪种"**：任务小到并发基础设施开销回不来就串行；选好之后用 4.7 评审清单与 5 章反模式表自检（GIL 反例/阻塞事件循环/共享无锁是前三名）

### 阶段验收清单

- [ ] 能区分并发和并行（对应 roadmap「能区分并发和并行」）：并发是「同时推进」（线程/协程交错），并行是「同时执行」（多核多进程）——GIL 让 CPython 线程只有并发没有并行，多进程才有并行
- [ ] 能选择线程/进程/异步（对应 roadmap「能选择线程/进程/异步」）：IO 密集→线程/协程、CPU 密集→进程、海量网络 IO→asyncio，能用实测数据（3.1/3.3/3.5 的表格）说明为什么
- [ ] 能避免阻塞异步代码（对应 roadmap「能避免阻塞异步代码」）：识别 `time.sleep`/同步 IO 在协程里的危害（3.6/3.8 反例），会用异步库与 `to_thread` 的正确做法
- [ ] 能说出 GIL 的机制与边界：为什么线程不能并行 CPU、为什么 IO 能重叠、竞争条件怎么复现与修复（4.1/4.2、ex01 Part C）
- [ ] 能写带限速与重试的异步采集（Semaphore + 退避），并会用 pytest + `asyncio.run` 验证正确性（练习 5、project）
- [ ] 能独立跑通 6 个示例并解释每个的实测数字（第 6 章），能对照 project 说出「单机并发选型的完整闭环」

### 跨语言对比：并发与异步

| 维度 | Python | Go | Node.js | Rust | Java |
|------|--------|----|---------|------|------|
| 轻量并发单元 | 协程（asyncio，库） | goroutine（语言内置） | Promise/async（内置） | Future/async（tokio 库） | 虚拟线程（Loom，2023） |
| 线程 | OS 线程 + GIL 限制 | 无 GIL，M:N 调度 | 单线程事件循环 | OS 线程 + 所有权保证 | OS 线程 / 虚拟线程 |
| 并行 | 多进程（内存隔离） | goroutine 天然并行 | worker_threads 集群 | tokio 多线程运行时 | JVM 线程池 |
| 同步原语 | Lock / Queue（库） | channel（语言内置） | 事件驱动，无共享内存 | 所有权 + channel/Mutex | synchronized / 并发集合 |
| 数据竞争 | 运行时锁，靠自觉 | 编译期 channel 心智 | 单线程无共享 | **编译期杜绝** | 运行时检测（可选） |
| 选型成本 | **三种模型按任务选型** | 一种模型通吃 | 一种模型通吃 | 异步为主，阻塞可换线程 | 虚拟线程屏蔽选择 |

一句话：Go / Node / Java(Loom) 各自把「一种并发模型」内建进语言，**Python 的答案是「三模型并存、按任务类型选型」**——这既是它的灵活，也是它的心智负担（选错就白忙，3.3 的 GIL 反例就是代价）。（为 analysis/ 与 Tenet 合成积累素材：一门并发语言若想降低选择成本，把「轻量线程 + 通道」内建是 Go 给的最直接启示。）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 [exercises/README.md](./exercises/README.md)，参考实现 sol-* 先别看）。对应 roadmap「练习」小节：并发下载文件（练习 1）、多进程处理大文件（练习 2，按区间分片思想）、并发请求 API（练习 3）、异步爬虫（练习 5，aiohttp 并发抓取本地接口 + 限速 + 重试）；练习 4 补「学习内容」里的 concurrent.futures 混合选型，完成 5 题后继续：

- 并发下载文件（★）：串行 vs 线程池下载 20 个模拟文件，断言结果一致（提示：`time.sleep(0.05)` 模拟；参考实现 ≈ 4 倍加速）
- 多进程处理大计算（★★）：质数统计按 4 段分片，串行 vs 进程池 + 线程对照组（提示：`ex.map(count_primes, los, his)` 多参数 map；参考实现 ≈ 2.7~2.8 倍）
- 异步并发请求 API（★★）：串行 await vs gather vs `time.sleep` 反例三组实测 + `return_exceptions`（提示：反例 ≈ 串行；参考实现 gather ≈ 20 倍）
- 混合任务流式收集（★★★）：12 IO + 4 CPU 双池并行 + as_completed，断言两类任务数量（提示：串行 0.94s → 混合 0.16s，≈ 5.9 倍）
- aiohttp 并发抓取 + 限速 + 重试（★★★）：本地服务 503 确定性注入，Semaphore(4) + 指数退避，断言成功/失败/attempts（提示：恒失败端点 attempts=3、其余 1；参考实现成功 16/20）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**异步遥测采集服务（async-telemetry-collector）**——进程内模拟遥测服务器（aiohttp web，延迟/失败率可注入、seed 可复现）→ aiohttp 并发采集（Semaphore 限速 + 指数退避重试）→ 汇总统计 → CSV 报表；16 个 pytest 用例覆盖模拟服务器/采集/统计/报表，`ruff` 全绿，`cli.py --demo` 离线自检（对应 roadmap「推荐项目」第一个「异步采集服务」；另一个「并发日志处理器」作为扩展方向）。建议完成练习后再动手，尤其练习 5（限速 + 重试的缩小版）。

- [ ] 完成 exercises/ 全部 5 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`python3 -m pytest` → 16 passed；`ruff check .` 全绿；`python3 cli.py --demo` 自检通过；`python3 cli.py` 默认 20 辆车 ≈ 0.12s 采完）

### 下一阶段

[ph15 AI 与机器学习阶段](../ph15-ai-ml/15-ai-ml.md) — 后续深入 **AI / 机器学习** 方向：NumPy / Pandas / Matplotlib 数据分析（系统能力在 ph09 已建立）、Scikit-learn 建模与评估、PyTorch / Transformers 认知、特征工程与模型评估、向量检索与 RAG、模型产物与部署衔接。本阶段攒下的「IO 密集用异步、CPU 密集用进程」选型直觉，正是 ph15 理解「数据预处理为什么卡、训练为什么吃 GPU、推理服务为什么用异步」的起点——异步 FastAPI（3.8）与采集服务（project）届时会直接变成模型服务的推理入口（ph15 的 3.11 已把模型产物落盘、命令行推理讲清，HTTP 服务化衔接 [ph16 部署与 DevOps 阶段](../ph16-deploy-devops/16-deploy-devops.md)（roadmap 第 16 节））；在此之前可先按推荐学习顺序巩固 ph13 测试与工程质量阶段与本阶段的练习与项目。
