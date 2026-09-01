# C++ 并发编程阶段

> 面向高性能系统、存储引擎方向，本阶段能写安全的多线程 C++ 程序——从线程创建、锁与条件变量，到 atomic、C++20 同步原语与协程，让并发从"碰运气"变成"有纪律"。

## 1. 概述

本阶段定位：**能写安全的多线程 C++ 程序——用 std::thread 表达并发任务，用 mutex/atomic 保护共享状态，用 condition_variable 组织等待通知，用 jthread/stop_token 实现协作取消，并掌握 C++20 同步原语与协程基础**。学完后能避免数据竞争和死锁，能用条件变量实现等待通知，能解释 atomic 与 mutex 的适用场景，能动手完成异步日志、任务调度等并发系统。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 线程创建 | std::thread、join / detach、参数传递 |
| 互斥与锁 | std::mutex、lock_guard、unique_lock、锁粒度 |
| 等待通知 | condition_variable、谓词等待、虚假唤醒 |
| 原子操作 | std::atomic、内存序基础（seq_cst / acquire / release / relaxed） |
| 任务与结果 | future、async、promise |
| 并发模式 | 线程池、生产者消费者 |
| C++20 同步 | jthread、stop_token、semaphore、latch、barrier |
| 协程基础 | co_await、co_return、无栈状态机 |

这个阶段只涉及进程内多线程并发的标准设施（thread / mutex / condition_variable / atomic / future / C++20 同步原语与协程基础），**不涉及文件/网络系统编程、对象生命周期深入和性能优化** — 那些是 ph09、ph12 对象生命周期、值类别与所有权深入阶段、ph18（目录待建）阶段的内容；无锁数据结构与复杂内存序优化也不展开——本阶段默认使用 seq_cst 与基本 acquire/release，把程序写对是首要目标。本阶段承接 ph07 异常安全阶段：锁与并发代码必须异常安全，RAII 锁在栈展开时自动解锁，线程函数内未捕获的异常会直接 terminate。

## 2. 来源与演变

线程与锁的历史早于 C++：1995 年 POSIX threads（pthread）成为事实标准，但 C++98/03 没有标准线程库，跨平台并发只能依赖 pthread 或 Windows API，代码不可移植且处处是裸 lock/unlock 的陷阱。C++11 是决定性转折：**一次性引入完整线程库（std::thread、mutex、condition_variable、atomic、future）与正式的内存模型（memory model）**——标准第一次明确定义"数据竞争是未定义行为"和 happens-before 关系，把"多线程可见性"从实现细节升格为语言规范。

C++20 继续补齐高层抽象：**jthread**（析构自动 join + stop_token 协作取消）、**semaphore / latch / barrier** 同步原语、以及**协程（coroutines）**（co_await / co_return）正式落地。演进主线清晰可见：**把并发安全从"程序员纪律"推向"语言与库的保证"**——RAII 锁让"忘记 unlock"成为不可能，jthread 让"忘记 join"不再 terminate，协程把异步流程写成顺序代码，每一步都在降低并发编程的心智负担。

| 阶段 | 代表 | 贡献 |
|------|------|------|
| 1995 | POSIX threads | pthread 线程与同步原语，成为事实标准 |
| C++98/03 | ISO C++98/03 | 无标准线程库，并发靠平台 API |
| C++11 | ISO C++11 | 线程库 + 内存模型正式化，atomic / future / condition_variable |
| C++14/17 | ISO C++14/17 | shared_timed_mutex / shared_mutex、并行算法起步 |
| C++20 | ISO C++20 | jthread / stop_token、semaphore / latch / barrier、协程 |

本文示例以 **C++20** 为基线（jthread、semaphore、latch、barrier 与协程均为 C++20 引入，是本阶段的核心增量），验证工具链 Apple clang 21（g++ 兼容），编译选项 `-std=c++20 -Wall -Wextra -pthread`。线程库自 C++11 定型以来接口高度稳定——C++14/17/20 只做加法，这个阶段的语法是 C++ 并发中最稳定的部分。

## 3. 语法与参数

### 3.1 std::thread：创建、join、detach

`std::thread` 对象构造即启动新线程，可接受函数、函数对象或 lambda 与任意参数；`join()` 等待线程结束并回收资源，`detach()` 分离线程（运行时接管其生命周期）。thread 不可拷贝、只可移动。

```cpp
#include <iostream>
#include <thread>
void worker(int id) { std::cout << "worker " << id << "\n"; }
int main() {
    std::thread t1(worker, 1);                          // 函数 + 参数
    std::thread t2([] { std::cout << "lambda thread\n"; });
    t1.join();                                          // 等待并回收
    t2.join();
    return 0;
}
```

要点：

- **坑：线程对象析构时若仍 joinable（未 join/detach）会调用 std::terminate**——最常见的崩溃源
- **坑：detach 后访问已销毁对象是 UB**——被分离的线程仍可能引用已离开作用域的栈对象
- 传递引用参数必须用 `std::ref`（否则按值拷贝）；线程函数抛出未捕获异常也会 terminate（见 ph07 异常安全阶段）
- **坑：并发写 std::cout 会交错**——输出本身不是原子的，练习中可用此现象直观感受竞争

### 3.2 std::mutex 与 RAII 锁：lock_guard、unique_lock

`std::mutex` 提供 lock/unlock 互斥；**永远不要裸调 unlock**——异常路径会漏解锁。`std::lock_guard` 是 RAII 锁：构造加锁、析构解锁；`std::unique_lock` 支持延迟加锁（`std::defer_lock`）、中途手动 unlock，是 condition_variable 的固定搭档。

```cpp
#include <iostream>
#include <mutex>
#include <thread>
#include <vector>
int counter = 0;
std::mutex mtx;
void increment(int n) {
    for (int i = 0; i < n; ++i) {
        std::lock_guard<std::mutex> lock(mtx);   // RAII：作用域结束自动解锁
        ++counter;
    }
}
int main() {
    std::vector<std::thread> ts;
    for (int i = 0; i < 4; ++i) ts.emplace_back(increment, 10000);
    for (auto& t : ts) t.join();
    std::cout << "counter=" << counter << "\n";  // 40000
    return 0;
}
```

要点：

- **必会概念：RAII 锁能避免忘记 unlock**——临界区 = 锁对象的作用域，异常安全（栈展开自动解锁）
- **坑：锁的粒度影响性能与正确性**——粒度太大（临界区含无关 IO/计算）把并发串行化；粒度太小（检查-使用被拆开）引入竞态
- `std::scoped_lock`（C++17）可一次锁多把且防死锁，多锁场景优先使用（见 3.7）
- std::mutex 不可拷贝、不可移动；默认构造即可用

### 3.3 condition_variable 与谓词等待

`std::condition_variable` 实现"等待-通知"：`cv.wait(lock, pred)` 在谓词不满足时释放锁并睡眠，被 `notify_one()`/`notify_all()` 唤醒后重新抢锁并**再次检查谓词**。必须配合 `std::unique_lock`，因为 wait 期间需要临时释放锁。

```cpp
#include <chrono>
#include <condition_variable>
#include <iostream>
#include <mutex>
#include <queue>
#include <thread>
std::mutex mtx;
std::condition_variable cv;
std::queue<int> q;
void producer() {
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    { std::lock_guard<std::mutex> lock(mtx); q.push(42); }
    cv.notify_one();                              // 唤醒一个等待者
}
void consumer() {
    std::unique_lock<std::mutex> lock(mtx);
    cv.wait(lock, [] { return !q.empty(); });     // 谓词等待：防虚假唤醒
    int v = q.front(); q.pop();
    std::cout << "got " << v << "\n";
}
int main() {
    std::thread c(consumer), p(producer);
    c.join(); p.join();
    return 0;
}
```

要点：

- **必会概念：condition_variable 必须配合条件谓词**——`cv.wait(lock, pred)` 等价于 `while (!pred()) cv.wait(lock);`，谓词循环同时防**虚假唤醒（spurious wakeup）**与**丢失唤醒**
- 谓词检查与数据访问必须在同一把锁保护下，否则"检查-使用"窗口 = 竞态
- `notify_one()` 唤醒一个线程（高效），`notify_all()` 唤醒全部；notify 通常放在锁外更高效
- 与 cv 配套的锁必须是 `std::unique_lock`（wait 期间要释放锁，lock_guard 做不到）

### 3.4 std::atomic 与内存序基础

`std::atomic<T>` 提供**原子读改写（RMW）**：`load` / `store` / `fetch_add` / `exchange` / `compare_exchange_weak|strong`，默认内存序 `std::memory_order_seq_cst`（顺序一致）。原子变量不可拷贝（用 load/store 传递）。

```cpp
#include <atomic>
#include <iostream>
#include <thread>
std::atomic<int> counter{0};
int main() {
    std::thread t1([] { for (int i = 0; i < 10000; ++i) counter.fetch_add(1); });
    std::thread t2([] { for (int i = 0; i < 10000; ++i) ++counter; });
    t1.join(); t2.join();
    std::cout << "counter=" << counter.load() << "\n";   // 20000，无锁且正确
    return 0;
}
```

要点：

- **必会概念：atomic 与 mutex 的适用场景**——单变量的计数/标志用 atomic（无锁、可伸缩）；"多个变量必须一起变化"的**复合不变式**必须用 mutex（atomic 无法原子更新两个相关变量）
- `memory_order_relaxed` 只保证原子性不保证顺序；`acquire/release` 配对建立 happens-before（见 4.3）；入门默认 seq_cst
- **坑：`volatile` ≠ 原子**——volatile 只防编译器优化，不防 CPU 重排，多线程共享必须用 atomic
- **坑：非原子的 `counter++` 在多线程下是数据竞争 = UB**——结果可能小于期望值且无法解释

### 3.5 future / async / promise

`std::async` 把任务丢到后台并返回 `std::future<T>` 占位结果，`get()` 阻塞取回；`std::promise<T>` 与 `std::future<T>` 组成手动通道：生产者 `set_value`，消费者 `get`。异常会沿 future 传递（`get()` 时重新抛出）。

```cpp
#include <future>
#include <iostream>
#include <thread>
int compute(int x) { return x * x; }
int main() {
    std::future<int> f = std::async(std::launch::async, compute, 7);
    std::cout << "result=" << f.get() << "\n";        // 阻塞直到有结果
    std::promise<int> p;                              // promise/future 手动通道
    std::future<int> g = p.get_future();
    std::thread t([&p] { p.set_value(99); });
    t.join();
    std::cout << "promised=" << g.get() << "\n";
    return 0;
}
```

要点：

- `std::async` 默认策略可能是**惰性执行（deferred）**——需要确定性并发时显式传 `std::launch::async`
- **坑：`future::get()` 只能调用一次**，future 不可拷贝（可移动）；多消费者用 `std::shared_future`
- async 函数抛异常不会崩线程，异常在 `get()` 时重新抛出——"线程内错误"的标准出路
- promise 在 set_value 前析构，future 侧 get 会抛 `std::future_error`

### 3.6 线程池与生产者消费者模式

两个最常用的并发骨架：**生产者消费者**把"产生任务"与"执行任务"解耦（线程安全队列 + 条件变量）；**线程池**预创建 N 个 worker 线程共享一个任务队列，避免频繁创建/销毁线程的系统调用开销。下面是最小骨架（线程池完整版见示例 4）：

```cpp
#include <condition_variable>
#include <functional>
#include <iostream>
#include <mutex>
#include <queue>
#include <thread>
std::mutex mtx;
std::condition_variable cv;
std::queue<std::function<void()>> tasks;
bool done = false;
void worker() {
    for (;;) {
        std::function<void()> task;
        {
            std::unique_lock<std::mutex> lock(mtx);
            cv.wait(lock, [] { return done || !tasks.empty(); });
            if (done && tasks.empty()) break;
            task = std::move(tasks.front());
            tasks.pop();
        }
        task();                                  // 锁外执行，避免长任务阻塞队列
    }
}
int main() {
    std::thread w(worker);
    {
        std::lock_guard<std::mutex> lock(mtx);
        for (int i = 0; i < 5; ++i) tasks.push([i] { std::cout << "job " << i << "\n"; });
    }
    cv.notify_all();
    { std::lock_guard<std::mutex> lock(mtx); done = true; }
    cv.notify_all();
    w.join();
    return 0;
}
```

要点：

- 任务类型统一为 `std::function<void()>`，可包装任意 lambda/函数
- **坑：有界队列满时生产者也要等待**——需要第二个 condition_variable（not_full_），见示例 3
- **坑：线程池析构顺序**——先置停止标志 → notify_all 唤醒 → join 全部 worker，顺序错了就死锁
- 任务执行放在锁外：锁内执行长任务会让整个队列停摆（锁粒度问题）

### 3.7 死锁与竞态排查

死锁（deadlock）是"互相等待对方持有的锁"；竞态条件（race condition）是"检查-使用之间有窗口"。排查并发 bug 的标准工具是 **ThreadSanitizer（TSan，`-fsanitize=thread`）**，死锁现场用 gdb / pstack 看线程栈：

> ⚠️ 下面这个示例**必然死锁**——它是故意的，用于观察死锁现场。务必带超时运行，不要无超时裸跑。

```cpp
// 故意出错示例：必然死锁。运行前提：必须带超时运行（如 timeout 2 ./a.out；
// macOS 无 timeout 可用 perl -e 'alarm 2; exec @ARGV' ./a.out），观察挂起后由超时终止，勿无超时裸跑
#include <chrono>
#include <iostream>
#include <mutex>
#include <thread>
std::mutex a, b;
void t1() {                       // 锁顺序：a → b
    std::scoped_lock l1(a);
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    std::scoped_lock l2(b);
}
void t2() {                       // 锁顺序：b → a ← 与 t1 相反 → 死锁
    std::scoped_lock l1(b);
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    std::scoped_lock l2(a);
}
int main() {
    std::thread x(t1), y(t2);
    x.join(); y.join();           // 永远等不到：用 timeout 2 ./a.out 观察挂起
    return 0;
}
```

要点：

- **避免死锁的铁律：所有线程按同一全局顺序获取多把锁**；或用 `std::scoped_lock` / `std::lock` 一次原子获取多把锁
- **坑：死锁四条件（互斥、持有并等待、不可剥夺、循环等待）**——打破任意一个即可预防
- 常见并发问题对照：

| 问题 | 成因 | 避免 / 排查 |
|------|------|------------|
| 死锁 | 锁顺序不一致、忘记 unlock | 统一锁顺序、RAII 锁、std::scoped_lock |
| 数据竞争 | 无同步访问共享变量 | mutex/atomic 保护；TSan 检测 |
| 竞态条件 | check-then-act 有窗口 | 检查与使用放进同一临界区 |
| 虚假唤醒 | 谓词未满足被唤醒 | while 循环检查谓词 |
| 丢失唤醒 | 先 wait 后 notify | 谓词循环 + 同一把锁保护 |

### 3.8 C++20 jthread 与 stop_token 协作取消

`std::jthread` 在 std::thread 基础上补两块：**析构时自动 join**（可 join 则 join，杜绝 terminate）与**内建协作取消**——线程函数可接收 `std::stop_token`，外部通过 `request_stop()` 请求停止。

```cpp
#include <chrono>
#include <iostream>
#include <thread>
int main() {
    std::jthread worker([](std::stop_token st) {
        while (!st.stop_requested()) {
            std::cout << "working...\n";
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        std::cout << "stopped\n";
    });
    std::this_thread::sleep_for(std::chrono::milliseconds(250));
    worker.request_stop();        // 协作式取消请求
    return 0;                     // jthread 析构自动 join
}
```

要点：

- **必会概念：jthread 析构时自动 join**——比 std::thread "忘 join 即 terminate" 安全得多
- **取消是协作式的**：`request_stop()` 只是请求，线程必须主动检查 `stop_requested()`（或在支持 stop 的 cv 上等待），不能强行终止线程（强杀会破坏数据完整性）
- `std::stop_source` / `std::stop_token` 可脱离 jthread 独立使用，实现"取消信号广播"（一个源多个 token）
- `std::stop_callback` 可在停止请求到达时回调注册的清理函数

### 3.9 C++20 semaphore / latch / barrier

三个同步原语补齐了 mutex/cv 之外的场景：**semaphore** 管理资源计数（限流），**latch** 是"一次性闸门"（N 个 count_down 后放行），**barrier** 是"循环闸门"（每轮 N 个线程到齐后一起放行，可复用）：

```cpp
#include <iostream>
#include <latch>
#include <thread>
#include <vector>
int main() {
    std::latch done(3);                   // 等待 3 次 count_down
    std::vector<std::thread> ts;
    for (int i = 0; i < 3; ++i)
        ts.emplace_back([&done, i] {
            std::cout << "stage " << i << " done\n";
            done.count_down();            // 到达闸门
        });
    done.wait();                          // 3 个线程全部到达才继续
    for (auto& t : ts) t.join();
    std::cout << "all stages done\n";
    return 0;
}
```

要点：

| 原语 | 用途 | 关键 API | 可重用 |
|------|------|---------|--------|
| `std::counting_semaphore<N>` | 资源限流（连接池、有界缓冲） | acquire() / release() | 是 |
| std::binary_semaphore | 0/1 信号量，类似"事件" | acquire() / release() | 是 |
| std::latch | 一次性汇合闸门 | count_down() / wait() | 否 |
| std::barrier | 每轮到齐后放行（阶段同步） | arrive_and_wait() | 是 |

- **坑：semaphore 的 acquire 不可中断**（没有谓词循环），与 cv 的取舍看语义：计数限流用 semaphore，条件等待用 cv
- barrier 自带阶段回调（completion function），可在每轮放行时执行汇总

### 3.10 协程基础：co_await / co_return

C++20 协程（coroutine）是**无栈协程**：函数体被编译器转换成**可恢复状态机**，挂起时不占用系统栈。写协程需要自定义 `promise_type`（标准库只给机制、没给通用 Task 类型），最小框架如下：

```cpp
#include <coroutine>
#include <iostream>
struct Task {                                // 最小协程框架（无结果传递）
    struct promise_type {
        Task get_return_object() { return {}; }
        std::suspend_never initial_suspend() { return {}; }   // 立即开始
        std::suspend_never final_suspend() noexcept { return {}; }
        void return_void() {}
        void unhandled_exception() { std::terminate(); }
    };
};
Task hello() {
    std::cout << "coroutine start\n";
    co_return;                               // 结束协程并返回 Task
}
int main() {
    auto t = hello();                        // 调用不阻塞
    std::cout << "back in main\n";
    return 0;
}
```

要点（编译：GCC 10 需显式开启 `-fcoroutines`，GCC 11 起 `-std=c++20` 默认启用协程；基线 Apple clang 21 无需该 flag）：

- **必会概念：C++20 协程是无栈协程，编译器将函数体转换为可恢复状态机**（见 4.5）
- `co_await` 挂起/恢复（等一个异步结果）；`co_return` 结束并返回值；`co_yield` 逐个产出值
- **坑：协程不是线程**——挂起不阻塞线程、不占系统栈；恢复可能发生在任意线程
- 三个挂起点（initial_suspend / 每次 co_await / final_suspend）由 promise_type 控制；帧内局部变量生命周期随协程而非作用域

## 4. 底层原理

### 4.1 数据竞争为何是 UB

C++11 起标准定义了正式**内存模型（memory model）**：两个线程访问同一内存位置、至少一个是写、且两者之间没有 happens-before 关系，就构成**数据竞争（data race）**，整个程序行为是**未定义行为**。关键在于编译器根本不知道其他线程的存在：它可以自由地把 `x = x + 1` 缓存到寄存器、重排指令、向量化循环——没有同步约束时，另一个线程可能永远看不到更新。**撕裂读写（torn read/write）**是另一个具体表现：大于机器字长的变量被拆成多次存取，另一个线程在中间写入，读方就会拿到"半个新值 + 半个旧值"的混合结果。

| 访问模式（同一内存位置） | 是否数据竞争 | 后果 |
|--------------------------|-------------|------|
| 两个线程同时读 | 否 | 安全 |
| 一读一写（无同步） | 是 | UB：旧值 / 撕裂值 / 编译器任意优化 |
| 两个线程同时写（无同步） | 是 | UB：丢失更新 / 撕裂 / 崩溃 |

说 UB 而非"结果不对"的含义是：标准不再对程序做任何承诺——可能崩溃、死循环，甚至看似无关的代码被"优化"掉。修复只有同步（mutex/atomic）一条路。TSan 能在运行期精确定位数据竞争的发生位置。

### 4.2 互斥锁的实现

一把互斥锁在底层做两件事：**互斥语义**（原子比较交换 CAS 把锁变量从"空闲"置为"持有"，只有一个线程成功）与**等待策略**（失败者怎么办）：

| 策略 | 等待方式 | 成本 | 适用 |
|------|---------|------|------|
| 自旋（spin） | 忙等重试 CAS | 占用 CPU、无切换 | 临界区极短（几十 ns） |
| 阻塞（block） | 内核睡眠、唤醒 | 上下文切换（微秒级） | 临界区较长 / 竞争激烈 |
| 混合（futex） | 先自旋一小段再睡眠 | 两者折中 | 通用默认 |

Linux 上 glibc 的 pthread mutex 与 std::mutex 底层基于 **futex（fast userspace mutex）**：无竞争时在用户态 CAS 直接成功、零系统调用；竞争激烈时才通过 futex 系统调用陷入内核睡眠，解锁时唤醒等待队列。此外锁还隐含**内存屏障**职责：加锁是 acquire、解锁是 release，保证临界区内的写对其他线程加锁后可见（见 4.3）——这就是"mutex 保护的不只是锁变量本身"的原因。

### 4.3 atomic 与内存序

atomic 解决两个独立问题：**原子性**（单变量读改写不撕裂）与**可见性/顺序**（内存序 memory order）：

| 内存序 | 保证 | 开销 | 典型场景 |
|--------|------|------|---------|
| seq_cst（默认） | 全局单一顺序，所有线程看到一致的操作顺序 | 最高（可能需全栅栏） | 入门默认、正确性优先 |
| acquire（读）/ release（写） | 配对建立 happens-before：release 前的写对 acquire 后的读可见 | 中 | mutex 语义、无锁队列、发布-订阅 |
| relaxed | 仅原子性，无顺序保证 | 最低 | 统计计数、独立标志位 |

acquire/release 是理解并发可见性的核心：**"写数据 → release 发布 → acquire 获取 → 读数据"**四步构成 happens-before 链，保证前面线程写入的数据对后面线程可见（mutex 的解锁/加锁正是 release/acquire 的封装）。**关键结论：单变量用 atomic 就够；复合不变式（多个相关变量必须一起变）必须用 mutex**——atomic 无法原子地更新两个变量，强行拼凑会引入窗口。

### 4.4 condition_variable 与等待队列

`cv.wait(lock, pred)` 在底层拆成三步：

| 步骤 | 锁的状态 | 说明 |
|------|---------|------|
| 检查谓词 | 持有 | 条件已满足则直接返回，不睡眠 |
| 入队睡眠 | 释放 | 当前线程加入 cv 的等待队列（futex 支撑）并睡眠，让出 CPU |
| 唤醒重查 | 重新获取 | 被 notify 后抢锁，**再次循环检查谓词**，满足才返回 |

三步设计环环相扣：睡眠前必须释放锁，否则其他线程进不了临界区修改条件（所以必须用 unique_lock）；唤醒后必须重新检查谓词，因为**唤醒本身不携带"条件是否满足"的信息**——可能被虚假唤醒（内核/调度器原因）、可能条件被别的线程抢先消费（丢失唤醒）。谓词循环 `while (!pred()) cv.wait(lock);` 把这三个坑一次性堵住，这就是"condition_variable 必须配合条件谓词"的底层原因。

### 4.5 协程的无栈实现

C++20 协程的无栈（stackless）实现，本质是**编译期状态机转换**：编译器把函数体按挂起点（每个 co_await / co_return / co_yield）切成若干片段，局部变量与当前执行位置存入**协程帧（coroutine frame）**——堆上分配的一块固定大小内存，生命周期由 promise 对象管理。调用协程 = 分配帧 → 执行到第一个挂起点（或结束）→ 把帧交还调用者；恢复 = 从挂起点继续执行、恢复帧内局部变量。

| 维度 | 无栈（C++20 协程） | 有栈（Go goroutine / ucontext） |
|------|--------------------|--------------------------------|
| 栈 | 复用调用者栈，局部变量在帧内 | 每个协程独立栈 |
| 切换开销 | 一次普通函数调用级别 | 保存/恢复寄存器与栈指针 |
| 内存占用 | 帧固定、极小 | 栈按需增长（KB 级起） |
| 嵌套挂起 | 受限：整条调用链需每层都是协程 | 任意深度 |
| 实现 | 编译器生成状态机 | 运行时调度器 |

结论：**协程不是线程、也不是线程的替代**——它不涉及调度器，挂起不阻塞线程；它是"用同步的写法表达异步流程"的工具，与线程、atomic、同步原语互补（文件/网络系统编程在 ph09 展开，异步 IO 网络模型属 ph18 性能优化与 Profiling 阶段、ph22 存储引擎与数据库内核专项阶段）。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 共享计数器、统计指标 | std::atomic（fetch_add） |
| 保护复合数据结构（队列、哈希表、缓存） | mutex + lock_guard / unique_lock |
| 等待-通知（任务完成、条件满足） | condition_variable + 谓词等待 |
| 多线程汇合与阶段同步 | std::latch / std::barrier |
| 资源限流（连接池、有界队列） | std::counting_semaphore |
| 异步任务与结果传递 | std::async / promise / future |
| 可取消的后台任务（日志刷盘、监控） | jthread + stop_token |
| 大量短任务并发执行 / 异步流程书写 | 线程池 / 协程 co_await、co_return |

**不适合**此阶段的事项：

- **文件/网络系统编程**（ph09 文件、网络与系统编程阶段）：socket、进程间通信；epoll 等异步 IO 模型属 ph18 性能优化与 Profiling 阶段、ph22 存储引擎与数据库内核专项阶段——本阶段只谈进程内多线程
- **复杂内存序优化与无锁数据结构**（ph18 性能优化与 Profiling 阶段）：本阶段默认 seq_cst 与基本 acquire/release，先把正确性做对再谈性能
- **跨进程并发**：socket IPC 属于 ph09 文件、网络与系统编程阶段；共享内存、跨进程信号量等不在本路线展开
- 分布式一致性与并发算法理论（Raft / Paxos 等）：超出本阶段范围

## 6. 代码示例

> 说明：每个示例的完整可运行文件在 [`examples/`](./examples/) 目录（ex01~ex06，与下面示例 1~6 一一对应），验证环境 Apple clang 21（g++ 兼容），编译命令统一 `c++ -std=c++20 -Wall -Wextra -pthread`（示例 6 是故意出错示例，需 `-fsanitize=thread`，命令见 examples/README.md）。全部示例已在本环境编译零警告并运行验证（已验证）。

### 示例 1：多线程计数器（mutex 保护 + 对比 atomic）

```cpp
// 编译：c++ -std=c++20 -Wall -Wextra -pthread ex01-counter.cpp -o ex01
#include <atomic>
#include <iostream>
#include <mutex>
#include <thread>
#include <vector>
int main() {
    constexpr int kThreads = 8;
    constexpr int kPerThread = 100000;
    {   // 方式一：mutex 保护 —— 复合临界区，串行但正确
        int counter = 0;
        std::mutex mtx;
        std::vector<std::thread> ts;
        for (int i = 0; i < kThreads; ++i)
            ts.emplace_back([&] {
                for (int j = 0; j < kPerThread; ++j) {
                    std::lock_guard<std::mutex> lock(mtx);
                    ++counter;
                }
            });
        for (auto& t : ts) t.join();
        std::cout << "mutex  counter = " << counter << "\n";
    }
    {   // 方式二：atomic —— 单变量 RMW，无锁
        std::atomic<int> counter{0};
        std::vector<std::thread> ts;
        for (int i = 0; i < kThreads; ++i)
            ts.emplace_back([&] {
                for (int j = 0; j < kPerThread; ++j)
                    counter.fetch_add(1);
            });
        for (auto& t : ts) t.join();
        std::cout << "atomic counter = " << counter.load() << "\n";
    }
    return 0;   // 两种方式都应输出 800000
}
```

完整文件：`examples/ex01-counter.cpp`

### 示例 2：线程安全队列（mutex + condition_variable）

```cpp
// 编译：c++ -std=c++20 -Wall -Wextra -pthread ex02-tsqueue.cpp -o ex02
#include <condition_variable>
#include <deque>
#include <iostream>
#include <mutex>
#include <optional>
template <typename T>
class ThreadSafeQueue {
public:
    void push(T v) {
        { std::lock_guard<std::mutex> lock(mtx_); data_.push_back(std::move(v)); }
        cv_.notify_one();
    }
    std::optional<T> pop() {              // 非阻塞：空队列返回 nullopt
        std::lock_guard<std::mutex> lock(mtx_);
        if (data_.empty()) return std::nullopt;
        T v = std::move(data_.front());
        data_.pop_front();
        return v;
    }
    T wait_pop() {                        // 阻塞：谓词等待直到有元素
        std::unique_lock<std::mutex> lock(mtx_);
        cv_.wait(lock, [this] { return !data_.empty(); });
        T v = std::move(data_.front());
        data_.pop_front();
        return v;
    }
    bool empty() const {
        std::lock_guard<std::mutex> lock(mtx_);
        return data_.empty();
    }
private:
    mutable std::mutex mtx_;              // empty() 是 const 方法，锁要 mutable
    std::condition_variable cv_;
    std::deque<T> data_;
};
int main() {
    ThreadSafeQueue<int> q;
    std::thread producer([&] { for (int i = 0; i < 10; ++i) q.push(i * i); });
    std::thread consumer([&] { for (int i = 0; i < 10; ++i) std::cout << "got " << q.wait_pop() << "\n"; });
    producer.join();
    consumer.join();
    std::cout << "queue empty: " << std::boolalpha << q.empty() << "\n";
    return 0;
}
```

完整文件：`examples/ex02-tsqueue.cpp`

### 示例 3：生产者消费者模型（有界队列，双条件变量）

```cpp
// 编译：c++ -std=c++20 -Wall -Wextra -pthread ex03-bounded-pc.cpp -o ex03
#include <condition_variable>
#include <cstddef>
#include <iostream>
#include <mutex>
#include <queue>
#include <thread>
class BoundedQueue {
public:
    explicit BoundedQueue(std::size_t cap) : capacity_(cap) {}
    void produce(int v) {
        std::unique_lock<std::mutex> lock(mtx_);
        not_full_.wait(lock, [this] { return q_.size() < capacity_; });   // 满则等待
        q_.push(v);
        lock.unlock();                    // 先解锁再 IO 与 notify，缩小临界区
        std::cout << "produced " << v << "\n";
        not_empty_.notify_one();
    }
    int consume() {
        std::unique_lock<std::mutex> lock(mtx_);
        not_empty_.wait(lock, [this] { return !q_.empty(); });            // 空则等待
        int v = q_.front();
        q_.pop();
        lock.unlock();
        std::cout << "consumed " << v << "\n";
        not_full_.notify_one();
        return v;
    }
private:
    std::mutex mtx_;
    std::condition_variable not_empty_, not_full_;
    std::queue<int> q_;
    std::size_t capacity_;
};
int main() {
    BoundedQueue q(4);                    // 有界缓冲：容量 4
    std::thread producer([&] { for (int i = 0; i < 20; ++i) q.produce(i); });
    std::thread consumer([&] { for (int i = 0; i < 20; ++i) q.consume(); });
    producer.join();
    consumer.join();
    return 0;
}
```

完整文件：`examples/ex03-bounded-pc.cpp`

### 示例 4：简单线程池（任务队列 + worker 线程）

```cpp
// 编译：c++ -std=c++20 -Wall -Wextra -pthread ex04-threadpool.cpp -o ex04
#include <condition_variable>
#include <cstddef>
#include <functional>
#include <iostream>
#include <mutex>
#include <queue>
#include <sstream>
#include <thread>
#include <vector>
class ThreadPool {
public:
    explicit ThreadPool(std::size_t n) {
        for (std::size_t i = 0; i < n; ++i)
            workers_.emplace_back([this] { worker_loop(); });
    }
    ~ThreadPool() {
        { std::lock_guard<std::mutex> lock(mtx_); stop_ = true; }
        cv_.notify_all();                 // 先置标志 → 唤醒所有 worker → join（顺序不能错）
        for (auto& w : workers_) w.join();
    }
    void submit(std::function<void()> task) {
        { std::lock_guard<std::mutex> lock(mtx_); tasks_.push(std::move(task)); }
        cv_.notify_one();
    }
private:
    void worker_loop() {
        for (;;) {
            std::function<void()> task;
            {
                std::unique_lock<std::mutex> lock(mtx_);
                cv_.wait(lock, [this] { return stop_ || !tasks_.empty(); });
                if (stop_ && tasks_.empty()) return;   // 停止且无任务 → 退出
                task = std::move(tasks_.front());
                tasks_.pop();
            }
            task();                       // 锁外执行任务
        }
    }
    std::vector<std::thread> workers_;
    std::queue<std::function<void()>> tasks_;
    std::mutex mtx_;
    std::condition_variable cv_;
    bool stop_ = false;
};
int main() {
    ThreadPool pool(4);                   // 4 个 worker 线程
    for (int i = 0; i < 12; ++i)
        pool.submit([i] {
            std::ostringstream line;      // 先拼好整行再一次输出，避免多线程输出交错
            line << "task " << i << " done by " << std::this_thread::get_id() << "\n";
            std::cout << line.str();
        });
    return 0;                             // 析构：停止 → 唤醒 → join，任务全部执行完
}
```

完整文件：`examples/ex04-threadpool.cpp`

### 示例 5：jthread + stop_token 可取消任务（C++20）

```cpp
// 编译：c++ -std=c++20 -Wall -Wextra -pthread ex05-jthread-stop.cpp -o ex05
#include <chrono>
#include <iostream>
#include <thread>
void background_work(std::stop_token st) {   // 第一个参数接收 stop_token
    int i = 0;
    while (!st.stop_requested()) {
        std::cout << "tick " << i++ << "\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
    std::cout << "cleanup: work cancelled\n";  // 优雅退出，可做收尾
}
int main() {
    std::jthread worker(background_work);
    std::this_thread::sleep_for(std::chrono::milliseconds(650));
    worker.request_stop();                 // 协作式取消请求
    return 0;                              // 析构自动 join，等待清理完成
}
```

完整文件：`examples/ex05-jthread-stop.cpp`

### 示例 6：数据竞争演示（故意出错，配合 TSan 观察）

```cpp
// 故意出错示例：本程序含数据竞争（UB），结果小于 200000 属预期。
// 运行前提：观察数据竞争请用 TSan 编译运行——
//   c++ -std=c++20 -Wall -Wextra -pthread -fsanitize=thread -g ex06-data-race.cpp -o ex06_tsan && ./ex06_tsan
// TSan 会精确定位 counter++ 的竞争；普通编译裸跑只是结果不确定，看不到诊断信息。
#include <iostream>
#include <thread>
#include <vector>
int main() {
    int counter = 0;                       // 故意不加保护：两个线程的 ++ 互相覆盖
    constexpr int kThreads = 2;
    constexpr int kPerThread = 100000;
    std::vector<std::thread> ts;
    for (int i = 0; i < kThreads; ++i)
        ts.emplace_back([&] {
            for (int j = 0; j < kPerThread; ++j) ++counter;   // 非原子 RMW：读-改-写有窗口
        });
    for (auto& t : ts) t.join();
    std::cout << "counter = " << counter << " (expected " << kThreads * kPerThread
              << "; 小于期望值即数据竞争导致的丢失更新)\n";
    return 0;
}
```

完整文件：`examples/ex06-data-race.cpp`

## 7. 总结

### 关键要点

1. **数据竞争是未定义行为**：两个线程无同步访问同一变量（至少一个写）就是 UB，不只是"结果不确定"——修复只有 mutex/atomic 一条路
2. **锁的粒度影响性能与正确性**：临界区要小（不含无关 IO），但"检查-使用"必须整体在锁内
3. **RAII 锁（lock_guard / unique_lock）杜绝忘记 unlock**：裸 mutex 手动解锁在异常路径必漏，栈展开自动解锁是并发代码的异常安全基石
4. **condition_variable 必须配合条件谓词**：`cv.wait(lock, pred)` 的 while 循环同时防虚假唤醒与丢失唤醒
5. **atomic 与 mutex 各有适用场景**：单变量计数/标志用 atomic；复合不变式必须用 mutex
6. **jthread 析构自动 join**，配合 stop_token 实现**协作式取消**——取消是请求，线程必须主动检查
7. **C++20 同步原语三件套**：semaphore 限流、latch 一次性汇合、barrier 循环汇合
8. **C++20 协程是无栈协程**：编译器把函数体转换为可恢复状态机（协程帧），挂起不占系统栈；协程不是线程
9. **排查工具先行**：ThreadSanitizer（`-fsanitize=thread`）检测数据竞争，gdb / pstack 定位死锁

### 跨语言对比：并发模型

| 维度 | C++ std::thread | C pthread | Go goroutine | Java 线程 | Rust std::thread |
|------|-----------------|-----------|--------------|-----------|------------------|
| 线程模型 | 1:1 系统线程 | 1:1 系统线程 | 用户态协程（M:N 调度） | 系统线程 + 池化 | 1:1 系统线程 |
| 创建成本 | 系统调用，较高 | 系统调用，较高 | 栈小（KB 级），极低 | 系统调用，较高 | 系统调用，较高 |
| 同步原语 | mutex / cv / atomic / semaphore / latch / barrier | mutex / cond / semaphore | channel + select（首选） | synchronized / Lock / atomic | mutex / cv / atomic |
| 数据竞争防护 | 无（UB，靠纪律 + TSan） | 无（UB，靠纪律） | 无（靠 channel 惯例） | 无（靠纪律 / 工具） | **编译期所有权 + Send/Sync** |
| 生命周期管理 | join / detach；jthread 自动 join | pthread_join / detach | 运行时自动回收 | join / detach | join / detach（作用域守卫） |
| 取消 / 停止 | stop_token（协作式） | pthread_cancel（强制） | context 取消 | interrupt | 无内置（Arc\<AtomicBool\>） |

一句话：C++ 与 C、Java 一样是 1:1 系统线程模型、靠纪律防数据竞争，但 RAII 锁、jthread 与 stop_token 让"忘记解锁/join"从惯例层消失；Go 用用户态协程 + channel 把并发写成消息流；Rust 用编译期所有权把数据竞争变成**编译错误**——**本阶段的收获是学会在 C++ 里用纪律 + 工具写出安全的多线程程序**。

### 阶段验收清单

- [ ] 能写出**避免数据竞争和死锁**的多线程程序：共享数据有 mutex/atomic 保护、多把锁按一致顺序获取、锁全部走 RAII
- [ ] 能用 condition_variable + 谓词实现**等待通知**（线程安全队列、生产者消费者模型）
- [ ] 能解释 **atomic 与 mutex 的适用场景**，并说清数据竞争为何是未定义行为
- [ ] 能用 jthread + stop_token 实现**协作式取消**，理解"取消是请求不是强杀"
- [ ] 能完成线程池并说清其生命周期管理（停止 → 唤醒 → join 的顺序）
- [ ] 能说出 C++20 同步原语（semaphore / latch / barrier）与协程的定位

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：多线程计数器、线程安全队列、生产者消费者、简单线程池、jthread + stop_token 可取消任务，共 5 题，与 roadmap ph08「练习」小节一一对应。完成 5 题后继续。进阶（可选）：用 std::latch 实现"N 个阶段任务全部完成才继续"，用 counting_semaphore 模拟连接池限流。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**异步日志系统**——业务线程产生日志 → 有界内存缓冲（生产者消费者）→ 后台线程批量写出，支持级别过滤、jthread + stop_token 优雅关闭与 atomic 统计，覆盖本阶段几乎全部知识点，也是存储引擎可观测性的地基。roadmap 的第二个推荐项目「多线程任务调度器」（任务队列 + 线程池 + 优先级 + future 结果回调 + stop_token 取消）可作为学有余力的扩展，未在 project/ 落地。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[文件、网络与系统编程阶段](../ph09-files-network/09-files-network.md) ——std::filesystem、socket 编程、进程间通信与协议设计（异步 IO 见 ph18/ph22）。
