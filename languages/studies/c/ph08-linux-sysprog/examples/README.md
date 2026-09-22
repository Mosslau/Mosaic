# examples —— Linux 系统编程阶段完整示例

验证环境：Apple clang 21.0.0（`cc`），macOS（Darwin arm64），编译选项 `-Wall -Wextra -std=c11`（线程示例加 `-pthread`）。

| 文件 | 说明 | 编译 | 运行 | 验证状态 |
|------|------|------|------|----------|
| `ex01-file-copy.c` | 文件复制：短读短写循环 + 完整错误处理与 fd 回收 | `cc -Wall -Wextra -std=c11 ex01-file-copy.c -o ex01` | `./ex01 src.txt dst.txt` | 已验证 |
| `ex02-fork-wait.c` | 多进程协作：fork 3 个子进程，父进程 wait 依次回收（防僵尸） | `cc -Wall -Wextra -std=c11 ex02-fork-wait.c -o ex02` | `./ex02` | 已验证 |
| `ex03-task-queue.c` | 生产者-消费者任务队列：mutex + condvar，环形缓冲，终止信号优雅退出 | `cc -Wall -Wextra -std=c11 -pthread ex03-task-queue.c -o ex03` | `./ex03` | 已验证 |
| `ex04-echo-server.c` | TCP echo server（阻塞版）：socket/bind/listen/accept 循环，send 处理短写 | `cc -Wall -Wextra -std=c11 ex04-echo-server.c -o ex04` | `./ex04` 后另开终端 `nc 127.0.0.1 8888` | 已验证 |
| `ex05-epoll-server.c` | epoll 版事件循环：单线程同时服务多个连接（**Linux 专有**） | `cc -Wall -Wextra ex05-epoll-server.c -o ex05` | `./ex05` 后 `nc 127.0.0.1 9999` | **未在本环境验证（需 Linux 2.6+，macOS 无 epoll）** |

## 说明

- 五个示例一一对应主文档第 6 章的示例 1~5；文档内嵌片段摘自这些文件（为便于排版节选关键部分，完整文件以 examples/ 为准）。
- 线程相关示例（ex03）必须加 `-pthread`；其余示例不需要。
- ex04 是阻塞模型，一次只服务一个连接；多客户端并发见 ex05（Linux）或 exercises 的 sol-03（fork 每连接，跨平台）。
- 运行产物（`ex01`~`ex05`、测试文件）验证后清理，不入仓库。
