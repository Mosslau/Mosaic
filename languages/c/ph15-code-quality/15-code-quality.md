# C 语言 高级 C 与代码质量阶段

> 面向"从会写 C 到把 C 写成可维护的系统代码"——本阶段把散落在前 14 个阶段里的工程经验收敛成方法论：宏怎么写才不咬人、函数指针与回调如何解耦、表驱动状态机怎么搭、错误码如何稳定可追踪、日志系统如何用 trace id 做诊断、handle-based API 与 opaque pointer 如何把库的边界立住，以及这些约定如何跨平台落地。全部结论都有本环境实测背书（副作用双求值、回调顺序、状态转移序列、日志级别过滤、错误码路径）。

## 1. 概述

高级 C 与代码质量阶段是 C 学习路线从"能写"到"能维护"的转折点。目标（roadmap §15）：**写出稳定、可维护、可移植的 C 代码**。ph01~ph08 建立了语法与系统编程基本功，ph09~ph14 解决了"类型宽度、UB、Sanitizer、字节序、文件 IO、跨语言 ABI"这些单个主题——本阶段回答它们之上那个共性问题：**一段 C 代码怎样才算"写得好"，以及怎么用语言机制把"好"固化下来**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 宏技巧与条件编译 | 副作用陷阱正反例；do-while(0)；可变参宏（##__VA_ARGS__ 与 C23 __VA_OPT__）；X-Macro 单表多产物 |
| 函数指针与回调 | typedef 形态；函数指针数组；回调 + void *ctx 上下文约定；ctx 生命周期谁负责 |
| 状态机 | 表驱动（转移表 + 动作函数指针）；非法事件返回错误码；状态序列可自测 |
| 错误码设计 | 0 成功/负数错误；显式赋值 + 历史锁定（发布不改值、新增只追加）；错误详情出参可追踪 |
| 日志系统 | 级别与阈值过滤；trace id 贯穿请求；时间/文件:行诊断；LOG 宏自动带调用点 |
| handle-based API / opaque pointer | create/destroy 生命周期；结构体藏 .c；借用指针注释；衔接 ph14 的句柄心智 |
| API 设计与跨平台 | 前缀命名、错误码契约、条件编译平台层、内部零全局状态 |

这个阶段只涉及"纯 C 库/组件怎么写才稳"的方法论与机制，**不涉及未定义行为的系统排查（ph10 未定义行为 UB 与常见坑阶段：越界、悬垂、别名、溢出案例）、Sanitizer 与单测工具链（ph11 Sanitizer / 静态分析 / 单元测试阶段）、字节序与二进制格式的位级处理（ph12 字节序、内存对齐与二进制格式解析阶段）、mmap/fsync/Page Cache 与落盘（ph13 mmap、Page Cache 与可靠文件 IO 阶段）和跨语言 ABI 互操作（ph14 C 与 C++ / Python / Rust 互操作阶段）** — 那些是 ph10/ph11/ph12/ph13/ph14 阶段的内容；存储引擎的完整 WAL/MemTable/SSTable 实现属 ph16 数据库存储引擎基础阶段（roadmap 第 16 节，目录待建），本阶段的 ring buffer / frame 解析组件只做"可复用组件 API"的教学载体，落盘与格式细节不展开；平台差异的完整抽象（特征宏清单、LP64/LLP64、GCC/Clang/MSVC 差异）属 ph09 C 标准、编译器与可移植性阶段，本阶段只在其结论之上讲"API 怎么设计"。回调的线程安全分发属 ph08 Linux 系统编程阶段的并发专题，本阶段一律单线程演示。

## 2. 来源与演变

**C 的"代码质量方法论"大多不是语言标准给的，而是社区几十年踩坑沉淀的惯例**——宏的陷阱从预处理器的设计而来，回调与上下文从函数指针的朴素能力长出来，错误码的稳定性教训则写在 errno 的历史里。理解这些惯例"为什么长这样"，才知道哪些要遵守、哪些可以打破。

**设计哲学一句话：能用数据描述的行为就不要用控制流写死**——转移表、选项表、回调表都是"把行为数据化"，换来的是可扩展、可测试、可排查；而宏、错误码、日志这类"跨调用点约定"，稳定性和可追踪性优先于语法上的便利。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| C 预处理器成型 | 1970s | 宏（#define）随 C 诞生；早期把宏当"文本替换的常量/函数"，副作用陷阱随之而来 |
| do-while(0) 惯例 | 1980s | 社区发现块语句宏在 if/else 下错挂 else，逐步确立 do{...}while(0) 包装惯例 |
| 函数指针 | 1970s（K&R） | C 一直支持函数指针；qsort 的比较器（void * 参数）成为"回调 + ctx"的教科书 |
| errno 的教训 | 1970s 起 | errno 是全局/线程局部变量：中间调用覆盖、跨层难传——现代库转向"返回错误码" |
| X-Macro 技巧 | 2000s（社区） | 用"宏表 + 换 X 展开"让枚举、字符串表、解析函数同源生成，杜绝手工不同步 |
| opaque pointer | 1980s（FILE *） | stdio 的 FILE * 是最早的"结构体藏实现"；后成库 API 设计标配（create/destroy） |
| syslog / 日志级别 | 1980s（BSD syslog） | 日志级别（emerg..debug）与设施分类成型；现代库普遍实现级别阈值过滤 |
| trace id（分布式追踪） | 2010s（Dapper 等论文） | 一次请求贯穿所有日志行的唯一 id；单机组件里同样用于串联调用链 |
| C99 可变参宏 | 1999 | __VA_ARGS__ 入标准；配合 ##__VA_ARGS__（GNU 扩展）支持零可变实参 |
| C11 | 2011 | _Static_assert、_Generic 等；本文基线 |
| C23 __VA_OPT__ | 2023 | 标准化的"逗号吞并"，取代 ##__VA_ARGS__ 扩展 |

本文示例以 **C11** 为基线（与全库 ph09/ph12/ph13/ph14 同一口径；宏与 API 设计的核心机制 C11 已全部具备，C23 的 __VA_OPT__ 只作对照说明）。验证工具链：**Apple clang 21.0.0（cc，macOS arm64，ProductVersion 26.6.2）**。全部代码 `cc -Wall -Wextra -std=c11` 零警告、本机真实编译运行；**状态转移序列、回调顺序、日志级别过滤、错误码路径均为实测输出**，文档引用的输出与 examples/、exercises/、project/ 的实际运行一致。涉及 `_WIN32` 分支的示例（ex01/ex06）只验证了 POSIX/macOS 分支，Windows 分支未在本环境验证；ex05 的时间格式化用 POSIX 的 `localtime_r`（Windows 需换 `localtime_s`，本示例不处理该差异）。**变化的是工具链与标准版本，不变的是"行为数据化、稳定性优先、可追踪性优先"这三条设计惯性**。

## 3. 语法与参数

### 3.1 宏：条件编译与副作用陷阱（正反例）

宏是文本替换，**先展开后编译**——这是它所有陷阱的总根源。最经典的错误是"宏参数被求值多次"：

```c
// examples/ex01-macro-tricks.c —— 副作用陷阱正反例（节选, 完整版见 examples/）
/* 反例：宏参数只加括号不够 —— 展开后参数表达式被求值多次。
 * MAX_BAD(i++, 10) 展开为 ((i++) > (10) ? (i++) : (10))：i++ 出现了两次。 */
#define MAX_BAD(a, b) ((a) > (b) ? (a) : (b))

/* 正解：要"函数语义"就别用宏 —— static inline 函数参数只求值一次。
 * （此处演示用 int 版，见主文档 3.1：类型泛化要靠 _Generic/宏工厂，同样要避开副作用） */
static inline int imax(int a, int b) {
    return a > b ? a : b;
}
```

`MAX_BAD` 只在参数两边加括号还不够：`MAX_BAD(i++, 0)` 展开成 `((i++)>(0)?(i++):(0))`，`i++` 在比较处与真分支各出现一次——**总共被求值两次**。正解是"要函数语义就别用宏"：`static inline` 函数参数只求值一次、有类型检查、可内联，代价为零。实测（ex01，Apple clang 21.0.0）对比如下：

```c
int i = 1;
int bad = MAX_BAD(i++, 0);   /* 反例: 展开后 i++ 两次, i: 1 → 3, 结果 2 */
i = 1;
int good = imax(i++, 0);     /* 正例: 只求值一次, i: 1 → 2, 结果 1 */
```

**块语句宏要用 do-while(0) 包裹**（ex01 区 2）：宏是文本替换，多语句宏直接写成 `{ ... }` 会在 if/else 下错挂 else——`if (c) SWAP_BAD(x, y); else z = 1;` 展开后是 `if (c) { ... }; else z = 1;`，分号让 else 悬空（无匹配的 if，语法错乱或 else 误挂）。`do{...}while(0)` 把宏包成"一条语句"，if/else 与循环里都能安全使用；`while(0)` 恒假保证只执行一次，末尾分号由调用处补上：

```c
// examples/ex01-macro-tricks.c —— do-while(0) 正反例（节选, 完整版见 examples/）
/* 反例：块语句宏没有 do-while(0) 包裹，else 会挂错 */
#define SWAP_BAD(a, b) \
    { int t_ = (a); (a) = (b); (b) = t_; }

/* 正例：do{...}while(0) 让宏在语法上等价于"一条语句"，可安全跟 else */
#define SWAP(a, b) \
    do { int t_ = (a); (a) = (b); (b) = t_; } while (0)
```

ex01 区 2 实测：`if (x > y) SWAP(x, y); else z = 1;` 里 SWAP 未执行、else 分支正确命中（输出 `z=1`）。两点边界：do-while(0) 只适用于"语句位置"，需要表达式语义（如函数实参）时仍走 static inline；宏内临时变量（如上 `t_`）展开在调用处作用域，可能与调用处同名变量冲突——真实库用 `__LINE__` 拼临时名或改用 inline 函数，此处演示从简。

**条件编译**同样要服从"宏是文本替换"的纪律：`#if defined(X)` 判断的是宏是否被定义（编译期文本层），不是运行时条件——ph09 已系统讲平台差异抽象，这里只提醒它在宏定义时的两条常见坑：① `#define` 换行续接用反斜杠且**反斜杠后不能有空格**；② 函数式宏展开后是"一串 token"，必须整体加括号。

### 3.2 宏进阶：可变参宏与 X-Macro

**可变参宏**：`...` 表示可变参数，转发给 printf 族函数（日志宏的标准形态，见 3.7）：

```c
// examples/ex01-macro-tricks.c —— 可变参宏（节选, 完整版见 examples/）
/* 注释：ISO C11 的 ... 至少要有一个实参。用 GNU/Clang 的 "##" 逗号吞并扩展
 * （本仓库工具链 gcc/clang 均支持）可以让零实参调用也合法；
 * C23 提供了标准化的 __VA_OPT__(,) 代替。两种写法效果相同。 */
#define LOG(fmt, ...) \
    printf("[%s:%d] " fmt "\n", __FILE__, __LINE__, ##__VA_ARGS__)
```

ISO C11 要求 `...` 至少有一个实参；GNU/Clang 的 `##__VA_ARGS__`（逗号吞并）让零实参调用也合法——**这是最常用的移植性妥协**：gcc/clang 全支持、零警告，C23 用标准化的 `__VA_OPT__(,)` 取代。本阶段示例一律 `-std=c11` + `##__VA_ARGS__`（见 ex01 区 3 实测：`LOG("零个可变实参也合法")` 编译运行通过）。

**X-Macro**：把"一组并列条目"定义成一张宏表，再用不同展开规则生成不同产物——**一张表同时是枚举、字符串数组、查找函数的唯一事实源**：

```c
// examples/ex01-macro-tricks.c —— X-Macro 单表多产物（节选, 完整版见 examples/）
/* ============ 区 4：X-Macro ============ */

/* 1) 先定义"表格"宏：每行是一个占位调用 X(...) */
#define ERROR_TABLE(X)      \
    X(ERR_OK,       "ok")   \
    X(ERR_BADARG,   "bad argument") \
    X(ERR_NOTFOUND, "not found")    \
    X(ERR_NOMEM,    "out of memory")

/* 2) 定义 X 的一次展开规则, 然后展开表格 → 生成枚举 */
#define ERROR_DEF_ENUM(name, msg) name,
typedef enum { ERROR_TABLE(ERROR_DEF_ENUM) ERR_COUNT } err_t;
#undef ERROR_DEF_ENUM

/* 3) 换一个 X 展开规则 → 生成字符串表（顺序与枚举一致） */
#define ERROR_DEF_STR(name, msg) msg,
static const char *const err_strs[] = { ERROR_TABLE(ERROR_DEF_STR) };
#undef ERROR_DEF_STR
```

展开顺序：先定义表 → 定义某次展开的 `X` → 展开表格 → `#undef X`。X-Macro 适合"枚举 ↔ 字符串 ↔ 解析"这类天然并列的数据；**不适合当控制流替身**（过度使用会让代码不可读）。实测（ex01 区 4）：`ERR_NOTFOUND` 枚举值 = 2 且 `err_str(ERR_NOTFOUND)` 返回 `"not found"`——两边由同一张表生成，增删一行错误码不会漏改。

### 3.3 函数指针：语法与表驱动

函数指针的三种基础形态（完整可运行版见 examples/ex02）：

```c
// examples/ex02-callback-ctx.c —— 函数指针形态（节选, 完整版见 examples/）
/* ===== 1. 函数指针基础 ===== */

/* 一元数学运算的"函数指针"形态：double (*)(double) */
typedef double (*unary_fn)(double);

static double twice(double x)  { return x * 2.0; }
static double square(double x) { return x * x; }
static double identity(double x) { return x; }

/* 函数指针作为参数：把"怎么变换"交给调用者（策略模式的最简形态） */
static double apply(unary_fn f, double x) {
    return f(x);
}

/* 函数指针数组 + 表驱动：ops[i] 按索引选策略 */
static unary_fn g_ops[3] = { identity, twice, square };

static void demo_funptr(void) {
    printf("函数指针传参: apply(twice,21)=%.0f  apply(square,6)=%.0f\n",
           apply(twice, 21.0), apply(square, 6.0));
    printf("函数指针数组: ops[0](7)=%.0f  ops[1](7)=%.0f  ops[2](7)=%.0f\n",
           g_ops[0](7.0), g_ops[1](7.0), g_ops[2](7.0));
}
```

**函数指针数组 = 表驱动**：`g_ops[i](x)` 按索引选策略，等价于把 switch 的每个 case 换成数组元素。它在状态机（转移表存动作指针）、命令行解析（选项表存处理函数）、命令分发（协议号 → 处理器）里都是主干结构。实测（ex02）：`apply(twice, 21) = 42`、`apply(square, 6) = 36`、`g_ops[2](7) = 49`（square）。

### 3.4 回调与上下文约定：ctx 与生命周期

回调 = "把函数指针交给别人，让它在特定时刻调用你"。C 没有闭包，**回调要携带自己的状态，只能通过 `void *ctx` 参数传回**——这是 C 回调区别于现代语言闭包的核心。回调签名与"ctx 还原"：

```c
// examples/ex02-callback-ctx.c —— 回调签名（节选, 完整版见 examples/）
/* 回调签名：回调要"记住"的数据装进 void *ctx 传回。
 * 约定（roadmap 必会概念）：ctx 由注册者提供并负责生命周期——回调只读用、
 * 不释放；注册者必须保证 ctx 存活到"注销/不再回调"之后。 */
typedef void (*event_cb)(int ev, void *ctx);
```

```c
// examples/ex02-callback-ctx.c —— ctx 还原与私有状态（节选, 完整版见 examples/）
/* ---- 回调实现：各自还原自己的 ctx 类型 ---- */

struct key_ctx { const char *name; int count; };  /* 回调私有状态 */

static void key_handler(int ev, void *ctx) {
    (void)ev;
    struct key_ctx *k = (struct key_ctx *)ctx;    /* ctx 还原回自己的类型 */
    k->count++;
    printf("  key_handler[%s]: 收到事件, 累计 %d 次\n", k->name, k->count);
}

static void timer_handler(int ev, void *ctx) {
    (void)ev;
    long *ticks = (long *)ctx;                    /* ctx 也可以只是一个计数变量 */
    (*ticks)++;
    printf("  timer_handler: 累计 tick = %ld\n", *ticks);
```

**上下文约定（roadmap 必会概念"回调适合解耦模块，但要约定上下文和生命周期"）**：

- **谁注册谁负责 ctx 生命周期**：ctx 通常由注册方提供（栈变量或堆对象），回调只读用、不释放；注册方必须保证 ctx 存活到"注销/不再回调"之后——栈上 ctx 在函数返回后即失效，是悬垂回调的最常见来源
- **回调顺序即注册顺序**：分发器按注册顺序回调（ex02 实测：注册 A→timer→B，触发事件输出顺序就是 A→timer→B；A/B 的 count 与 timer 的 ticks 各自隔离累计）
- **回调里不要再注销自己**（简化约定）：分发期间修改注册表会破坏遍历（真实框架用"延迟注销"或快照，超出本阶段范围）

ex02 实测核心（三次触发 EV_KEY 后的输出，A/B 与 timer 各计到 3 且互不干扰）：

```text
  key_handler[A]: 收到事件, 累计 3 次
  timer_handler: 累计 tick = 3
  key_handler[B]: 收到事件, 累计 3 次
```

### 3.5 状态机：表驱动

状态机适合解析器、任务调度、连接管理、存储恢复流程（roadmap 必会概念）。**表驱动写法**：把 `(当前状态, 事件) → (动作, 下一状态)` 放成只读数组，查找表驱动转移——行为集中成数据、增删状态只改表、整套表可打印可测试。转移表与动作（动作是函数指针）：

```c
// examples/ex03-state-machine.c —— 动作与转移表（节选, 完整版见 examples/）
typedef void (*action_fn)(void);

static void act_noop(void)          { printf("    [动作] (无)\n"); }
static void act_alloc_conn(void)    { printf("    [动作] 分配连接\n"); }
static void act_start_read(void)    { printf("    [动作] 开始监听读事件\n"); }
static void act_read_buf(void)      { printf("    [动作] 读取并处理数据\n"); }
static void act_flush_close(void)   { printf("    [动作] 刷缓冲并发出 FIN\n"); }
static void act_notify_app(void)    { printf("    [动作] 通知应用层连接已关闭\n"); }
static void act_free_conn(void)     { printf("    [动作] 释放连接资源\n"); }

/* ---- 转移表：一行 = 一条合法转移 ---- */
typedef struct {
    int from;
    int event;
    action_fn action;
    int to;
} transition_t;

static const transition_t g_trans[] = {
    { ST_CLOSED,      EV_CONNECT,   act_alloc_conn,   ST_LISTEN },
    { ST_LISTEN,      EV_ACCEPT,    act_start_read,   ST_ESTABLISHED },
    { ST_ESTABLISHED, EV_DATA,      act_read_buf,     ST_ESTABLISHED },
    { ST_ESTABLISHED, EV_CLOSE,     act_flush_close,  ST_FIN_WAIT },
    { ST_FIN_WAIT,    EV_PEER_FIN,  act_notify_app,   ST_CLOSED_WAIT },
    { ST_CLOSED_WAIT, EV_CLOSE,     act_free_conn,    ST_CLOSED },
    /* 超时兜底：LISTEN/ESTABLISHED 下超时回初始, 并打印动作 */
    { ST_LISTEN,      EV_TIMEOUT,   act_noop,         ST_CLOSED },
    { ST_ESTABLISHED, EV_TIMEOUT,   act_free_conn,    ST_CLOSED },
};

static const int g_trans_n = (int)(sizeof g_trans / sizeof g_trans[0]);
```

转移语义（ex03 实测，连接状态机）——喂事件 → 线性查表找第一条 `(当前状态, 事件)` 匹配 → 执行动作 → 换状态：

```text
转移: CLOSED --CONNECT--> LISTEN
    [动作] 分配连接
转移: ESTABLISHED --DATA--> ESTABLISHED    （自环: 处理数据后仍 ESTAB）
...（省略中间步骤）...
非法事件: CLOSED 状态下不能处理 DATA (返回 -1, 状态不变)
走过的状态序列: 0122340   ← CLOSED→LISTEN→ESTAB→ESTAB→FIN_WAIT→CLOSE_WAIT→CLOSED
```

**非法事件（当前状态下无对应转移）返回错误码、状态不变**——这是状态机"不变量可验证"的关键。完整可复用框架见 project/（fsm 库 + 两个场景 + 自测断言），详见第 6 章与第 7 章。

### 3.6 错误码设计：稳定、可追踪

错误码是 C 的"异常"——没有异常机制，错误只能靠返回值传递。**稳定可追踪**（roadmap 必会概念）是设计主线：

1. **0 = 成功；负数为错误码**。数值与含义一一对应，**一经发布不再改值**（下游可能已按旧值写判断）；新增错误只追加不复用
2. **不用 errno 传业务错误**：errno 是全局/线程局部变量，中间调用会覆盖、跨层难传。库函数返回自己的错误码（ph14 跨语言语境已立同样契约）
3. **可追踪 = 错误码 + 出错位置 + 出错内容快照一起上报**，而不是只丢一个裸整数给调用方

错误码定义（显式赋值 + "历史, 勿改"注释锁定）：

```c
// examples/ex04-error-code.c —— 稳定错误码（节选, 完整版见 examples/）
    CFG_OK = 0,
    /* 历史错误码：一经发布不得改值。新增错误只追加新项 */
    CFG_ERR_OPEN = -1,     /* 配置文件打不开           （历史, 勿改） */
    CFG_ERR_BADLINE = -2,  /* 某一行格式非法           （历史, 勿改） */
    CFG_ERR_UNKNOWNKEY = -3, /* 未知配置键             （历史, 勿改） */
    CFG_ERR_OOM = -4,      /* 内存不足                 （历史, 勿改） */
    /* 下面是从 2.x 版本新增的错误（继续向下追加, 不复用历史值） */
    CFG_ERR_VALUE = -5,    /* 值域非法（新增于 2.1）   */
};

```

可追踪错误详情出参：

```c
// examples/ex04-error-code.c —— 可追踪错误详情（节选, 完整版见 examples/）

static void errinfo_set(errinfo_t *e, int code, int line, const char *detail) {
    e->code = code;
    e->line = line;
    snprintf(e->detail, sizeof e->detail, "%s", detail);
}

```

ex04 实测（mini 配置加载器）：第 3 行 `timeout=abc` 值非法 → 返回 `-5`（`config value out of range`）并上报 `出错行 3, 原文 "timeout=abc"`；第 4 行未知键 `colormode=1` → 返回 `-3`。**数值稳定靠"显式赋值 + 历史锁定注释"，可追踪靠"出参携带上下文"**——两者配合，线上看到一个 -5 就能定位到配置文件第几行。

### 3.7 日志系统：级别、阈值过滤、trace id、诊断

日志是"可追踪性"的运行期实现。一个够用的日志器要回答四个问题（完整工程版见 ph09 project 的跨平台日志库；本阶段示范级别/trace id/诊断语义）：

**级别与阈值过滤**：`DEBUG < INFO < WARN < ERROR`，低于当前阈值的日志不输出（也计数 dropped——诊断"被过滤了多少"）。核心输出函数与过滤逻辑：

```c
// examples/ex05-logging.c —— 级别过滤 + trace id（节选, 完整版见 examples/）

    /* 时间（秒级; 精确到毫秒需要 clock_gettime, 见 ph09 project 的跨平台日志库） */
    time_t now = time(NULL);
    struct tm tmv;
    localtime_r(&now, &tmv);

    char hdr[32];
    snprintf(hdr, sizeof hdr, "%02d:%02d:%02d",
             tmv.tm_hour, tmv.tm_min, tmv.tm_sec);

    printf("[%s][%-5s][trace=%04lx][%s:%d] %s\n",
           hdr, lvl_tag(lvl), trace_id, file, line, msg);
}

```

**trace id**：一次请求/一次调用链的日志行带同一个 id，按 id grep 即还原全过程——单机组件里同样适用，不必等到分布式才需要它。日志宏自动带调用点（3.2 的可变参宏在这里派上用场）：

```c
// examples/ex05-logging.c —— LOG 宏自动带文件:行（节选, 完整版见 examples/）
/* ---- 日志宏: 自动带 __FILE__/__LINE__（衔接 ex01 宏技巧） ---- */
#define LOG(lvl, tid, ...) \
    log_emit((lvl), (tid), __FILE__, __LINE__, ##__VA_ARGS__)
```

ex05 实测（阈值过滤行为，`emitted`=输出条数 / `dropped`=被过滤条数）：

```text
-- 场景 1: 阈值=DEBUG, 四级全输出 --
[HH:MM:SS][DEBUG][trace=1a2b][ex05-logging.c:NN] 收到请求, 开始解析
[HH:MM:SS][INFO ][trace=1a2b][ex05-logging.c:NN] 路由到 handler
[HH:MM:SS][WARN ][trace=1a2b][ex05-logging.c:NN] 参数过期, 使用默认值
[HH:MM:SS][ERROR][trace=1a2b][ex05-logging.c:NN] 写回失败, 已重试
-- 场景 2: 阈值调到 WARN, DEBUG/INFO 被过滤 --
[HH:MM:SS][WARN ][trace=1a2b][ex05-logging.c:NN] WARN 仍输出
[HH:MM:SS][ERROR][trace=1a2b][ex05-logging.c:NN] ERROR 仍输出
-- 诊断统计 --
emitted=6 dropped=2 (场景1 输出 4 条; 场景2 输出 2 条、过滤 2 条)
```

### 3.8 handle-based API 与 opaque pointer：把库的边界立住

ph14 在跨语言语境教过 opaque 句柄 + create/destroy + 错误码；本阶段把它收进"纯 C 库 API 设计"的常规——**句柄类型不透明、struct 藏在实现里、所有函数返回错误码、生命周期 create/destroy 闭环**：

```c
// examples/ex06-handle-api.c —— handle-based API 公开面（节选, 完整版见 examples/）

typedef struct cfg cfg_t;   /* opaque 句柄 */

cfg_t *cfg_create(const char *name, int32_t *err);   /* create: 失败返回 NULL */
int32_t cfg_set(cfg_t *c, const char *key, int64_t val);   /* 写入一个键值 */
int32_t cfg_get(const cfg_t *c, const char *key, int64_t *out); /* 读键值 */
const char *cfg_name(const cfg_t *c);   /* 借用内部 name, 不得 free */
int32_t cfg_destroy(cfg_t *c);          /* 谁 create 谁 destroy */
const char *cfg_strerror(int32_t err);  /* 错误消息(静态串, 借用) */
```

API 契约要点（ex06 实测全链路 create→set/get→覆盖→destroy 退出码 0）：

- **不透明**：`struct cfg` 只在 .c 定义，头文件只见 `cfg_t`——内部布局随便改不破坏调用方（ABI 稳定的工程实现，ph14 已论证）
- **错误上报**：create 失败返回 NULL 且 `*err` 写错误码；普通操作返回错误码（ex06：查不存在的键返回 `-3`）
- **生命周期写进注释**：`cfg_name` 返回借用指针，注释写明"不得 free"——所有权在 C 库里的表达就是注释 + 惯例
- **零全局状态**：句柄自包含，可同时开多个实例互不干扰（project/ 的 fsm 库同款设计）

### 3.9 API 设计与跨平台：命名、契约、条件编译层

跨平台兼容是 API 设计的一部分，不是事后补丁（roadmap 学习内容"API 设计、跨平台兼容"）。三层惯例：

1. **命名即边界**：库前缀（`cfg_`/`fsm_`）避免符号冲突；类型、错误码、函数在头文件里一次性立契约
2. **错误码/句柄/借用三件套统一**（3.6/3.8）：调用方只需要学会一套约定，就能用整个库
3. **平台差异收敛到条件编译层**：业务代码零 `#ifdef`，平台差异（路径分隔符、sleep、时间格式化）封成小函数

平台探测宏示例（把"我在哪个平台"编译期写死成常量，诊断/日志可用）：

```c
// examples/ex06-handle-api.c —— 条件编译平台探测（节选, 完整版见 examples/）
/* 跨平台探测宏: 输出编译目标平台（供诊断与演示条件编译） */
#if defined(__APPLE__)
#define CFG_PLATFORM "macOS (Apple)"
#elif defined(__linux__)
#define CFG_PLATFORM "Linux"
#elif defined(_WIN32)
#define CFG_PLATFORM "Windows"
#else
#define CFG_PLATFORM "unknown POSIX"
#endif

/* ============ 实现（opaque 结构体只在这里出现） ============ */
```

> 平台差异的**完整**抽象（特征宏清单、类型宽度、编译器差异对照）属于 ph09 C 标准、编译器与可移植性阶段，本阶段只示范"平台探测宏放进 API 层、业务代码不碰 #ifdef"这一设计位置。

## 4. 底层原理

### 4.1 宏的展开机制：为什么副作用会翻倍

```text
#define MAX_BAD(a,b) ((a)>(b)?(a):(b))

MAX_BAD(i++, 0)
──文本替换(无求值)──▶ ((i++)>(0)?(i++):(0))
──运行时求值────────▶ 条件处 i++ 一次, 真分支 i++ 又一次 → 共两次
```

预处理器在编译最早期做纯文本替换，**宏参数不被视为"一次求值的值"，而是"原样粘贴的代码"**——参数出现几次就粘贴几份。函数（含 static inline）在编译期才做类型检查与一次求值，所以"函数语义"必须交给函数。

### 4.2 函数指针与回调：间接调用与 ctx 的机器级含义

```text
普通调用:  call  act_alloc_conn        (直接调用, 地址编译期确定)
函数指针:  call  [g_trans[i].action]   (间接调用, 地址运行期从表里取)

ctx 的机器级含义: void *ctx 就是"一个指针宽的寄存器/栈槽",
                  回调侧强转回自己的结构体指针 —— 类型安全由约定保证, 编译器不检查
```

表驱动状态机的"查表 → 间接调用"在机器层面就是**一次数组索引 + 一次间接 call**，代价恒定、行为完全由数据决定——这也是它能被穷举测试的原因（转移表 = 规格）。

### 4.3 错误码为什么必须稳定：ABI 视角

错误码数值一旦被下游编译进二进制（`if (rc == -5)`），改值等于改 ABI——旧二进制按旧值判断，新库返回新值，错位静默发生。**稳定错误码 = 只追加不复用 + 显式赋值**，是把"错误语义"变成不变量（ph14 的"ABI 稳定优先"在错误码上的落地）。

### 4.4 opaque pointer 的原理：类型擦除与编译边界

```text
头文件:  typedef struct cfg cfg_t;   ← 不完整类型, 只能声明指针
实现:    struct cfg { char name[..]; kv_t kvs[..]; };   ← 完整定义只在 .c

调用方 sizeof(cfg_t) 不合法 → 编译器强制"只能用指针 + API 函数"
→ 结构体布局成了 .c 的私有实现细节, 改布局不破坏调用方(不需重编)
```

不完整类型是 C 给"封装"的唯一语言级工具：**看不到定义就无法拆解，封装不是纪律而是语法强制**。

## 5. 使用场景

| 场景 | 用什么 | 依据 |
|------|--------|------|
| 解析器 / 协议状态机 / 连接管理 | 表驱动状态机 | 行为数据化、转移表可测、非法事件可拒（ex03/project/） |
| 事件分发 / 插件式解耦（IO 回调、定时器、命令表） | 函数指针 + ctx 回调 | 模块只认签名不认实现；ctx 携带每份回调的状态（ex02） |
| 配置 / 选项 / 命令解析 | 选项表/命令表（函数指针数组） | 加一个选项=加一行表（exercises/sol-03） |
| 枚举 ↔ 字符串 ↔ 查找需要同源 | X-Macro | 一张表生成三处，杜绝手工不同步（ex01 区 4） |
| 库的对外边界 | handle-based API + opaque pointer | 布局可藏、所有权闭环、错误码统一（ex06/project/） |
| 线上问题定位 | 日志级别 + trace id + 文件:行 | 按 trace grep 一次请求全过程（ex05） |
| 跨平台库分发 | 条件编译平台层 + 定宽类型 | 业务零 #ifdef；平台差异收进小函数（ex06/ph09） |

**不适合**本阶段手段的场景：

- **热路径的宏替代函数**：宏没有类型检查、可能双求值；性能敏感但语义是函数的，用 `static inline`
- **状态爆炸的状态机**：状态 × 事件乘积太大时表会稀疏；考虑嵌套状态机/分层（超出本阶段）
- **需要跨线程的复杂回调**：单线程回调约定在多线程下要加锁/队列（ph08 并发专题）
- **错误码能表达的不用日志**：错误码给机器判断（if/else 分支），日志给人看；两者分工，不是替代

**跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：C 没有闭包、异常、垃圾回收，所以"状态携带"靠 ctx、"错误"靠返回码、"封装"靠不完整类型——每一样都是机制缺失逼出的显式约定；现代语言把这些变成语言特性（闭包、Result/异常、private 字段），开发者少写样板但少了"看得见边界"的强制力。**C 的方式是把约定写进注释和头文件，靠纪律维护；这正是 Tenet 合成时"该把哪些约定提升为语言特性"的观察样本**。

## 6. 代码示例

> 完整可运行文件在 [`examples/`](./examples/) 目录（编译/运行命令与验证状态见其 README）。本阶段示例均为**正常工程代码**，无故意出错演示（ex01 的"反例"宏是教学对照，运行安全、结果即教训）；可任意编译运行。以下所有实测输出来自 Apple clang 21.0.0（macOS arm64）；文档内嵌片段与对应源文件逐字一致（节选关键部分，完整文件以 examples/ 为准）。

### 示例 1：宏技巧（副作用陷阱 / do-while(0) / 可变参宏 / X-Macro）

对应 roadmap 学习内容"宏技巧、条件编译"，完整版见 [`examples/ex01-macro-tricks.c`](./examples/ex01-macro-tricks.c)。

> 运行前提：无（正常工程代码，可任意编译运行）。产物写 /tmp/ph15c-ex。

```c
// examples/ex01-macro-tricks.c —— 宏技巧：副作用陷阱/do-while(0)/可变参宏/X-Macro（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
/* 反例：宏参数只加括号不够 —— 展开后参数表达式被求值多次。
 * MAX_BAD(i++, 10) 展开为 ((i++) > (10) ? (i++) : (10))：i++ 出现了两次。 */
#define MAX_BAD(a, b) ((a) > (b) ? (a) : (b))

/* 正解：要"函数语义"就别用宏 —— static inline 函数参数只求值一次。
 * （此处演示用 int 版，见主文档 3.1：类型泛化要靠 _Generic/宏工厂，同样要避开副作用） */
static inline int imax(int a, int b) {
    return a > b ? a : b;
}
```

```bash
# 1. 编译并运行
mkdir -p /tmp/ph15c-ex && cc -Wall -Wextra -std=c11 ex01-macro-tricks.c -o /tmp/ph15c-ex/ex01 && /tmp/ph15c-ex/ex01
```

实测输出关键行（本机一次运行）：

```text
区1 反例: MAX_BAD(i++,0)   i 从 1 变到 3 (结果=2)  ← i++ 求值两次
区1 正例: imax(i++,0)     i 从 1 变到 2 (结果=1)  ← 只求值一次
区4 X-Macro: ERR_NOTFOUND=2, 字符串="not found"
条件编译: 标准=C11 平台=Apple (macOS) (编译期由宏决定)
```

解读：反例 `MAX_BAD(i++,0)` 里 `i` 被求值两次（1→3），正解 inline 函数只求值一次（1→2）；X-Macro 让 `ERR_NOTFOUND=2` 与字符串 `"not found"` 来自同一张表；条件编译在编译期决定标准与平台字符串。

### 示例 2：函数指针与回调（上下文约定 + 回调顺序）

对应 roadmap 学习内容"函数指针、回调函数"与必会概念"回调适合解耦模块，但要约定上下文和生命周期"，完整版见 [`examples/ex02-callback-ctx.c`](./examples/ex02-callback-ctx.c)。核心验证 = 回调顺序与 ctx 状态隔离（实测）。

> 运行前提：无（正常工程代码，可任意编译运行）。

```c
// examples/ex02-callback-ctx.c —— 函数指针/回调：上下文约定 + 回调顺序实测（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
/* 回调签名：回调要"记住"的数据装进 void *ctx 传回。
 * 约定（roadmap 必会概念）：ctx 由注册者提供并负责生命周期——回调只读用、
 * 不释放；注册者必须保证 ctx 存活到"注销/不再回调"之后。 */
typedef void (*event_cb)(int ev, void *ctx);

#define MAX_HANDLERS 8
#define EV_KEY 1
#define EV_TIMER 2

/* 事件分发器：内部只存"函数指针 + ctx"对，不关心回调业务 */
typedef struct {
    event_cb fn;
    void *ctx;
} handler_t;
```

```bash
# 1. 编译并运行
mkdir -p /tmp/ph15c-ex && cc -Wall -Wextra -std=c11 ex02-callback-ctx.c -o /tmp/ph15c-ex/ex02 && /tmp/ph15c-ex/ex02
```

实测输出关键行（本机一次运行）：

```text
回调演示 1: 触发 EV_KEY（应看到 A → timer → B 顺序）:
  key_handler[A]: 收到事件, 累计 1 次
  timer_handler: 累计 tick = 1
  key_handler[B]: 收到事件, 累计 1 次
回调演示 3: 再触发 EV_KEY（A/B 的 count 与 timer 的 ticks 持续累计, ...）:
  key_handler[A]: 收到事件, 累计 3 次
  timer_handler: 累计 tick = 3
  key_handler[B]: 收到事件, 累计 3 次
```

解读：注册顺序 A→timer→B 即回调顺序；三次触发后 A/B 累计 3 次、timer 累计 3 次——**ctx 各自隔离、跨事件保留**。

### 示例 3：表驱动状态机（状态转移序列实测）

对应 roadmap 学习内容"状态机"与必会概念"状态机适合解析器、任务调度、连接管理"，完整版见 [`examples/ex03-state-machine.c`](./examples/ex03-state-machine.c)。

> 运行前提：无（正常工程代码，可任意编译运行）。

```c
// examples/ex03-state-machine.c —— 表驱动状态机：状态转移序列实测（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
static const transition_t g_trans[] = {
    { ST_CLOSED,      EV_CONNECT,   act_alloc_conn,   ST_LISTEN },
    { ST_LISTEN,      EV_ACCEPT,    act_start_read,   ST_ESTABLISHED },
    { ST_ESTABLISHED, EV_DATA,      act_read_buf,     ST_ESTABLISHED },
    { ST_ESTABLISHED, EV_CLOSE,     act_flush_close,  ST_FIN_WAIT },
    { ST_FIN_WAIT,    EV_PEER_FIN,  act_notify_app,   ST_CLOSED_WAIT },
    { ST_CLOSED_WAIT, EV_CLOSE,     act_free_conn,    ST_CLOSED },
    /* 超时兜底：LISTEN/ESTABLISHED 下超时回初始, 并打印动作 */
    { ST_LISTEN,      EV_TIMEOUT,   act_noop,         ST_CLOSED },
    { ST_ESTABLISHED, EV_TIMEOUT,   act_free_conn,    ST_CLOSED },
};

static const int g_trans_n = (int)(sizeof g_trans / sizeof g_trans[0]);
```

```bash
# 1. 编译并运行
mkdir -p /tmp/ph15c-ex && cc -Wall -Wextra -std=c11 ex03-state-machine.c -o /tmp/ph15c-ex/ex03 && /tmp/ph15c-ex/ex03
```

实测输出关键行（本机一次运行）：

```text
转移: CLOSED --CONNECT--> LISTEN
    [动作] 分配连接
转移: ESTABLISHED --DATA--> ESTABLISHED
    [动作] 读取并处理数据
...
非法事件: CLOSED 状态下不能处理 DATA (返回 -1, 状态不变)
  返回码 = -1, 状态仍是 CLOSED
走过的状态序列: 0122340 (用状态号 0~4 表示)
自测: 序列长度=7 (期望 7: 0→1→2→2→3→4→0)
```

解读：每步打印"转移 + 动作"；DATA 自环（ESTAB 保持 ESTAB）；CLOSED 下发 DATA 是非法事件——返回 -1、状态不变；走过的序列 `0122340` 与期望逐位一致（状态机的可测试性）。

### 示例 4：错误码设计（稳定、可追踪）

对应 roadmap 学习内容"错误码设计"与必会概念"错误码设计要稳定、可追踪"，完整版见 [`examples/ex04-error-code.c`](./examples/ex04-error-code.c)。

> 运行前提：无（正常工程代码，可任意编译运行）。

```c
// examples/ex04-error-code.c —— 错误码设计：稳定、可追踪（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）
    CFG_OK = 0,
    /* 历史错误码：一经发布不得改值。新增错误只追加新项 */
    CFG_ERR_OPEN = -1,     /* 配置文件打不开           （历史, 勿改） */
    CFG_ERR_BADLINE = -2,  /* 某一行格式非法           （历史, 勿改） */
    CFG_ERR_UNKNOWNKEY = -3, /* 未知配置键             （历史, 勿改） */
    CFG_ERR_OOM = -4,      /* 内存不足                 （历史, 勿改） */
    /* 下面是从 2.x 版本新增的错误（继续向下追加, 不复用历史值） */
    CFG_ERR_VALUE = -5,    /* 值域非法（新增于 2.1）   */
};

```

```bash
# 1. 编译并运行
mkdir -p /tmp/ph15c-ex && cc -Wall -Wextra -std=c11 ex04-error-code.c -o /tmp/ph15c-ex/ex04 && /tmp/ph15c-ex/ex04
```

实测输出关键行（本机一次运行）：

```text
第 3 行  错误码=-5 (config value out of range)
          出错行 3, 原文 "timeout=abc"
第 4 行  错误码=-3 (unknown config key)
          出错行 4, 原文 "colormode=1"
可追踪 = 错误码(-5) + 行号(3) + 原文快照("timeout=abc") 三者一起上报
```

解读：错误码显式赋值 + "历史, 勿改"注释锁定数值；错误详情出参携带行号与原文——看到 -5 能直接定位配置第 3 行。

### 示例 5：日志系统（级别 / 阈值过滤 / trace id / 诊断）

对应 roadmap 学习内容"日志系统、trace id、诊断信息"，完整版见 [`examples/ex05-logging.c`](./examples/ex05-logging.c)。

> 运行前提：无（正常工程代码，可任意编译运行）。输出含运行时刻的时间列（随运行变化），其余行为输出确定可复核。

```c
// examples/ex05-logging.c —— 日志系统：级别/阈值过滤/trace id/诊断（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）

    /* 时间（秒级; 精确到毫秒需要 clock_gettime, 见 ph09 project 的跨平台日志库） */
    time_t now = time(NULL);
    struct tm tmv;
    localtime_r(&now, &tmv);

    char hdr[32];
    snprintf(hdr, sizeof hdr, "%02d:%02d:%02d",
             tmv.tm_hour, tmv.tm_min, tmv.tm_sec);

    printf("[%s][%-5s][trace=%04lx][%s:%d] %s\n",
           hdr, lvl_tag(lvl), trace_id, file, line, msg);
}

```

```bash
# 1. 编译并运行
mkdir -p /tmp/ph15c-ex && cc -Wall -Wextra -std=c11 ex05-logging.c -o /tmp/ph15c-ex/ex05 && /tmp/ph15c-ex/ex05
```

实测输出关键行（本机一次运行，时间列略）：

```text
-- 场景 1: 阈值=DEBUG, 四级全输出 --
[HH:MM:SS][DEBUG][trace=1a2b][ex05-logging.c:NN] 收到请求, 开始解析
[HH:MM:SS][ERROR][trace=1a2b][ex05-logging.c:NN] 写回失败, 已重试
-- 场景 2: 阈值调到 WARN, DEBUG/INFO 被过滤 --
[HH:MM:SS][WARN ][trace=1a2b][ex05-logging.c:NN] WARN 仍输出
[HH:MM:SS][ERROR][trace=1a2b][ex05-logging.c:NN] ERROR 仍输出
-- 诊断统计 --
emitted=6 dropped=2 (场景1 输出 4 条; 场景2 输出 2 条、过滤 2 条)
```

解读：阈值从 DEBUG 调到 WARN 后，DEBUG/INFO 被过滤（dropped=2）、WARN/ERROR 仍输出（emitted=6 对两场景共 8 次调用）；所有行带同一 `trace=1a2b`——按 id grep 还原一次请求全过程。

### 示例 6：handle-based API / opaque pointer（衔接 ph14）+ 跨平台探测

对应 roadmap 学习内容"handle-based API、opaque pointer、API 设计、跨平台兼容"，完整版见 [`examples/ex06-handle-api.c`](./examples/ex06-handle-api.c)。

> 运行前提：无（正常工程代码，可任意编译运行）。macOS/POSIX 分支已验证；`_WIN32` 分支未在本环境验证（需 Windows）。

```c
// examples/ex06-handle-api.c —— handle-based API/opaque pointer：承接 ph14（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）

typedef struct cfg cfg_t;   /* opaque 句柄 */

cfg_t *cfg_create(const char *name, int32_t *err);   /* create: 失败返回 NULL */
int32_t cfg_set(cfg_t *c, const char *key, int64_t val);   /* 写入一个键值 */
int32_t cfg_get(const cfg_t *c, const char *key, int64_t *out); /* 读键值 */
const char *cfg_name(const cfg_t *c);   /* 借用内部 name, 不得 free */
int32_t cfg_destroy(cfg_t *c);          /* 谁 create 谁 destroy */
const char *cfg_strerror(int32_t err);  /* 错误消息(静态串, 借用) */
```

```bash
# 1. 编译并运行
mkdir -p /tmp/ph15c-ex && cc -Wall -Wextra -std=c11 ex06-handle-api.c -o /tmp/ph15c-ex/ex06 && /tmp/ph15c-ex/ex06
```

实测输出关键行（本机一次运行）：

```text
编译平台: macOS (Apple) (条件编译宏 __APPLE__/__linux__/_WIN32 决定)
create 成功: name=demo-config (借用指针)
cfg_get(port) rc=0 val=8080
cfg_set(port,9090) 覆盖后 cfg_get(port) val=9090
cfg_get(nope): rc=-3 (operation not allowed / key not found)
destroy rc=0
```

解读：opaque 句柄 create→set/get→覆盖→destroy 全链路退出码 0；查不存在的键返回错误码 -3（不崩溃）；平台探测宏在编译期决定输出——handle 心智与 ph14 的跨语言句柄同源，这里收进"同一语言内的库 API 设计"。

## 7. 总结

### 关键要点

1. **宏是文本替换**（4.1）：参数出现几次就粘贴几份——副作用陷阱的根源；要函数语义就用 `static inline`（3.1/ex01）
2. **块语句宏用 do-while(0) 包裹**，否则 if/else 错挂（3.1/ex01 区 2）
3. **可变参宏 + `##__VA_ARGS__` 让零实参合法**，`__FILE__/__LINE__` 自动注入是日志/断言宏的标准形态（3.2/ex01/ex05）
4. **X-Macro = 单表多产物**：枚举/字符串/查找同源，杜绝手工不同步（3.2/ex01 区 4）
5. **函数指针数组 = 表驱动**：策略、选项表、状态机转移表的主干（3.3）
6. **回调必须约定 ctx 与生命周期**：谁注册谁负责 ctx；顺序 = 注册顺序；ctx 状态各自隔离（3.4/ex02）
7. **状态机表驱动 + 非法事件返回错误码**：行为数据化、可测、不变量可验证（3.5/ex03/project/）
8. **错误码 0 成功负数错误 + 显式赋值 + 历史锁定**：发布不改值、新增只追加；可追踪 = 错误码 + 位置 + 快照（3.6/ex04）
9. **日志 = 级别过滤 + trace id + 文件:行诊断**：过滤行为可数（emitted/dropped），trace 串起一次请求（3.7/ex05）
10. **handle-based API + opaque pointer 立住库边界**：结构体藏 .c、错误码统一、借用指针注释、零全局状态（3.8/ex06/project/）
11. **跨平台差异收进条件编译层**，业务零 #ifdef（3.9/ex06；特征宏清单属 ph09）

### 阶段验收清单

- [ ] 能说清宏的副作用陷阱（为什么 `MAX_BAD(i++,0)` 双求值）并给出正解（3.1/ex01）
- [ ] 能用 X-Macro 让枚举与字符串表同源，并解释展开顺序（3.2/ex01）
- [ ] 能写出带 ctx 的回调并说清 ctx 生命周期谁负责（3.4/ex02）
- [ ] 能搭表驱动状态机：转移表 + 动作指针 + 非法事件错误码 + 状态序列自测（3.5/ex03/project/）
- [ ] 能设计稳定可追踪的错误码：0 成功/负数错误/历史锁定/详情出参（3.6/ex04）
- [ ] 能实现日志级别过滤与 trace id 贯穿，并实测过滤行为（3.7/ex05）
- [ ] 能写出 handle-based API（opaque 句柄 + create/destroy + 错误码），衔接 ph14 心智（3.8/ex06）
- [ ] 能设计清晰模块边界、避免宏副作用与全局状态滥用、写出可测试的 C API（roadmap 阶段验收，project/ fsm 库即样例）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。五题与 roadmap ph15「练习」一一对应：

- 通用状态机框架（★★★）
- 事件驱动框架（★★★）
- 命令行解析器（★★）
- ring buffer（★★）
- 可复用 frame 解析库（★★★）

完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**fsm——通用状态机框架（表驱动）**——对应 roadmap ph15「推荐项目」第一个「状态机框架」（第二个推荐项目「系统级日志库」未单独落地：ph09 项目已是完整跨平台日志库，本阶段日志主题由 examples/ex05 演示级别/阈值过滤/trace id/诊断语义）：一个 `-Wall -Wextra -std=c11` 零警告的可复用 FSM 库（fsm.h/fsm.c）+ 连接管理/数据包解析两个场景 + 20 项自测，把"函数指针表驱动、稳定错误码、opaque 句柄、可测试 API、零全局状态"全部落地。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`make test` 全过退出码 0、`make clean` 零残留）

### 下一阶段

本阶段是当前已完成目录的最后一个阶段（ph15 之后暂无 ph 目录）：**ph16+（roadmap 第 16 节，目录待建）：后续可深入数据库存储引擎基础** — 本阶段解决了"怎么写稳定、可维护、可移植的 C 代码"，ph16 将用这套方法论去搭存储引擎组件：本阶段练习的 ring buffer 是 Buffer Pool / LRU 淘汰的基础、可复用 frame 解析库是 WAL record 读取的引擎雏形、状态机框架正好承接"WAL 崩溃恢复流程"这类恢复状态机；ph13 project 的 kvlog（append-only log）会在那里升级为完整 WAL + MemTable + SSTable。C 的 roadmap 只规划到第 16 节，ph16 之后仓库暂无后续阶段规划。
