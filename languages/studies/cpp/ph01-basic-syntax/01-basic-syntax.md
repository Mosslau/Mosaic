# C++ 基础语法阶段

> 面向现代 C++、高性能系统、数据库内核方向，从 C++ 类型系统、引用和标准库起步。

## 1. 概述

C++ 基础语法阶段的定位是：**能写简单 C++ 程序，理解 C++ 相比 C 在类型、库和抽象上的变化**。如果你有 C 基础，这个阶段的关键是接受 C++ 自己的做事方式——`std::string` 而不是 `char*`，`std::vector` 而不是裸数组。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 程序结构 | `iostream`、`namespace`、`main` |
| 类型 | `bool`、`const`、`auto`、引用（Reference） |
| 函数 | 重载（Overload）、默认参数、`inline` |
| 控制流 | 运算符、`if`/`switch`、`for`/`while`（与 C 相同）、range-for |
| 内存 | `new`/`delete`、`nullptr` |
| 标准库 | `std::string`、`std::vector` |

这个阶段的目标不是学完 C with Classes，而是建立**现代 C++ 的初始心智模型**。

这个阶段只涉及单文件、过程式写法加少量标准库类型，**不涉及类与对象、继承多态、模板和智能指针** — 那些是 ph02 面向对象、ph05 模板与泛型、ph06 现代 C++ 阶段的内容。

## 2. 来源与演变

C++ 由 Bjarne Stroustrup 于 1979 年在贝尔实验室开始设计，最初名为"C with Classes"，1983 年更名为 C++。其设计哲学是**零成本抽象（Zero-cost Abstraction）**——你不用的特性不应该为它付出代价。

| 标准 | 年份 | 标志性变化 |
|------|------|-----------|
| C++98 | 1998 | 首个标准：STL、模板、异常 |
| C++11 | 2011 | 革命性更新：`auto`、lambda、移动语义、智能指针 |
| C++14 | 2014 | 泛型 lambda、`decltype(auto)`、`make_unique` |
| C++17 | 2017 | `optional`/`variant`、结构化绑定、`if constexpr`、`string_view` |
| C++20 | 2020 | Concepts、Ranges、协程、Modules |
| C++23 | 2023 | `std::expected`、`std::flat_map`、deducing this |

基础语法阶段同时涉及 C++98 的根基和 C++11/17 的现代写法——后者是你应该优先使用的。

本文示例以 **C++17** 为基线（`auto`、range-for、结构化绑定、`string_view` 均可用），现代编译器（GCC 7+ / Clang 5+ / MSVC 2017+）默认或加 `-std=c++17` 即可编译，无需额外选项。这个阶段的语法是现代 C++ 最稳定的部分。

## 3. 语法与参数

### 3.1 程序结构与 I/O

```cpp
#include <iostream>   // C++ 标准输入输出头文件
#include <string>     // std::string 头文件

int main() {
    std::string name = "C++";
    std::cout << "Hello, " << name << std::endl;  // << 流输出运算符
    return 0;
}
```

| 头文件 | 用途 |
|--------|------|
| `<iostream>` | `std::cin`、`std::cout`、`std::cerr` |
| `<string>` | `std::string` |
| `<vector>` | `std::vector` |
| `<array>` | `std::array` |

`std::` 是标准库命名空间（Namespace），用于避免名称冲突。可以用 `using namespace std;` 省略，但**不推荐在头文件和大型项目中使用**。

**输入用 `std::cin` 和 `>>` 运算符**（方向与输出相反）：

```cpp
std::string name;
int age;
std::cout << "请输入姓名和年龄: ";
std::cin >> name >> age;    // >> 按空白分隔，依次读入 name 和 age
std::cout << name << " 今年 " << age << " 岁\n";
```

`std::cin >>` 遇到空白（空格、换行）即停止；要读取整行文本用 `std::getline(std::cin, line)`。

### 3.2 变量、类型与 const

```cpp
int age = 25;              // 整型
double pi = 3.14159;       // 浮点
bool ready = true;         // 布尔类型（C++ 原生支持 true/false）
char grade = 'A';          // 字符

auto score = 95;           // auto 自动推导类型（C++11），score 是 int
auto name = std::string{"Alice"}; // auto 推导为 std::string

const int MAX = 100;       // const 常量：编译期不可修改
constexpr int SIZE = 256;  // constexpr 保证编译期求值（C++11）
```

`auto` 几乎总是对的，但要注意它**不会推导引用和 const 限定符**——`auto s = "hi"` 推导为 `const char*`，不是 `std::string`。

**const 是接口设计的一部分**（本阶段只需建立直觉，完整规则见 ph14 const 正确性与接口设计阶段）：

```cpp
// 1. const 引用参数：承诺"只读不修改"，避免大对象拷贝
void print(const std::string& s);   // 传引用零拷贝，const 保证不改

// 2. const 成员函数：承诺"不修改对象状态"，const 对象只能调 const 成员函数
class Counter {
    int count_ = 0;
public:
    int  value() const { return count_; }  // 只读：尾部 const
    void increment()   { ++count_; }       // 可改：无 const
};

const Counter c;
// c.increment();   // 编译错误：const 对象不能调非 const 成员函数
int v = c.value();  // 合法
```

看到函数签名里的 `const`，先读成"承诺"——`const std::string&` 承诺不修改参数，成员函数尾部的 `const` 承诺不修改对象。这套约定让调用方不看实现就知道函数的副作用边界。

### 3.3 引用（Reference）— 不是指针语法糖

```cpp
int x = 10;
int& ref = x;     // ref 是 x 的别名，不是指针
ref = 20;         // 修改 ref 就是修改 x

// 对比指针
int* ptr = &x;    // ptr 保存 x 的地址
*ptr = 30;        // 通过解引用修改 x
```

| 特性 | 引用 | 指针 |
|------|------|------|
| 是否可为空 | 不允许（没有空引用） | 可为 `nullptr` |
| 是否可重新绑定 | 否（绑定后永久指向同一对象） | 是 |
| 语法 | 直接使用，无需解引用 | 需要 `*` 解引用 |
| 用法 | 函数参数、返回值 | 动态内存、数据结构 |

**关键概念**：引用是别名（Alias），不是"自动解引用的指针"。引用一旦绑定就不可更改目标。

### 3.4 函数：重载、默认参数

```cpp
// 函数重载：同名函数，参数列表不同
int add(int a, int b) { return a + b; }
double add(double a, double b) { return a + b; }

// 默认参数：从右向左定义
void log(const std::string& msg, int level = 0) {
    std::cout << "[" << level << "] " << msg << std::endl;
}

log("error", 2);   // [2] error
log("info");       // [0] info  — 使用默认值
```

- **重载决策**（Overload Resolution）：编译器根据参数类型和数量选择最佳匹配
- **默认参数**必须从最右侧开始，不允许 `void f(int a = 1, int b)` 这样的声明

### 3.5 运算符（与 C 相同）

| 类别 | 运算符 | 示例 |
|------|--------|------|
| 算术 | `+ - * / %` | `a + b`, `x % 2` |
| 关系 | `== != < > <= >=` | `a == b`（注意：不是 `=`） |
| 逻辑 | `&& \|\| !` | `a > 0 && b > 0`（短路求值） |
| 位运算 | `& \| ^ ~ << >>` | `n & 1`（判断奇偶） |
| 赋值 | `= += -= *= /=` | `x += 1` |
| 自增自减 | `++ --` | `i++`（后置）, `++i`（前置） |
| 三元 | `? :` | `max = a > b ? a : b` |

C++ 没有新增基础运算符；`<<` / `>>` 在 `<iostream>` 中被重载为流输入输出运算符——这就是 `std::cout << x` 的原理。

### 3.6 控制流（与 C 相同）

```cpp
// if/else、switch、for、while、do-while 语法与 C 一致
// C++11 增加 range-based for：
std::vector<int> nums = {1, 2, 3, 4};
for (int n : nums) {           // 只读遍历
    std::cout << n << " ";
}
for (int& n : nums) {          // 可修改遍历
    n *= 2;
}
```

### 3.7 new/delete 与 nullptr

```cpp
int* p = new int(42);    // 在堆上分配单个 int，初始化为 42
delete p;                // 释放

int* arr = new int[10];  // 分配数组
delete[] arr;            // 数组释放必须用 delete[]

// nullptr（C++11）替代 NULL 和 0
int* q = nullptr;        // 类型安全的空指针
```

> **注意**：在基础语法阶段了解 `new`/`delete` 即可，实际工程中优先使用智能指针（`std::unique_ptr`/`std::shared_ptr`）和容器。

### 3.8 std::string 与 std::vector

```cpp
#include <string>
#include <vector>

// string：安全字符串，不再需要管理 char 数组和 \0
std::string s = "hello";
s += " world";             // 拼接
size_t len = s.length();   // 长度
std::string sub = s.substr(0, 5);  // 子串

// vector：动态数组，自动管理内存
std::vector<int> v = {1, 2, 3};
v.push_back(4);            // 尾部添加
v.pop_back();              // 尾部删除
for (int x : v) { ... }   // range-for 遍历
```

`std::string` 和 `std::vector` 是 C++ 基础阶段最重要的两个标准库类型——它们替代了 C 中的 `char[]` 和手动 `malloc`/`free`。

### 3.9 三种参数形态：按值、引用、const 引用

有了引用与 `std::string`/`std::vector`，函数参数就有三种写法，各有各的用途：

```cpp
void f1(std::string s);              // 按值：拷贝一份，函数内随便改，不影响调用者
void f2(std::string& s);             // 引用：不拷贝，函数内可修改调用者的对象
void f3(const std::string& s);       // const 引用：不拷贝、承诺不改（只读）
```

| 形态 | 是否拷贝 | 能否修改原对象 | 适合场景 |
|------|---------|--------------|---------|
| 按值 `T` | 是（拷贝/移动） | 否 | 小对象（`int`、`char`、枚举）；函数本来就要一份副本 |
| 引用 `T&` | 否 | **能** | 需要"改回去"——如 `swap`、累加器 |
| const 引用 `const T&` | 否 | 否（承诺） | **默认首选**：读大对象（`string`/`vector`）时避免拷贝 |

为什么"读参数"默认用 `const T&` 而不是按值？因为拷贝 `std::vector<int>` 会把整个动态数组复制一遍——`printNames(names)` 这种只读函数按值传就是白拷贝。看一个需要"改回去"的经典例子：

```cpp
// swap 必须用引用：不拷贝、且要修改调用者的 a 和 b
void swap(int& a, int& b) {
    int tmp = a;
    a = b;
    b = tmp;
}

int x = 1, y = 2;
swap(x, y);    // 现在 x == 2, y == 1
```

> 选型口诀：**读用 `const T&`，改要用 `T&`，小对象或要副本才按值**。移动语义（按值+移动的现代写法）会让这个决策更精细，那是 ph06 现代 C++ 阶段的内容，这里先建立"避免不必要拷贝"的直觉。

### 3.10 类型转换：隐式转换与 static_cast

C++ 继承 C 的类型规则，整数除法截断、混合运算提升这些行为一致（见 C 路线 ph01 的 3.7）；不同之处是 C++ 推荐**用 `static_cast` 代替 C 风格 `(类型)`**：

```cpp
double d = 3.9;
int n1 = d;                     // 隐式转换：截断为 3（编译器通常给警告）
int n2 = static_cast<int>(d);   // 显式转换：同样得 3，但意图一目了然

int a = 7, b = 2;
double r = static_cast<double>(a) / b;   // 3.5：转浮点再除
```

| 写法 | 例子 | 评价 |
|------|------|------|
| 隐式转换 | `int n = d;` | 简洁但容易藏 bug，编译器告警要当真 |
| C 风格 `(类型)` | `(int)d` | C++ 里**不推荐**——它在类型系统里"横冲直撞"，无法表达转换意图 |
| `static_cast<类型>` | `static_cast<int>(d)` | C++ 首选：只做"合理"的转换（数值截断、`double`↔`int`、派生类↔基类指针等），编译期检查 |

为什么要较真？`static_cast` 是"受检的"——它能做的转换类型有限，写错（如把整数转成不相关类型指针）会在编译期报错，而 C 风格转换会安静地做任何事。**基础阶段先养成"数值转换用 `static_cast`"的习惯**，它和 `auto` 一样是现代 C++ 的"签名动作"。

### 3.11 新手高频编译错误排查

C++ 编译错误比 C 啰嗦，但前几条高频错误有固定模式：

| 错误信息（节选） | 含义 | 修法 |
|-----------------|------|------|
| `'cout' was not declared` | 头文件没包含或漏了 `std::` | 检查 `#include <iostream>` 与 `std::` 前缀 |
| `no matching function for call to 'add'` | 函数重载匹配不上 | 参数个数或类型对不上声明；查类型是否隐式可转换 |
| `cannot convert 'std::string' to 'int'` | 类型不匹配 | 检查变量声明与赋值两侧类型（结合 3.10） |
| `expected ';' before ...` | 上一行漏分号 | 报错位置通常指向真正出问题的**上一行** |
| `use of undeclared identifier 'x'` | 变量没声明 / 超出作用域 | 变量用在了声明之前或花括号之外 |

**读错误信息从第一行开始**：编译器先报真正的问题，后面的常常是"连锁反应"。改一个错、重新编译、再看下一个——一次修一个，别一次改十处。

### 3.12 遍历的三种形态与"改容器"禁忌

range-for 遍历 `vector` 时有三种写法，对应三种意图（承接 3.9 的参数决策）：

```cpp
std::vector<std::string> names = {"Alice", "Bob", "Carol"};

for (std::string n : names)          // ① 按值：每轮拷贝一个字符串——只读小对象可用，大对象浪费
for (const auto& n : names)          // ② const 引用：只读不拷贝——**遍历大对象默认选这个**
for (auto& n : names)                // ③ 可变引用：要修改元素本身（如加后缀）
{
    n += "!";
}
```

```cpp
// ③ 的完整例子：给每个名字加后缀
for (auto& n : names) {
    n += "!";
}
// 现在 names == {"Alice!", "Bob!", "Carol!"}
```

**禁忌**：range-for 遍历的是"容器当前的元素范围"，**在遍历中增删元素会让迭代器失效（Iterator Invalidation）**——`push_back` 可能触发扩容搬移，正在遍历的位置就悬空了，行为未定义。`for (auto& n : v) { v.push_back(...); }` 这类代码几乎必然出错。遍历时收集要删的元素、遍历完再删，是常见的安全模式（容器与迭代器的完整规则是 [ph04 STL 阶段](../ph04-stl/04-stl.md) 的内容）。

## 4. 底层原理

### 4.1 引用在底层是如何实现的

```cpp
void increment(int& n) { n++; }

// 编译器通常将其等价转换为（概念上）：
// void increment(int* n) { (*n)++; }
```

引用在底层通常实现为指针，但编译器保证引用一定绑定到有效对象、不可重新绑定，因此可以安全地当作别名使用。

### 4.2 C++ 的"零成本抽象"

```cpp
std::vector<int> v = {1, 2, 3};
int sum = 0;
for (int x : v) sum += x;
```

编译后的机器码与手写 C 循环**几乎一致**。C++ 的设计目标就是：高级抽象不应引入运行时开销。

### 4.3 编译模型

C++ 的编译模型与 C 相同：源文件 → 目标文件 → 链接。但 C++ 引入了一些额外复杂性：

- **模板**：在实例化时才生成代码，因此模板实现通常放在头文件中
- **name mangling**：C++ 函数重载导致符号名编码，链接时需要匹配
- **ODR（One Definition Rule）**：同一个实体在程序中只能有一处定义

### 4.4 auto 的推导规则

```cpp
auto x = 42;         // int
auto& y = x;         // int& — 显式写 & 保留引用
const auto& z = x;   // const int&
auto s = "hello";    // const char*（不是 std::string）
```

`auto` 会剥离引用和顶层 const，如果需要保留，必须显式写出。

## 5. 使用场景

基础语法阶段适合解决的问题：

| 场景 | 涉及知识点 |
|------|-----------|
| 字符串处理 | `std::string`、拼接、查找 |
| 动态数据收集 | `std::vector`、`push_back` |
| 小型工具 | 变量、控制流、函数、I/O |
| 改写 C 程序 | 用 `string`/`vector` 替代 `char*`/数组 |

**本阶段建立的三个直觉，是后续每一阶段的伏笔**：

| 后续阶段 | 用到的本阶段基础 |
|---------|----------------|
| ph02 面向对象 | `struct`/`class` 是 `struct Contact` 的自然延伸；const 成员函数先例（3.2） |
| ph04 STL | `std::vector` 是全部容器的起点——迭代器、算法都围着它转（3.8 / 3.12） |
| ph05 模板与泛型 | `auto` 的类型推导直觉 + 函数重载（3.4）是模板的基础 |
| ph06 现代 C++ | 移动语义补全 3.9 的按值决策；智能指针替代 3.7 的 `new`/`delete` |
| ph14 const 正确性 | 3.2 / 3.9 的 `const` 承诺体系在这里变成完整规则 |

这些阶段在 roadmap 里的编号与主题以 [`cpp.md`](../cpp.md) 为准，本表只标记"谁站在谁的肩上"——C++ 的学习曲线陡，正是因为每一层都叠在上一层上。

## 6. 代码示例

> 完整可运行文件见 [`examples/`](./examples/)，每个示例对应一个 `ex0*-*.cpp`，已在本环境用 `g++ -Wall -Wextra -std=c++17` 验证（零警告）。

### 示例 1：通讯录（string + vector）

完整文件：`examples/ex01-contacts.cpp`

```cpp
// examples/ex01-contacts.cpp —— 通讯录：用 struct + vector 组织数据，按名字查找
#include <iostream>
#include <string>
#include <vector>
#include <algorithm>

struct Contact {
    std::string name;
    std::string phone;
};

int main() {
    std::vector<Contact> contacts;

    // 添加联系人
    contacts.push_back({"Alice", "138-0001"});
    contacts.push_back({"Bob",   "138-0002"});
    contacts.push_back({"Carol", "138-0003"});

    // 按名字查找
    std::string query = "Bob";
    for (const auto& c : contacts) {
        if (c.name == query) {
            std::cout << c.name << ": " << c.phone << '\n';
        }
    }
    return 0;
}
```

### 示例 2：词频统计

完整文件：`examples/ex02-word-frequency.cpp`

```cpp
// examples/ex02-word-frequency.cpp —— 词频统计：排序后按相邻相同词计数
#include <iostream>
#include <string>
#include <vector>
#include <algorithm>

int main() {
    std::vector<std::string> words = {
        "apple", "banana", "apple", "orange", "banana", "apple"
    };

    std::sort(words.begin(), words.end());

    std::string current = words[0];
    int count = 1;
    for (size_t i = 1; i < words.size(); ++i) {
        if (words[i] == current) {
            count++;
        } else {
            std::cout << current << ": " << count << '\n';
            current = words[i];
            count = 1;
        }
    }
    std::cout << current << ": " << count << '\n';
    return 0;
}
```

### 示例 3：用 auto 和 range-for 简化

完整文件：`examples/ex03-auto-range-for.cpp`

```cpp
// examples/ex03-auto-range-for.cpp —— CTAD、range-for 与迭代器遍历对比
#include <iostream>
#include <vector>

int main() {
    auto nums = std::vector{1, 2, 3, 4, 5};  // C++17 CTAD

    // range-for 遍历
    for (const auto& n : nums) {
        std::cout << n << " ";
    }
    std::cout << '\n';

    // auto 避免重复写类型名
    auto it = nums.begin();
    auto end = nums.end();
    while (it != end) {
        std::cout << *it++ << " ";
    }
    std::cout << '\n';
    return 0;
}
```

## 7. 总结

### 关键要点

1. **引用是别名，不是指针语法糖**：绑定后不可改变，无空引用概念
2. **const 是接口设计的第一公民**：表达"不可修改"的承诺
3. **优先使用 std::string 和 std::vector**：替代 C 风格字符串和裸数组
4. **auto 减少类型噪声**：但不要滥用——类型名本身就是文档
5. **C++ 多范式**：过程式、面向对象、泛型、函数式——基础阶段以前两种为主
6. **new/delete 在基础阶段学习即可**：后续阶段用智能指针替代

### 跨语言对比：C/C++ 基础语法

| 方向 | C | C++ |
|------|---|-----|
| 字符串 | `char[]` / `char*` | `std::string` |
| 动态数组 | `malloc` / `free` | `std::vector` |
| 空指针 | `NULL` | `nullptr` |
| 类型推导 | 无 | `auto` |
| 函数重载 | 不支持 | 支持 |
| 默认参数 | 不支持 | 支持 |
| 引用 | 无 | `T&` / `const T&` |

### 阶段验收清单

- [ ] 能写出基础 C++ 程序，正确使用 `std::cout`/`std::cin`
- [ ] 能说明引用、指针和值传递的区别及选择依据
- [ ] 能使用 `std::string` 和 `std::vector` 解决数据处理问题
- [ ] 能阅读和理解简单的 C++ 编译错误

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：简单通讯录——命令行交互式增删查改联系人，数据用 `std::vector<Contact>` 存储。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[面向对象 OOP 阶段](../ph02-oop/02-oop.md) — 理解类、对象、封装、继承和多态。
