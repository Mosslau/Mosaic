# C 语言函数与模块化阶段

> 面向系统底层、数据库存储引擎、KV 库方向，从单文件逻辑走向可复用函数与多文件组织。

## 1. 概述

C 语言函数与模块化阶段是语法基础之后的第一个能力提升点，目标是：**能把代码拆成可复用函数和独立模块，理解声明、定义、链接三者的分工**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 函数基础 | 定义、声明、调用；参数、返回值、函数原型 |
| 参数传递 | 按值传递；形参修改不影响实参 |
| 递归 | 终止条件、调用栈、递归与迭代的取舍 |
| 作用域 | 局部变量、全局变量、块作用域、文件作用域 |
| 模块化 | `.h` 头文件、`.c` 源文件、`#include`、include guard |
| 多文件编译 | `gcc main.c math_utils.c -o app`、目标文件、链接 |

本阶段在单文件基础上扩展到多文件项目，**不涉及指针深入、堆内存分配、结构体和复杂数据结构** — 那些是 **ph03 数组与指针**、**ph04 内存管理**、**ph05 结构体与数据结构**阶段的内容。ph01 中提到"`scanf` 需要 `&`"，本阶段会讲清"按值传递"的本质，并预告："要让函数修改调用者的变量，需要指针，ph03 详解"。

## 2. 来源与演变

C 语言诞生于 1972 年，最初用于重写 Unix 操作系统。为了适应当时内存极小、编译器单遍扫描的硬件环境，C 采用了"声明与定义分离"的设计。

| 阶段 | 特点 |
|------|------|
| 早期汇编 | 通过跳转复用代码 |
| K&R C | 声明可省略参数类型 |
| ANSI C / C89 | 强制函数原型 |
| C99 / C11 | `inline`、可变参数宏 |

C 的模块化思想：**源文件做一件事，头文件暴露接口，链接器拼接目标文件**。

本文示例以 **C99** 为基线（函数原型、`inline`、`static` 语义均与 ph01 一致），现代编译器（GCC / Clang / MSVC）默认支持，编译统一加 `-Wall -Wextra -std=c99`。函数与模块化是 C 语言自诞生起就稳定不变的部分。

## 3. 语法与参数

### 3.1 函数的定义与声明

**函数定义**给出完整实现，**函数声明**只告诉编译器签名，让调用处能进行类型检查。

```c
#include <stdio.h>

// 函数声明（Prototype）
int add(int a, int b);

int main(void) {
    int result = add(3, 5);
    printf("3 + 5 = %d\n", result);
    return 0;
}

// 函数定义
int add(int a, int b) {
    return a + b;
}
```

| 概念 | 作用 | 位置 |
|------|------|------|
| 定义 | 分配存储、提供实现 | `.c` 源文件 |
| 声明 | 告诉编译器签名，供类型检查 | `.h` 头文件或被调用前 |

### 3.2 按值传递

C 函数参数默认**按值传递**（Pass by Value）：调用时把实参的值复制给形参，函数内部修改的是副本，不影响调用者。

```c
#include <stdio.h>

void swap_wrong(int x, int y) {
    int tmp = x;
    x = y;
    y = tmp;
    printf("  函数内: x=%d, y=%d\n", x, y);
}

int main(void) {
    int a = 3, b = 7;
    printf("调用前: a=%d, b=%d\n", a, b);
    swap_wrong(a, b);
    printf("调用后: a=%d, b=%d\n", a, b);
    return 0;
}
```

输出：

```text
调用前: a=3, b=7
  函数内: x=7, y=3
调用后: a=3, b=7
```

要在函数内修改调用者的变量，需要传递地址，即使用指针 — 这是 ph03 的核心内容。

### 3.3 返回值与作用域

| 返回类型 | 含义 | 示例 |
|----------|------|------|
| 具体类型 | 返回一个值 | `int max(int, int)` |
| `void` | 不返回值 | `void greet(void)` |

```c
#include <stdio.h>

int global_count = 0;          // 文件作用域

void increment(void) {
    int local = 0;             // 块作用域
    local++;
    global_count++;
    printf("local=%d, global=%d\n", local, global_count);
}

int main(void) {
    for (int i = 0; i < 3; i++) {
        increment();
    }
    return 0;
}
```

输出：

```text
local=1, global=1
local=1, global=2
local=1, global=3
```

| 变量类型 | 生命周期 | 作用域 | 默认初值 |
|----------|----------|--------|----------|
| 局部变量 | 函数/块执行期间 | 所在块 | 不确定 |
| 全局变量 | 程序运行期间 | 整个文件 | 0 |
| static 局部变量 | 程序运行期间 | 所在块 | 0，只初始化一次 |

### 3.4 static 与链接范围

`static` 有两种含义：延长局部变量生命周期，或限制全局变量/函数的链接范围到本文件。

```c
#include <stdio.h>

static int internal_state = 0;       // 仅本文件可见

static void helper(void) {           // 仅本文件可调用
    internal_state++;
}

int next_id(void) {
    static int id = 0;               // 只初始化一次
    helper();
    return ++id;
}

int main(void) {
    printf("id=%d\n", next_id());
    printf("id=%d\n", next_id());
    printf("id=%d\n", next_id());
    return 0;
}
```

输出：`id=1`、`id=2`、`id=3`（static 局部变量保持状态）

### 3.5 递归

递归函数必须具备：**基准情形**终止递归，**递归情形**向基准推进。

```c
#include <stdio.h>

long long factorial(int n) {
    if (n < 0) return -1;
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

long long fib(int n) {
    if (n <= 0) return 0;
    if (n == 1) return 1;
    return fib(n - 1) + fib(n - 2);
}

int main(void) {
    printf("5! = %lld\n", factorial(5));
    for (int i = 0; i <= 10; i++) {
        printf("fib(%d)=%lld%s", i, fib(i), (i == 10) ? "\n" : ", ");
    }
    return 0;
}
```

输出：`5! = 120`，以及 `fib(0)=0, fib(1)=1, ... fib(10)=55`

### 3.6 头文件与 include guard

头文件本质是**文本包含**。为避免同一头文件被多次包含导致重复定义，使用 include guard。

```c
#ifndef MATH_UTILS_H
#define MATH_UTILS_H

int add(int a, int b);
int max(int a, int b);

#endif // MATH_UTILS_H
```

常见编译器（GCC、Clang、MSVC）支持 `#pragma once` 作为更简洁的替代。

## 4. 底层原理

### 4.1 声明给编译器，定义给链接器

多文件编译流程：

```text
main.c ──预处理──▶ main.i ──编译──▶ main.o ──┐
                                             ├──链接──▶ app
math_utils.c ──▶ math_utils.o ──────────────┘
```

- 编译阶段：每个 `.c` 独立编译，看到声明时生成未解析的函数符号引用
- 链接阶段：合并所有 `.o`，找到函数定义地址，填充引用

缺失定义会报 `undefined reference`，重复定义会报 `multiple definition`。

### 4.2 调用栈与栈帧

每次函数调用在**调用栈**上分配一块**栈帧**，存放返回地址、参数副本、局部变量。函数返回时栈帧销毁。

```c
#include <stdio.h>

void bar(int x) {
    int local = x * 2;
    printf("bar: %d\n", local);
}

void foo(int n) {
    bar(n + 1);
}

int main(void) {
    foo(3);
    return 0;
}
```

输出：`bar: 8`

递归没有终止条件会导致栈帧无限叠加，最终**栈溢出**。

### 4.3 链接范围

| 链接类型 | 可见范围 | 示例 |
|----------|----------|------|
| 外部链接 | 其他文件（需声明） | 非 static 全局变量/函数 |
| 内部链接 | 仅本文件 | `static` 全局变量/函数 |
| 无链接 | 仅所在块 | 局部变量 |

## 5. 使用场景

函数与模块化阶段能解决的典型问题：

| 场景 | 涉及知识点 |
|------|-----------|
| 提取可复用算法 | 函数定义、返回值、参数 |
| 把大程序拆成多个文件 | 头文件、源文件、多文件编译 |
| 实现数学 / 字符串工具库 | 静态函数、include guard |
| 用递归表达分治思想 | 基准情形、调用栈 |
| 隐藏内部实现 | `static` 内部链接 |

**不适合**此阶段的事项：
- 通过函数修改调用者的变量（需要指针，ph03 详解）
- 动态内存分配与释放（`malloc` / `free`，ph04 详解）
- 处理复杂字符串操作（需要字符指针，ph03 详解）
- 实现链表、树等动态数据结构（需要结构体 + 指针，ph05 详解）

## 6. 代码示例

> 完整可运行文件见 [`examples/`](./examples/)，每个示例对应一个 `ex0*-*.c`（示例 4 是多文件项目，在 `ex04-math-utils/` 子目录），已在本环境用 `gcc -Wall -Wextra -std=c99` 验证（零警告）。

### 示例 1：基础函数（单文件）

完整文件：`examples/ex01-basic-func.c`

```c
#include <stdio.h>

int add(int a, int b);
int max(int a, int b);

int main(void) {
    int x = 10, y = 20;
    printf("add(%d, %d) = %d\n", x, y, add(x, y));
    printf("max(%d, %d) = %d\n", x, y, max(x, y));
    return 0;
}

int add(int a, int b) {
    return a + b;
}

int max(int a, int b) {
    return (a > b) ? a : b;
}
```

### 示例 2：按值传递与作用域

完整文件：`examples/ex02-static-scope.c`

```c
#include <stdio.h>

void demo_scope(void) {
    static int call_count = 0;
    call_count++;
    printf("第 %d 次调用\n", call_count);
}

int main(void) {
    for (int i = 0; i < 3; i++) {
        demo_scope();
    }
    return 0;
}
```

输出：`第 1 次调用`、`第 2 次调用`、`第 3 次调用`

### 示例 3：递归阶乘与斐波那契

完整文件：`examples/ex03-recursion.c`

```c
#include <stdio.h>

long long factorial(int n) {
    if (n < 0) return -1;
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

long long fib(int n) {
    if (n <= 0) return 0;
    if (n == 1) return 1;
    return fib(n - 1) + fib(n - 2);
}

int main(void) {
    int n;
    printf("请输入非负整数 n: ");   // 输入格式: 一个整数，如 5
    scanf("%d", &n);

    if (n < 0) {
        printf("n 必须 >= 0\n");
        return 1;
    }

    printf("%d! = %lld\n", n, factorial(n));
    printf("fib(%d) = %lld\n", n, fib(n));
    return 0;
}
```

### 示例 4：多文件项目 — 小型数学工具库

完整文件：`examples/ex04-math-utils/`（`math_utils.h` + `math_utils.c` + `main.c`）

目录结构：

```text
project/
├── math_utils.h
├── math_utils.c
└── main.c
```

`math_utils.h`：

```c
#ifndef MATH_UTILS_H
#define MATH_UTILS_H

int add(int a, int b);
int multiply(int a, int b);
int power(int base, int exp);

#endif // MATH_UTILS_H
```

`math_utils.c`：

```c
#include "math_utils.h"

int add(int a, int b) {
    return a + b;
}

int multiply(int a, int b) {
    return a * b;
}

static int helper(int base, int exp) {
    if (exp == 0) return 1;
    return base * helper(base, exp - 1);
}

int power(int base, int exp) {
    if (exp < 0) return 0;
    return helper(base, exp);
}
```

`main.c`：

```c
#include <stdio.h>
#include "math_utils.h"

int main(void) {
    printf("add(2, 3) = %d\n", add(2, 3));
    printf("multiply(4, 5) = %d\n", multiply(4, 5));
    printf("power(2, 10) = %d\n", power(2, 10));
    return 0;
}
```

编译运行：`gcc -std=c11 -Wall -Wextra main.c math_utils.c -o app && ./app`

输出：

```text
add(2, 3) = 5
multiply(4, 5) = 20
power(2, 10) = 1024
```

### 示例 5：静态作用域与内部链接

完整文件：`examples/ex05-static-internal.c`

```c
#include <stdio.h>

static int secret = 42;

static void internal_helper(void) {
    printf("internal helper\n");
}

int get_secret(void) {
    internal_helper();
    return secret;
}

int main(void) {
    printf("secret = %d\n", get_secret());
    return 0;
}
```

输出：`internal helper` / `secret = 42`

## 7. 总结

### 关键要点

1. **声明给编译器看，定义给链接器看**：头文件放声明，源文件放定义
2. **C 函数参数默认按值传递**：函数内修改的是副本，不影响调用者
3. **递归必须有两个要素**：基准情形终止递归，递归情形向基准推进
4. **`static` 有两种含义**：局部变量延长生命周期，全局变量/函数限制链接范围
5. **头文件本质是文本包含**：include guard 防止重复定义
6. **调用栈和栈帧是函数调用的物理基础**：递归深度过大将导致栈溢出

### 跨语言对比：函数与模块

| 特性 | C | C++ | Java | Python |
|------|---|---|------|--------|
| 声明/定义分离 | 需要（头文件 + 源文件） | 需要 | 不需要 | 不需要 |
| 默认参数传递 | 按值传递 | 按值传递 | 基本类型按值，对象按引用值 | 对象引用 |
| 递归支持 | 支持 | 支持 | 支持 | 支持 |
| 静态局部变量 | `static` 局部变量 | `static` 局部变量 | 无 | 无直接等价 |
| 模块组织 | `.h` / `.c` | 头文件 / 源文件 | `package` | `import` |

### 阶段验收清单

- [ ] 能解释函数声明和函数定义的区别
- [ ] 能写出参数和返回值设计合理的可复用函数
- [ ] 能解释 C 按值传递的行为，并知道修改调用者变量需要指针
- [ ] 能正确编写带终止条件的递归函数
- [ ] 能完成一个多文件小项目（`.h` + `.c` + `main.c`）并成功链接

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：小型数学工具库（加减乘除、幂、gcd、lcm，多文件组织）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[数组、字符串、指针阶段](../ph03-array-str-ptr/03-array-str-ptr.md) — 深入数组退化、指针运算与字符串处理。
