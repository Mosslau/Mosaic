# examples —— 并发编程阶段完整示例

验证环境：Apple clang 21（g++ 兼容），`-Wall -Wextra -std=c++20 -pthread`。本目录示例与主文档第 6 章示例 1~6 一一对应。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| `ex01-counter.cpp` | 多线程计数器：mutex 保护与 atomic 无锁对比 | `c++ -std=c++20 -Wall -Wextra -pthread ex01-counter.cpp -o ex01` | `./ex01` |
| `ex02-tsqueue.cpp` | 线程安全队列：mutex + condition_variable（pop 非阻塞 / wait_pop 阻塞） | `c++ -std=c++20 -Wall -Wextra -pthread ex02-tsqueue.cpp -o ex02` | `./ex02` |
| `ex03-bounded-pc.cpp` | 生产者消费者：有界队列 + 双条件变量（not_full / not_empty） | `c++ -std=c++20 -Wall -Wextra -pthread ex03-bounded-pc.cpp -o ex03` | `./ex03` |
| `ex04-threadpool.cpp` | 简单线程池：固定 worker + 任务队列，析构自动 drain | `c++ -std=c++20 -Wall -Wextra -pthread ex04-threadpool.cpp -o ex04` | `./ex04` |
| `ex05-jthread-stop.cpp` | jthread + stop_token 协作式取消（C++20） | `c++ -std=c++20 -Wall -Wextra -pthread ex05-jthread-stop.cpp -o ex05` | `./ex05` |
| `ex06-data-race.cpp` | **故意出错**：数据竞争演示，配合 TSan 观察诊断 | `c++ -std=c++20 -Wall -Wextra -pthread -fsanitize=thread -g ex06-data-race.cpp -o ex06_tsan` | `./ex06_tsan` |

## 说明

- ex01 两种方式都应输出 800000；mutex 版把临界区缩到最小（仅 `++counter`）
- ex02 的 `empty()` 是 const 方法，互斥锁声明为 `mutable`；notify 放在锁外
- ex03 队列容量恒不超过 4：队列满时生产者在 `not_full_` 上等待，空时消费者在 `not_empty_` 上等待
- ex04 析构顺序是「置 stop_ → notify_all → join」；任务在锁外执行；输出先拼整行再一次写出，避免交错
- ex05 的取消是协作式的：`request_stop()` 只是请求，线程主动检查 `stop_requested()` 后自行收尾退出
- ex06 是「故意出错」示例：块内首行注释写明运行前提；普通编译运行结果小于 200000 属预期（丢失更新），TSan 编译运行会精确定位 `++counter` 的数据竞争

前五个示例均已在 Apple clang 21（g++ 兼容）下以 `-std=c++20 -Wall -Wextra -pthread` 编译零警告并运行验证；ex06 已以 `-fsanitize=thread` 编译运行、TSan 正确报告数据竞争（已验证）。
