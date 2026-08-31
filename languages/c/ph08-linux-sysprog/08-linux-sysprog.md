# C 语言 Linux 系统编程阶段

> 面向系统底层、存储引擎方向，本阶段从标准库走进内核的门口：能写系统级程序，理解进程、线程、文件描述符与 socket。

## 1. 概述

Linux 系统编程阶段是 C 学习路线中"从写应用走向写系统"的节点。目标：**能用 open/read/write 操作文件描述符，用 fork/exec/wait 管理进程，用 pthread 编写多线程程序并用 mutex/condition variable 解决同步，用 socket 写出可用的 TCP/UDP 网络程序**——一句话，能写系统级程序，理解进程、线程、文件描述符和 socket。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 文件描述符 | open、read、write、close、O_* 标志、fd 生命周期 |
| 进程 | fork、exec、wait、僵尸进程与孤儿、进程资源隔离 |
| 进程间通信 | pipe、signal、SIGCHLD、异步信号安全 |
| 线程 | pthread_create、pthread_join、pthread_detach、共享与独享 |
| 同步 | mutex、condition variable、数据竞争与死锁 |
| 网络编程 | socket、TCP 四步（socket/bind/listen/accept + connect）、UDP |
| 事件模型 | select、poll、epoll 基础与就绪通知模型 |

本阶段承接 ph07 的工程化能力：Makefile/GDB 直接用于系统级程序，GDB 的 `-p` 附加进程、线程切换是调试多进程/多线程程序的利器。

**范围边界**：这个阶段只涉及 POSIX/Linux 系统接口本身——文件描述符、进程、线程、同步原语、socket 与事件模型，**不涉及 C 标准与可移植性细节、未定义行为深入和 mmap 与 Page Cache 的存储语义** — 那些是 ph09 C 标准、编译器与可移植性阶段、ph10 未定义行为 UB 与常见坑阶段和 ph13 mmap、Page Cache 与可靠文件 IO 阶段（roadmap 第 13 节，目录待建）的内容；TCP 拥塞控制、TLS、HTTP 框架等网络协议栈深入属于后续阶段。

## 2. 来源与演变

Unix 从诞生起就把"访问资源"统一成四个系统调用——open/read/write/close，文件、设备、管道、socket 在程序员眼里都是"可读写的字节流"。**文件描述符（file descriptor，fd）**正是"一切皆文件"哲学的载体：一个整数句柄，背后指向内核维护的资源表项。1971 年 Unix V1 就有了 fork（复制当前进程），1988 年 **POSIX**（Portable Operating System Interface）把 open/fork 等进程与文件接口标准化（线程接口 pthread 到 1995 年 POSIX.1c 才标准化），让系统编程代码能在各 Unix 平台间移植——Linux 系统编程本质上就是在写"POSIX 程序"。

进程与线程的演化是两条线。进程用 fork 复制、用 exec 换壳，早期 fork 要完整复制地址空间、代价高昂，后来引入**写时复制（Copy-On-Write，COW）**才让 fork 变便宜。线程方面：1996 年 Linux 有了第一个 pthread 实现 **LinuxThreads**，但模拟得粗糙、与 POSIX 语义有出入；2003 年 **NPTL**（Native POSIX Thread Library）重写并入 glibc，成为今天 Linux 上 pthread 的事实实现——每个线程对应一个由 clone 系统调用创建的内核线程。

IO 多路复用（I/O multiplexing）的演化则是"从轮询到事件回调"：1983 年 BSD 的 **select** 首次让一个进程同时等待多个 fd，但有 1024 个 fd 上限（`FD_SETSIZE`）且每次调用 O(n) 扫描；1986 年 System V 的 **poll** 取消上限，仍是 O(n) 扫描；2002 年 Linux 2.5 引入 **epoll**，用内核事件回调 + 就绪链表做到 O(1) 获取就绪事件，成为高并发 Linux 服务的标配。

| 时间 | 事件 | 关键演变 |
|------|------|---------|
| 1971 | Unix V1 | fork 诞生，"一切皆文件"哲学成型 |
| 1983 | select | BSD 引入 IO 多路复用，fd 上限 1024 |
| 1986 | poll | System V 改进，取消 fd 上限，仍是 O(n) 扫描 |
| 1988 | POSIX | 系统接口标准化（open/fork 等），pthread 线程接口 1995 年 POSIX.1c 才标准化 |
| 1995 | POSIX.1c | pthread 线程接口标准化 |
| 1996 | LinuxThreads | 首个 Linux pthread 实现，与 POSIX 语义有出入 |
| 2002 | epoll | Linux 2.5 引入，事件回调 + 就绪链表，O(1) 就绪获取 |
| 2003 | NPTL | 重写 pthread 并入 glibc，1:1 内核线程模型定型 |

本文示例以 **POSIX.1-2008**（IEEE Std 1003.1-2008）为基线（open/fork/pthread/sigaction/socket 等接口在该版定型，Linux 与 macOS 均完整支持），epoll 是 Linux 2.6+ 专有扩展、单独标注。验证工具链：Apple clang 21.0.0（macOS），除 epoll 示例外均已在该环境验证；epoll 示例需在 Linux 上编译运行。这个阶段涉及的接口是 Unix 系统编程中最稳定的部分——open/read/write/fork 的语义五十年未变，学会一次终身受用。

## 3. 语法与参数

### 3.1 文件描述符与 open / read / write / close

```c
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>
int main(void) {
    int fd = open("data.txt", O_RDONLY);      /* 打开一个 fd */
    if (fd < 0) { perror("open"); return 1; } /* 失败返回 -1, errno 说明原因 */
    char buf[32];
    ssize_t n = read(fd, buf, sizeof buf);    /* 读最多 32 字节 */
    if (n > 0)      printf("读到 %zd 字节\n", n);
    else if (n == 0) printf("已到文件末尾 (EOF)\n");
    else            perror("read");           /* n < 0: 出错 */
    close(fd);                                /* 归还 fd, 否则泄漏 */
    return 0;
}
```
read 返回值三态：**>0 实际读到的字节数、0 到达文件末尾（EOF）、-1 出错**；write 同理，返回实际写出的字节数。

| O_* 标志 | 含义 |
|----------|------|
| `O_RDONLY` / `O_WRONLY` / `O_RDWR` | 只读 / 只写 / 读写（三选一，必须给） |
| `O_CREAT` | 文件不存在则创建（需第三个参数 mode，如 `0644`） |
| `O_TRUNC` | 打开时把文件截断为空 |
| `O_APPEND` | 每次写追加到末尾（多进程/多线程写日志的安全选择） |
| `O_EXCL` | 与 O_CREAT 连用：文件已存在则打开失败（原子创建） |

**要点（坑必背）**：
- **短读与短写是常态**：read/write 不保证一次完成请求的字节数（管道、socket、信号打断时尤其常见），**必须循环直到读满/写完或遇到 EOF/错误**——本阶段必会概念。
- **EINTR**：read 被信号打断时返回 -1 且 `errno == EINTR`，正确做法是重试（或用 sigaction 的 `SA_RESTART` 让内核自动重试）。
- **fd 泄漏**：每个成功返回的 open/socket 都必须 close；进程 fd 上限由 `ulimit -n` 决定（Linux 默认 soft limit 通常 1024，macOS 默认 256），泄漏多了 open 返回 `EMFILE`。排查：`ls /proc/<pid>/fd/`（Linux）。
- 检查**每个**系统调用的返回值：`fd < 0`、`n < 0` 都要处理，这是 ph06"检查每个 IO 返回值"在系统层的延续。

### 3.2 进程：fork / exec / wait

```c
#include <stdio.h>
#include <sys/wait.h>
#include <unistd.h>
int main(void) {
    pid_t pid = fork();                       /* 复制当前进程 */
    if (pid < 0) { perror("fork"); return 1; }
    if (pid == 0) {                           /* 子进程: fork 返回 0 */
        printf("子进程 pid=%d, 父进程 pid=%d\n", getpid(), getppid());
        execl("/bin/echo", "echo", "exec 换壳成功", (char *)NULL);
        perror("execl");                      /* 只有 exec 失败才走到这里 */
        _exit(127);
    }
    int status;                               /* 父进程: fork 返回子进程 pid */
    waitpid(pid, &status, 0);                 /* 阻塞等待子进程结束 */
    if (WIFEXITED(status))
        printf("父进程: 子进程退出码 %d\n", WEXITSTATUS(status));
    return 0;
}
```
- **fork**：调用一次、返回两次——父进程得到子进程 pid，子进程得到 0；失败返回 -1。
- **exec 系列**（execl/execv/execlp/execvp）：用新程序**替换**当前进程映像，进程 pid 不变；exec 成功后不返回，只有失败才返回 -1。
- **wait/waitpid**：父进程回收子进程退出状态，是"收养"子进程尸体的唯一途径。

**要点（坑必背）**：
- **僵尸进程（zombie）**：子进程先退出而父进程没 wait，子进程变成 `defunct` 僵尸、占据进程表项——父进程不 wait，僵尸会累积。排查：`ps aux | grep defunct`。
- **孤儿进程**：父进程先退出，子进程被 PID 1（init/systemd）收养并自动回收——守护进程（daemon）正是利用这一机制。
- **fork 与 stdio 缓冲**：fork 复制用户态缓冲区，父子各打一份输出，可能看到重复 printf——需要时 fork 前 `fflush(NULL)`。
- fork 后父子**共享打开的文件描述符表拷贝**（指向同一打开文件表项，见 4.1），fd 数字相同但各自独立 close。

### 3.3 进程间通信：pipe 与 signal 基础

```c
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
int main(void) {
    int fds[2];
    if (pipe(fds) < 0) { perror("pipe"); return 1; } /* fds[0]读端 fds[1]写端 */
    pid_t pid = fork();
    if (pid < 0) { perror("fork"); return 1; }
    if (pid == 0) {
        close(fds[0]);                              /* 子进程关读端 */
        const char *msg = "来自子进程的消息";
        write(fds[1], msg, strlen(msg) + 1);        /* 含 '\0' */
        close(fds[1]);
        return 0;
    }
    close(fds[1]);                                  /* 父进程关写端 */
    char buf[64] = {0};
    read(fds[0], buf, sizeof buf);                  /* 阻塞直到有数据 */
    printf("父进程收到: %s\n", buf);
    close(fds[0]);
    wait(NULL);
    return 0;
}
```
**pipe**（管道）是单向字节流：一端写、一端读，数据在内核缓冲区中流转，`|` 命令符的底层就是它；半双工，双向通信要建两根。**signal**（信号）是异步通知：内核或 `kill` 命令把信号投递给进程，进程通过 handler 响应。
```c
#include <signal.h>
#include <stdio.h>
#include <unistd.h>
static volatile sig_atomic_t got = 0;               /* 信号安全的原子变量 */
void on_sigint(int sig) { (void)sig; got = 1; }     /* 只做原子赋值, 不做 printf! */
int main(void) {
    struct sigaction sa = {0};
    sa.sa_handler = on_sigint;
    sigaction(SIGINT, &sa, NULL);                   /* 优于 signal(): 可设 SA_RESTART */
    printf("按 Ctrl+C (pid=%d)...\n", getpid());
    while (!got) pause();                           /* 挂起直到收到信号 */
    printf("收到 SIGINT, 退出\n");
    return 0;
}
```
**要点（坑必背）**：
- **信号处理函数必须 async-signal-safe**：只能调用 `write`、`_exit`、`sig_atomic_t` 赋值等少数操作，printf/malloc/lock 一律禁止——否则与主程序互锁产生诡异死锁。
- **SIGKILL 与 SIGSTOP 不可捕获**：`kill -9` 是"物理删除"，任何程序都无法拦截；`SIGCHLD` 通知父进程"子进程结束了"，可配合 waitpid 处理。
- `SA_RESTART` 标志让被信号打断的系统调用自动重试，是应对 EINTR 的另一种思路。

### 3.4 线程：pthread_create / join / detach

```c
#include <pthread.h>
#include <stdio.h>
void *worker(void *arg) {                 /* 线程函数签名固定: void *(*)(void *) */
    int id = *(int *)arg;
    printf("线程 %d 开始工作\n", id);
    return (void *)(long)(id * 2);        /* 返回值经 void * 传回 */
}
int main(void) {
    pthread_t tid;
    int id = 42;                          /* arg 传栈变量: 须保证线程运行期它仍存活 */
    if (pthread_create(&tid, NULL, worker, &id) != 0) { perror("pthread_create"); return 1; }
    void *ret;
    pthread_join(tid, &ret);              /* 阻塞等待线程结束, 取回返回值 */
    printf("线程返回: %ld\n", (long)ret);
    return 0;
}
```

```bash
gcc -pthread thread.c -o thread && ./thread   # 必须加 -pthread, 否则链接失败
```
- **pthread_create**：第 1 参输出线程 id，第 3 参是线程函数，第 4 参是传给它的参数（任意指针）。
- **pthread_join**：等待线程结束并回收其资源、取回返回值——对线程而言 join 相当于进程的 wait。
- **pthread_detach**：声明"不用 join 了"，线程结束后资源自动回收；detach 后不能再 join。

**要点（坑必背）**：
- **坑 1：传给线程的 arg 指向栈变量**——主线程可能在线程使用前就离开该变量作用域（如循环变量 `&i`），造成数据竞争；**必须传堆分配或静态数据**。
- **坑 2：漏写 `-pthread`** 会报 `undefined reference to 'pthread_create'`——链接 pthread 库是编译命令的一部分。
- 线程函数返回值 `void *` 复用为整数时要 `(void *)(long)x` 往返转换，避免指针截断。

### 3.5 同步：mutex 与 condition variable

```c
#include <pthread.h>
#include <stdio.h>
static int counter = 0;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;  /* 静态初始化 */
void *increment(void *arg) {
    (void)arg;
    for (int i = 0; i < 100000; i++) {
        pthread_mutex_lock(&lock);
        counter++;                          /* 临界区: 互斥保护 */
        pthread_mutex_unlock(&lock);
    }
    return NULL;
}
int main(void) {
    pthread_t t1, t2;
    pthread_create(&t1, NULL, increment, NULL);
    pthread_create(&t2, NULL, increment, NULL);
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    printf("counter = %d (期望 200000)\n", counter);
    return 0;
}
```
把两处 `pthread_mutex_lock/unlock` 注释掉再运行：counter 大概率小于 200000——这就是**数据竞争（data race）**，`counter++` 是"读-改-写"三步，两线程交错读写同一内存。可用 `gcc -fsanitize=thread`（TSan）运行时直接报告。

**condition variable（条件变量）**解决"等待某个条件成立"：`pthread_cond_wait(&cond, &mutex)` 原子地释放 mutex 并睡眠，被 `pthread_cond_signal`（唤醒一个）/`pthread_cond_broadcast`（唤醒全部）唤醒后**重新获得 mutex** 再返回——完整可编译的生产者-消费者队列见第 6 章示例 3。

| API | 作用 |
|-----|------|
| `pthread_mutex_lock/unlock` | 进入/离开临界区；已锁则阻塞等待 |
| `pthread_mutex_trylock` | 拿不到锁立即返回 `EBUSY`，不死等（死锁逃生） |
| `pthread_cond_wait/signal/broadcast` | 等待条件 / 唤醒一个 / 唤醒全部 |

**要点（坑必背）**：
- **数据竞争（race condition）**：共享数据没有互斥保护，结果随调度乱变；TSan 是定位利器，根治靠"所有共享读写都加锁"。
- **死锁（deadlock）**：两个线程各持一把锁、互相等对方——典型是**锁顺序不一致**（A 拿 lock1 再拿 lock2，B 拿 lock2 再拿 lock1）。对策：全局统一加锁顺序、`trylock` 失败回退、或一次只持一把锁。
- **条件变量必须配合 while 而非 if 重查条件**：虚假唤醒（spurious wakeup）下 `if` 会直接越界。
- **cond_wait 前必须先持锁**：它原子地"释放锁 + 睡眠"，不持锁调用是未定义行为。

### 3.6 socket 编程基础：TCP 四步

TCP 服务端四步：**socket → bind → listen → accept**；客户端：**socket → connect**。
```c
/* 服务端骨架 */
int lfd = socket(AF_INET, SOCK_STREAM, 0);            /* 1. 创建监听 fd */
struct sockaddr_in addr = {0};
addr.sin_family = AF_INET;
addr.sin_addr.s_addr = htonl(INADDR_ANY);             /* 监听所有网卡 */
addr.sin_port = htons(8888);                          /* 主机序 → 网络序 */
bind(lfd, (struct sockaddr *)&addr, sizeof addr);     /* 2. 绑定地址+端口 */
listen(lfd, 16);                                      /* 3. 进入监听, 16=backlog */
int cfd = accept(lfd, NULL, NULL);                    /* 4. 接受连接, 返回新 fd */

/* 客户端 */
int fd = socket(AF_INET, SOCK_STREAM, 0);
struct sockaddr_in addr = {0};
addr.sin_family = AF_INET;
addr.sin_port = htons(8888);
inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);      /* "点分十进制" → 二进制 */
connect(fd, (struct sockaddr *)&addr, sizeof addr);   /* 发起连接(三次握手) */
```
- 读写连接用 read/write 或 recv/send；`sockaddr_in` 是 IPv4 地址结构，端口用 `htons`/`ntohs` 做主机序与网络序（大端）转换。
- **accept 返回的新 fd 才是连接**，监听 fd 继续 accept 下一个；`AF_INET` + `SOCK_STREAM` 即 TCP，`SOCK_DGRAM` 即 UDP（见 3.7）。

**要点（坑必背）**：
- **半包**：TCP 是字节流，recv 返回多少字节**不由发送方的 write 决定**——一次 send 可能被拆成多次 recv（半包），多次 send 也可能粘在一次 recv（粘包）。必须靠**应用层协议**界定消息边界：定长消息、`\n` 分隔、或"长度前缀 + 内容"。
- **超时缺失**：阻塞 recv 可能永远等不到数据；用 `setsockopt(SO_RCVTIMEO/SO_SNDTIMEO)` 设超时，或非阻塞 + select/epoll。
- **fd 泄漏**：accept 的每个 cfd 用完必须 close；服务端重启报 `Address already in use` 是 TIME_WAIT——`setsockopt(lfd, SOL_SOCKET, SO_REUSEADDR, ...)` 解决。
- 发送方同理：send 也要处理**短写**，循环直到全部发出。

### 3.7 UDP 基础

UDP 无连接、无握手，但**保留消息边界**——每次 recvfrom 恰好收到一个完整数据报（sendto 一次发送的内容），代价是不保证不丢包、不保证顺序。
```c
#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
int main(void) {
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) { perror("socket"); return 1; }
    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(7777);
    if (bind(fd, (struct sockaddr *)&addr, sizeof addr) < 0) { perror("bind"); close(fd); return 1; }

    const char *msg = "ping";
    struct sockaddr_in dst = {0};
    dst.sin_family = AF_INET;
    dst.sin_port = htons(7777);
    inet_pton(AF_INET, "127.0.0.1", &dst.sin_addr);
    sendto(fd, msg, (size_t)strlen(msg) + 1, 0,        /* 无连接, 直接发 */
           (struct sockaddr *)&dst, sizeof dst);

    char buf[64];
    struct sockaddr_in src;
    socklen_t slen = sizeof src;
    ssize_t n = recvfrom(fd, buf, sizeof buf, 0,       /* 收完整数据报 */
                         (struct sockaddr *)&src, &slen);
    printf("收到 %zd 字节: %s\n", n, buf);
    close(fd);
    return 0;
}
```
**要点**：
- sendto/recvfrom 每次都要带对方地址；接收方 `bind` 后 recvfrom 会填出"谁发的"。
- **丢包要应用层自己处理**（重传、ACK、序号）——TCP 帮你做的那些事，UDP 一概不管；DNS、NTP 这类"查一次就行"的场景才适合 UDP。
- 接收缓冲区小于数据报时**截断**（多余字节丢弃）；UDP 保留消息边界，**没有 TCP 式的短读**——recvfrom 一次恰好取回一个完整数据报（或截断部分）。

### 3.8 select / poll / epoll 事件模型入门

三个 API 解决同一问题：**一个线程同时等待多个 fd 就绪**。select 有 1024 上限、poll 取消上限，但两者都是"每次调用全量拷贝 fd 集合 + 内核 O(n) 扫描"；epoll 是 Linux 专有的事件驱动方案。
```c
#include <stdio.h>
#include <sys/epoll.h>
#include <unistd.h>
int main(void) {
    int epfd = epoll_create1(0);
    if (epfd < 0) { perror("epoll_create1"); return 1; }
    struct epoll_event ev = {0};
    ev.events = EPOLLIN;                    /* 关注"可读"事件 */
    ev.data.fd = STDIN_FILENO;              /* 用户数据: 通常是 fd 或指针 */
    epoll_ctl(epfd, EPOLL_CTL_ADD, STDIN_FILENO, &ev);  /* 注册 stdin */
    struct epoll_event ready[8];
    printf("等 stdin 可读 (输入一行回车)...\n");
    int n = epoll_wait(epfd, ready, 8, 5000);   /* 最多等 5 秒 */
    if (n > 0)       printf("fd %d 可读!\n", ready[0].data.fd);
    else if (n == 0) printf("超时, 没有输入\n");
    else             perror("epoll_wait");
    close(epfd);
    return 0;
}
```

```bash
gcc -Wall -Wextra epoll_demo.c -o epoll_demo && ./epoll_demo   # Linux 专有; 未在本环境验证（macOS 无 epoll）
```

| 维度 | select | poll | epoll |
|------|--------|------|-------|
| fd 数量上限 | 1024（FD_SETSIZE） | 无硬上限 | 无硬上限 |
| 每次调用开销 | 全量拷贝集合 + O(n) 扫描 | 同左 | 只注册一次，epoll_wait O(就绪数) 取就绪 |
| 触发方式 | 水平触发 | 水平触发 | 水平（默认）+ 边缘（EPOLLET） |
| 平台 | 几乎所有平台 | 几乎所有平台 | **Linux 专有** |

**要点**：
- **水平触发（LT）**：fd 一直有数据就反复通知；**边缘触发（ET）**：只在状态"从无到有"时通知一次，**必须循环读到 EAGAIN** 才不会被饿死——ET + 非阻塞是高性能服务器的标配。
- epoll 三件套：`epoll_create1` 建表、`epoll_ctl`（ADD/MOD/DEL）增改删、`epoll_wait` 取就绪事件；完整多客户端服务器见第 6 章示例 5。
- 选型：连接数少用 select/poll 足够；**上万连接、大部分空闲**时 epoll 才显出数量级优势。

## 4. 底层原理

### 4.1 文件描述符表与内核资源：fd → 文件表项 → inode 三层

```text
进程 fd 表 (每进程)     打开文件表 (系统级)           inode (磁盘/内存)
┌─────────────────┐  指向 ┌──────────────────────┐  指向 ┌──────────────┐
│ 0 stdin          │─────▶│ 文件偏移 offset        │─────▶│ inode         │
│ 1 stdout         │      │ 状态标志 O_APPEND/...  │      │ 大小/权限/锁   │
│ 2 stderr         │      │ 引用计数 refcount      │      │ 数据块位置     │
│ 3 data.txt       │      └──────────────────────┘      └──────────────┘
└─────────────────┘
```
- **fd 只是数组下标**（整数）；真正状态在**打开文件表项**（open file description，含当前读写 offset、O_* 标志）里；最底层是 **inode**——文件本身的元数据与数据块。
- 为什么"文件描述符是一类统一的内核资源句柄"：普通文件、管道、socket、设备最终都落到同一张三层表里，open/read/write/close 一套 API 通吃一切资源。
- **fork 复制的是 fd 表（拷贝），不是文件表项**：父子共享同一 offset——父读 100 字节，子接着读到第 101 字节；`dup/dup2`（重定向底层）同理。`close` 只是引用计数减一，全部关闭才真正释放。

### 4.2 fork 的写时复制（COW）与进程地址空间

早期 fork 要完整复制父进程地址空间，慢且费内存。现代 Linux 的 fork 只做两件事：**复制页表**，并把所有页标记为只读（写保护）。之后谁先写，谁触发缺页异常（page fault），内核**只复制那一页**再放行写入——这就是**写时复制（Copy-On-Write，COW）**：fork 的代价从 O(内存大小) 降为 O(页表大小)。
```text
进程虚拟地址空间 (低 → 高):
┌──────────────────┐
│ Text  代码段(只读) │
│ Data/BSS 全局变量  │
│ Heap  堆(↑增长)    │  ← malloc 小块 (brk) / 大块 (mmap)
│ mmap 区域          │  ← 动态库、共享内存
│ Stack 栈(↓增长)    │  ← 局部变量, 默认上限 8MB (ulimit -s)
└──────────────────┘
```
- fork 返回后父子拥有**相同内容、不同地址空间**：任何一方修改自己的页，COW 保证不影响对方——这就是"进程隔离资源"的底层含义。
- 随后子进程调用 **exec**：直接丢弃旧映像（页表全部替换），把新程序从磁盘装载进同一地址空间——"fork + exec"是"造一个壳 + 装新程序"两步。
- 顺带解释 3.2 的坑：printf 的用户态缓冲区在 fork 时被 COW 复制，父子各写各的副本，才会"输出两遍"。

### 4.3 线程的共享与互斥底层：TLS 与栈隔离

NPTL 的 pthread 是 1:1 模型：**每个线程是一个内核线程**，由 clone 系统调用创建，但 clone 与 fork 的关键区别是**共享地址空间**。

| 共享（地址空间内） | 独享（每线程一份） |
|--------------------|--------------------|
| 代码段、全局/静态变量 | 线程栈（默认 8MB，独立） |
| 堆（malloc 的内存） | 寄存器现场 |
| 打开的文件描述符表 | **TLS**（线程局部存储，`__thread` 变量） |
| 信号处理函数 | **errno**（所以 errno 是线程安全的） |

- **栈隔离**：每个线程有自己的栈，`pthread_create` 时内核分配；栈溢出触发 SIGSEGV，**整个进程崩溃**（并非只崩当前线程）；默认 8MB × 上千线程会吃光虚拟内存——这是"每连接一线程"撑不住高并发的根源。
- **互斥的底层**：`pthread_mutex_lock` 先做**原子指令**（如 `lock cmpxchg`）抢锁——无竞争时全程用户态、零系统调用（快速路径）；抢不到才陷入 **futex**（fast userspace mutex）系统调用睡眠，等持有者 unlock 时被唤醒（慢速路径）。条件变量同样建立在 futex 之上。
- **数据竞争的本质**：多线程共享同一内存，而 `x++` 是"读-改-写"三步，两步之间线程切换就会丢更新——必须靠原子操作或锁把"读-改-写"变成不可分割的临界区。

### 4.4 阻塞 IO vs 多路复用：就绪通知模型

- **阻塞 IO**：线程在 read 上睡眠，数据来了才返回。模型简单，但**每连接需要一个线程**——1 万连接 = 1 万线程，仅线程栈就吃 80GB 虚拟内存，调度开销爆炸。
- **select/poll**：把 fd 集合拷进内核，内核**线性扫描**所有 fd 看谁就绪，再把就绪集合拷回用户态。O(n) 扫描 + 两次全量拷贝，连接一多（如 1 万）每轮都要扫 1 万项——即便只有 1 个就绪。
- **epoll**：`epoll_ctl` 注册时内核为每个 fd 挂回调；fd 就绪，回调把它挂上**就绪链表**。`epoll_wait` 只把就绪链表拷给用户——**复杂度 O(就绪数)**，与总连接数无关。红黑树管理注册表、就绪链表做事件队列，这就是"事件驱动"。
- **就绪通知模型**统一了三种 API 的心智：程序不阻塞在某个 fd 上，而是"注册关注 + 等通知 + 批量处理"，配合非阻塞 fd（`O_NONBLOCK`）实现单线程服务海量连接。

### 4.5 TCP 连接的建立与关闭：三次握手/四次挥手与半包

```text
三次握手 (connect 的底层)            四次挥手 (close 的底层)
客户端            服务端            主动关闭方            被动关闭方
 │── SYN ──────▶│                  │── FIN ──────▶│   半关闭: 不再发数据
 │◀─ SYN+ACK ───│                  │◀── ACK ──────│
 │── ACK ──────▶│  连接建立         │◀── FIN ──────│
 │── 数据 ─────▶│  可双向收发        │── ACK ──────▶│   连接彻底关闭
```
- **三次握手**：客户端 SYN → 服务端 SYN+ACK → 客户端 ACK，双方确认"你收得到我、我收得到你"；connect 返回即握完成。
- **四次挥手**：任何一方 close 发起 FIN；对端 ACK 后进入半关闭（还能继续收数据），对端也 close 再发 FIN，发起方 ACK 后进入 **TIME_WAIT**（等 2MSL，约 60 秒）——这是服务端重启报 `Address already in use` 的原因，`SO_REUSEADDR` 就是为它准备的。
- **半包与粘包为什么存在**：TCP 是**字节流**，内核按 MTU/拥塞窗口把应用数据切成任意大小的段发送，接收方 recv 能取到的字节数由"内核缓冲区里现在有什么"决定——与发送方的 write 边界无关。因此**必须由应用层协议定义消息边界**（定长/分隔符/长度前缀），并在接收侧维护"累积缓冲 + 按边界解析"的状态机。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 系统工具（cat/cp/管道实现） | open/read/write、短读短写、EINTR |
| shell 与守护进程 | fork/exec/wait、孤儿与僵尸进程 |
| 进程间数据流转 | pipe、signal、SIGCHLD |
| 并发任务处理 | pthread_create/join、mutex、condvar |
| 网络服务（echo/HTTP/下载器） | socket、TCP 四步、半包与超时 |
| 海量连接服务器 | select/poll/epoll、非阻塞、边缘触发 |
| 日志采集与后台任务 | 多线程 + 任务队列 + O_APPEND 文件写 |

**不适合**此阶段的事项：
- C 标准与跨平台可移植性细节（ph09：C89~C23、GCC/Clang/MSVC、stdint.h）
- 未定义行为的系统化梳理（ph10）
- mmap 与 Page Cache 的存储语义（ph13 mmap、Page Cache 与可靠文件 IO 阶段：存储引擎视角，roadmap 第 13 节）
- 高性能网络框架（协程、io_uring、零拷贝、用户态协议栈，后续阶段）

## 6. 代码示例

> 完整可运行文件在 [`examples/`](./examples/) 目录（编译/运行命令见其 README）。示例 1~4 已在 macOS + Apple clang 21.0.0 验证；示例 5 使用 epoll（Linux 专有），未在本环境验证（需 Linux）。示例 4/5 运行后可用 `nc 127.0.0.1 <端口>` 测试。

### 示例 1：文件复制程序

对应 roadmap 练习"简单 shell / 文件类工具"的前置技能：完整处理短读、短写与错误。

```c
// examples/ex01-file-copy.c —— 文件复制: 短读短写循环 + 完整错误处理（已验证）
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#define BUF_SIZE 4096
int main(int argc, char *argv[]) {
    if (argc != 3) { fprintf(stderr, "用法: %s <源文件> <目标文件>\n", argv[0]); return 1; }
    int in = open(argv[1], O_RDONLY);
    if (in < 0) { perror("open 源文件"); return 1; }
    int out = open(argv[2], O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (out < 0) { perror("open 目标文件"); close(in); return 1; }
    char buf[BUF_SIZE];
    ssize_t n;
    while ((n = read(in, buf, sizeof buf)) > 0) {
        ssize_t off = 0;
        while (off < n) {                     /* 循环写, 处理短写 */
            ssize_t w = write(out, buf + off, (size_t)(n - off));
            if (w < 0) { perror("write"); close(in); close(out); return 1; }
            off += w;
        }
    }
    if (n < 0) { perror("read"); close(in); close(out); return 1; }
    close(in); close(out);
    printf("复制完成\n");
    return 0;
}
```
要点：外层循环处理**短读**（read 不满一缓冲就继续），内层循环处理**短写**；每个失败路径都 close 两个 fd（**fd 泄漏**高发点）；`O_TRUNC` 保证目标文件被清空重写。

### 示例 2：多进程协作（fork + wait）

对应 roadmap 练习"简单 shell"的核心机制：fork 出子进程干活、父进程等待并收尸。

```c
// examples/ex02-fork-wait.c —— fork 3 个子进程 + wait 依次回收（已验证）
#include <stdio.h>
#include <sys/wait.h>
#include <unistd.h>
#define CHILDREN 3
int main(void) {
    for (int i = 0; i < CHILDREN; i++) {
        pid_t pid = fork();
        if (pid < 0) { perror("fork"); return 1; }
        if (pid == 0) {
            printf("子进程 %d: 我是第 %d 个孩子\n", getpid(), i + 1);
            return (i + 1) * 10;              /* 用退出码回传结果 */
        }
    }
    int status;
    pid_t child;
    while ((child = wait(&status)) > 0)       /* 父进程: 依次回收全部子进程 */
        printf("父进程: 子进程 %d 退出, 退出码 %d\n",
               child, WIFEXITED(status) ? WEXITSTATUS(status) : -1);
    return 0;
}
```
要点：子进程里 return 的值变成退出码，父进程 wait 依次回收（**僵尸进程**必须 wait 才能清除）；`wait` 回收任意一个子进程，`waitpid(pid,...)` 回收指定一个——简单 shell 逐条执行命令时应 waitpid 当前这条。

### 示例 3：多线程任务队列（pthread + mutex + condvar）

对应 roadmap 推荐项目"多线程任务队列"与练习"日志采集程序"：生产者-消费者模型，mutex 保护队列、condvar 处理"满/空"等待。

```c
// examples/ex03-task-queue.c —— 生产者-消费者任务队列（已验证; 完整文件含 tq_destroy 资源释放）
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#define QUEUE_CAP  8
#define WORKER_NUM 3
#define TASK_NUM   20
typedef struct {
    int *items;
    int head, tail, count;
    pthread_mutex_t lock;
    pthread_cond_t  not_empty;      /* 队列非空: 消费者可取 */
    pthread_cond_t  not_full;       /* 队列未满: 生产者可放 */
} TaskQueue;
static void tq_init(TaskQueue *q) {
    q->items = malloc(QUEUE_CAP * sizeof(int));
    q->head = q->tail = q->count = 0;
    pthread_mutex_init(&q->lock, NULL);
    pthread_cond_init(&q->not_empty, NULL);
    pthread_cond_init(&q->not_full, NULL);
}
static void tq_push(TaskQueue *q, int task) {
    pthread_mutex_lock(&q->lock);
    while (q->count == QUEUE_CAP)               /* 满则等, while 防虚假唤醒 */
        pthread_cond_wait(&q->not_full, &q->lock);
    q->items[q->tail] = task;
    q->tail = (q->tail + 1) % QUEUE_CAP;
    q->count++;
    pthread_cond_signal(&q->not_empty);         /* 通知消费者 */
    pthread_mutex_unlock(&q->lock);
}
static int tq_pop(TaskQueue *q) {
    pthread_mutex_lock(&q->lock);
    while (q->count == 0)
        pthread_cond_wait(&q->not_empty, &q->lock);
    int task = q->items[q->head];
    q->head = (q->head + 1) % QUEUE_CAP;
    q->count--;
    pthread_cond_signal(&q->not_full);          /* 通知生产者 */
    pthread_mutex_unlock(&q->lock);
    return task;
}
void *worker(void *arg) {
    TaskQueue *q = arg;
    for (;;) {
        int task = tq_pop(q);
        if (task < 0) break;                    /* -1 为终止信号 */
        printf("worker %lu 处理任务 %d\n", (unsigned long)pthread_self(), task);
        struct timespec ts = {0, 10 * 1000 * 1000}; /* 10ms, 模拟耗时 */
        nanosleep(&ts, NULL);
    }
    return NULL;
}
int main(void) {
    TaskQueue q;
    tq_init(&q);
    pthread_t workers[WORKER_NUM];
    for (int i = 0; i < WORKER_NUM; i++)
        pthread_create(&workers[i], NULL, worker, &q);
    for (int i = 0; i < TASK_NUM; i++)          /* 生产者: 投递 20 个任务 */
        tq_push(&q, i);
    for (int i = 0; i < WORKER_NUM; i++)        /* 再投 3 个终止信号 */
        tq_push(&q, -1);
    for (int i = 0; i < WORKER_NUM; i++)
        pthread_join(workers[i], NULL);         /* 全部 worker 退出 */
    printf("所有 worker 已退出\n");
    return 0;
}
```
要点：队列是共享数据，**所有读写都持 lock**（数据竞争免疫）；生产者满时等 `not_full`、消费者空时等 `not_empty`，互不忙等；"终止信号"复用队列传递，比全局标志更不易漏。日志采集程序把"生产"换成各线程记日志、把消费换成单写线程 `open(..., O_APPEND)` 落盘即可。

### 示例 4：TCP echo server（阻塞版）

对应 roadmap 练习与推荐项目"TCP echo server"的基础形态：accept 循环 + 完整错误处理。

```c
// examples/ex04-echo-server.c —— TCP echo server 阻塞版（已验证）
#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#define PORT      8888
#define BUF_SIZE  4096
int main(void) {
    int lfd = socket(AF_INET, SOCK_STREAM, 0);
    if (lfd < 0) { perror("socket"); return 1; }
    int opt = 1;
    setsockopt(lfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof opt); /* 防 TIME_WAIT */
    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(PORT);
    if (bind(lfd, (struct sockaddr *)&addr, sizeof addr) < 0) { perror("bind"); close(lfd); return 1; }
    if (listen(lfd, 16) < 0) { perror("listen"); close(lfd); return 1; }
    printf("echo server 监听 %d 端口\n", PORT);
    for (;;) {
        struct sockaddr_in peer;
        socklen_t plen = sizeof peer;
        int cfd = accept(lfd, (struct sockaddr *)&peer, &plen);
        if (cfd < 0) { perror("accept"); continue; }   /* accept 失败不退出 */
        char ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &peer.sin_addr, ip, sizeof ip);
        printf("新连接: %s:%d\n", ip, ntohs(peer.sin_port));
        char buf[BUF_SIZE];
        ssize_t n;
        while ((n = recv(cfd, buf, sizeof buf, 0)) > 0) {
            ssize_t off = 0;
            while (off < n) {                  /* send 也要处理短写 */
                ssize_t w = send(cfd, buf + off, (size_t)(n - off), 0);
                if (w < 0) { perror("send"); goto out; }
                off += w;
            }
        }
        if (n < 0) perror("recv");             /* EINTR 时按 3.1 的规则重试 */
out:
        close(cfd);                            /* 连接 fd 用完即关 */
    }
    close(lfd);
    return 0;
}
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex04-echo-server.c -o echo_server
# 2. 运行服务端
./echo_server
# 3. 另开终端: 输入什么回显什么
nc 127.0.0.1 8888
```
要点：accept 失败 `continue` 不退出（临时性错误）；**每个 cfd 用完 close**；`recv` 返回 0 表示对端关闭、-1 表示错误——两个出口都正确处理。局限：阻塞版一次只能服务一个连接，多客户端请用示例 5。

### 示例 5：epoll 版简易事件循环

对应 roadmap 学习内容"select、poll、epoll 基础"与练习"简单 HTTP server"的前置：单线程同时服务多个连接。

```c
// examples/ex05-epoll-server.c —— epoll 事件循环（Linux 专有, 未在本环境验证）
#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdio.h>
#include <string.h>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <unistd.h>
#define PORT        9999
#define MAX_EVENTS  64
#define BUF_SIZE    4096
int main(void) {
    int lfd = socket(AF_INET, SOCK_STREAM, 0);
    if (lfd < 0) { perror("socket"); return 1; }
    int opt = 1;
    setsockopt(lfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof opt);
    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(PORT);
    if (bind(lfd, (struct sockaddr *)&addr, sizeof addr) < 0) { perror("bind"); close(lfd); return 1; }
    if (listen(lfd, 16) < 0) { perror("listen"); close(lfd); return 1; }
    int epfd = epoll_create1(0);
    if (epfd < 0) { perror("epoll_create1"); close(lfd); return 1; }
    struct epoll_event ev = {0};
    ev.events = EPOLLIN;
    ev.data.fd = lfd;
    epoll_ctl(epfd, EPOLL_CTL_ADD, lfd, &ev);      /* 注册监听 fd */
    printf("epoll server 监听 %d 端口\n", PORT);
    struct epoll_event ready[MAX_EVENTS];
    for (;;) {
        int n = epoll_wait(epfd, ready, MAX_EVENTS, -1);
        if (n < 0) { perror("epoll_wait"); break; }
        for (int i = 0; i < n; i++) {
            if (ready[i].data.fd == lfd) {         /* 新连接 */
                struct sockaddr_in peer;
                socklen_t plen = sizeof peer;
                int cfd = accept(lfd, (struct sockaddr *)&peer, &plen);
                if (cfd < 0) continue;
                struct epoll_event cev = {0};
                cev.events = EPOLLIN;
                cev.data.fd = cfd;
                epoll_ctl(epfd, EPOLL_CTL_ADD, cfd, &cev);  /* 新 fd 注册进 epoll */
            } else {                               /* 已有连接可读 */
                int cfd = ready[i].data.fd;
                char buf[BUF_SIZE];
                ssize_t r = read(cfd, buf, sizeof buf);
                if (r <= 0) {                      /* 0=对端关闭, <0=错误 */
                    epoll_ctl(epfd, EPOLL_CTL_DEL, cfd, NULL);
                    close(cfd);                    /* fd 泄漏高发点 */
                } else {
                    /* 简化: 半包/短写见主文档 3.6 要点 */
                    ssize_t off = 0;
                    while (off < r) {
                        ssize_t w = write(cfd, buf + off, (size_t)(r - off));
                        if (w < 0)
                            break;
                        off += w;
                    }
                }
            }
        }
    }
    close(epfd); close(lfd);
    return 0;
}
```
要点：**监听 fd 与连接 fd 都挂在同一个 epoll 表里**，靠 `data.fd` 区分；连接关闭时 DEL + close 缺一不可；`read` 返回的是当前内核缓冲里的字节数，**半包**同样存在——完整 HTTP server 需要累积缓冲 + 按 `\r\n\r\n` 或 Content-Length 解析请求（对应 roadmap 练习"简单 HTTP server"）。

## 7. 总结

### 关键要点

1. **文件描述符是一类统一的内核资源句柄**：普通文件、管道、socket 都是 fd，背后是"进程 fd 表 → 打开文件表项 → inode"三层结构
2. **短读短写是常态**：read/write/recv/send 都不保证一次完成，所有 IO 都要循环处理
3. **EINTR 要重试**：被信号打断返回 -1 且 errno==EINTR，用循环或 SA_RESTART 解决
4. **每个 open/socket 都要 close**：fd 泄漏会耗尽 `ulimit -n` 上限，导致 EMFILE
5. **僵尸进程必须 wait 回收**：子进程退出后父进程不 wait 就变 defunct，孤儿由 PID 1 收养
6. **进程隔离资源，线程共享进程地址空间**：隔离带来安全，共享带来数据竞争
7. **多线程必须处理竞态和死锁**：共享数据全加锁、锁顺序全局一致、condvar 配 while 防虚假唤醒
8. **网络 IO 必须考虑超时、半包和错误返回**：应用层协议界定消息边界，SO_RCVTIMEO 设超时
9. **阻塞 IO 每连接一线程，epoll 事件驱动海量连接**：就绪通知模型把 O(n) 扫描变成 O(k) 就绪获取
10. **检查每个系统调用的返回值**：`-1/0/正数` 三态各有含义，这是 ph06"检查每个 IO"的延续

### 跨语言对比：并发与系统编程模型

| 维度 | C pthread | C++ std::thread | Go goroutine | Java 线程 | Rust std::thread |
|------|-----------|-----------------|--------------|-----------|------------------|
| 创建方式 | `pthread_create(&t,0,f,&a)` | `std::thread t(f, a)` | `go f(a)` | `new Thread(...)` / Executor | `thread::spawn(move \|\| f(a))` |
| 同步原语 | pthread_mutex/cond | std::mutex / condition_variable | channel / sync.Mutex | synchronized / Lock | Mutex / Condvar / channel |
| 线程模型 | 1:1 内核线程（NPTL） | 1:1（pthread 封装） | M:N 用户态调度（栈 2KB 起） | 1:1 JVM 线程 | 1:1 系统线程 |
| 数据安全 | 全靠自觉（TSan 兜底） | 全靠自觉（RAII 缓解） | 共享内存需自行加锁 | 内存安全，竞态靠工具 | 编译期 Send/Sync 所有权检查 |
| 错误处理 | 返回码 + errno | 异常 | error 返回值 | 异常 | Result\<T, E\> |
| 创建开销 | 低（clone 系统调用） | 低 | 极低（协程，可百万级） | 较高（原生线程） | 低 |

C 的模型最"裸"：没有语言级并发原语、没有安全网，线程的一切共享与同步都显式可见——这正是存储引擎需要的精确控制力，也是理解其它语言并发设计的地基（goroutine 的 M:N 调度、Rust 的 Send/Sync 都建立在这套底层认知之上）。

### 阶段验收清单

- [ ] 能解释进程与线程的区别（进程隔离资源、线程共享进程地址空间，以及共享带来的数据竞争）
- [ ] 能写出基础 TCP 服务端（socket/bind/listen/accept + recv/send 循环 + 错误处理）
- [ ] 能处理线程同步问题（mutex 保护共享数据、condvar 处理等待、识别并规避死锁）
- [ ] 能管理文件描述符生命周期（open/socket 后正确 close、处理 fd 泄漏）
- [ ] 能说出网络 IO 的三类陷阱（超时、半包、错误返回）并给出对策
- [ ] 能用 select/poll/epoll 之一同时处理多个客户端连接

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。5 题与 roadmap「练习」一一对应：简单 shell、多线程下载器、TCP echo server、简单 HTTP server、日志采集程序。完成 3 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：多线程任务队列——有界环形缓冲 + 多生产者多消费者 + 优雅关闭，Makefile 构建。建议完成练习后再动手。roadmap 的另一个推荐项目「TCP echo server」由示例 4/5 与 exercises 练习 3 覆盖。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[C 标准、编译器与可移植性](../ph09-portability/09-portability.md) —— C89~C23 差异、GCC/Clang/MSVC、条件编译、stdint.h 固定宽度类型；届时把本阶段学到的 POSIX/Linux API 放到"标准 C 与平台 API 的边界"下重新审视。
