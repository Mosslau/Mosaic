# C 语言基础语法阶段

> 面向系统底层、数据库存储引擎、KV 库方向，从 C 程序结构和编译模型起步。

## 1. 概述

C 语言基础语法阶段是整个 C 学习路线的起点，目标是：**能读懂并写出简单 C 程序，理解编译、链接和可执行文件的基本关系**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 程序结构 | `.c` 源文件、`.h` 头文件、`main` 函数、注释 |
| 数据 | 变量、常量、基本数据类型（`int`/`float`/`char`） |
| 控制流 | 运算符、`if`/`switch`、`for`/`while` |
| 工具链 | `gcc main.c -o app` 编译、链接 |
| I/O | `printf`/`scanf`、标准输入输出 |

这个阶段停留在一个源文件内，**不涉及指针、堆内存、结构体和多文件编译** — 那些是后续阶段的内容。

## 2. 来源与演变

C 语言由 Dennis Ritchie 于 1972 年在贝尔实验室设计，最初用于重写 Unix 操作系统。其设计哲学是**信任程序员、最小运行时、贴近硬件**。

| 版本 | 年份 | 主要变化 |
|------|------|---------|
| K&R C | 1978 | 第一版《The C Programming Language》，定义早期 C 方言 |
| C89/ANSI C | 1989 | 标准化，引入函数原型、`void` 指针、标准库 |
| C99 | 1999 | `//` 注释、变长数组、`inline`、`stdint.h` |
| C11 | 2011 | `_Generic`、`_Atomic`、匿名结构体、多线程支持 |
| C17 | 2017 | 主要是缺陷修复，无重大新特性 |
| C23 | 2023 | `nullptr`、`typeof`、`constexpr`、二进制字面量 |

本文示例以 **C99** 为基线（`//` 注释、`for` 循环内声明变量、`stdbool.h` 均为 C99 引入），现代编译器（GCC / Clang / MSVC）默认支持 C11 及以上，无需任何编译选项即可直接编译。这个阶段的语法是 C 语言最稳定的部分。

## 3. 语法与参数

### 3.1 C 程序结构

```c
#include <stdio.h>   // 预处理指令：引入标准输入输出库

int main(void) {     // 程序入口，int 表示返回整数状态码
    printf("Hello, C\n");  // 库函数调用
    return 0;        // 返回 0 表示成功，非零表示错误
}
```

每一个 C 程序必须有且仅有一个 `main` 函数。`#include` 是预处理指令（Preprocessor Directive），在编译前由预处理器展开。

**源文件 `.c` 与头文件 `.h`**

C 项目由两种文本文件组成：

- **源文件（Source File，`.c`）**：存放函数的**实现**（函数体）与可执行代码，是编译的基本单位，一个 `.c` 文件对应一个编译单元（Translation Unit）
- **头文件（Header File，`.h`）**：存放**声明**（函数原型、宏、类型定义、常量），供源文件通过 `#include` 引入，自身通常不包含可执行代码

上面示例里的 `#include <stdio.h>` 引入的正是标准库头文件 `stdio.h`——它声明了 `printf`、`scanf` 等函数原型。编译器看到头文件里的声明，才能检查调用格式是否正确；而函数真正的实现位于标准库中，要到**链接**阶段才会被找到：

```text
stdio.h（声明 printf/scanf）──#include──▶ 程序.c ──编译──▶ 程序.o ──链接 libc──▶ 可执行文件
```

> 本阶段只用单文件，**`.h` 与 `.c` 分离、多文件编译属于 ph02 函数与模块化阶段**，这里只需理解头文件「提供声明、被 `#include` 引入」的角色。

### 3.2 变量与基本数据类型

| 类型 | 典型大小 (64位) | 范围 | 说明 |
|------|----------------|------|------|
| `char` | 1 字节 | -128 ~ 127 | 字符/小整数 |
| `short` | 2 字节 | -32768 ~ 32767 | 短整数 |
| `int` | 4 字节 | -2.1×10⁹ ~ 2.1×10⁹ | 默认整数类型 |
| `long` | 8 字节 | -9.2×10¹⁸ ~ 9.2×10¹⁸ | 长整数 |
| `float` | 4 字节 | ~6 位精度 | 单精度浮点 |
| `double` | 8 字节 | ~15 位精度 | 双精度浮点 |

```c
int age = 25;           // 整型变量
float pi = 3.14159f;    // 浮点常量加 f
char grade = 'A';       // 字符用单引号
const int MAX = 100;    // const 限定只读
```

**关键概念**：C 是静态类型语言（Static Typing），变量类型在编译时确定且不可改变。每种类型在内存中占用固定字节数，超出范围会产生溢出。

### 3.3 运算符

| 类别 | 运算符 | 示例 |
|------|--------|------|
| 算术 | `+ - * / %` | `a + b`, `x % 2` |
| 关系 | `== != < > <= >=` | `a == b`（注意：不是 `=`） |
| 逻辑 | `&& \|\| !` | `a > 0 && b > 0` |
| 赋值 | `= += -= *= /=` | `x += 1` 等价于 `x = x + 1` |
| 自增自减 | `++ --` | `i++`（后置）, `++i`（前置） |
| 三元 | `? :` | `max = a > b ? a : b` |

### 3.4 控制流

**条件判断**：

```c
if (score >= 90) {
    printf("A\n");
} else if (score >= 60) {
    printf("Pass\n");
} else {
    printf("Fail\n");
}

// switch: 多分支选择，注意 break
switch (day) {
    case 1: printf("Mon\n"); break;
    case 2: printf("Tue\n"); break;
    default: printf("Other\n"); break;
}
```

**循环**：

```c
// for: 已知循环次数
for (int i = 0; i < 10; i++) {
    printf("%d\n", i);
}

// while: 前置条件判断
int n = 10;
while (n > 0) {
    printf("%d\n", n--);
}

// do-while: 至少执行一次
int m = 0;
do {
    printf("%d\n", m);
} while (m > 0);  // 条件为假，但循环体已执行一次
```

### 3.5 注释

```c
// 单行注释（C99 引入）
/* 多行
   注释 */
```

### 3.6 输入输出

```c
#include <stdio.h>

int main(void) {
    int age;
    printf("Enter your age: ");   // 输出到 stdout
    scanf("%d", &age);            // 从 stdin 读取，注意取地址符 &
    printf("You are %d years old.\n", age);
    return 0;
}
```

| 格式说明符 | `printf`（输出） | `scanf`（输入） |
|-----------|-----------------|-----------------|
| `%d` / `%i` | `int` | `int*` |
| `%f` | `double`（`float` 实参会自动提升为 `double`） | `float*` |
| `%lf` | 同 `%f`（`l` 被忽略） | `double*` |
| `%c` | `char`（提升为 `int` 传递） | `char*` |
| `%s` | 字符串（`char*`） | `char*` 缓冲区 |
| `%p` | 指针地址 | —（极少使用） |

**注意**：`printf` 和 `scanf` 的格式符含义并不对称——`printf` 的可变参数会发生**默认实参提升**（`float` → `double`），而 `scanf` 接收的是指针，必须和变量的真实类型严格匹配（`float` 用 `%f`、`double` 用 `%lf`），写错就是未定义行为。

**为什么 `scanf` 需要 `&` 而 `printf` 不需要？**

```c
int age;
scanf("%d", &age);    // scanf 需要修改 age 的值 → 必须知道 age 的地址
printf("%d", age);    // printf 只需要读取 age 的值 → 传值即可
```

C 函数默认**按值传递**（Pass by Value）：`printf` 拿到的是 `age` 的副本，读取即可；而 `scanf` 需要**修改**调用者的变量，只能通过传递变量地址（指针）来实现。这是 C 语言设计的基础权衡——基础阶段只需要记住"输入要加 `&`"，指针阶段会深入理解原因。

## 4. 底层原理

### 4.1 编译与链接不是一回事

```
源文件 .c  ──预处理──▶  展开后的 .i  ──编译──▶  汇编 .s  ──汇编──▶  目标文件 .o  ──链接──▶  可执行文件
```

- **预处理**（Preprocessing）：处理 `#include`、`#define`、条件编译指令
- **编译**（Compilation）：将 C 代码翻译成汇编代码
- **汇编**（Assembly）：将汇编代码翻译成机器码，生成目标文件（Object File，`.o`）
- **链接**（Linking）：将多个 `.o` 文件和库合并，解析符号引用，生成可执行文件

理解这个流程是后续处理编译错误和链接错误的基础。

### 4.2 栈上变量的生命周期

```c
void func(void) {
    int x = 42;    // x 分配在栈上
}                  // x 随函数返回自动销毁
```

函数内定义的局部变量（Local Variable）分配在**栈**（Stack）上，函数返回后内存自动回收。超出作用域（Scope）访问变量是未定义行为（Undefined Behavior）。

### 4.3 类型的物理约束

- `int` 在 32 位和 64 位系统上通常都是 4 字节，但标准只规定最小范围
- `char` 默认有无符号取决于实现
- 有符号整数溢出是未定义行为（UB）：`INT_MAX + 1` 的后果编译器和优化级别都可能改变结果
- 浮点数遵循 IEEE 754 标准，但存在精度问题

## 5. 使用场景

基础语法阶段能解决的典型问题：

| 场景 | 涉及知识点 |
|------|-----------|
| 计算器 | 变量、算术运算、输入输出 |
| 成绩等级判定 | 条件分支、范围比较 |
| 九九乘法表 | 嵌套循环、格式化输出 |
| 素数判断 | 循环、取模运算 |
| 数组统计（最值、均值） | 数组定义、循环遍历 |

**不适合**此阶段的事项：
- 任何涉及指针的场景
- 处理长度未知的字符串
- 文件读写
- 多文件项目

## 6. 代码示例

> **说明**：示例 2 起会用到自定义函数——函数将在下一阶段（ph02 函数与模块化）详解，此处模仿写法即可。

### 示例 1：命令行计算器

```c
#include <stdio.h>

int main(void) {
    double a, b;
    char op;

    printf("输入算式 (如 3 + 4): ");
    scanf("%lf %c %lf", &a, &op, &b);

    switch (op) {
        case '+': printf("%.2f\n", a + b); break;
        case '-': printf("%.2f\n", a - b); break;
        case '*': printf("%.2f\n", a * b); break;
        case '/':
            if (b != 0.0)
                printf("%.2f\n", a / b);
            else
                printf("错误: 除数为零\n");
            break;
        default: printf("不支持的操作符\n"); break;
    }
    return 0;
}
```

### 示例 2：判断素数

```c
#include <stdio.h>
#include <stdbool.h>

bool is_prime(int n) {
    if (n < 2) return false;
    for (int i = 2; i * i <= n; i++) {
        if (n % i == 0) return false;
    }
    return true;
}

int main(void) {
    for (int i = 1; i <= 100; i++) {
        if (is_prime(i)) printf("%d ", i);
    }
    printf("\n");
    return 0;
}
```

### 示例 3：数组统计

```c
#include <stdio.h>

int main(void) {
    int scores[] = {78, 92, 85, 63, 99, 71};
    int count = sizeof(scores) / sizeof(scores[0]);
    int sum = 0, max = scores[0], min = scores[0];

    for (int i = 0; i < count; i++) {
        sum += scores[i];
        if (scores[i] > max) max = scores[i];
        if (scores[i] < min) min = scores[i];
    }

    printf("人数: %d\n", count);
    printf("平均: %.2f\n", (double)sum / count);
    printf("最高: %d, 最低: %d\n", max, min);
    return 0;
}
```

### 示例 4：九九乘法表

```c
#include <stdio.h>

int main(void) {
    for (int i = 1; i <= 9; i++) {
        for (int j = 1; j <= i; j++) {
            printf("%d×%d=%-2d  ", j, i, i * j);
        }
        printf("\n");
    }
    return 0;
}
```

## 7. 总结

### 关键要点

1. **C 程序以 `main` 为入口**，返回值表示程序状态（0 = 成功）
2. **编译和链接是两步**：编译检查语法，链接解析跨文件符号
3. **静态类型**：每种变量的类型在编译时确定，不可改变
4. **栈变量生命周期由作用域控制**：离开花括号即销毁
5. **整数和浮点都有范围限制**：超出范围会导致溢出或精度丢失
6. **`=` 是赋值，`==` 是相等比较**——混淆是最常见的 bug 之一

### 跨语言对比：基础语法

| 特性 | C | C++ | Java | Python |
|------|---|-----|------|--------|
| 执行方式 | 编译为机器码 | 编译为机器码 | 字节码 + JVM | 解释执行 |
| 程序入口 | `int main(void)` | `int main()` | `public static void main(String[])` | 无需入口，逐行执行 |
| 空值 | `NULL` | `nullptr` | `null` | `None` |
| 字符串 | `char[]` / `char*` | `std::string` | `String` | `str` |
| 动态数组 | `malloc` / `free` | `std::vector` | 定长数组 + `ArrayList` | `list` |
| 布尔 | `_Bool`（C99 `stdbool.h` 提供 `bool`） | `bool` | `boolean` | `bool`（`True`/`False`） |

### 阶段验收标准

- 能独立编译并运行单文件 C 程序（`gcc main.c -o app && ./app`）
- 能解释 `main` 返回值的含义
- 能用循环和条件分支解决基础算法题
- 能调试基础编译错误（漏分号、未声明变量等）

### 进入下一阶段前

确保能完成以下练习：
- 计算器（支持 `+ - * /`）
- 九九乘法表
- 判断素数
- 数组最大值、最小值、平均值

### 推荐项目

- **命令行计算器**：处理基本四则运算和除零错误
- **成绩等级判断工具**：输入分数输出 A/B/C/D/F

### 下一阶段

[函数与模块化阶段](../ph02-func-module/02-func-module.md) — 把代码拆成函数和模块，避免所有逻辑堆在 `main` 中。
