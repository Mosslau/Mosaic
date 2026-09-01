# C 语言 mmap、Page Cache 与可靠文件 IO 阶段

> 面向系统底层、数据库与 KV 存储方向，本阶段把"会读写文件"升级为"理解文件 IO 的完整链路"——从 open/read/write 的文件 offset、短读短写与错误返回出发，掌握 Page Cache 与 fsync 的刷盘语义、mmap 内存映射、append-only 落盘与崩溃恢复，为 WAL、SSTable 和存储引擎打好 IO 底座。

## 1. 概述

mmap、Page Cache 与可靠文件 IO 阶段是 C 学习路线中"从语法到系统"的落地关卡。目标（roadmap §13）：**理解数据库和 KV 存储依赖的文件 IO、Page Cache、mmap 和刷盘语义**。ph06 已讲过 stdio 与基础文件 IO，ph08 讲过文件描述符与进程视图，ph12 讲过二进制 record 的字节序与 CRC——本阶段回答它们共同缺的那一环：**字节流到底怎么可靠地落到磁盘，又怎么被高效地读回来**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 文件 IO 系统调用 | open/read/write/lseek、文件 offset 的推进规则、短读短写、错误返回（errno） |
| 随机与定位 IO | pread/pwrite（不推进 offset、多线程共享 fd 时的原子性） |
| 持久化语义 | fsync/fdatasync、write 成功 ≠ 持久化、macOS F_FULLFSYNC 边界 |
| 内核缓存 | Page Cache、脏页回写、热读/冷读、缓存对读写性能与基准测试的影响 |
| 内存映射 | mmap/munmap/msync、MAP_SHARED/MAP_PRIVATE、只读索引、缺页机制 |
| 可靠写入模式 | append-only 日志（O_APPEND）、半写入识别、崩溃恢复（回放 + ftruncate） |

这个阶段只涉及 POSIX 文件 IO 与存储语义——open/read/write/pread/pwrite、fsync/fdatasync、Page Cache、mmap/munmap/msync 与 append-only 落盘和崩溃恢复，**不涉及网络 socket IO（ph08）、跨语言互操作 ABI（ph14，roadmap 第 14 节，目录待建）、高级 C 与代码质量（ph15，roadmap 第 15 节，目录待建）和存储引擎的完整实现（ph16，roadmap 第 16 节，目录待建）** — 那些是 ph08 Linux 系统编程阶段、ph14 C 与 C++ / Python / Rust 互操作阶段、ph15 高级 C 与代码质量阶段和 ph16 数据库存储引擎基础阶段的内容；多线程共享 fd 的并发访问只讲 pread 的原子性收益，锁与内存序深入属 ph08 的并发专题；mmap 的移植性细节（32 位地址空间限制、页大小差异）本阶段不展开。

## 2. 来源与演变

**文件 IO 的语法在 1970 年代就定型了，之后几十年的演进都发生在"数据从 write 到磁盘之间那几层"**。UNIX 第一版（1971）就把文件抽象成字节流 + offset，open/read/write/close 四个系统调用成为一切 IO 的基石；V6/V7 时代内核引入 buffer cache（缓冲区缓存），让读写先经过内存、减少磁盘访问——这就是 Page Cache 的祖先。1980 年代 Sun 的虚拟内存学派把"文件映射进地址空间"做成 mmap（SunOS 4.0，1986），与"read 拷贝进用户缓冲区"的流派分庭抗礼，两个流派在今天的 Linux 上以 Page Cache 为共同底座并存。**可靠性的核心命题——write 返回后数据到底在哪——则要等到"缓冲 + 延迟回写"成为事实标准后才凸显**：既然 write 只进缓存，就必须有显式的"刷盘"动词（fsync），于是"持久化边界"成为存储引擎设计的头等问题。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| UNIX V1（open/read/write 系统调用） | 1971 | 文件 = 字节流 + offset；open/read/write/lseek/close 模型定型，沿用至今 |
| UNIX V6/V7（buffer cache） | 1975~1979 | 内核用内存缓冲块缓存磁盘数据，读写先过缓存——Page Cache 的雏形 |
| SunOS 4.0（mmap） | 1986 | 把文件映射进进程地址空间、按需缺页调入；与 read 拷贝流派并存 |
| POSIX.1-1988（IEEE 1003.1） | 1988 | open/read/write/lseek/close 首次标准化，结束各家 UNIX 各自为政 |
| POSIX.1b-1993（实时与 XSI 扩展） | 1993 | mmap/munmap/msync 与 pread/pwrite 进入标准 |
| SUSv3 / POSIX:2001 | 2001 | fdatasync、pread/pwrite 等定型，成为 Linux/macOS 共同遵循的基线 |
| IEEE 1003.1-2008 / -2017 | 2008 / 2017 | 现行基线；SSD/NVMe 时代刷盘成本成为热点，"fsync 到底刷到哪"被重新审视（macOS F_FULLFSYNC） |
| Linux 2.6（O_DIRECT 等） | 2003 | 绕过 Page Cache 的直接 IO 选项出现，作为特定场景的补充手段 |

本文示例以 **C11 + POSIX（IEEE Std 1003.1-2017，含 XSI 扩展）** 为基线（文件 IO、内存映射与刷盘语义都是 POSIX 接口，ISO C 只提供 stdio 文件函数；选 C11 与全库 ph11/ph12 同一口径）。验证工具链：**Apple clang 21.0.0（`cc`，macOS Darwin arm64）**，全部代码 `-Wall -Wextra -std=c11` 零警告编译运行；示例兼容 Linux（glibc）——唯一差异是 macOS 的 `F_FULLFSYNC` 扩展，已在 ex03/ex04 中以 `#ifdef` 隔离。open/read/write/mmap/fsync 是几十年来最稳定的系统接口：**变化的是存储硬件（HDD → SSD → NVMe），不是 API**——本阶段讲的语义今天与 30 年前一致。

## 3. 语法与参数

### 3.1 open/read/write 与文件 offset

文件 IO 的最小模型：`open` 得到一个文件描述符（fd），fd 上挂着一个**文件 offset**（读/写位置），`read`/`write` 从当前 offset 开始操作并推进它。

```c
// examples/ex01-open-read-write.c —— ①~③ 节选：open、write、offset（完整版见 examples/）
int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0644);
const char *msg = "hello";
ssize_t w = write(fd, msg, 5);        /* 返回值是实际写入字节数 */
off_t cur = lseek(fd, 0, SEEK_CUR);   /* 查询当前 offset */
```

**open 的 flags 与 mode**

| 标志 | 含义 |
|------|------|
| O_RDONLY / O_WRONLY / O_RDWR | 只读 / 只写 / 读写（三选一，必须给） |
| O_CREAT | 不存在则创建（此时第三个参数 mode 才生效，如 0644） |
| O_TRUNC | 打开即清空到 0 长度 |
| O_APPEND | 每次 write 原子地追加到文件末尾（见 3.7） |
| O_CLOEXEC | exec 时自动关闭（防 fd 泄漏进子进程，ph08 视角） |

**offset 的三条规则**（roadmap 学习内容"文件 offset"）：

- `read`/`write` 从当前 offset 开始，成功后**推进**它；`lseek` 显式移动它
- 每个 fd 有自己的 offset：同一个文件被 open 两次，两个 fd 的 offset 互不影响；`fork` 出的子进程与父进程**共享**同一个文件表项（同一 offset）——多线程/多进程各自持有独立 fd 时，offset 竞争就来了（见 3.3）
- 读超出文件末尾：`read` 返回 **0**（EOF），不是错误——"read 返回 0 是 EOF，返回 -1 才是错误"是必须内化的纪律

**错误返回**：系统调用失败返回 -1，errno 给出原因。`对 O_WRONLY fd 调用 read` 返回 -1 且 errno = EBADF（ex01 第 ⑦ 步实测 errno=9）。**判断成功必须看返回值，不能假设"应该成功"**——磁盘满、权限、信号都会让它失败。

### 3.2 短读短写：read_full / write_full 循环

**短读（short read）**：`read` 请求 n 字节，实际可能返回少于 n——对 pipe、socket、终端这几乎是常态（数据到达多少给多少）；**短写（short write）**：`write` 可能只写出一部分（磁盘满、信号中断）。**返回值是"实际处理了多少"，不是"你请求了多少"**。

```c
// examples/ex02-short-io.c —— write_full：循环 write 直到写够（完整版见 examples/）
static int write_full(int fd, const void *buf, size_t n) {
    const char *p = buf;
    size_t left = n;
    while (left > 0) {
        ssize_t w = write(fd, p, left);
        if (w < 0) {
            if (errno == EINTR)
                continue;            /* 被信号打断：重试，不算失败 */
            return -1;
        }
        p += w;
        left -= (size_t)w;           /* 短写：只推进实际写出的部分 */
    }
    return 0;
}
```

三条纪律（ex02 实测打印）：① read/write 的返回值是实际字节数，可能 < 请求值；② 返回 -1 且 errno == EINTR 是被信号打断，重试即可；③ read 返回 0 是 EOF，不是错误。ex02 用 pipe 制造了一次真实的短读（请求 15 字节只拿到 3），再用 `read_full` 补齐——**凡是读写文件/socket/pipe，一律包一层 full 循环**，这是 C 工程里最容易被新手省略、后果最隐蔽的习惯。

### 3.3 pread/pwrite：不推进 offset 的随机 IO

`pread(fd, buf, n, off)` 等价于"lseek 到 off + read"，**但不推进 fd 的 offset**；`pwrite` 同理。两个价值：

1. **省 lseek 往返**：随机读索引时不必"seek 过去、读、seek 回来"，offset 始终停在原地
2. **原子性**：`lseek + read` 是两步，两个线程共享同一 fd 时会被插入（A seek 到 100，B seek 到 200，A 读到的却是 200 处的内容）；`pread` 一步完成，**不依赖共享 offset 状态**——多线程随机读的正确姿势

```c
// examples/ex01-open-read-write.c —— ④⑤ 节选：pread/pwrite 不推进 offset（完整版见 examples/）
ssize_t r = pread(fd, buf, 5, 0);     /* 从偏移 0 读 5 字节 */
/* 读后 offset 仍是 5（write 留下的位置），见 ex01 实测输出 */
if (pwrite(fd, "HELLO", 5, 0) != 5)   /* 向偏移 0 覆盖写，同样不动 offset */
    die("pwrite");
```

练习 1 要求只用 pread 按索引随机读 record，并每次证明 offset 恒为 0——把"pread 不碰 offset"变成肌肉记忆。

### 3.4 fsync/fdatasync：刷盘语义

**write 成功 ≠ 数据已持久化**（roadmap 必会概念）。write 只是把数据拷进内核的 Page Cache 就返回；真正到达存储设备要等内核回写或显式刷盘：

| 函数 | 保证 | 备注 |
|------|------|------|
| write | 数据进了 Page Cache，**未承诺持久** | 返回快；断电/内核崩溃会丢 |
| fsync(fd) | 数据 + 文件元数据（mtime、大小等）刷到存储设备 | 慢，是"持久化承诺"的边界 |
| fdatasync(fd) | 只刷数据，元数据（除非影响读取）不刷 | 语义够用时比 fsync 便宜（ex03 实测同量级，场景不同） |
| F_FULLFSYNC（macOS 专用） | 连设备自身的写缓存一起刷到介质 | macOS 的 fsync 只到设备缓存，Linux 的 fsync 即真落盘 |

**刷盘成本是"次数"的函数**，ex03 实测（本机一次）：写 20000 条 × 128 字节 record——只结尾 fsync 1 次总 25.5 ms（约 78 万条/秒）；每 200 条 fsync 总 36.4 ms；**每条都 fsync 总 439.7 ms（约 4.5 万条/秒，慢 17 倍）**。结论：**刷盘次数与耗时近似成正比**——存储引擎"攒批 + 批量 fsync"（group commit）不是因为懒，是数量级的性能差。

> 属于 ph16 数据库存储引擎基础阶段（roadmap 第 16 节，目录待建）的内容：WAL 中"哪些记录必须 fsync、哪些可以延迟"的完整策略与 group commit 设计，这里只建立"fsync 是持久化边界、次数是成本"的心智模型。

### 3.5 Page Cache：write 之后的"中间态"

内核用内存充当磁盘的缓存：**所有 read/write 都先经过 Page Cache**（read 命中缓存直接返回，未命中从磁盘调入；write 修改缓存页并标记脏页，内核后台回写磁盘）。这带来两个直接影响：

- **热读 vs 冷读**：刚写完的文件立刻读，命中缓存（热读）；缓存被逐出后再读，只能去磁盘（冷读）。ex04 实测写 256 MiB 后：热读 17.7 ms（14472 MiB/s）、冷读 42.6 ms（6010 MiB/s）——**Page Cache 命中加速约 2.4 倍**
- **基准测试陷阱**（roadmap 必会概念）："刚写完就读"测出的是 Page Cache 的速度，不是磁盘的速度。ex04 的 write 阶段 4431 MiB/s 也是缓存速度（真正到介质的 F_FULLFSYNC 另计成本）

**分层视角**：进程崩溃（kill -9）只杀掉进程，**已 write 的数据仍在内核 Page Cache 里，不丢**；真正丢数据的是断电、内核崩溃——那才是 fsync 要防的场景（练习 4 用真实 SIGKILL 验证了这条）。

**逐出手段**（测试/基准用）：Linux `posix_fadvise(POSIX_FADV_DONTNEED)` 或写 `/proc/sys/vm/drop_caches`；macOS 的 `fcntl(F_NOCACHE)` 只影响之后的行为、不逐出已缓存页，实测无效，本阶段用 `msync(MS_SYNC | MS_INVALIDATE)` 演示逐出（ex04 的 evict_page_cache）。

### 3.6 mmap/munmap/msync：把文件映射进地址空间

```c
void *mmap(void *addr, size_t len, int prot, int flags, int fd, off_t offset);
int   munmap(void *addr, size_t len);        /* 解除映射 */
int   msync(void *addr, size_t len, int flags); /* MS_SYNC 刷回 / MS_INVALIDATE 使失效 */
```

| 参数 | 取值与含义 |
|------|-----------|
| prot | PROT_READ / PROT_WRITE / PROT_EXEC / PROT_NONE（可组合） |
| flags | **MAP_SHARED**（写会回写文件，其他映射者可见）/ **MAP_PRIVATE**（写时复制，不写回文件）/ MAP_ANONYMOUS（匿名内存，fd 传 -1） |
| len / offset | 映射长度与起点；**长度必须 > 0**（空文件 mmap 直接失败）；**offset 须页对齐**（调用方义务，非页对齐返回 EINVAL），长度由内核向上取整 |

**只读索引的标准姿势**（ex05）：`fstat` 取长度 → `mmap(PROT_READ, MAP_SHARED)` → 映射建立后 **fd 即可关闭**（映射本身持有文件）→ 像访问数组一样 `p[offset]` 读 → `munmap` 配对释放。**访问前三个检查一个不能少**：长度 < 头部不许 mmap、magic 必须匹配、count 与文件实际长度必须吻合（不信任文件里的长度声明）——练习 3 的验收标准。

**写 + 刷回**：`MAP_SHARED` 下直接改内存 = 改文件的 Page Cache，`msync(MS_SYNC)` 等效 mmap 世界的 fsync。ex05 实测（256 MiB 逐页触摸，热缓存）：read 15.1 ms（16994 MiB/s），mmap 9.9 ms（25864 MiB/s）——mmap 省去 read 的"内核 → 用户态"拷贝与每块一次系统调用。

**错误模型更复杂**（roadmap 必会概念）：文件被其他进程 `ftruncate` 截断后，访问映射中已不存在的页会收到 **SIGBUS**（进程崩）；访问映射范围之外是 SIGSEGV——错误不是返回值，是信号。这是"mmap 适合只读索引、写场景要慎用"的原因之一。

### 3.7 append-only 写入：O_APPEND 与日志格式

append-only 日志（只追加、不修改旧记录）是 WAL 的物理形态。两个关键：

1. **O_APPEND 的原子追加**：每次 write 原子地落到文件末尾，不受其他写者影响（多进程追加互不覆盖）——这是 append-only 多进程安全的根基
2. **记录自带长度与校验**：`[len: u32 大端][crc32: u32][payload]`，头部 8 字节，crc 覆盖 payload（字节序与 CRC 衔接 ph12）

```c
// examples/ex06-append-only.c —— log_append：O_APPEND 追加 + 头部组装（完整版见 examples/）
static int log_append(int fd, const void *payload, uint32_t len) {
    if (len > MAX_PAYLOAD)
        return -1;
    uint8_t hdr[HDR_SIZE];
    write_be32(hdr, len);
    write_be32(hdr + 4, crc32(payload, len));   /* crc 覆盖 payload */
    if (write_full(fd, hdr, sizeof hdr) < 0)
        return -1;
    if (write_full(fd, payload, len) < 0)
        return -1;
    return 0;
}
```

为什么 append-only 适合日志：**顺序写**对 SSD/HDD 都友好，且崩溃恢复点简单——"最后一个完整记录的末尾"就是可继续写的位置，不需要原地修改旧数据（原地修改 = 读到一半断电 = 旧数据也没了）。

### 3.8 崩溃恢复与刷盘边界

把 3.4~3.7 串起来就是崩溃恢复的完整流程（练习 4 用 fork + 真实 SIGKILL 验证）：

1. **崩溃只留下最后一条残记录**：假设每次 fsync 前已追加 n 条完整记录，断电发生在写第 n+1 条到一半——文件尾部是一个"半写入"（头部不完整 / payload 不完整 / crc 不符）
2. **回放识别残尾**：顺序解析，遇到长度非法、字节不够或 crc 不符即停在残尾偏移——完整记录全部恢复，残尾被安全跳过（ex06 实测：5 条完整 + 3 字节残头部，回放恢复 5 条、残尾停在偏移 98）
3. **ftruncate 修复**：把文件截到残尾偏移，文件恢复"可继续安全追加"状态

```c
// examples/ex06-append-only.c —— 回放中的残尾判定（完整版见 examples/）
if (r < (ssize_t)HDR_SIZE)
    goto torn;                   /* 头部没写全 = 截断 */
uint32_t len = read_be32(hdr);
if (len > MAX_PAYLOAD)
    goto torn;                   /* 长度非法 = 损坏 */
/* ... payload 读不齐 / crc 不符也 goto torn ... */
if (crc32(payload, len) != crc)
    goto torn;                   /* 半写入/位翻转 = 损坏 */
```

**刷盘边界**的完整表述（roadmap 必会概念"存储引擎必须明确哪些数据需要 fsync"）：`kvl_append` 返回只代表数据进了 Page Cache，`kvl_sync`（fsync）返回后才算"这条记录在断电后仍然存在"——**承诺持久化的最小单位是"一次 fsync 前的全部记录"**。process crash 不丢 Page Cache 数据、power loss 丢——这个区分是本阶段最重要的心智模型。

## 4. 底层原理

### 4.1 Page Cache：所有文件 IO 都经过内核内存

```text
进程                             内核                              磁盘
┌──────────────┐        ┌──────────────────────┐
│ write(buf) ──┼─copy──▶│  Page Cache 页 (dirty)│──后台回写/fsync──▶ 扇区
│ read(buf)  ◀─┼─copy───│  Page Cache 页        │◀──缺页调入──────── 扇区
└──────────────┘        └──────────────────────┘
```

read/write 都是"用户缓冲区 ↔ Page Cache 页"之间的拷贝，磁盘只在内核后台（writeback）或显式 fsync 时被触碰。**这就是为什么 write 快、fsync 慢**：前者是内存拷贝，后者等物理介质。基准测试里"刚写完就读"全部命中缓存，测的是内存速度——评估真实 IO 性能必须先想清楚缓存是否命中（ex04 的全部意义）。

### 4.2 mmap：虚拟地址直接指向 Page Cache 页

```text
进程虚拟地址空间                    页表映射                内核               磁盘
┌───────────────────────┐        ┌─────────────┐
│ [文件映射区域: p[0..n]]│──页表──▶│ Page Cache 页│◀──按需调入──── 文件扇区
│  首次访问 p[i] ──触发缺页异常──▶ 内核调入该页 ──▶ 返回用户态继续执行
└───────────────────────┘        └─────────────┘
```

mmap 不是"把文件读进内存"，而是**在页表里建立"虚拟地址 → Page Cache 页"的映射**：首次访问某页触发缺页异常（page fault），内核把对应磁盘页调入缓存并建立映射，之后对该地址的读写直接作用于缓存页——没有 read 那样的一次性大拷贝。MAP_SHARED 的写会改脏缓存页，最终由 writeback 或 msync 落盘。**代价**：每个首次访问的页都是一次缺页异常（ex05 的逐页触摸就是在逐个触发它）；文件在映射期间被截断，访问已消失的页 = SIGBUS。

### 4.3 数据在哪一层：write、fsync、断电的三级视角

```text
write 返回  ──▶ 数据在内核 Page Cache（进程崩溃不丢）
fsync 返回  ──▶ 数据到达存储设备（Linux 即介质；macOS 到设备缓存）
F_FULLFSYNC ──▶ 数据刷到介质（macOS；Linux 无此区分）
断电        ──▶ 只有"已到介质"的数据存在
```

存储引擎的可靠性设计（ph16）就是围绕这条线：**数据每上升一级（进程内存 → 内核缓存 → 设备 → 介质），代价越大、越抗崩溃**。本阶段要内化的是：进程崩溃不是丢数据的场景（练习 4 用 SIGKILL 实证），断电才是——所以 fsync 的位置决定了一条记录"承诺持久"的边界。

## 5. 使用场景

| 场景 | 用什么 | 依据 |
|------|--------|------|
| WAL / 数据库日志 | append-only 追加 + 批量 fsync（攒批） | 顺序写友好；fsync 次数与耗时成正比（3.4/3.7，project/ 完整落地） |
| 只读索引文件（key → offset 查找表） | mmap(PROT_READ, MAP_SHARED) | 随机读省 lseek 与拷贝，当数组访问（3.6，练习 3） |
| 大文件顺序读 / 流式处理 | read（或 mmap，量级相当） | ex05 实测差异有限；read 错误模型简单（3.2/3.6） |
| 每次写入都要"立刻持久" | write + fsync（每批一次） | 明确刷盘边界（3.4） |
| 基准测试 / 性能评估 | 先想清楚 Page Cache 命中与否 | 热读/冷读差 2.4 倍（3.5，ex04） |
| 跨进程共享大数据（只读） | mmap MAP_SHARED | 同一份 Page Cache 多进程共享 |

**不适合**本阶段手段的场景：

- **每条小写都 fsync**：吞吐掉两个数量级（ex03 实测 17 倍），是"正确但极慢"的典型——改用攒批或接受延迟（group commit 属 ph16）
- **mmap 做高频随机写**：错误是信号（SIGBUS）不是返回值，截断即崩；写路径用 read/write + fsync 边界更清晰（roadmap 必会概念"mmap 适合随机读和只读索引，但错误处理更复杂"）
- **网络 IO**：socket 读写同样有短读短写与 EINTR，但事件模型与缓冲语义属 ph08
- **跨平台二进制格式**：mmap 映射后的布局仍受字节序与对齐影响——先按 ph12 的显式读写把字节流解析好，再谈映射访问

**跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：C 的 fsync 是 POSIX 直通；Go 的 `os.File.Sync` / `f.Sync` 包 fsync；Rust 的 `File::sync_all` / `sync_data`（对应 fdatasync）；Python 的 `os.fsync`；Java 的 `FileChannel.force(true/false)` 对应"含/不含元数据"。**各语言的持久化原语底层都是同一个 fsync**——语法不同，刷盘语义一致；而 mmap 在 Go（`mmap` 包）、Rust（`memmap2`）、Python（`mmap` 模块）里都有封装，同样共享"缺页调入 + 页缓存"内核机制。

## 6. 代码示例

> 完整可运行文件在 [`examples/`](./examples/) 目录（编译/运行命令与验证状态见其 README）。本阶段示例均为**正常工程代码**，无故意出错演示，可任意编译运行。以下所有实测输出来自 Apple clang 21.0.0（macOS arm64），编译命令 `cc -Wall -Wextra -std=c11` 零警告；文档内嵌片段与对应源文件逐字一致（节选关键部分，完整文件以 examples/ 为准）。

### 示例 1：open/read/write 与文件 offset

对应 roadmap 学习内容"open、read、write、文件 offset、错误返回"。

> 运行前提：无（正常工程代码，可任意编译运行）。

```c
// examples/ex01-open-read-write.c —— open/read/write/pread/pwrite 与文件 offset（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
    /* ④ pread：从指定 offset 读，但【不推进】fd 的 offset */
    char buf[6] = {0};
    ssize_t r = pread(fd, buf, 5, 0);
    if (r < 0)
        die("pread");
    printf("pread(0) 读到 \"%s\"，read 后 offset = %lld（未变）\n",
           buf, (long long)lseek(fd, 0, SEEK_CUR));
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex01-open-read-write.c -o /tmp/ph13/ex01
# 2. 运行
/tmp/ph13/ex01
```

实测输出关键行（本机一次运行）：

```text
write(5) 返回 5 字节
write 后 offset = 5
pread(0) 读到 "hello"，read 后 offset = 5（未变）
再 read 一次: 返回 0（EOF 返回 0，不是错误）
对 O_WRONLY fd 调用 read: 返回 -1, errno = 9（Bad file descriptor）
文件大小 = 5 字节
```

解读：write 推进 offset（5），pread 不推进（仍 5），EOF 返回 0，错误返回 -1 + errno——三个"返回值的语义"一次实测齐全。

### 示例 2：短读短写与 read_full / write_full

对应 roadmap 学习内容"短读短写"。

> 运行前提：无（正常工程代码，可任意编译运行）。

```c
// examples/ex02-short-io.c —— 短读短写与 read_full / write_full 循环（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
static int write_full(int fd, const void *buf, size_t n) {
    const char *p = buf;
    size_t left = n;
    while (left > 0) {
        ssize_t w = write(fd, p, left);
        if (w < 0) {
            if (errno == EINTR)
                continue;            /* 被信号打断：重试，不算失败 */
            return -1;
        }
        p += w;
        left -= (size_t)w;           /* 短写：只推进实际写出的部分 */
    }
    return 0;
}
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex02-short-io.c -o /tmp/ph13/ex02
# 2. 运行
/tmp/ph13/ex02
```

实测输出关键行（本机一次运行）：

```text
单次 read 请求 15 字节，实际返回 3 字节（"AAA"）—— 短读
read_full(7) 返回 7 字节（"BBBBBCC"）—— 循环读齐了
对端关闭后 read_full(1) 返回 0（0 = EOF）
```

解读：父进程分 3 批（3 + 5 + 2 字节）往 pipe 写，子进程单次 read 只能拿到已到达的第 1 批——**真实的短读**；read_full 循环补齐；对端关闭后返回 0 判 EOF。

### 示例 3：fsync/fdatasync 与刷盘语义

对应 roadmap 学习内容"fsync、fdatasync"与必会概念"write 成功不代表数据已经持久化"。

> 运行前提：无（正常工程代码，可任意编译运行）。耗时数字与机器相关，以下为本文档引用的一次实测值；你的机器上数量级关系一致、绝对值会不同。

```c
// examples/ex03-fsync.c —— fsync/fdatasync 的语义与耗时实测（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64，Apple Silicon 内置 SSD）
    printf("\n结论: write 把数据交给内核 Page Cache 就返回（快）;\n");
    printf("      fsync 等数据到达存储设备（慢，次数与耗时近似成正比）;\n");
    printf("      fdatasync 不刷元数据（mtime 等），语义足够时比 fsync 便宜。\n");
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex03-fsync.c -o /tmp/ph13/ex03
# 2. 运行
/tmp/ph13/ex03
```

实测输出关键行（本机一次运行，20000 条 × 128 字节 record）：

```text
  只结尾 fsync 1 次: 总 25.5 ms（其中 flush 0.6 ms），782871 条/秒
  每 200 条 fsync:   总 36.4 ms（其中 flush 5.3 ms），549119 条/秒
  每条都 fsync:      总 439.7 ms（其中 flush 385.0 ms），45485 条/秒
  每次 fsync      : flush 累计 31.5 ms，31725 次/秒
  每次 F_FULLFSYNC: flush 累计 4051.7 ms，247 次/秒
```

解读：刷盘次数决定成本（每条 fsync 比只结尾慢约 17 倍）；macOS 上 fsync 只到设备缓存，F_FULLFSYNC 才到介质（慢两个数量级）——Linux 的 fsync 本身就是真落盘语义，无此区分。

### 示例 4：Page Cache 的存在与影响

对应 roadmap 必会概念"Page Cache 会影响读写性能和基准测试结果"。

> 运行前提：无（正常工程代码，可任意编译运行）。耗时会写 /tmp 下 256 MiB 临时文件，运行后自动删除。

```c
// examples/ex04-pagecache.c —— Page Cache 的存在与影响实测（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64，Apple Silicon 内置 SSD）
static void evict_page_cache(int fd, size_t len) {
    void *m = mmap(NULL, len, PROT_READ, MAP_SHARED, fd, 0);
    if (m == MAP_FAILED)
        die("mmap");
    if (msync(m, len, MS_SYNC | MS_INVALIDATE) < 0)
        die("msync");
    munmap(m, len);
}
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex04-pagecache.c -o /tmp/ph13/ex04
# 2. 运行
/tmp/ph13/ex04
```

实测输出关键行（本机一次运行，256 MiB 文件）：

```text
写 256 MiB: write 阶段 57.8 ms（4431 MiB/s —— 进了 Page Cache）
热读（写完立即读, Page Cache 命中）: 17.7 ms（14472 MiB/s）
冷读（msync(MS_INVALIDATE) 逐出缓存后）: 42.6 ms（6010 MiB/s）
再热读（重新进了缓存）: 14.2 ms（18074 MiB/s）
三遍数据一致: 是；Page Cache 命中加速约 2.4 倍
```

解读：write 的 4431 MiB/s 是"进 Page Cache"的速度，不是磁盘速度；冷读（缓存被逐出）比热读慢 2.4 倍——基准测试必须先想清楚缓存命中。

### 示例 5：mmap/munmap/msync 与 mmap vs read

对应 roadmap 学习内容"mmap、munmap、msync"与必会概念"mmap 适合随机读和只读索引，但错误处理更复杂"。

> 运行前提：无（正常工程代码，可任意编译运行）。耗时会写 /tmp 下 256 MiB 临时文件，运行后自动删除。

```c
// examples/ex05-mmap.c —— mmap/munmap/msync 与 mmap vs read 实测对比（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64，Apple Silicon 内置 SSD）
    unsigned *p = mmap(NULL, (size_t)st.st_size, PROT_READ, MAP_SHARED, fd, 0);
    if (p == MAP_FAILED)
        die("mmap");
    /* 映射建立后 fd 即可关闭，映射本身继续持有文件 */
    close(fd);
    /* ...magic 校验、count 与文件长度校验... */
    unsigned count = p[1];
    unsigned long long sum = 0;
    for (unsigned i = 0; i < count; i++)
        sum += p[2 + i];              /* 像访问数组一样访问文件内容 */
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex05-mmap.c -o /tmp/ph13/ex05
# 2. 运行
/tmp/ph13/ex05
```

实测输出关键行（本机一次运行，256 MiB 逐页触摸求和）：

```text
索引文件 28 字节
magic 校验通过, 5 个值求和 = 150（mmap 当数组读）
MAP_SHARED 写 + msync 后, pread 读回: "written via mmap"
  read(1 MiB 块): 15.1 ms（16994 MiB/s）
  mmap 直接访问: 9.9 ms（25864 MiB/s）
```

解读：mmap 把文件当数组读、映射后 fd 可关闭、MAP_SHARED 写 + msync 后 pread 验证确实落盘；mmap 比 read 快约 1.5 倍（省拷贝与系统调用），代价是缺页与 SIGBUS 错误模型。

### 示例 6：append-only 日志与崩溃恢复

对应 roadmap 学习内容"append-only 文件写入"、"崩溃恢复中的刷盘边界"与必会概念"存储引擎必须明确哪些数据需要 fsync"。

> 运行前提：无（正常工程代码，可任意编译运行）。

```c
// examples/ex06-append-only.c —— append-only 日志：O_APPEND 追加 + 截断尾检测回放（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
        if (r < (ssize_t)HDR_SIZE)
            goto torn;                   /* 头部没写全 = 截断 */
        uint32_t len = read_be32(hdr);
        uint32_t crc = read_be32(hdr + 4);
        if (len > MAX_PAYLOAD)
            goto torn;                   /* 长度非法 = 损坏 */
        /* ...payload 读不齐 / crc 不符也 goto torn... */
        if (crc32(payload, len) != crc)
            goto torn;                   /* 半写入/位翻转 = 损坏 */
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex06-append-only.c -o /tmp/ph13/ex06
# 2. 运行
/tmp/ph13/ex06
```

实测输出关键行（本机一次运行）：

```text
① 追加 5 条记录并 fsync
② 模拟半写入：追加一条只写了 3 字节头部的残记录
  回放停在偏移 98（损坏/截断记录被安全跳过）
③ 回放结果：恢复 5 条完整记录
④ ftruncate 到 98 修复残尾，文件可继续安全追加
```

解读：O_APPEND 追加 + 尾部长度/CRC 校验，让"崩溃只留下最后一条残记录"；残记录被识别、截掉即恢复——这就是 WAL 的恢复原理。

## 7. 总结

### 关键要点

1. **write 成功不代表数据已经持久化**（roadmap 必会概念）：write 只进 Page Cache，fsync/fdatasync 返回才是"到达存储设备"的承诺边界；macOS 上 fsync 只到设备缓存，F_FULLFSYNC 才到介质（3.4/4.3）
2. **read/write 的返回值是实际字节数**：可能短读短写；返回 0 是 EOF、返回 -1 才是错误、EINTR 要重试——所有文件/socket 读写一律包 read_full/write_full 循环（3.2，示例 2）
3. **pread/pwrite 不推进 offset**：随机读不需要 lseek 往返，多线程共享 fd 时比"lseek+read"原子（3.3，练习 1）
4. **Page Cache 会影响读写性能和基准测试结果**（roadmap 必会概念）：热读/冷读差 2.4 倍（示例 4）；"刚写完就读"测的是缓存速度，不是磁盘速度（3.5）
5. **mmap 适合随机读和只读索引，但错误处理更复杂**（roadmap 必会概念）：当数组访问、fd 可关、省拷贝；错误是 SIGBUS 信号而非返回值，写场景慎用（3.6，示例 5）
6. **存储引擎必须明确哪些数据需要 fsync**（roadmap 必会概念）：刷盘次数与耗时近似成正比（示例 3 实测慢 17 倍）；"承诺持久化的最小单位 = 一次 fsync 前的全部记录"（3.8）
7. **进程崩溃不丢 Page Cache 数据，断电才丢**：kill -9 只杀进程、不杀内核缓存（练习 4 实证）；fsync 防的是断电，不是进程崩溃（3.5/3.8）
8. **append-only + 长度/CRC 让崩溃只留下最后一条残记录**：回放停在残尾偏移，ftruncate 截掉即恢复——WAL 的恢复原理（3.7/3.8，示例 6，project/）
9. **mmap 前三个检查不能少**：空文件/长度 < 头部不许 mmap、magic 校验、count 与文件实际长度吻合——不信任文件里的长度声明（3.6，练习 3）

### 跨语言对比：可靠文件 IO

| 维度 | C（本阶段） | Go | Rust | Python | Java |
|------|------------|-----|------|--------|------|
| 刷盘 | fsync / fdatasync（POSIX 直通） | `f.Sync()` | `sync_all()` / `sync_data()` | `os.fsync()` | `FileChannel.force(true/false)` |
| 追加写 | open + O_APPEND + write | `os.OpenFile(..., O_APPEND, ...)` | `OpenOptions().append(true)` | `open(..., 'a')` | `Files.newBufferedWriter(..., APPEND)` |
| 内存映射 | mmap/munmap/msync | `syscall.Mmap` / x/sys | `memmap2` crate | `mmap` 模块 | `FileChannel.map()` |
| Page Cache 感知 | posix_fadvise / F_NOCACHE | 无直接接口 | 无 | 无 | 无 |

各语言把"刷盘"包装成 Sync 类方法、把"映射"包装成库，**底层都是同一个内核机制**：数据是否持久看 fsync 是否返回，性能是否可信先问 Page Cache（为 analysis/ 与 Tenet 合成积累素材）。

### 阶段验收清单

- [ ] 能解释 Page Cache 与磁盘持久化的关系：write 到哪一层、fsync 到哪一层、断电丢哪一层（3.4/4.3）
- [ ] 能实现可靠追加写入：O_APPEND + write_full + 明确刷盘边界，崩溃后回放不丢完整记录（3.7/3.8，练习 2/4）
- [ ] 能说明 mmap 和 read/write 的适用场景：只读索引用 mmap、写与错误处理用 read/write，理由充分（3.6/5，练习 3）
- [ ] 能处理短读短写与错误返回：full 循环、EINTR 重试、EOF 与 -1 区分（3.2，练习 1/2）
- [ ] 能识别崩溃残尾并修复：长度/CRC 判定、ftruncate 截尾、恢复可追加状态（3.8，示例 6，project/）
- [ ] 能指出基准测试里的 Page Cache 陷阱：热读 vs 冷读、刚写完就读的吞吐不是磁盘速度（3.5，示例 4）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。四题与 roadmap ph13「练习」一一对应：

- 用 pread 按 offset 读取 record（★）
- 实现 append-only log（★★）
- 用 mmap 读取只读数据文件（★★）
- 模拟进程崩溃后的 log replay（★★★，fork + 真实 SIGKILL）

完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**kvlog——可靠 append-only log**——对应 roadmap 推荐项目「append-only log」（第二个推荐项目「mmap 只读索引文件」由示例 5 与练习 3 覆盖），一个带 magic + 长度 + CRC32 的日志库与命令行工具（`make` 构建 / `make test` 自测 / `make demo` 演示写/读/崩溃/残尾/损坏 / `make san` Sanitizer 复跑），把"write 成功 ≠ 持久化、崩溃最多留下最后一条残记录、长度/CRC 识别后截掉即恢复"三条核心纪律落地成可运行代码——即 WAL 的原型，ph16 数据库存储引擎基础阶段的 WAL replay 将直接复用它。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`make test` 退出码 0、`make demo` 演示链全过、`make clean` 零残留）

### 下一阶段

本阶段是当前已完成目录的最后一个阶段（ph13 之后暂无 ph 目录）：**ph14+（roadmap 第 14 节，目录待建）：后续可深入 C 与 C++ / Python / Rust 互操作** — 本阶段解决了"怎么可靠地落盘与刷盘"，ph14 将解决"怎么把写好的 C 库暴露给其他语言"：C ABI、动态库导出符号、opaque pointer、create/destroy 生命周期约定——本阶段 project/ 的 kvlog 库（kvl.h/kvl.c）正是 ph14 做「C ABI KV 插件接口」「Rust 调用 C WAL 库」时的现成 C 库载体；再往后 ph16 数据库存储引擎基础阶段将把本阶段的 append-only log 升级为完整 WAL + MemTable + SSTable 的存储引擎 IO 底座。
