# C 语言数组、字符串、指针阶段

> C 学习路线上最陡的台阶——从函数模块化进入内存模型，掌握"数据在内存中如何摆放、如何被访问"这个核心问题。

## 1. 概述

数组、字符串、指针阶段是 C 语言学习的分水岭，目标是：**能画出数组和指针在内存中的关系图，理解数组退化与指针运算的物理意义，手写字符串处理函数，写出不越界的代码**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 数组 | 一维数组、二维数组、字符数组、Row-Major 内存布局 |
| 字符串 | `\0` 终止符、字符数组与字符串字面量、`strlen/strcpy/strcmp/strcat` |
| 指针基础 | 声明、取地址 `&`、解引用 `*`、指针类型与步长 |
| 指针运算 | `p+1` 跳过 `sizeof(*p)` 字节、`arr[i]` ≡ `*(arr+i)` |
| 指针与数组 | 数组退化（array decay）、`arr` vs `&arr` 的类型差异 |
| 函数传参 | 指针参数实现"修改调用者变量"（兑现 ph02 3.2 的伏笔） |

本阶段聚焦**栈上数据和指针本身**，不涉及 `malloc/free`、堆内存分配、`struct` — 这些是后续 ph04（内存管理）和 ph05（结构体）的内容。

## 2. 来源与演变

C 指针的设计直接反映了 PDP-11 的寻址硬件。

| 阶段 | 硬件/语言 | 指针形态 |
|------|----------|---------|
| PDP-11 汇编 | 寄存器间接寻址 `@R5` | 寄存器存地址，间接访问内存 |
| B 语言（Thompson） | 单一类型"字" | 一切是指针，无类型系统 |
| 早期 C（Ritchie） | 引入类型系统 | `int *p` 知道指向什么类型 |
| K&R C | 指针与数组语法交织 | `a[i]` 是 `*(a+i)` 的语法糖 |
| ANSI C / C89 | `void *` 泛型指针 | 类型擦除，需显式转换 |
| C99 / C11 | `restrict`、VLA | 为编译器优化提供别名信息 |

**数组退化是"免费"抽象的代价**：C 的设计哲学是"不隐藏机器细节"。传递整个数组的副本太昂贵，所以 C 选择只传首地址——这在汇编层面是零开销的，但在语义上把"数组"和"首元素指针"搅在了一起。理解这一点，就理解了 C 指针设计中最核心的权衡。

本文示例以 **C99** 为基线（`//` 注释、`for` 循环内声明变量、`stdint.h` 均可用），现代编译器（GCC / Clang / MSVC）默认支持，编译统一加 `-Wall -Wextra -std=c99`。数组、指针与字符串的语义自 C89 起就是 C 语言最稳定的部分。

## 3. 语法与参数

### 3.1 一维数组

数组是一段**连续内存**，所有元素类型相同。

```c
#include <stdio.h>

int main(void) {
    int arr[5] = {10, 20, 30, 40, 50};

    printf("sizeof(arr) = %zu 字节\n", sizeof(arr));  // 5 * 4 = 20
    for (int i = 0; i < 5; i++) {
        printf("arr[%d] = %d, 地址 = %p\n", i, arr[i], (void *)&arr[i]);
    }
    return 0;
}
```

| 操作 | 写法 | 含义 |
|------|------|------|
| 声明 | `int a[5];` | 栈上分配 5 个 int（20 字节，假设 int=4） |
| 初始化 | `int a[5] = {1,2,3};` | 前三个为 1/2/3，后两个为 0 |
| 访问 | `a[2]` 或 `2[a]` | 等价于 `*(a+2)` |
| 数组大小 | `sizeof(a)` | 整个数组的字节数，不是元素个数 |
| 元素个数 | `sizeof(a) / sizeof(a[0])` | 编译期常量时可这样算 |

### 3.2 二维数组

C 的二维数组是"数组的数组"：`int arr[2][3]` 是 2 个元素，每个元素是一个 `int[3]`。内存中按**行优先（Row-Major）**连续存放。

```c
#include <stdio.h>

int main(void) {
    int matrix[2][3] = {{1, 2, 3}, {4, 5, 6}};

    printf("sizeof(matrix) = %zu 字节\n", sizeof(matrix));  // 2 * 3 * 4 = 24
    for (int i = 0; i < 2; i++)
        for (int j = 0; j < 3; j++)
            printf("matrix[%d][%d] = %d\n", i, j, matrix[i][j]);
    return 0;
}
```

`matrix[i][j]` 的寻址公式：`*(*(matrix + i) + j)` — 先定位第 i 行，再在该行中找第 j 个元素。

### 3.3 字符数组与字符串

C 没有内置字符串类型。字符串本质是**以 `\0`（NUL，ASCII 值 0）结尾的字符数组**。

```c
#include <stdio.h>

int main(void) {
    char s1[] = "hello";                            // 长度 6：h e l l o \0
    char s2[6] = {'h', 'e', 'l', 'l', 'o', '\0'};  // 手动加 \0
    const char *s3 = "hello";                       // 指向只读数据段

    printf("s1=%s, 长度=%zu\n", s1, sizeof(s1));
    printf("s2=%s\n", s2);
    printf("s3=%s\n", s3);
    return 0;
}
```

字符串字面量 `"hello"` 存储在只读数据段，用 `char *` 指向时不应修改内容；用 `char[]` 声明时，编译器会在栈上复制一份，可以修改。

### 3.4 指针基础

指针保存的是**另一个变量的内存地址**。三个核心操作：`&` 取地址，`*` 解引用，声明时 `*` 表示指针类型。

```c
#include <stdio.h>

int main(void) {
    int x = 42;
    int *p = &x;           // p 保存 x 的地址

    printf("x 的值: %d\n", x);
    printf("x 的地址: %p\n", (void *)&x);
    printf("p 的值（即 &x）: %p\n", (void *)p);
    printf("*p（解引用）: %d\n", *p);

    *p = 99;               // 通过指针修改 x
    printf("修改后 x = %d\n", x);
    return 0;
}
```

| 符号 | 语境 | 含义 |
|------|------|------|
| `int *p` | 声明 | p 是指向 int 的指针 |
| `&x` | 表达式 | 取 x 的地址 |
| `*p` | 表达式 | 解引用：访问 p 指向的值 |
| `p` | 表达式 | 指针本身的值（某个地址） |

空指针用 `NULL` 表示"不指向任何有效地址"，解引用 `NULL` 是未定义行为。

### 3.5 指针运算

指针运算的**物理意义**：`p + n` 的地址值 = `p` 的值 + `n * sizeof(*p)` 字节。指针类型决定了步长。

```c
#include <stdio.h>

int main(void) {
    int  arr[] = {100, 200, 300, 400};
    char str[] = "ABCD";
    int  *pi = arr;
    char *pc = str;

    printf("pi = %p, *pi = %d\n",   (void *)pi, *pi);
    printf("pi+1 = %p, *(pi+1) = %d\n", (void *)(pi+1), *(pi+1));
    printf("pc = %p, *pc = %c\n",   (void *)pc, *pc);
    printf("pc+1 = %p, *(pc+1) = %c\n", (void *)(pc+1), *(pc+1));
    return 0;
}
```

步长对比：

```text
char  *p;   p+1  → 地址 + 1 字节   （sizeof(char)  = 1）
int   *p;   p+1  → 地址 + 4 字节   （sizeof(int)   = 4）
double *p;  p+1  → 地址 + 8 字节   （sizeof(double) = 8）
```

指针相减 `p - q` 得到的是**元素个数**（不是字节差），前提是两个指针指向同一数组。

### 3.6 `arr[i]` ≡ `*(arr + i)` — C 标准规定的等价

这不是巧合，是 C 标准（C11 6.5.2.1）的规定：`E1[E2]` 等价于 `(*((E1)+(E2)))`。编译器对两者生成的机器码完全相同。

内存视角（`int arr[4] = {10, 20, 30, 40}`，起始地址 `0x1000`，`sizeof(int) = 4`）：

```text
地址:     0x1000  0x1004  0x1008  0x100C
         +-------+-------+-------+-------+
内容:     |  10   |  20   |  30   |  40   |
         +-------+-------+-------+-------+
表达式:    arr[0]   arr[1]   arr[2]   arr[3]
等价:     *(arr+0) *(arr+1) *(arr+2) *(arr+3)
```

### 3.7 数组退化（Array Decay）— 本章最核心概念

在**绝大多数表达式**中，数组名会**退化为指向首元素的指针**。例外仅有两处：`sizeof(数组名)` 返回整个数组的字节数，`&数组名` 返回整个数组的地址（类型不同）。

```c
#include <stdio.h>

int main(void) {
    int arr[4] = {10, 20, 30, 40};

    printf("arr     = %p  类型: int*      (退化后)\n", (void *)arr);
    printf("&arr[0] = %p  类型: int*      (首元素地址)\n", (void *)&arr[0]);
    printf("&arr    = %p  类型: int(*)[4] (整个数组的地址)\n", (void *)&arr);

    printf("\n数值上三者相同，但类型不同：\n");
    printf("  arr + 1     = %p  (跳 4 字节)\n", (void *)(arr + 1));
    printf("  &arr[0] + 1 = %p  (跳 4 字节)\n", (void *)(&arr[0] + 1));
    printf("  &arr + 1    = %p  (跳 16 字节 = 整个数组)\n", (void *)(&arr + 1));

    printf("\nsizeof(arr)  = %zu  (整个数组)\n", sizeof(arr));
    printf("sizeof(&arr[0]) = %zu  (指针大小)\n", sizeof(&arr[0]));
    return 0;
}
```

| 表达式 | 值（地址数值） | 类型 | `+1` 跳过 |
|--------|:-------------:|------|----------|
| `arr`（退化后） | `0x1000` | `int *` | 4 字节 |
| `&arr[0]` | `0x1000` | `int *` | 4 字节 |
| `&arr` | `0x1000` | `int (*)[4]` | 16 字节（整个数组） |

### 3.8 指针作为函数参数——兑现 ph02 的伏笔

ph02 3.2 讲过"要让函数修改调用者的变量需要指针"。本章兑现这个承诺。

```c
#include <stdio.h>

void swap(int *a, int *b) {
    int tmp = *a;
    *a = *b;
    *b = tmp;
}

void print_array(int arr[], int n) {   // int arr[] 等价于 int *arr
    for (int i = 0; i < n; i++)
        printf("%d ", arr[i]);
    printf("\n");
}

int main(void) {
    int x = 3, y = 7;
    printf("交换前: x=%d, y=%d\n", x, y);
    swap(&x, &y);
    printf("交换后: x=%d, y=%d\n", x, y);

    int nums[] = {1, 2, 3, 4, 5};
    print_array(nums, 5);
    return 0;
}
```

函数参数中的 `int arr[]` 本质上就是 `int *arr` — 这是数组退化在函数签名中的体现。调用 `print_array(nums, 5)` 时，`nums` 退化为 `&nums[0]`，传递的是首元素地址，不是整个数组的副本。

## 4. 底层原理

### 4.1 一维数组的内存布局

假设 `int arr[5] = {10, 20, 30, 40, 50}` 从地址 `0x7ffc1000` 开始：

```text
地址       偏移   内容     对应表达式
─────────────────────────────────────
0x7ffc1000  +0   [ 10 ]   arr[0] / *(arr+0)
0x7ffc1004  +4   [ 20 ]   arr[1] / *(arr+1)
0x7ffc1008  +8   [ 30 ]   arr[2] / *(arr+2)
0x7ffc100C  +12  [ 40 ]   arr[3] / *(arr+3)
0x7ffc1010  +16  [ 50 ]   arr[4] / *(arr+4)
            每个方格 4 字节（sizeof(int)）
            arr 退化为 0x7ffc1000（类型 int*）
```

### 4.2 字符串在内存中的形态

C 字符串的本质是字符指针指向连续 `char` 序列的第一个字节，以 `\0` 标记结束。

```text
char str[] = "hi";
char *p   = "hi";   // p 指向只读数据段

栈上 str（可写）:              只读数据段（不可写）:
┌────┬────┬────┐              ┌────┬────┬────┐
│ h  │ i  │ \0 │              │ h  │ i  │ \0 │
└────┴────┴────┘              └────┴────┴────┘
  ^                              ^
  str 退化为 &str[0]             p 指向这里
```

关键风险：如果 `\0` 缺失（例如用 `{'a','b','c'}` 初始化但没有 `\0`），`strlen` 会持续越界读取直到碰巧遇到值为 0 的字节——这是典型的未定义行为。

### 4.3 二维数组的 Row-Major 布局

`int matrix[2][3] = {{1,2,3}, {4,5,6}}` 从地址 `0x2000` 开始：

```text
地址       对应元素      逻辑位置
──────────────────────────────────
0x2000     [  1  ]      matrix[0][0]
0x2004     [  2  ]      matrix[0][1]
0x2008     [  3  ]      matrix[0][2]
0x200C     [  4  ]      matrix[1][0]  ← 第二行紧接第一行
0x2010     [  5  ]      matrix[1][1]
0x2014     [  6  ]      matrix[1][2]

matrix     → 类型 int (*)[3]，指向第一行
matrix[0]  → 类型 int *，    指向第一行第一个元素
matrix+1   → 地址 = 0x2000 + 1*12 = 0x200C（跳一整行）
```

寻址展开：`matrix[1][2]` → `*(*(matrix + 1) + 2)` → `*(0x200C + 2*4)` → `*(0x2014)` → `6`。注意 `matrix` 类型是 `int (*)[3]`（指向 `int[3]` 的指针），不是 `int **`。`int **` 用于动态分配的指针数组，内存不连续——和栈上二维数组是完全不同的内存模型。

### 4.4 指针越界——未定义行为的典型来源

```text
int arr[3] = {1, 2, 3};
         ┌──────┬──────┬──────┬─ ─ ─ ─
合法访问: │  1   │  2   │  3   │  ???   ← arr[3] 越界，UB
         └──────┴──────┴──────┴─ ─ ─ ─
```

越界读可能读到栈上其他变量；越界写可能覆盖返回地址导致崩溃。理解指针步长和数组边界是写出安全 C 代码的基础。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 遍历数组并修改元素 | 指针作为迭代器，`*p++` 惯用法 |
| 字符串比较、复制、拼接 | `\0` 终止、指针运算、手写 `strcpy/strcmp` |
| 函数返回多个值 | 通过指针参数"输出"额外结果 |
| 反转数组 / 反转字符串 | 双指针相向而行，`while (left < right)` |
| 子串查找 | 双重循环 + 指针匹配模式 |
| 文本统计（字数、行数、词频） | 遍历字符数组，识别 `\n`、空格、标点 |

**不适合**此阶段的事项：
- 动态数组扩容 / 变长字符串 — 需要 `malloc/realloc`（ph04 详解）
- 链表、树、哈希表 — 需要 `struct` + 动态分配（ph05 详解）
- 通用回调 / 函数表 — 需要函数指针（ph05+ 详解）
- 多级间接寻址（`int ***` 等）— 过度抽象，生产代码极少使用

## 6. 代码示例

> 完整可运行文件见 [`examples/`](./examples/)，每个示例对应一个 `ex0*-*.c`，已在本环境用 `gcc -Wall -Wextra -std=c99` 验证（零警告）。

### 示例 1：手写 strlen、strcpy、strcmp、strcat（带测试）

完整文件：`examples/ex01-strlib.c`

```c
#include <stdio.h>

/* 计算字符串长度（不含 \0） */
size_t my_strlen(const char *s) {
    const char *p = s;
    while (*p) p++;
    return (size_t)(p - s);
}

/* 复制 src 到 dst（含 \0），返回 dst */
char *my_strcpy(char *dst, const char *src) {
    char *d = dst;
    while ((*d++ = *src++) != '\0')
        ;
    return dst;
}

/* 按字典序比较 s1 和 s2 */
int my_strcmp(const char *s1, const char *s2) {
    while (*s1 && *s1 == *s2) { s1++; s2++; }
    return (unsigned char)*s1 - (unsigned char)*s2;
}

/* 把 src 追加到 dst 末尾（覆盖 dst 的 \0），返回 dst */
char *my_strcat(char *dst, const char *src) {
    char *d = dst;
    while (*d) d++;                    /* 走到 dst 的 \0 */
    while ((*d++ = *src++) != '\0')    /* 从这里开始追加 src */
        ;
    return dst;
}

int main(void) {
    const char *test = "hello world";
    printf("my_strlen(\"%s\") = %zu  (期望 11)\n", test, my_strlen(test));

    char buf[64];
    my_strcpy(buf, "C pointer");
    printf("my_strcpy: \"%s\"  (期望 \"C pointer\")\n", buf);

    my_strcat(buf, " is power");
    printf("my_strcat: \"%s\"  (期望 \"C pointer is power\")\n", buf);

    printf("my_strcmp(\"abc\",\"abc\") = %d  (期望 0)\n", my_strcmp("abc", "abc"));
    printf("my_strcmp(\"abc\",\"abd\") = %d  (期望 <0)\n", my_strcmp("abc", "abd"));
    printf("my_strcmp(\"xyz\",\"abc\") = %d  (期望 >0)\n", my_strcmp("xyz", "abc"));
    return 0;
}
```

**strcat 的两个坑**：① 目标缓冲区必须有足够剩余空间（`dst` 容量 ≥ `strlen(dst) + strlen(src) + 1`），否则溢出是未定义行为；② `dst` 必须已有 `\0` 结尾——未初始化的 `char buf[64]` 直接 strcat 会从随机位置开始追加。工程代码用 `strncat(dst, src, sizeof(dst) - strlen(dst) - 1)` 限定追加长度。

### 示例 2：数组反转与字符串反转

完整文件：`examples/ex02-reverse.c`

```c
#include <stdio.h>

void reverse_array(int *arr, size_t n) {
    int *left = arr, *right = arr + n - 1;
    while (left < right) {
        int tmp = *left;
        *left = *right;
        *right = tmp;
        left++; right--;
    }
}

void reverse_string(char *s) {
    if (s == NULL || *s == '\0') return;
    char *left = s, *right = s;
    while (*right) right++;      // right 走到 \0
    right--;                     // right 指向最后一个字符
    while (left < right) {
        char tmp = *left;
        *left = *right;
        *right = tmp;
        left++; right--;
    }
}

int main(void) {
    int arr[] = {1, 2, 3, 4, 5, 6};
    size_t n = sizeof(arr) / sizeof(arr[0]);

    reverse_array(arr, n);
    printf("数组反转: ");
    for (size_t i = 0; i < n; i++) printf("%d ", arr[i]);
    printf(" (期望 6 5 4 3 2 1)\n");

    char s1[] = "pointer";
    reverse_string(s1);
    printf("字符串反转: \"%s\"  (期望 \"retniop\")\n", s1);
    return 0;
}
```

### 示例 3：子串查找（朴素匹配）

完整文件：`examples/ex03-strstr.c`

```c
#include <stdio.h>

char *my_strstr(const char *str, const char *sub) {
    if (*sub == '\0') return (char *)str;
    while (*str) {
        const char *s = str, *p = sub;
        while (*s && *p && *s == *p) { s++; p++; }
        if (*p == '\0') return (char *)str;
        str++;
    }
    return NULL;
}

int main(void) {
    const char *text = "hello world, welcome to C";
    const char *pattern = "world";
    char *pos = my_strstr(text, pattern);
    if (pos)
        printf("找到 \"%s\"，偏移 = %td\n", pattern, pos - text);
    else
        printf("未找到 \"%s\"\n", pattern);
    return 0;
}
```

### 示例 4：简单文本统计工具（推荐项目雏形）

完整文件：`examples/ex04-text-stats.c`

```c
#include <stdio.h>

void text_stats(const char *text) {
    int chars = 0, words = 0, lines = 0, in_word = 0;
    for (const char *p = text; *p != '\0'; p++) {
        chars++;
        if (*p == '\n') lines++;
        if (*p == ' ' || *p == '\n' || *p == '\t')
            in_word = 0;
        else if (!in_word) { in_word = 1; words++; }
    }
    /* 若最后一行没有换行符结尾，行数要 +1；否则 lines 已经等于行数 */
    int total_lines = (chars > 0 && text[chars - 1] != '\n') ? lines + 1 : lines;
    printf("字符数: %d\n单词数: %d\n行数: %d\n", chars, words, total_lines);
}

int main(void) {
    /* 输入格式: 多行文本，Ctrl+D（Unix）或 Ctrl+Z（Windows）结束 */
    char buf[4096] = {0};
    size_t total = 0;
    int c;
    while (total < sizeof(buf) - 1 && (c = getchar()) != EOF)
        buf[total++] = (char)c;
    buf[total] = '\0';
    text_stats(buf);
    return 0;
}
```

## 7. 总结

### 关键要点

1. **数组名退化为首元素指针**：`sizeof` 和 `&` 是仅有的两个例外
2. **`arr`、`&arr[0]`、`&arr` 数值相同类型不同**：前两个 `+1` 跳 `sizeof(T)` 字节，第三个跳整个数组
3. **指针运算步长由类型决定**：`p + n` 移动 `n * sizeof(*p)` 字节
4. **`arr[i]` 就是 `*(arr + i)`**：C 标准规定的等价，不是巧合
5. **字符串是 `\0` 结尾的字符数组**：`\0` 缺失导致 `strlen` 越界读
6. **指针越界是未定义行为**：越界写可能覆盖返回地址
7. **`T arr[]` 参数就是 `T *arr`**：传指针不是传数组副本

### 跨语言对比：指针 / 引用 / 字符串

| 特性 | C | Java | Go | Rust |
|------|---|------|----|------|
| 指针/引用 | `int *p`，可算术 | 引用（无算术） | `*int`（unsafe） | `&T`（无算术） / `*const T` 裸指针 |
| 空值 | `NULL` | `null` | `nil` | `None`（`Option<&T>`） |
| 字符串类型 | `char *`/`char[]`，`\0` 终止 | `String`（UTF-16） | `string`（UTF-8） | `&str` / `String` |
| 数组越界 | 未定义行为 | 抛异常 | panic | panic |
| 修改调用者变量 | 传指针 | 基本类型不可 | 传指针 | `&mut T` |

### 阶段验收清单

- [ ] 能画出数组和指针在内存中的关系图
- [ ] 能解释 `arr` 与 `&arr` 在类型和步长上的区别
- [ ] 能手写 `strlen`、`strcpy`、`strcmp`，不是调用 API
- [ ] 能写出不越界的数组遍历和字符串处理代码
- [ ] 能用双指针技巧实现数组反转 / 字符串反转，并解释 `left < right` 终止条件
- [ ] 能说明二维数组 Row-Major 布局和 `matrix[i][j]` 的寻址展开过程

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：字符串处理库（`my_strlen`/`my_strcpy`/`my_strcmp`/`my_strcat`/`my_strstr`，多文件组织）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[内存管理阶段](../ph04-memory-mgmt/04-memory-mgmt.md) — `malloc` / `free`、动态数组、内存泄漏与悬空指针、`valgrind` / ASan 工具链。
