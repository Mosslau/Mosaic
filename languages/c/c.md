# C 语言学习 Roadmap

> 面向系统底层、数据库存储引擎、KV 库、跨语言 ABI 与高性能运行时基础，从语法基础逐步走到可维护的系统级 C 代码。

## 1. 基础语法阶段

> 📖 详细展开版见 [ph01-basic-syntax/01-basic-syntax.md](./ph01-basic-syntax/01-basic-syntax.md)

### 目标
能读懂并写出简单 C 程序，理解编译、链接和可执行文件的基本关系。

### 学习内容
- C 程序结构、源文件 .c、头文件 .h
- main 函数、标准输入输出、注释
- 变量、常量、基本数据类型
- 运算符、条件判断、循环控制
- 编译与运行：gcc main.c -o app

### 必会概念
- 编译和链接不是一回事
- 栈上变量的生命周期由作用域决定
- 整数、浮点和字符类型都有范围限制
- if、switch、for、while 是基础控制流

### 示例
```c
#include <stdio.h>

int main(void) {
    printf("Hello, C\n");
    return 0;
}
```

### 练习
- 计算器
- 九九乘法表
- 判断素数
- 数组最大值、最小值、平均值

### 阶段验收
- 能独立编译并运行单文件 C 程序
- 能解释 main 的返回值含义
- 能用循环和条件分支解决基础题目

### 推荐项目
- 命令行计算器
- 成绩等级判断工具

## 2. 函数与模块化阶段

> 📖 详细展开版见 [ph02-func-module/02-func-module.md](./ph02-func-module/02-func-module.md)

### 目标
把代码拆成函数和模块，避免所有逻辑堆在 main 中。

### 学习内容
- 函数定义、声明、调用
- 参数传递、返回值、递归
- 局部变量、全局变量、作用域
- .h 与 .c 分离
- 多文件编译

### 必会概念
- C 默认按值传递参数
- 头文件放声明，源文件放实现
- static 可限制函数或全局变量的链接范围
- 递归必须有明确终止条件

### 示例
```text
project/
├── main.c
├── math_utils.c
└── math_utils.h
```

### 练习
- 字符串工具库
- 数组排序工具库
- 递归阶乘与斐波那契
- 把单文件程序拆成多个 .c/.h

### 阶段验收
- 能解释声明和定义的区别
- 能写出可复用函数
- 能完成一个多文件小项目并成功链接

### 推荐项目
- 小型数学工具库
- 通讯录程序模块化重构

## 3. 数组、字符串、指针阶段

> 📖 详细展开版见 [ph03-array-str-ptr/](ph03-array-str-ptr/03-array-str-ptr.md)

### 目标
真正理解 C 的内存模型，掌握数组、字符串和指针的关系。

### 学习内容
- 一维数组、二维数组、字符数组
- 字符串结束符 \0
- 指针基础、指针运算
- 指针与数组的关系
- 函数参数中的指针
- strlen、strcpy、strcmp、strcat

### 必会概念
- 数组名在多数表达式中会退化为指向首元素的指针
- 字符串本质是以 \0 结尾的字符数组
- 指针保存地址，解引用访问地址上的值
- 指针越界访问是未定义行为

### 示例
```c
int arr[3] = {1, 2, 3};
int *p = arr;
printf("%d\n", *(p + 1));
```

### 练习
- 手写 strlen
- 手写 strcpy
- 手写 strcmp
- 数组反转、字符串反转、查找子串

### 阶段验收
- 能画出数组和指针在内存中的关系
- 能解释 arr 与 &arr 的区别
- 能写出不越界的字符串处理代码

### 推荐项目
- 字符串处理库
- 简单文本统计工具

## 4. 内存管理阶段

> 📖 详细展开版见 [ph04-memory-mgmt/](ph04-memory-mgmt/04-memory-mgmt.md)

### 目标
能安全使用堆内存，避免泄漏、越界、悬空指针和野指针。

### 学习内容
- 栈内存与堆内存
- malloc、calloc、realloc、free
- NULL 检查
- 内存泄漏、越界访问、use-after-free
- sizeof 的正确使用

### 必会概念
- 谁申请，谁释放
- free 后指针最好置为 NULL
- sizeof(ptr) 和 sizeof(*ptr) 含义不同
- 动态数组扩容需要处理失败路径

### 示例
```c
int *p = malloc(sizeof(int) * 10);
if (p == NULL) {
    return 1;
}

free(p);
p = NULL;
```

### 练习
- 动态数组
- 动态字符串
- 简单内存池
- 用 Valgrind 或 ASan 检查内存问题

### 阶段验收
- 能解释常见内存错误
- 能写出申请、扩容、释放完整路径
- 能使用工具定位内存泄漏或越界

### 推荐项目
- 动态数组库
- 固定块内存池

## 5. 结构体与数据结构阶段

> 📖 详细展开版见 [ph05-struct-datastruct/](ph05-struct-datastruct/05-struct-datastruct.md)

### 目标
用 C 表达复杂数据，并实现常用数据结构。

### 学习内容
- struct、typedef
- 结构体指针、结构体数组、嵌套结构体
- enum、union、位域
- 链表、栈、队列、哈希表、树、堆、图

### 必会概念
- 点号访问对象成员，箭头访问指针指向对象的成员
- 结构体内存布局受对齐影响
- 链表节点所有权需要明确
- 数据结构应提供清晰的初始化和销毁接口

### 示例
```c
typedef struct {
    int id;
    int speed;
    int enabled;
} Motor;
```

### 练习
- 单链表增删改查
- 栈实现括号匹配
- 队列模拟任务调度
- 哈希表统计词频

### 阶段验收
- 能为结构体设计初始化、更新、销毁函数
- 能实现至少链表、栈、队列三种结构
- 能解释结构体对齐对大小的影响

### 推荐项目
- 内存表 / HashMap KV 表
- 通用链表库

## 6. 文件操作阶段

> 📖 详细展开版见 [ph06-file-io/06-file-io.md](./ph06-file-io/06-file-io.md)

### 目标
能读写文件并处理持久化数据。

### 学习内容
- fopen、fclose、fread、fwrite
- fprintf、fscanf、fgets、fputs
- 文本文件与二进制文件
- fseek、ftell、rewind

### 必会概念
- 文件打开后必须关闭
- 文本格式便于调试，二进制格式更紧凑
- fgets 通常比不受限读取更安全
- IO 操作必须检查返回值

### 示例
```c
FILE *fp = fopen("data.txt", "r");
if (fp == NULL) {
    return 1;
}

char line[128];
while (fgets(line, sizeof(line), fp) != NULL) {
    printf("%s", line);
}

fclose(fp);
```

### 练习
- 读取配置文件
- CSV 文件解析
- 日志系统
- 二进制文件读写结构体数据

### 阶段验收
- 能处理文件不存在、权限不足、格式错误
- 能读写文本和二进制文件
- 能设计简单持久化格式

### 推荐项目
- CSV 解析器
- append-only 数据文件

## 7. 编译、调试与工程化阶段

> 📖 详细展开版见 [ph07-build-debug/07-build-debug.md](./ph07-build-debug/07-build-debug.md)

### 目标
像工程项目一样组织、构建和调试 C 代码。

### 学习内容
- gcc、clang
- -Wall、-Wextra、-g、-O2
- 静态库 .a、动态库 .so
- Makefile、CMake
- GDB 调试、断点、单步执行、查看变量
- core dump 分析

### 必会概念
- 警告要当成质量信号处理
- Debug 构建和 Release 构建目标不同
- Makefile 描述依赖关系，不只是命令集合
- 调试器比打印日志更适合定位崩溃

### 示例
```bash
gcc -Wall -Wextra -g main.c -o app
gdb ./app
```

### 练习
- 给前面项目写 Makefile
- 用 GDB 调试段错误
- 封装静态库
- 写一个多文件 C 项目

### 阶段验收
- 能从编译错误和链接错误中定位问题
- 能用 GDB 找到崩溃位置
- 能编写基础 Makefile 或 CMakeLists.txt

### 推荐项目
- 多模块命令行工具
- 静态库形式的数据结构库

## 8. Linux 系统编程阶段

> 📖 详细展开版见 [ph08-linux-sysprog/08-linux-sysprog.md](./ph08-linux-sysprog/08-linux-sysprog.md)

### 目标
能写系统级程序，理解进程、线程、文件描述符和 socket。

### 学习内容
- Linux 文件描述符
- open、read、write、close
- fork、exec、wait
- pthread_create、pthread_join
- mutex、condition variable
- signal、pipe、socket、TCP/UDP
- select、poll、epoll 基础

### 必会概念
- 文件描述符是一类统一的内核资源句柄
- 进程隔离资源，线程共享进程地址空间
- 多线程必须处理竞态和死锁
- 网络 IO 必须考虑超时、半包和错误返回

### 示例
```c
int fd = open("data.txt", O_RDONLY);
if (fd < 0) {
    return 1;
}
close(fd);
```

### 练习
- 简单 shell
- 多线程下载器
- TCP echo server
- 简单 HTTP server
- 日志采集程序

### 阶段验收
- 能解释进程与线程的区别
- 能写出基础 TCP 服务端
- 能处理线程同步问题

### 推荐项目
- TCP echo server
- 多线程任务队列

## 9. C 标准、编译器与可移植性

### 目标
理解不同 C 标准和编译器差异，写出更可移植的代码。

### 学习内容
- C89、C99、C11、C17、C23 基本差异
- GCC、Clang、MSVC 差异
- 标准库与平台 API 边界
- 条件编译与平台抽象
- 固定宽度整数：stdint.h

### 必会概念
- 不同平台上 int、long、指针宽度可能不同
- 标准 C 与 POSIX/Linux API 不是一回事
- 编译器扩展会降低可移植性
- 使用 uint32_t 等类型能明确协议字段宽度

### 示例
```c
#include <stdint.h>

uint32_t id = 0x12345678u;
```

### 练习
- 用 stdint.h 重写协议字段定义
- 为 Windows/Linux 分别封装路径分隔符
- 尝试用 GCC 和 Clang 编译同一项目

### 阶段验收
- 能说明 C 标准和平台 API 的区别
- 能避免依赖未声明的编译器扩展
- 能写出跨平台类型定义

### 推荐项目
- 跨平台日志库
- 协议字段类型定义库

## 10. 未定义行为 UB 与常见坑

### 目标
识别并避免 C 中最危险的一类错误。

### 学习内容
- 数组越界
- 空指针解引用
- 悬空指针、重复释放
- 有符号整数溢出
- 未初始化变量
- 严格别名、对齐访问

### 必会概念
- 未定义行为不是“结果不确定”，而是编译器可做任何假设
- UB 可能在优化级别变化后暴露
- 越界写通常比越界读更危险
- 初始化和边界检查是 C 代码的生命线

### 示例
```c
int arr[3] = {1, 2, 3};
/* arr[3] = 4;  // 越界，未定义行为 */
```

### 练习
- 收集 10 个常见 UB 示例并修复
- 用 ASan 检查越界和 use-after-free
- 给字符串处理函数补边界检查

### 阶段验收
- 能解释至少 5 种 UB
- 能使用工具复现并定位 UB
- 能在代码评审中主动发现危险写法

### 推荐项目
- C 常见坑示例库
- 安全字符串工具库

## 11. Sanitizer / 静态分析 / 单元测试

### 目标
建立 C 代码质量工具链，减少运行时事故。

### 学习内容
- AddressSanitizer、UndefinedBehaviorSanitizer
- Valgrind
- cppcheck、clang-tidy
- 单元测试框架：Unity、CMocka、Criterion
- 覆盖率：gcov/lcov

### 必会概念
- 动态检测和静态分析互补
- Sanitizer 适合开发和 CI，不一定适合生产发布
- 单元测试应覆盖边界输入和错误路径
- 内存错误越早发现越便宜

### 示例
```bash
gcc -fsanitize=address,undefined -g main.c -o app
./app
```

### 练习
- 给动态数组库写单元测试
- 用 ASan 修复越界问题
- 用 cppcheck 检查一个项目
- 生成覆盖率报告

### 阶段验收
- 能在 CI 或本地一键运行测试
- 能解释 ASan 报告中的栈信息
- 能用测试覆盖核心边界条件

### 推荐项目
- 带测试的数据结构库
- 带 Sanitizer 构建选项的 CMake 模板
- 带测试的 WAL / buffer 库

## 12. 字节序、内存对齐与二进制格式解析

### 目标
能处理数据库文件、WAL 日志、SSTable block、网络 frame 和跨平台二进制数据布局。

### 学习内容
- 大端、小端
- 结构体对齐、padding
- sizeof 与字段偏移
- 位运算、掩码、移位
- 网络字节序
- 二进制 record 解析
- length-prefix frame
- checksum / CRC
- varint 编码基础
- 文件格式版本号与 magic number

### 必会概念
- 不要直接把不可信字节强转成结构体指针
- 多字节字段必须明确字节序
- 多数二进制解析应先检查长度再读取字段
- 对齐不一致会导致性能问题，甚至触发未定义行为
- 二进制格式要考虑版本兼容和损坏检测
- checksum 能帮助发现半写入、截断和数据损坏

### 示例
```c
uint16_t read_be16(const uint8_t *buf) {
    return ((uint16_t)buf[0] << 8) | buf[1];
}

typedef struct {
    uint32_t magic;
    uint16_t version;
    uint16_t type;
    uint32_t key_len;
    uint32_t value_len;
    uint32_t checksum;
} RecordHeader;
```

### 练习
- 解析固定格式二进制 record
- 实现大端、小端转换函数
- 实现 length-prefix frame 解析器
- 实现 varint 编码和解码
- 为 WAL record 设计 header 和 checksum
- 解析 SSTable block header
- 设计二进制文件 magic number 和版本字段

### 阶段验收
- 能解释结构体 padding
- 能安全解析长度可变 record
- 能避免字节序导致的跨平台错误
- 能识别截断、长度不足和 checksum 错误
- 能设计一个可演进的二进制文件头

### 推荐项目
- WAL record 解析器
- length-prefix frame parser
- 二进制数据文件解析库
- SSTable block header parser

## 13. mmap、Page Cache 与可靠文件 IO 阶段

### 目标
理解数据库和 KV 存储依赖的文件 IO、Page Cache、mmap 和刷盘语义。

### 学习内容
- open、read、write、pread、pwrite
- fsync、fdatasync
- mmap、munmap、msync
- Page Cache 基础
- append-only 文件写入
- 文件 offset、短读短写、错误返回
- 崩溃恢复中的刷盘边界

### 必会概念
- write 成功不代表数据已经持久化
- Page Cache 会影响读写性能和基准测试结果
- mmap 适合随机读和只读索引，但错误处理更复杂
- 存储引擎必须明确哪些数据需要 fsync

### 示例
```text
可用 `open + write + fsync` 的小例子。
```

### 练习
- 实现 append-only log
- 用 pread 按 offset 读取 record
- 用 mmap 读取只读数据文件
- 模拟进程崩溃后的 log replay

### 阶段验收
- 能解释 Page Cache 与磁盘持久化的关系
- 能实现可靠追加写入
- 能说明 mmap 和 read/write 的适用场景

### 推荐项目
- append-only log
- mmap 只读索引文件

## 14. C 与 C++ / Python / Rust 互操作

### 目标
理解 C ABI 的边界，用 C 作为跨语言接口层。

### 学习内容
- C ABI、头文件接口
- C++ 调 C、C 调 C++ 包装层
- Python ctypes / C 扩展
- Rust FFI：extern C
- 动态库导出符号
- opaque pointer
- create/destroy API
- 错误码与错误消息

### 必会概念
- 跨语言接口应使用简单稳定的 C 类型
- 内存分配和释放必须在同一侧约定清楚
- 字符串、数组、结构体都要定义所有权规则
- ABI 稳定比源码语法更重要

### 示例
```c
#ifdef __cplusplus
extern "C" {
#endif

int add(int a, int b);

#ifdef __cplusplus
}
#endif
```

### 练习
- 编译一个 C 动态库给 Python 调用
- 用 C++ 包装 C 接口
- 用 Rust 调用 C 函数
- 设计跨语言错误码

### 阶段验收
- 能解释 ABI 与 API 的区别
- 能写出稳定的 C 头文件接口
- 能明确跨语言内存所有权

### 推荐项目
- C ABI KV 插件接口
- Python 调用 C buffer 解析库
- Rust 调用 C WAL 库

## 15. 阶段性项目验收标准

### 目标
用项目验证学习成果，而不是只背语法点。

### 学习内容
- 阶段项目拆解
- 功能验收、质量验收、测试验收
- README、构建脚本、运行说明
- 错误路径与边界条件

### 必会概念
- 好项目要能构建、能运行、能测试、能说明
- 阶段验收应包括代码质量，而不只是功能完成
- 每个项目都应有最小可复现用例

### 示例
```text
验收项：
- make test 通过
- ASan 无错误
- README 写明构建和运行方式
- 错误输入有明确处理
```

### 练习
- 给已有项目补 README
- 给已有项目补测试用例
- 给已有项目开启警告和 Sanitizer

### 阶段验收
- 初级：完成单文件工具并处理错误输入
- 中级：完成多文件项目、Makefile、测试
- 高级：完成网络 / 存储 / 二进制格式类项目并通过工具检查

### 推荐项目
- C 学习项目集
- 可复用 C 工程模板

## 16. 高级 C 与代码质量阶段

### 目标
写出稳定、可维护、可移植的 C 代码。

### 学习内容
- 宏技巧、条件编译
- 函数指针、回调函数
- 状态机、错误码设计
- 日志系统、trace id、诊断信息
- API 设计、跨平台兼容
- handle-based API、opaque pointer

### 必会概念
- 宏要少而清晰，避免隐藏副作用
- 回调适合解耦模块，但要约定上下文和生命周期
- 状态机适合解析器、任务调度、连接管理和存储恢复流程
- 错误码设计要稳定、可追踪

### 示例
```c
typedef void (*event_handler_t)(int event, void *ctx);
```

### 练习
- 通用状态机框架
- 事件驱动框架
- 命令行解析器
- ring buffer
- 可复用 WAL / frame 解析库

### 阶段验收
- 能设计清晰模块边界
- 能避免宏副作用和全局状态滥用
- 能写出可测试的 C API

### 推荐项目
- 状态机框架
- 系统级日志库

## 17. 数据库存储引擎基础阶段

### 目标
面向 KV 库、数据库内核和时序存储原型，理解 WAL、MemTable、SSTable、B+Tree、LSM 和 Buffer Pool 的基础实现。

### 学习内容
- WAL record 设计
- append-only log 与 replay
- MemTable
- SSTable 文件格式
- Bloom Filter
- B+Tree 基础
- LSM Tree 基础
- Buffer Pool / LRU Cache
- range scan 与 iterator

### 必会概念
- WAL 用于崩溃恢复
- SSTable 是不可变有序文件
- Bloom Filter 用于减少无效查询
- LSM 通过顺序写提升写入吞吐，但会引入 compaction 成本
- Buffer Pool 需要处理缓存命中、脏页和淘汰策略

### 示例
```c
// 可以给一个 WAL record layout
// | magic | type | key_len | value_len | payload | checksum |
```

### 练习
- 实现 WAL append / replay
- 实现 Mini SSTable writer / reader
- 实现 Bloom Filter
- 实现 LRU Cache
- 实现简化 B+Tree 或 LSM 文件层

### 阶段验收
- 能通过 WAL 恢复 put/delete 操作
- 能按 key 查询 SSTable
- 能解释 B+Tree 与 LSM 的差异
- 能说明读放大、写放大、空间放大

### 推荐项目
- Mini WAL
- Mini SSTable
- 简化 LSM KV 文件层
- Buffer Pool toy

# 推荐学习顺序

```text
基础语法
→ 函数与模块化
→ 数组、字符串、指针
→ 内存管理
→ 结构体与数据结构
→ 文件操作
→ Makefile / GDB
→ Linux 系统编程
→ UB / Sanitizer / 测试
→ 字节序 / 二进制格式解析
→ mmap / Page Cache / fsync
→ C ABI / FFI
→ WAL / SSTable / B+Tree / LSM
→ SIMD / CUDA C 基础
```

# 项目路线

## 初级项目
- 计算器
- 文本文件统计工具
- 字符串处理库
- 动态数组库
- 二进制 buffer 工具库

## 中级项目
- 动态数组库
- 链表库
- HashMap KV 表
- 日志系统
- CSV / 二进制 record 解析器
- 简单 shell
- append-only log

## 高级项目
- HTTP server
- 多线程任务队列
- 内存池
- ring buffer
- Mini WAL
- Mini SSTable
- Bloom Filter
- LRU Cache
- 简化 B+Tree
- 简化 LSM 文件层
- C ABI 插件接口

# 对你最有用的路线

如果目标是数据库内核、KV 库、向量库、AI 推理训练引擎和跨语言高性能组件，优先路线是：

```text
C 基础
→ 指针
→ 结构体
→ 位运算
→ 内存管理
→ Linux 文件 IO
→ mmap / Page Cache
→ 二进制格式解析
→ WAL
→ SSTable / B+Tree / LSM
→ C ABI / FFI
→ SIMD / CUDA C 基础
```

重点掌握：指针、结构体、位运算、内存布局、对齐、allocator、mmap、fsync、WAL、SSTable、B+Tree、LSM、Bloom Filter、LRU Cache、C ABI、动态库、GDB、Makefile/CMake、ASan/UBSan、perf。
