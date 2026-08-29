# C++ 模板与泛型编程、元编程阶段

> 揭开 ph04 STL 的幕布——从函数模板到 concepts，掌握编译期代码生成、类型推导与 C++20 约束编程。

## 1. 概述

模板与泛型编程阶段的定位是：**从"会用 STL 容器"推进到"理解 STL 背后的泛型机制"——掌握函数模板、类模板、特化/偏特化、非类型模板参数、concept 约束以及编译期计算**。核心思想是"编译期代码生成（单态化）"：编译器为每种使用的类型组合生成一份独立机器码，不依赖运行时类型信息。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 函数模板 | 类型推导、auto 返回类型、重载决议 |
| 类模板 | 成员函数定义、CTAD（C++17 类模板参数推导） |
| 模板实参 | 类型参数、非类型参数（`template<size_t N>`）、模板模板参数 |
| 特化 | 全特化（`template<>`）、偏特化（部分参数匹配） |
| 编译期计算 | constexpr 函数、if constexpr（C++17 编译期分支） |
| 约束 | concept、requires 子句（C++20），替代 SFINAE + enable_if |
| 消歧义 | 依赖名称的 `typename`、`template` 关键字 |

ph04 中大量使用的 `vector<T>`、`sort(begin,end)` 都是模板——本章揭开幕布，讲清这些 API 背后的泛型机制。本章不涉及变参模板深入与 SFINAE 技巧。

## 2. 来源与演变

| 标准 | 关键能力 | 痛点 |
|------|---------|------|
| C++98 | 函数/类模板、全特化/偏特化、非类型参数 | 错误信息灾难级（数百行模板回溯） |
| C++11 | 变参模板、`decltype` 返回类型、别名模板 | SFINAE + enable_if 成为约束主流（语法丑陋） |
| C++14 | 变量模板、`auto` 返回类型自动推导 | — |
| C++17 | `if constexpr` 编译期分支、CTAD、折叠表达式 | 模板可读性大幅提升 |
| C++20 | concept + requires 约束编程、`auto` 非类型参数 | **彻底替代 SFINAE**，错误信息一行说清 |

模板核心设计选择是**单态化（monomorphization）**：编译器为 `<int>`、`<double>` 各生成一份独立机器码。这是与 Java 泛型（类型擦除）的根本分歧——C++ 多占编译时间和二进制体积，换零运行时开销；Java 省体积，但付出装箱/拆箱和运行时类型检查的代价。

## 3. 语法与参数

### 3.1 函数模板：自动类型推导

编译器从调用实参推导 `T`，推导失败则从重载候选集移除（SFINAE 原则，C++20 后由 concept 提供更清晰替代）。

```cpp
#include <iostream>
#include <string>

template<typename T>
T my_max(T a, T b) { return a > b ? a : b; }

int main() {
    std::cout << "max(3, 7) = " << my_max(3, 7) << "\n";             // T=int
    std::cout << "max(3.14, 2.71) = " << my_max(3.14, 2.71) << "\n"; // T=double
    std::cout << "max(abc,xyz) = "
              << my_max(std::string("abc"), std::string("xyz")) << "\n";
    return 0;
}
```

### 3.2 类模板：显式指定或 CTAD

类模板成员函数**独立按需实例化**：不用的成员不生成代码。C++17 CTAD 允许从构造函数实参推导模板参数。

```cpp
#include <iostream>
#include <vector>
#include <utility>

template<typename T>
class Stack {
public:
    void push(const T& val) { data_.push_back(val); }
    T pop() { T v = std::move(data_.back()); data_.pop_back(); return v; }
    const T& top() const { return data_.back(); }
    bool empty() const    { return data_.empty(); }
private:
    std::vector<T> data_;
};

int main() {
    Stack<int> si;          // C++17 前：必须显式指定 <int>
    si.push(10); si.push(20);
    std::cout << "top=" << si.top() << " pop=" << si.pop() << "\n";
    return 0;
}
```

### 3.3 模板特化：全特化 vs 偏特化

全特化固定所有参数为特定类型做定制优化；偏特化只固定部分参数或改变参数模式（如 `T` → `T*`）。编译器选**最特化**版本：全特化 > 偏特化 > 主模板。

```cpp
#include <iostream>
#include <vector>
#include <deque>

// 主模板
template<typename T>
class Stack {
    std::vector<T> data_;
public:
    void push(const T& v) { data_.push_back(v); }
    T pop() { T v = std::move(data_.back()); data_.pop_back(); return v; }
    size_t size() const { return data_.size(); }
};

// 全特化：bool → deque<bool> 位压缩
template<>
class Stack<bool> {
    std::deque<bool> data_;
public:
    void push(bool v) { data_.push_back(v); }
    bool pop() { bool v = data_.back(); data_.pop_back(); return v; }
    size_t size() const { return data_.size(); }
};

// 偏特化：指针版本 → 存储裸指针，对外自动解引用
template<typename T>
class Stack<T*> {
    std::vector<T*> data_;
public:
    void push(T* p) { data_.push_back(p); }
    T* pop() { T* v = data_.back(); data_.pop_back(); return v; }
    T& top() { return *data_.back(); }
    size_t size() const { return data_.size(); }
};

int main() {
    Stack<int>  si; si.push(42);
    Stack<bool> sb; sb.push(true); sb.push(false);
    int a = 10, b = 20;
    Stack<int*> sp; sp.push(&a); sp.push(&b);

    std::cout << "Stack<int>  size=" << si.size() << "\n";
    std::cout << "Stack<bool> size=" << sb.size() << " (full spec)\n";
    std::cout << "Stack<int*> top=" << sp.top()   << " (partial spec)\n";
    return 0;
}
```

### 3.4 非类型模板参数

编译期常量作为模板参数——`Buffer<int,1024>` 和 `Buffer<int,4096>` 是不同类型，容量差异在编译期而非运行期。`std::array<T,N>` 原理与此相同。

```cpp
#include <array>
#include <iostream>

template<typename T, size_t N>
class Buffer {
    std::array<T, N> data_{};
public:
    constexpr size_t size() const { return N; }
    T& operator[](size_t i) { return data_[i]; }
};

int main() {
    Buffer<int, 5> buf;
    for (size_t i = 0; i < buf.size(); ++i) buf[i] = static_cast<int>(i * i);
    std::cout << "buf[3]=" << buf[3] << " sizeof=" << sizeof(buf) << " bytes\n";
    return 0;
}
```

### 3.5 if constexpr：编译期分支（C++17）

`if constexpr` 替代 SFINAE 和 tag dispatch：被丢弃的分支**完全不实例化**，该分支内的语法错误不会导致编译失败。

```cpp
#include <iostream>
#include <type_traits>

template<typename T>
constexpr auto describe(T) {
    if constexpr (std::is_integral_v<T>)
        return "integer";
    else if constexpr (std::is_floating_point_v<T>)
        return "floating-point";
    else
        return "other type";
}

int main() {
    std::cout << "42: "   << describe(42)   << "\n";
    std::cout << "3.14: " << describe(3.14) << "\n";
    return 0;
}
```

#### 3.5.1 编译期递归与 typelist（类型列表）

模板元编程没有循环——**编译期"迭代"靠递归实例化**：

```cpp
// 编译期阶乘：经典递归实例化
template<int N> struct Factorial { static constexpr int value = N * Factorial<N-1>::value; };
template<>      struct Factorial<0> { static constexpr int value = 1; };

static_assert(Factorial<5>::value == 120);   // 编译期计算，零运行时代码
```

**typelist** 把一组类型打包为一个类型，是元编程的"容器"：

```cpp
#include <type_traits>

// 类型列表：空模板结构体做标签
template<typename... Ts> struct TypeList {};

// 基本变换 1：count —— 列表长度（变参包展开）
template<typename List> struct Length;
template<typename... Ts>
struct Length<TypeList<Ts...>> { static constexpr size_t value = sizeof...(Ts); };

// 基本变换 2：contains —— 类型是否在列表中（C++17 折叠表达式）
template<typename T, typename List> struct Contains;
template<typename T, typename... Ts>
struct Contains<T, TypeList<Ts...>>
    : std::bool_constant<(std::is_same_v<T, Ts> || ...)> {};

using MyTypes = TypeList<int, double, char>;

static_assert(Length<MyTypes>::value == 3);
static_assert(Contains<double, MyTypes>::value);
static_assert(!Contains<float, MyTypes>::value);
```

| 变换 | 手段 | 说明 |
|------|------|------|
| `Length` | 偏特化 + `sizeof...` | 数变参包长度 |
| `Contains` | 折叠表达式 `|| ...` | C++17 前要写递归偏特化 |
| push/pop/concat | 偏特化重组变参包 | 类型层面的"容器操作" |

typelist 的用途：**编译期类型分发**（序列化框架按类型列表注册处理器）、**变体类型的受支持类型清单**（`std::variant` 底层思想）、SFINAE 时代的"类型集合运算"。现代 C++ 里很多场景被 concept + 变参模板取代，但理解 typelist 是读懂 STL 与老牌元编程库（Boost.MPL）的前提。

### 3.6 concept + requires：C++20 约束编程

上一代用 SFINAE + `enable_if` 做泛型约束，错误信息灾难级（数百行回溯）。concept 让约束声明式、错误可读。

```cpp
#include <concepts>
#include <iostream>
#include <vector>

// 标准库 concept：约束 T 必须是整数
template<std::integral T>
T gcd(T a, T b) {
    while (b != 0) { T t = b; b = a % b; a = t; }
    return a;
}

// requires 子句等价写法
template<typename T>
  requires std::integral<T> || std::floating_point<T>
T square(T x) { return x * x; }

// 自定义 concept 组合
template<typename T>
concept Printable = requires(T v) { std::cout << v; };

template<typename T>
  requires std::ranges::range<T> && Printable<std::ranges::range_value_t<T>>
void print_all(const T& c) {
    for (const auto& v : c) std::cout << v << " ";
    std::cout << "\n";
}

int main() {
    std::cout << "gcd(48,18)=" << gcd(48, 18) << "\n";
    std::vector v = {1, 2, 3};
    print_all(v);
    // gcd(3.14, 2.7);  // 一行错误：double 不满足 std::integral
    return 0;
}
```

| 特性 | C++17 enable_if | C++20 concept |
|------|----------------|---------------|
| 语法 | `std::enable_if_t<cond, int> = 0` | `template<std::integral T>` |
| 错误信息 | 数十行模板实例化回溯 | 一行："constraint not satisfied" |
| 重载 | 复杂的 enable_if 互斥分支 | 按约束更严格者优先 |

### 3.7 typename 与 template 消歧义

两阶段名称查找：第一阶段（模板定义时）查非依赖名称；第二阶段（实例化时）查依赖名称。`typename` 和 `template` 是第二阶段的路标。

```cpp
#include <iostream>
#include <vector>

// typename：告知编译器 C::value_type 是一个类型名
template<typename C>
void show_first(const C& c) {
    if (c.empty()) return;
    typename C::value_type v = c.front();
    std::cout << "first: " << v << "\n";
}

// template：告知编译器 to 是一个成员模板
template<typename T>
struct Wrap {
    template<typename U>
    U to(const T& val) const { return static_cast<U>(val); }
};

template<typename W>
void demo(const W& w, int x) {
    auto d = w.template to<double>(x);
    std::cout << "to<double>: " << d << "\n";
}

int main() {
    std::vector<int> v = {10, 20, 30};
    show_first(v);
    Wrap<int> w;
    demo(w, 42);
    return 0;
}
```

## 4. 底层原理

### 4.1 单态化：编译期代码生成

编译器为每种模板实参组合生成一份独立机器码。`my_max(3,7)` 和 `my_max(3.14,2.71)` 分别生成 `my_max<int>` 和 `my_max<double>`——完全独立的函数体，各自享受独立的 inline 展开和向量化优化。

优势：零运行时开销（无虚表、无装箱、无类型检查）。代价：**代码膨胀**——每种 `<T>` 组合产出一份机器码；模板定义必须头文件可见；增量编译慢。现代编译器会合并相同机器码的实例化（如所有指针类型 `int*`/`double*` 共享一份），但 `int` 与 `double` 无法合并。

### 4.2 两阶段名称查找

```cpp
template<typename T>
void foo(T x) {
    bar(x);     // 第一阶段：查非依赖 bar() — 必须在定义点可见
    x.baz();    // 第二阶段：依赖名称 baz — 实例化时查找 T::baz()
}
```

非依赖名称在定义点查找（所以模板通常放头文件），依赖名称在实例化点查找。`typename` / `template` 关键字告知编译器："这个依赖名称是类型/模板，在第二阶段解析"。

### 4.3 模板特化的参数匹配

```
template<typename T> class Stack        // (1) 主模板
template<typename T> class Stack<T*>    // (2) 偏特化：T* 比 T 更特化
template<>           class Stack<bool>  // (3) 全特化：直接命中

调用 Stack<int*> → (2) 胜出；调用 Stack<bool> → (3) 胜出；调用 Stack<float> → (1)
```

编译器按三步选择：匹配主模板参数 → 偏特化间做偏序比较（"更特化"那个胜出）→ 全特化直接命中。

### 4.4 concept 的编译模型

concept 在编译期执行**谓词检查**——编译器将 concept 展开为一组编译期布尔表达式（`requires` 子句要求的有效表达式），在模板实例化**之前**对实参执行"类型级单元测试"。检查失败即短路，不进入模板体，因此错误信息短而精确。

### 4.5 跨语言泛型对比

| 维度 | C++ 模板 | Java 泛型 | Rust 泛型 | Go 泛型（1.18+） |
|------|---------|----------|----------|----------------|
| 实现方式 | 单态化（编译期） | 类型擦除（运行期） | 单态化（编译期） | 单态化（编译期 + 字典） |
| 运行时开销 | 零 | 装箱/拆箱 + checkcast | 零 | 接近零 |
| 约束方式 | concept（C++20） | `<T extends Foo>` | trait bound | interface 约束 |
| 编译体积 | 每种 T 一份代码 | 一份字节码 | 每种 T 一份代码 | GCShape 共享 + 字典 |
| 基本类型 | `vector<int>` 直接用 | `ArrayList<Integer>` 需装箱 | `Vec<i32>` 直接用 | `[]int` 切片原生支持 |
| 特化支持 | 全特化 + 偏特化 | 无 | 无（用 trait 实现） | 无 |

## 5. 使用场景

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 算法独立于类型 | 函数模板 | 编译器自动推导，零开销 |
| 类型安全容器 | 类模板 `Stack<T>` | 一个实现服务所有类型 |
| 特定类型优化 | 全特化 `template<>` | bool 位压缩、特定类型定制 |
| 指针/智能指针不同行为 | 偏特化 `Stack<T*>` | 存储不变，行为针对指针调整 |
| 容量编译期确定 | 非类型参数 `template<size_t N>` | 栈分配替代堆分配 |
| 编译期常量计算 | constexpr + if constexpr | 阶乘、类型分发、编译期配置 |
| 泛型 API 约束 | concept + requires | 声明式约束，错误一行说清 |
| 依赖名称消歧义 | typename / template 关键字 | 标记依赖名称的类型/模板身份 |

## 6. 代码示例

### 示例 1：函数模板 max/min + concept 约束

```cpp
#include <iostream>
#include <concepts>
#include <string>

template<typename T>
T my_max(T a, T b) { return a > b ? a : b; }

template<std::integral T>
T my_min(T a, T b) { return a < b ? a : b; }

int main() {
    std::cout << "max(3, 7) = " << my_max(3, 7) << "\n";
    std::cout << "max(abc, xyz) = "
              << my_max(std::string("abc"), std::string("xyz")) << "\n";
    std::cout << "min(3, 7) = " << my_min(3, 7) << "\n";
    // my_min(3.14, 2.71); // 编译错误：double 不满足 std::integral
    return 0;
}
```

### 示例 2：类模板 Stack<T> + 全特化/偏特化

```cpp
#include <iostream>
#include <vector>
#include <deque>

template<typename T>
class Stack {
public:
    void push(const T& v) { data_.push_back(v); }
    T pop() { T v = std::move(data_.back()); data_.pop_back(); return v; }
    bool empty() const { return data_.empty(); }
    size_t size() const { return data_.size(); }
private:
    std::vector<T> data_;
};

// 全特化：bool → deque<bool> 位压缩
template<>
class Stack<bool> {
public:
    void push(bool v) { data_.push_back(v); }
    bool pop() { bool v = data_.back(); data_.pop_back(); return v; }
    bool empty() const { return data_.empty(); }
    size_t size() const { return data_.size(); }
private:
    std::deque<bool> data_;
};

// 偏特化：指针版本 → 自动解引用
template<typename T>
class Stack<T*> {
public:
    void push(T* p) { data_.push_back(p); }
    T* pop() { T* v = data_.back(); data_.pop_back(); return v; }
    T& top() { return *data_.back(); }
    bool empty() const { return data_.empty(); }
    size_t size() const { return data_.size(); }
private:
    std::vector<T*> data_;
};

int main() {
    Stack<int> si; si.push(42);
    Stack<bool> sb; sb.push(true); sb.push(false);
    int a = 10, b = 20;
    Stack<int*> sp; sp.push(&a); sp.push(&b);
    std::cout << "int=" << si.size()
              << " bool=" << sb.size()
              << " ptr-top=" << sp.top() << "\n";
    return 0;
}
```

### 示例 3：constexpr + if constexpr 编译期计算

```cpp
#include <iostream>

constexpr unsigned long long factorial(unsigned int n) {
    unsigned long long r = 1;
    for (unsigned int i = 2; i <= n; ++i) r *= i;
    return r;
}

template<unsigned int N>
constexpr unsigned long long sum_to() {
    if constexpr (N == 0) return 0;
    else return N + sum_to<N - 1>();
}

int main() {
    constexpr auto f5 = factorial(5);
    static_assert(f5 == 120, "5! must be 120");
    std::cout << "5!=" << f5 << " 10!=" << factorial(10) << "\n";
    constexpr auto s100 = sum_to<100>();
    std::cout << "sum_to<100>=" << s100 << "\n"; // 5050
    return 0;
}
```

### 示例 4：自定义 concept + requires 约束

```cpp
#include <concepts>
#include <iostream>
#include <vector>

template<typename T>
concept Printable = requires(T v) { std::cout << v; };

template<std::integral T>
T gcd(T a, T b) {
    while (b != 0) { T t = b; b = a % b; a = t; }
    return a;
}

template<typename T>
  requires std::ranges::range<T> && Printable<std::ranges::range_value_t<T>>
void print_all(const T& c) {
    for (const auto& v : c) std::cout << v << " ";
    std::cout << "\n";
}

int main() {
    std::cout << "gcd(48,18)=" << gcd(48, 18) << "\n";
    std::vector<int> v = {1, 2, 3, 4, 5};
    print_all(v);
    // gcd(3.14, 2.71); // 一行错误：double 不满足 std::integral
    return 0;
}
```

### 示例 5：RingBuffer<T, N> —— 推荐项目

```cpp
#include <array>
#include <concepts>
#include <iostream>
#include <optional>

template<typename T, size_t N>
  requires std::default_initializable<T> && (N > 0)
class RingBuffer {
public:
    bool push(const T& val) {
        if (full_) return false;
        buf_[write_] = val;
        write_ = (write_ + 1) % N;
        if (write_ == read_) full_ = true;
        return true;
    }

    std::optional<T> pop() {
        if (empty()) return std::nullopt;
        T val = std::move(buf_[read_]);
        read_ = (read_ + 1) % N;
        full_ = false;
        return val;
    }

    bool empty() const { return !full_ && write_ == read_; }
    bool full()  const { return full_; }
    size_t capacity() const { return N; }
    size_t size() const { return full_ ? N : (write_ + N - read_) % N; }

private:
    std::array<T, N> buf_{};
    size_t read_ = 0, write_ = 0;
    bool full_ = false;
};

int main() {
    RingBuffer<int, 4> rb;
    for (int i = 1; i <= 4; ++i) rb.push(i);
    std::cout << "cap=" << rb.capacity()
              << " full=" << std::boolalpha << rb.full()
              << " size=" << rb.size() << "\n";
    std::cout << "push(5) -> " << rb.push(5) << "\n";
    while (!rb.empty()) std::cout << *rb.pop() << " ";
    std::cout << "\nempty-pop has_value=" << rb.pop().has_value() << "\n";
    return 0;
}
```

### 示例 6：依赖名称消歧义

```cpp
#include <iostream>
#include <vector>

template<typename C>
void show_first(const C& c) {
    if (c.empty()) return;
    typename C::value_type v = c.front();
    std::cout << "first: " << v << "\n";
}

template<typename T>
struct Wrap {
    template<typename U>
    U to(const T& val) const { return static_cast<U>(val); }
};

template<typename W>
void demo(const W& w, int x) {
    auto d = w.template to<double>(x);
    std::cout << "to<double>: " << d << "\n";
}

int main() {
    std::vector<int> v = {10, 20, 30};
    show_first(v);
    Wrap<int> w;
    demo(w, 42);
    return 0;
}
```

## 7. 总结

### 关键要点

1. **单态化是 C++ 模板的根本**：编译器为每种 `<T>` 生成独立代码——零运行时开销，二进制体积和编译时间随之增长
2. **函数模板自动推导，类模板需显式指定或 CTAD**：C++17 CTAD 为类模板提供类似函数模板的便利性
3. **全特化 > 偏特化 > 主模板**：编译器选最匹配版本；全特化做定制优化，偏特化做模式匹配
4. **if constexpr 替代 SFINAE**：C++17 起编译期分支优先用 `if constexpr`，被弃分支完全不实例化
5. **concept 是 C++20 最重要的泛型特性**：约束声明式、错误可读、重载清晰——替代 enable_if 的现代方案
6. **非类型模板参数让常量参数化**：`Buffer<T,4096>` 和 `Buffer<T,8192>` 是不同类型，容量在编译期
7. **typename/template 是依赖名称的路标**：模板内部 `T::x` 需要用 `typename` 标记为类型、`template` 标记为模板

### 跨语言对比：泛型

| 维度 | C++ | Java | Rust | Go |
|------|-----|------|------|-----|
| 范式 | 编译期单态化 | 类型擦除 | trait 约束 + 单态化 | 接口约束 + 单态化 |
| 运行时开销 | 零 | 装箱/类型检查 | 零 | 接近零 |
| 约束演进 | enable_if → concept | extends（始终简洁） | trait bound（始终清晰） | interface（始终清晰） |
| 核心取舍 | 编译时间换极致性能 | 编译快，运行有开销 | 安全+性能，学习陡 | 简洁+性能，能力受限 |

### 阶段验收标准

- 能写函数模板和类模板，理解单态化与类型擦除的根本差异
- 能解释全特化与偏特化的选择规则，为特定类型编写特化版本
- 能用 concept + requires 写出带约束的泛型函数，替代 enable_if / SFINAE
- 能解释 if constexpr 编译期分支原理，以及两阶段名称查找
- 能在依赖名称前正确使用 `typename` 和 `template` 关键字

### 进入下一阶段前

泛型 max/min（含 concept 约束）、泛型 Stack（含全特化/偏特化）、constexpr 阶乘与编译期求和、自定义 concept 约束的泛型函数、RingBuffer<T,N> 推荐项目、依赖名称消歧义实验。

### 推荐项目

- **泛型 RingBuffer<T, N>**：非类型模板参数指定容量，concept 约束元素类型，环形缓冲区经典的读写指针逻辑
- **泛型 Stack<T> 完整实现**：含 bool 全特化（位图优化）和 T* 偏特化（自动解引用），验证分发到正确版本

### 下一阶段

[现代 C++（C++11~C++23）阶段](../ph06-modern-cpp/06-modern-cpp.md) —— auto/智能指针/lambda/optional/variant/std::format 等现代写法；异常安全与错误码体系将随后在 ph07 展开。
