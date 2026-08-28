# C 语言内存管理阶段

> Ph03 讲完了指针能"指到哪"——本阶段回答指针真正该"指向哪里"：从栈上的自动变量走向堆上的手动管理，掌握 malloc/free 的完整生命周期。

## 1. 概述

内存管理阶段是 C 语言从"能写代码"到"能写生产代码"的分界线。目标：**能安全使用堆内存，理解栈与堆的本质区别，写出申请-扩容-释放的完整路径，用 Valgrind/ASan 定位内存错误**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 栈 vs 堆 | 生命周期、大小限制、分配方式对比 |
| 分配 API | malloc、calloc、realloc、free |
| sizeof 陷阱 | `sizeof(ptr)` vs `sizeof(*ptr)` vs 数组 `sizeof` |
| 经典错误 | 内存泄漏、double-free、use-after-free、野指针、越界 |
| 检测工具 | Valgrind（`--leak-check=full`）、ASan（`-fsanitize=address`） |
| 实践项目 | 动态数组（含扩容/缩容）、动态字符串、简单内存池 |

本阶段呼应 Ph03：Ph03 的指针一直指向栈上的数组，本阶段进入堆内存——指针指向**运行期确定大小、跨函数生命周期**的内存。结构体与数据结构（链表/树/哈希表）将在 Ph05 展开。

## 2. 来源与演变

| 阶段 | 来源 | 关键演变 |
|------|------|---------|
| Unix V1（1971） | 无用户态分配器 | 内核管理一切内存 |
| Unix V6（1975） | 引入 alloc/free | 简单首次适配（first-fit）分配器 |
| K&R C（1978） | malloc/free 定型 | 成为 C 标准库的一部分 |
| C89/C90 | stdlib.h 标准化 | malloc/calloc/realloc/free 四件套固定 |
| 现代 | 多种策略 | ptmalloc（glibc）/ jemalloc（FreeBSD）/ tcmalloc（Google）/ mimalloc |

**malloc 不是系统调用**：它是 brk/sbrk + mmap 之上的用户态分配器。小块（< 128KB）调 brk 移动堆顶，大块通过 mmap 匿名映射。分配器维护空闲链表，只有不够时才向内核要内存。

**C 选择手动管理而非 GC 的根源**：PDP-11 上内存只有几十 KB，GC 不可承受。更深层的原因：C 是"可移植的汇编"——每一条内存操作应对程序员可见、可控。指针让你**看到**地址，malloc/free 让你**管理**地址背后的生命周期。

## 3. 语法与参数

### 3.1 栈内存 vs 堆内存

| 维度 | 栈（Stack） | 堆（Heap） |
|------|-----------|-----------|
| 分配/释放 | 自动（编译器插入） | 手动 malloc / free |
| 大小确定时机 | 编译期 | 运行期 |
| 容量上限 | 约 8MB（Linux 默认） | 受虚拟内存 + swap 限制 |
| 内存布局 | 连续、LIFO（移动 SP） | 非连续、任意次序 |
| 生命周期 | 离开作用域自动回收 | 忘 free → 内存泄漏 |
| 速度 | 快（SP ± offset） | 慢（搜索空闲块或 syscall） |

关键判断标准：**编译期已知大小且函数内使用 → 栈；运行期确定大小或需跨函数返回 → 堆**。

### 3.2 malloc — 分配未初始化内存

```c
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int n = 5;
    int *arr = malloc((size_t)n * sizeof(int));
    if (arr == NULL) {
        fprintf(stderr, "malloc 失败，内存不足\n");
        return 1;
    }
    /* arr 的内容未初始化，是随机值（取决于之前那块内存的内容） */
    for (int i = 0; i < n; i++)
        printf("arr[%d] = %d (未初始化，可能非零)\n", i, arr[i]);
    free(arr);
    return 0;
}
```

| 要点 | 说明 |
|------|------|
| 参数 | `malloc(size)` 分配 `size` 字节，返回 `void *` |
| 返回值 | 成功返回指针，失败返回 `NULL`——**每次调用必须检查** |
| 内容 | 未初始化（不保证为 0），内容是之前该内存区域残留的值 |
| 计算大小 | 用 `n * sizeof(T)` 而非硬编码数字，可移植 |
| 释放 | 分配的内存必须由 `free` 释放 |

### 3.3 calloc — 分配并清零

```c
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int n = 5;
    int *arr = calloc((size_t)n, sizeof(int));
    if (arr == NULL) {
        fprintf(stderr, "calloc 失败\n");
        return 1;
    }
    /* calloc 保证所有字节为 0 */
    for (int i = 0; i < n; i++)
        printf("arr[%d] = %d (确认为 0)\n", i, arr[i]);
    free(arr);
    return 0;
}
```

| 对比 | malloc | calloc |
|------|--------|--------|
| 参数 | `malloc(size)` | `calloc(count, size)` |
| 初始化 | 不初始化（随机值） | 逐字节清零（bit 全 0） |
| 性能 | 略快 | 略慢（需写内存） |
| 适用 | 即将全部覆写的 buffer | 数组、结构体等需零值的场景 |

注意：`calloc` 零初始化逐字节置 0。多数平台 `NULL` / `0.0` 恰好 byte 全 0，但 C 标准**不保证**。

### 3.4 realloc — 调整已分配内存的大小

```c
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int *arr = malloc(3 * sizeof(int));
    if (arr == NULL) return 1;
    arr[0] = 10; arr[1] = 20; arr[2] = 30;

    /* 扩容到 5 个 int —— 必须用临时指针承接！ */
    int *tmp = realloc(arr, 5 * sizeof(int));
    if (tmp == NULL) {
        fprintf(stderr, "realloc 失败，但 arr 指向的原内存仍然有效\n");
        free(arr);  /* 必须释放，否则泄漏 */
        return 1;
    }
    arr = tmp;      /* 只在成功后才覆盖原指针 */
    arr[3] = 40;    /* 新增元素的值未初始化 */
    arr[4] = 50;

    for (int i = 0; i < 5; i++)
        printf("arr[%d] = %d\n", i, arr[i]);
    free(arr);
    return 0;
}
```

realloc 两种行为：**原地扩容**（块后有足够空间 → 直接扩展，返回原指针）或**新分配+复制+释放**（空间不足 → 分配新块、复制旧内容、释放旧块、返回新指针）。

| 要点 | 说明 |
|------|------|
| 临时指针 | `ptr = realloc(ptr, ...)` 是反模式：失败时原指针丢失 → 内存泄漏 |
| 缩容 | `realloc(ptr, smaller)` 可以缩容，不保证一定成功 |
| 特殊参数 | `realloc(NULL, n)` ≡ `malloc(n)`；`realloc(ptr, 0)` 实现定义，不应使用 |

### 3.5 free — 释放内存

```c
#include <stdlib.h>

int main(void) {
    int *p = malloc(100 * sizeof(int));
    if (p == NULL) return 1;

    /* ... 使用 p ... */

    free(p);
    p = NULL;   /* 立即置空，防止后续误用 */
    return 0;
}
```

| 规则 | 说明 |
|------|------|
| 只能 free malloc 系列返回值 | free 非 malloc 指针 → UB |
| 不可重复释放 | double-free → 堆损坏 / 崩溃 |
| `free(NULL)` 安全 | C 标准保证，无需判断 |
| 释放后置 NULL | 防 use-after-free（不能防其他别名） |
| 谁申请谁释放 | 文档需明确调用者是否负责 free |

### 3.6 sizeof 陷阱

```c
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int *p = malloc(10 * sizeof(int));
    if (p == NULL) return 1;

    /* sizeof 在编译期求值，不会解引用 p */
    printf("sizeof(p)   = %zu   ← 指针变量的大小（64 位平台为 8）\n",
           sizeof(p));
    printf("sizeof(*p)  = %zu   ← 指针指向的类型大小（int 通常为 4）\n",
           sizeof(*p));

    /* 经典错误：sizeof(p) = 8，只初始化了 8 字节而非 40 字节 */
    /* memset(p, 0, sizeof(p));   ← 错误！应改为 10 * sizeof(*p) */

    /* 动态数组必须单独记录长度 —— sizeof 无法反推 malloc 分配了多少 */
    printf("10 * sizeof(*p) = %zu   ← 这才是分配的实际大小\n",
           (size_t)(10 * sizeof(*p)));

    free(p);
    return 0;
}
```

| 表达式 | 结果 | 说明 |
|--------|:---:|------|
| `sizeof(arr)`，`int arr[10]` | 40 | 编译期已知数组大小（Ph03 特例） |
| `sizeof(ptr)`，`int *ptr` | 8 | 指针变量本身大小 |
| `sizeof(*ptr)` | 4 | 指针指向的类型大小 |
| malloc 分配的大小 | — | **无法得知**，必须单独记录 |

## 4. 底层原理

### 4.1 malloc 如何获取内存：brk 与 mmap

```text
进程地址空间（简化，从高到低）:
栈 ↓       — 局部变量，自动回收
mmap 区域   — 大块分配（默认 ≥ 128KB），独立映射
堆 ↑       — 小块分配，brk/sbrk 上移堆顶
BSS/Data   — 全局/静态变量
Text       — 代码段（只读）
```

malloc 不每次调用都发起系统调用——它维护用户态空闲链表，优先从中分配。只有空闲链表不够时，才通过 brk 或 mmap 向内核申请更多内存。

### 4.2 free 如何知道释放多大 — 块头部的秘密

每个 malloc 返回的指针前面，隐藏着一个**块头部（chunk header）**：

```text
                    ┌──────────────────────────┐
 malloc 返回值 p →  │     用户数据区             │  ← 你可以读写的区域
                    ├──────────────────────────┤
                    │ chunk size + flags        │  ← 分配器的元数据
 实际块起始地址 →    └──────────────────────────┘
```

`free(p)` 从 p 往前偏移读取头部的 size 字段以确定释放字节数。传给 `free` 的指针**必须等于 malloc/calloc/realloc 的原始返回值**——偏移后的指针读到错误数据，导致未定义行为。

### 4.3 内存碎片：为什么"总空闲够了"却"分不出来"

```text
初始:         [████████ 空闲 100 字节 ████████]
分配 A(30):  [AAAA ██████ 空闲 70 ██████]
分配 B(30):  [AAAA][BBBB ████ 空闲 40 ████]
释放 A:      [空30][BBBB ████ 空闲 40 ████]
分配 C(50):  [空30][BBBB ████ 空闲 40 ████]   ← 总空闲 70，但最大连续仅 40
```

频繁的小分配/释放产生**外部碎片**——总空闲足够但被分割成不连续小块。现代分配器（jemalloc、tcmalloc）通过 size-class 策略缓解：同大小对象从同一 slab 分配。

## 5. 使用场景

| 场景 | 选栈还是堆 | 理由 |
|------|:---------:|------|
| 编译期大小未知的数组（如用户输入决定 N） | 堆 | 栈数组大小必须编译期常量（VLA 除外） |
| 函数返回新创建的数据 | 堆 | 栈变量离开作用域即失效 |
| 几 MB 以上的大缓冲区 | 堆 | 栈默认仅 8MB，大型 buffer 会栈溢出 |
| 函数内部的小型临时 buffer（≤ 1KB） | 栈 | 更快，自动回收，不会忘记释放 |
| 变长字符串拼接 | 堆 realloc | 需要动态扩容 |
| 固定大小对象高频分配 | 内存池 | 批量申请，减少 malloc/free 开销 |
| 跨模块共享的数据 | 堆 | 需明确所有权（谁申请谁释放） |

### 经典内存错误速查

| 错误类型 | 症状 | 根因 | 检测 |
|---------|------|------|:---:|
| 内存泄漏 | 进程内存增长 → OOM | malloc 后没 free | Valgrind |
| double-free | 堆损坏 / 崩溃 | 同一指针 free 两次 | ASan |
| use-after-free | 随机崩溃 / 数据错乱 | free 后继续读写 | ASan |
| 野指针 | 不可预测行为 / 崩溃 | 未初始化指针解引用 | ASan |
| 越界写 | 覆盖相邻数据 / 崩溃 | 写入超分配大小 | ASan |
| 越界读 | 读到随机值 | 读取超分配大小 | Valgrind |

## 6. 代码示例

### 示例 1：动态数组（含扩容与缩容）
```c
#include <stdio.h>
#include <stdlib.h>

typedef struct {
    int   *data;
    size_t len;   /* 已使用的元素数 */
    size_t cap;   /* 已分配的容量（元素数） */
} DynArray;

int da_init(DynArray *da) {
    da->data = malloc(4 * sizeof(int));
    if (da->data == NULL) return -1;
    da->len = 0;
    da->cap = 4;
    return 0;
}

void da_destroy(DynArray *da) {
    free(da->data);
    da->data = NULL;
    da->len = da->cap = 0;
}

/* 追加元素，容量不够时自动 2x 扩容 */
int da_push(DynArray *da, int val) {
    if (da->len == da->cap) {
        size_t new_cap = da->cap * 2;
        int *tmp = realloc(da->data, new_cap * sizeof(int));
        if (tmp == NULL) return -1;  /* 扩容失败，原数据不丢失 */
        da->data = tmp;
        da->cap  = new_cap;
    }
    da->data[da->len++] = val;
    return 0;
}

/* 使用率 < 25% 时容量减半 */
void da_shrink(DynArray *da) {
    if (da->len < da->cap / 4 && da->cap > 4) {
        size_t new_cap = da->cap / 2;
        int *tmp = realloc(da->data, new_cap * sizeof(int));
        if (tmp != NULL) { da->data = tmp; da->cap = new_cap; }
    }
}

int main(void) {
    DynArray da;
    if (da_init(&da) != 0) return 1;

    for (int i = 0; i < 20; i++)
        da_push(&da, i * 10);
    printf("插入 20 个后: len=%zu, cap=%zu\n", da.len, da.cap);

    da.len = 4;  /* 模拟弹出到只剩 4 个元素 */
    da_shrink(&da);
    printf("缩容后: len=%zu, cap=%zu, data=[", da.len, da.cap);
    for (size_t i = 0; i < da.len; i++)
        printf("%d%s", da.data[i], i < da.len - 1 ? ", " : "");
    printf("]\n");

    da_destroy(&da);
    return 0;
}
```

### 示例 2：动态字符串（append 操作）

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char  *data;
    size_t len;   /* 不含 \0 的字符数 */
    size_t cap;   /* 缓冲区总字节数，含 \0 */
} DynStr;

int ds_init(DynStr *ds) {
    ds->data = malloc(16);
    if (ds->data == NULL) return -1;
    ds->data[0] = '\0';
    ds->len = 0;
    ds->cap = 16;
    return 0;
}

void ds_destroy(DynStr *ds) {
    free(ds->data);
    ds->data = NULL;
    ds->len = ds->cap = 0;
}

/* 在末尾追加 C 字符串 */
int ds_append(DynStr *ds, const char *suffix) {
    size_t slen = strlen(suffix);
    size_t need = ds->len + slen + 1;   /* +1 给 \0 */
    if (need > ds->cap) {
        size_t new_cap = ds->cap;
        while (new_cap < need) new_cap *= 2;
        char *tmp = realloc(ds->data, new_cap);
        if (tmp == NULL) return -1;
        ds->data = tmp;
        ds->cap  = new_cap;
    }
    memcpy(ds->data + ds->len, suffix, slen + 1); /* +1 复制 \0 */
    ds->len += slen;
    return 0;
}

int main(void) {
    DynStr ds;
    if (ds_init(&ds) != 0) return 1;

    ds_append(&ds, "Hello");
    ds_append(&ds, ", ");
    ds_append(&ds, "World!");
    printf("\"%s\"  (len=%zu, cap=%zu)\n", ds.data, ds.len, ds.cap);

    ds_destroy(&ds);
    return 0;
}
```

### 示例 3：简单固定块内存池

核心思想：一次申请大块内存，切分成固定大小 slot，分配/释放只操作空闲链表，O(1) 且避免频繁系统调用。

```c
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

#define POOL_BLOCK_SIZE 32
#define POOL_BLOCK_COUNT 8

typedef struct Block {
    struct Block *next;               /* 空闲链表指针 */
    char          data[POOL_BLOCK_SIZE]; /* 用户数据区 */
} Block;

typedef struct {
    Block *free_list;   /* 空闲链表头 */
    Block *chunk;       /* 整块申请，用于整体释放 */
} MemPool;

int pool_init(MemPool *pool) {
    pool->chunk = malloc(POOL_BLOCK_COUNT * sizeof(Block));
    if (pool->chunk == NULL) return -1;
    /* 将所有 block 串成空闲链表 */
    pool->free_list = pool->chunk;
    for (int i = 0; i < POOL_BLOCK_COUNT - 1; i++)
        pool->chunk[i].next = &pool->chunk[i + 1];
    pool->chunk[POOL_BLOCK_COUNT - 1].next = NULL;
    return 0;
}

void pool_destroy(MemPool *pool) {
    free(pool->chunk);
    pool->chunk     = NULL;
    pool->free_list = NULL;
}

void *pool_alloc(MemPool *pool) {
    if (pool->free_list == NULL) return NULL;  /* 池已空 */
    Block *blk = pool->free_list;
    pool->free_list = blk->next;
    return blk->data;
}

void pool_free(MemPool *pool, void *ptr) {
    if (ptr == NULL) return;
    /* 通过 ptr 反推 Block 起始地址 */
    Block *blk = (Block *)((char *)ptr - offsetof(Block, data));
    blk->next = pool->free_list;
    pool->free_list = blk;
}

int main(void) {
    MemPool pool;
    if (pool_init(&pool) != 0) {
        fprintf(stderr, "内存池初始化失败\n");
        return 1;
    }
    void *a = pool_alloc(&pool);
    void *b = pool_alloc(&pool);
    printf("分配 2 块: a=%p, b=%p\n", a, b);

    pool_free(&pool, a);
    pool_free(&pool, b);
    printf("释放后空闲链表头: %p\n", (void *)pool.free_list);

    /* 耗尽池中所有块 */
    for (int i = 0; i < POOL_BLOCK_COUNT; i++)
        pool_alloc(&pool);
    void *overflow = pool_alloc(&pool);
    printf("超容量分配: %s\n",
           overflow == NULL ? "正确返回 NULL" : "ERROR: 应返回 NULL");

    pool_destroy(&pool);
    return 0;
}
```

## 7. 总结

### 关键要点

1. **栈 vs 堆**：栈自动、编译期定大小、8MB 限制；堆手动、运行期定大小、受虚拟内存限制
2. **malloc 必须检查 NULL**：不检查 → 解引用空指针 → 崩溃
3. **realloc 必须用临时指针**：`tmp = realloc(p, ...)` → 检查 `tmp` → 成功后才 `p = tmp`
4. **free 后置 NULL**：防 use-after-free（但不能防御指向同一块的别名指针）
5. **sizeof(ptr) 不是分配大小**：返回 8（指针本身），动态数组长度必须单独记录
6. **谁申请谁释放**：跨模块传递所有权时，文档必须说明调用者是否负责 free
7. **工具链必选**：`valgrind --leak-check=full` 查泄漏、`-fsanitize=address` 查越界和 UAF

### 跨语言对比：内存管理模型

| 特性 | C | C++ | Java | Rust |
|------|---|-----|------|------|
| 分配/释放 | malloc / free | new / delete + 智能指针 | new（GC） | Box::new（所有权 Drop） |
| 释放时机 | 程序员决定 | 手动 / RAII 自动 | GC（STW 暂停） | 编译期（离开作用域） |
| 泄漏风险 | 高 | 中（循环引用） | 低（GC） | 极低（借用检查） |
| 性能 | 最快 | 快 | GC 暂停不可控 | 零成本抽象 |
| 安全保障 | 无 | 部分（智能指针） | 内存安全 | 编译期保证 |

C 给程序员最大控制权和最小安全网——这使它适合 OS、数据库内核和嵌入式，也使它必须用 Valgrind/ASan 托底。

### 阶段验收标准

- 能画出栈和堆在进程地址空间中的位置，解释两者生命周期、大小限制差异
- 能说明 malloc/calloc/realloc/free 四个 API 的参数、返回值、失败处理
- 能写出包含错误处理的"分配 → 使用 → 扩容 → 释放"完整路径
- 能识别并修复内存泄漏、double-free、use-after-free、野指针和越界访问
- 能解释 `sizeof(ptr)` vs `sizeof(*ptr)` 的含义差异，动态数组为何必须单独记录长度
- 能使用 `gcc -fsanitize=address -g` 编译定位越界和 use-after-free
- 能使用 `valgrind --leak-check=full ./a.out` 并确认 `definitely lost` 为 0

### 推荐项目与练习

- **动态数组库**（`darray.h` + `darray.c`）：支持 `push/pop`、2x 自动扩容、手动缩容，realloc 失败路径不丢数据
- **动态字符串**（`DynStr`）：支持 `append`、赋值、清空，处理 `\0` 结尾
- **固定块内存池**：32 或 64 字节块，演示 O(1) 分配/释放，对比与 malloc/free 的速度差异（`clock()` 计时）
- 用 Valgrind 检查动态数组代码，确认 `definitely lost` 为 0
- 写一个故意越界的程序（`p[len] = 0`），用 `gcc -fsanitize=address -g` 编译运行，读懂 ASan 输出中的源码行号

### 下一阶段
[结构体与数据结构阶段](../Ph05-struct-datastruct/05-struct-datastruct.md)— `struct`/`union`/`enum`、结构体内存对齐与 padding、链表/栈/队列/哈希表在 C 中的实现。
