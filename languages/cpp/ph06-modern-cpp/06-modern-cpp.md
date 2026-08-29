# C++ 现代 C++（C++11~C++23）阶段

> 面向高性能系统、存储引擎方向，本阶段从 C++11 起掌握现代写法——用类型推断、智能指针、lambda 与类型安全格式化，告别裸资源和样板代码。

## 1. 概述

本阶段定位：**能写出 C++11 之后的现代代码——用 auto/lambda/智能指针消灭裸 new/delete 与样板代码，用 optional/variant/std::format/<=> 表达类型安全的语义**，覆盖 C++17/20 关键特性。学完后不再手写裸指针资源管理，不再用 printf 或 iostream 拼接输出，能清晰解释每个对象的所有权归属。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 类型推断 | auto、decltype、nullptr、范围 for |
| 智能指针 | unique_ptr、shared_ptr、weak_ptr（所有权与 RAII） |
| 可调用对象 | lambda 表达式、std::function |
| 可选与多态值 | std::optional、std::variant、std::any |
| 类型安全格式化 | std::format、std::print（C++20/23） |
| 现代运算符与声明 | `<=>` 三路比较、enum class、using、noexcept |
| 编译期求值 | constexpr / consteval 常量表达式 |

**范围边界**：本阶段承接 ph05 模板与泛型；**不涉及**异常安全体系（ph07）、并发与线程（ph08）、对象生命周期深入（ph12），也不展开协程与 C++20 模块，这些留给后续阶段。

## 2. 来源与演变

C++11（2011）是现代 C++ 的分水岭，Stroustrup 形容它"像一门新语言"：auto、lambda、移动语义、智能指针、nullptr、范围 for、enum class、constexpr 一次性涌入，把"资源管理"从程序员纪律变成语言与库的默认行为。C++14 与 C++17 是实用主义阶段：放宽 constexpr、引入泛型 lambda，随后带来 optional/variant/any、结构化绑定、if constexpr 与 CTAD，几乎消灭了手写样板。C++20 完成现代化拼图：concept、`<=>`、std::format、consteval、ranges；C++23 继续增强：std::print、std::expected、mdspan。

| 版本 | 年份 | 关键特性 |
|------|------|---------|
| C++11 | 2011 | auto/decltype、lambda、智能指针、移动语义、nullptr、范围 for、enum class、constexpr |
| C++14 | 2014 | 泛型 lambda、constexpr 放宽、返回类型推导 |
| C++17 | 2017 | optional/variant/any、结构化绑定、if constexpr、CTAD |
| C++20 | 2020 | concept、`<=>` 三路比较、std::format、consteval、ranges |
| C++23 | 2023 | std::print、std::expected、mdspan、deducing this |

演进主线是**在保持零成本抽象的前提下消灭样板与裸资源**：每个版本都在"更安全"与"不增加运行时开销"之间平衡——这正是存储引擎、数据库内核最看重的语言特质。

## 3. 语法与参数
### 3.1 auto / decltype / nullptr / 范围 for
`auto` 从初始化表达式推导类型，消灭冗长的类型名；`decltype` 不经过初始化，直接问"表达式的类型是什么"；`nullptr` 是真正的空指针常量，替代 `NULL`/`0`；范围 for 统一遍历容器，替代手写下标/迭代器循环。
```cpp
#include <iostream>
#include <string>
#include <vector>

int main() {
    auto x = 42;                           // int
    auto pi = 3.14;                        // double
    auto s = std::string("hi");            // std::string（而非 const char*）

    int v = 42;
    decltype(v) y = 100;

    int* p = nullptr;
    if (p == nullptr) std::cout << "p is null\n";

    std::vector<int> nums = {1, 2, 3, 4, 5};
    for (const auto& n : nums) std::cout << n << " ";  // 范围 for
    std::cout << "\n";
    return 0;
}
```
要点：
- **auto 不保留 const 与引用**：只读遍历必须写 `const auto&`，修改元素用 `auto&`
- `decltype` 常用于泛型返回类型（`decltype(auto)`）；`nullptr` 的类型是 `std::nullptr_t`，不能隐式转为整数
### 3.2 智能指针：unique_ptr / shared_ptr / weak_ptr
智能指针是 RAII 在堆对象上的标准实现——**对象离开作用域时析构函数自动释放**，从此不必手写 `delete`：

| 智能指针 | 所有权 | 典型用途 |
|---------|-------|---------|
| `unique_ptr<T>` | 唯一所有权，不可拷贝、可移动 | 默认选择：一个对象只有一个所有者 |
| `shared_ptr<T>` | 共享所有权，引用计数 | 多方共享同一资源（如连接池中的连接） |
| `weak_ptr<T>` | 弱引用，不增加计数 | 观察 shared_ptr 是否存活、打破循环引用 |
```cpp
#include <iostream>
#include <memory>

struct Sensor {
    Sensor() { std::cout << "Sensor()\n"; }
    ~Sensor() { std::cout << "~Sensor()\n"; }
    int read() const { return 42; }
};

int main() {
    auto s = std::make_unique<Sensor>();   // 唯一所有权，离开作用域自动释放
    // std::unique_ptr<Sensor> s2 = s;     // 编译错误：不可拷贝
    auto s2 = std::move(s);                // 所有权转移
    if (!s) std::cout << "s 已为空\n";

    auto a = std::make_shared<Sensor>();   // 共享所有权，引用计数
    std::shared_ptr<Sensor> b = a;
    std::cout << "use_count=" << a.use_count() << "\n";

    std::weak_ptr<Sensor> w = a;
    if (auto sp = w.lock()) std::cout << "weak lock ok\n";
    a.reset();
    b.reset();
    std::cout << "expired=" << w.expired() << "\n";
    return 0;
}
```
要点：
- **unique_ptr 是默认选择，shared_ptr 不是**：共享所有权引入控制块与原子计数开销
- 构造优先 `make_unique` / `make_shared`：异常安全，make_shared 还能把对象与控制块合并为一次分配
- **shared_ptr 循环引用会泄漏**：A↔B 互持 shared_ptr 计数永不为 0，用 weak_ptr 打破环；weak_ptr 需 `lock()` 提升后才能访问
### 3.3 lambda 与 std::function
lambda 是**就地定义的匿名函数对象**：`[捕获列表](参数) { 函数体 }`，捕获列表决定闭包携带的外部状态；`std::function` 是"可调用对象的类型擦除包装"，可统一存放 lambda、函数指针与仿函数。
```cpp
#include <algorithm>
#include <functional>
#include <iostream>
#include <vector>

int main() {
    std::vector<int> v = {5, 2, 8, 1, 9};
    std::sort(v.begin(), v.end(), [](int a, int b) { return a > b; }); // 降序
    for (int n : v) std::cout << n << " ";
    std::cout << "\n";

    int base = 10;
    auto add_val = [base](int x) { return x + base; };  // 按值捕获
    auto add_ref = [&base](int x) { return x + base; }; // 按引用捕获
    std::cout << add_val(5) << " " << add_ref(5) << "\n";

    std::function<int(int)> cb = add_val;    // 类型擦除包装
    cb = [](int x) { return x * x; };        // 可重新赋值
    std::cout << "cb(6)=" << cb(6) << "\n";
    return 0;
}
```
要点：
- **捕获默认按值拷贝，`[&]` 有悬垂风险**：lambda 存活期超过被捕获变量时，`[&]` 会访问已销毁对象
- 空捕获 `[]` 的 lambda 可转为函数指针零开销；`std::function` 有类型擦除开销，仅在需要存储/传递任意回调（注册表、事件系统）时使用
### 3.4 std::optional / std::variant / std::any
三个"值语义工具箱"成员（C++17）：`optional<T>` 表示**值可能不存在**；`variant<Ts...>` 表示**同一时刻恰好是 Ts 之一**（类型安全的 union）；`any` 表示**任意类型**（运行时类型擦除）。
```cpp
#include <any>
#include <iostream>
#include <optional>
#include <string>
#include <variant>

int main() {
    std::optional<int> o1 = 42, o2;                        // o2 无值
    std::cout << o1.value_or(0) << " " << o2.value_or(0) << "\n";

    std::variant<int, double, std::string> v = 42;         // 同一时刻一种类型
    v = std::string("hello");
    std::cout << std::get<std::string>(v) << " index=" << v.index() << "\n";

    std::any a = 42;                                       // 任意类型
    a = std::string("world");
    if (a.type() == typeid(std::string))
        std::cout << std::any_cast<std::string>(a) << "\n";
    return 0;
}
```
要点：
- `optional` 显式表达"查找可能失败"，替代返回 `-1`/空串/哨兵值；访问用 `*o` 或 `value_or(default)`
- `variant` 是**类型安全的 union**：不活跃分支不构造，用 `std::get_if`/`std::visit` 安全访问；`any` 依赖运行时 typeid，开销最大
- 三者都**不要求 T 可默认构造**，用 `emplace` 就地构造
### 3.5 std::format / std::print（C++20/23）
`std::format`（C++20，`<format>`）提供 **printf 的简洁、类型安全、可扩展**的格式化：格式串在编译期解析校验，实参类型在编译期与占位符匹配。`std::print`/`std::println`（C++23，`<print>`）直接输出到 stdout，省去 `std::cout <<` 的拼接样板。
```cpp
// 编译：g++ -std=c++23 fmt.cpp（GCC 13+ / Clang 17+）
#include <format>
#include <iostream>
#include <print>
#include <string>

int main() {
    int id = 7;
    double val = 3.1415926;
    std::string unit = "V";
    std::string msg = std::format("sensor {}: value = {:.2f} {}", id, val, unit);
    std::println("{}", msg);                        // C++23 直接打印到 stdout
    std::cout << std::format("sensor {}: value = {:.2f} {}\n", id, val, unit);
    // std::format("{} {}", 42);   // 编译错误：占位符多于实参
    // std::format("{:d}", 3.14);  // 编译错误：double 不能用整数说明符 d
    return 0;
}
```
要点：
- **格式串必须是常量表达式**（P2216 起）：拼错占位符、实参类型不匹配都在编译期报错，这是相对 printf 的根本改进
- 说明符与 printf 类似：`{:d}` 整数、`{:.2f}` 浮点两位小数、`{:>8}` 右对齐、`{:x}` 十六进制
- 自定义类型特化 `std::formatter<T>` 即可接入 `{}`（见示例 5），实现"类型安全、可扩展"
### 3.6 三路比较运算符 `<=>`（C++20）
`<=>` 一次比较返回 `std::strong_ordering` / `std::weak_ordering` / `std::partial_ordering` 之一，**默认化后编译器自动生成全部六个比较运算符**（`==`、`!=`、`<`、`<=`、`>`、`>=`），消灭手写重载的样板与不一致。
```cpp
#include <compare>
#include <iostream>

struct Point {
    int x, y;
    auto operator<=>(const Point&) const = default;  // 自动生成全部比较
    bool operator==(const Point&) const = default;
};

int main() {
    Point a{1, 2}, b{1, 3};
    std::cout << (a < b ? "a < b" : "a >= b") << "\n";
    std::cout << (a != b ? "a != b" : "a == b") << "\n";
    auto r = a <=> b;
    std::cout << (r < 0 ? "less" : r > 0 ? "greater" : "equal") << "\n";
    return 0;
}
```
要点：
- 默认化 `<=>` 按成员**声明顺序**逐字段比较；未显式声明 `==` 时编译器隐式默认生成
- 成员含浮点（NaN 语义）时返回 `partial_ordering`；需要自定义规则时再手写重载
- `std::sort`、`std::map`、`std::set` 只需要 `<`，默认化 `<=>` 一次到位
### 3.7 enum class / using / noexcept
`enum class` 是**有作用域、无隐式转换**的强类型枚举，避免传统 `enum` 把名字泄漏进外层命名空间；`using` 承担类型别名、引入基类成员、命名空间指令三类职责；`noexcept` 声明函数"不抛异常"，既是优化承诺也是接口契约。
```cpp
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

enum class Level : uint8_t { Low = 1, Medium, High };  // 强类型 + 底层类型
enum class Color { Red, Green, Blue };
using StringList = std::vector<std::string>;

int add(int a, int b) noexcept { return a + b; }       // 承诺不抛异常

int main() {
    Color c = Color::Red;
    // if (c == 0) { }   // 编译错误：enum class 不能与 int 隐式比较
    if (c == Color::Red) std::cout << "is red\n";
    std::cout << "Low=" << static_cast<int>(Level::Low) << "\n";
    StringList names = {"a", "b"};
    std::cout << add(2, 3) << " size=" << names.size() << "\n";
    return 0;
}
```
要点：
- **enum class 不污染命名空间、不隐式转 int**：与整数比较/赋值必须 `static_cast`——这正是 roadmap 必会概念
- `using` 别名可模板化（别名模板），`typedef` 不能；`using Base::foo;` 把基类重载引入派生类作用域
- `noexcept` 不是"可以不写 try/catch"：函数内真的抛出会直接 `std::terminate`，只在确定不抛（getter、移动构造）时声明
### 3.8 constexpr 与现代常量表达式
`constexpr` 把"编译期常量"从宏和枚举扩展到**任意可在编译期求值的函数与对象**：C++11 起可写 constexpr 函数（限制多），C++14 放宽为普通函数体（可循环/局部变量），C++20 的 `consteval` 强制编译期求值。
```cpp
#include <array>
#include <iostream>

constexpr int square(int x) { return x * x; }          // 编译期可算
consteval int cube(int x) { return x * x * x; }        // C++20：必须编译期求值

constexpr std::array<int, 5> make_table() {            // C++14：函数体内可循环
    std::array<int, 5> a{};
    for (int i = 0; i < 5; ++i) a[i] = i * i;
    return a;
}

int main() {
    constexpr int sq = square(12);
    static_assert(sq == 144);
    constexpr auto table = make_table();
    static_assert(table[4] == 16);
    std::cout << "cube(3)=" << cube(3) << "\n";
    std::cout << "square(5)=" << square(5) << "\n";
    return 0;
}
```
要点：
- constexpr 对象可作**模板参数、数组大小、case 标签**；`static_assert` 在编译期验证
- constexpr 函数**也可在运行期调用**；`consteval` 强制编译期，无法传入运行期变量

## 4. 底层原理
### 4.1 智能指针的实现原理
**unique_ptr 是零开销包装**：内部只含裸指针 `T*` 与删除器（默认 `delete`），大小与裸指针相同，无控制块、无原子操作——这是它成为默认选择的原因。**shared_ptr 分为两部分**：对象指针 + 控制块指针。控制块（control block）保存：

| 控制块成员 | 作用 |
|-----------|------|
| use_count | 存活 shared_ptr 数量（原子计数） |
| weak_count | weak_ptr 数量（含 use_count 本身） |
| deleter / allocator | 自定义删除器与分配器 |
| （make_shared 时）对象本身 | 对象与控制块合并为一次堆分配 |

`weak_ptr` 只持有控制块、不参与对象所有权：`lock()` 先**原子地**检查 use_count 是否为 0——不为 0 则递增并返回 shared_ptr，为 0 返回空。原子操作保证多线程下"检查-提升"无悬垂窗口；但**指向对象本身的访问仍需外部同步**（计数安全 ≠ 数据安全）。

**循环引用**：A↔B 互持 shared_ptr 时计数互为依赖、永不为 0；让环中一条边改用 weak_ptr——"强"边 shared_ptr + "弱"边 weak_ptr，环即可断开。
### 4.2 lambda 的闭包实现
lambda 在编译期展开为一个**匿名闭包类型（closure type）**：捕获变量变成闭包对象的成员，函数体变成 `operator()`：

```cpp
void demo_closure() {
    int base = 10;
    auto add = [base](int x) { return x + base; };
    // 等价于编译器生成：
    struct Closure {
        int base;                                    // 按值捕获 → 成员拷贝
        int operator()(int x) const { return x + base; }
    };
    Closure c{base};
    (void)c(5);                                      // 与 add(5) 结果一致
}
```

- **按值捕获 `[base]`**：闭包内拷贝一份，`sizeof(闭包)` 随捕获增多而增大，闭包独立存活
- **按引用捕获 `[&base]`**：成员是引用，只含一个指针；**原变量销毁后访问即悬垂**
- `[=]`/`[&]` 是"全部捕获"语法糖；空捕获 `[]` 闭包可转为函数指针零开销；`std::function` 通过类型擦除（虚调用/小对象优化）包装任意可调用对象
### 4.3 optional / variant 的存储布局
三者都是**无堆分配的值语义**类型（any 除外），用"原始存储 + 状态标记"实现：

| 类型 | 存储 | 活跃标记 | 构造方式 |
|------|------|---------|---------|
| `optional<T>` | `alignas(T) unsigned char storage[sizeof(T)]` | 1 个 bool | 有值时 placement-new |
| `variant<Ts...>` | 最大成员的 sizeof + 最严对齐 | 判别索引 index | `emplace` 就地构造分支 |
| `any` | 类型擦除包装 | typeid | 小对象优化；大对象堆分配 |

关键点：**存储必须按 `alignof(T)` 对齐**——`alignas(T)` 让原始缓冲区满足对齐要求；赋值/换值先析构旧对象再就地构造新对象（`emplace` 内部即 placement-new）。因此 `optional<T>` 不要求 T 可默认构造、`variant` 不构造未活跃的分支；限制：variant 不接受引用、void、数组与重复类型。
### 4.4 std::format 的类型安全实现思路
`std::format` 把"格式化"拆成编译期与运行期两半：

1. **编译期解析**：格式串参数包装成 `basic_format_string`，其构造函数是 `consteval`——编译期解析格式串、校验占位符数量与说明符（P2216 起格式串必须是常量表达式）
2. **运行期类型擦除**：实参包成 `format_arg`（内部类似 variant 的类型集合），按说明符逐一格式化，不再依赖 printf 的 `va_arg` 运行时解释
3. **可扩展**：`std::formatter<T>` 是可定制点，用户特化即可让自定义类型接入 `{}`（见示例 5）

对比：printf 的 `%d`/`%f` 与实参类型靠程序员自觉，错配是未定义行为；iostream 用运行时状态机 + 操作符重载，拼接样板冗长；`std::format` 在编译期消灭这两类问题，运行时开销接近 sprintf。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 对象唯一所有权（资源、连接、缓冲） | unique_ptr + make_unique |
| 多方共享同一资源（连接池、缓存） | shared_ptr + weak_ptr |
| 观察/缓存引用但不延长生命周期 | weak_ptr.lock() |
| 查找/解析可能失败，拒绝哨兵值 | std::optional |
| 设备/消息/状态多种形态，类型安全建模 | std::variant + std::visit |
| 排序规则、回调、事件处理 | lambda + std::function |
| 日志、上报、用户可见输出 | std::format / std::print |
| 值类型排序、比较，避免手写重载 | `<=>` 默认化 |

**不适合**此阶段的事项：
- **协程 coroutine（C++20）**：异步/生成器编程，后续阶段再学
- **并行算法与执行策略**（`std::execution`）：依赖并发与内存序知识，属于并发阶段
- **C++20 模块 module**：影响构建系统与头文件组织，留到工程规范阶段
- **ranges 视图组合深入**：管道式写法需先吃透模板与容器，必要时回 ph05 补充

## 6. 代码示例
### 示例 1：智能指针管理资源（make_unique / make_shared，RAII 替代裸 new/delete）
```cpp
// 编译：g++ -std=c++17 ex1_smart_ptr.cpp -o ex1
#include <iostream>
#include <memory>
#include <string>

struct FileHandle {                          // RAII：构造打开、析构关闭
    explicit FileHandle(const std::string& name) : name_(name) {
        std::cout << "open " << name_ << "\n";
    }
    ~FileHandle() { std::cout << "close " << name_ << "\n"; }
    const std::string& name() const { return name_; }
private:
    std::string name_;
};

int main() {
    auto f1 = std::make_unique<FileHandle>("data.db");     // 唯一所有权
    std::cout << "working on " << f1->name() << "\n";
    auto f2 = std::move(f1);                               // 所有权转移
    std::cout << "f1 is " << (f1 ? "alive" : "null") << " after move\n";

    auto shared = std::make_shared<FileHandle>("log.txt"); // 共享所有权
    std::shared_ptr<FileHandle> alias = shared;            // 计数 2
    std::cout << "use_count=" << shared.use_count() << "\n";

    std::weak_ptr<FileHandle> watcher = shared;            // 观察者
    if (auto sp = watcher.lock())
        std::cout << "watcher sees " << sp->name() << "\n";
    shared.reset();
    alias.reset();
    std::cout << "expired=" << watcher.expired() << "\n";
    return 0;
}
```
### 示例 2：用 lambda 定义排序规则与回调（std::sort + capture）
```cpp
// 编译：g++ -std=c++17 ex2_lambda.cpp -o ex2
#include <algorithm>
#include <functional>
#include <iostream>
#include <string>
#include <vector>

struct Sensor {
    std::string name;
    double value;
};

int main() {
    std::vector<Sensor> sensors = {{"temp", 36.5}, {"hum", 60.2}, {"co2", 810.0}};

    // lambda 定义排序规则：按 value 降序
    std::sort(sensors.begin(), sensors.end(),
              [](const Sensor& a, const Sensor& b) { return a.value > b.value; });
    for (const auto& s : sensors) std::cout << s.name << " = " << s.value << "\n";

    // capture 外部阈值过滤
    double threshold = 50.0;
    auto above = [threshold](const Sensor& s) { return s.value > threshold; };
    std::cout << "value > " << threshold << "：\n";
    for (const auto& s : sensors)
        if (above(s)) std::cout << "  " << s.name << "\n";

    // std::function 包装回调
    std::function<void(const Sensor&)> report = [](const Sensor& s) {
        std::cout << "report: " << s.name << " = " << s.value << "\n";
    };
    for (const auto& s : sensors) report(s);
    return 0;
}
```
### 示例 3：std::optional 表示查找结果 / 配置项可选值
```cpp
// 编译：g++ -std=c++17 ex3_optional.cpp -o ex3
#include <iostream>
#include <optional>
#include <string>
#include <unordered_map>

// 查找配置项：可能不存在，用 optional 表达，拒绝 -1/空串哨兵值
std::optional<int> lookup(const std::unordered_map<std::string, int>& conf,
                          const std::string& key) {
    auto it = conf.find(key);
    if (it == conf.end()) return std::nullopt;   // 显式"无值"
    return it->second;
}

int main() {
    std::unordered_map<std::string, int> config = {
        {"port", 8080}, {"timeout_ms", 5000},
    };

    auto port = lookup(config, "port");
    if (port) std::cout << "port = " << *port << "\n";          // 8080

    auto retries = lookup(config, "retries");
    std::cout << "retries has_value = "
              << std::boolalpha << retries.has_value() << "\n"; // false
    std::cout << "retries value_or = "
              << retries.value_or(3) << "\n";

    std::optional<std::string> name;            // emplace 就地构造
    name.emplace("cache_node");
    std::cout << "name = " << *name << "\n";
    return 0;
}
```
### 示例 4：std::variant 建模多种状态（设备状态 / 消息类型）
```cpp
// 编译：g++ -std=c++17 ex4_variant.cpp -o ex4
#include <iostream>
#include <string>
#include <type_traits>
#include <variant>
#include <vector>

// 设备状态：运行中（带读数）/ 故障（带错误码）/ 离线
struct Running { double value; };
struct Faulted { int error_code; std::string message; };
struct Offline {};
using DeviceState = std::variant<Running, Faulted, Offline>;

std::string describe(const DeviceState& s) {
    if (std::holds_alternative<Running>(s))
        return "running, value=" + std::to_string(std::get<Running>(s).value);
    if (std::holds_alternative<Faulted>(s)) {
        const auto& f = std::get<Faulted>(s);
        return "fault " + std::to_string(f.error_code) + ": " + f.message;
    }
    return "offline";
}

int main() {
    std::vector<DeviceState> states = {
        Running{36.5}, Faulted{503, "sensor timeout"}, Offline{},
    };
    for (const auto& s : states) std::cout << describe(s) << "\n";

    // std::visit：对当前活跃分支统一处理（与 if constexpr 结合）
    std::visit([](const auto& s) {
        using T = std::decay_t<decltype(s)>;
        if constexpr (std::is_same_v<T, Running>)
            std::cout << "[visit] running value=" << s.value << "\n";
        else if constexpr (std::is_same_v<T, Faulted>)
            std::cout << "[visit] fault code=" << s.error_code << "\n";
        else
            std::cout << "[visit] offline\n";
    }, states[1]);

    std::cout << "index of Faulted = " << states[1].index() << "\n"; // 1
    return 0;
}
```
### 示例 5：std::format 类型安全格式化输出（C++20，替代 printf / iostream 拼接）
```cpp
// 编译：g++ -std=c++23 ex5_format.cpp -o ex5（GCC 13+ / Clang 17+）
#include <format>
#include <iostream>
#include <print>
#include <string>

struct Sensor {
    std::string name;
    double value;
};

// 自定义类型接入 std::format：特化 std::formatter
template<>
struct std::formatter<Sensor> {
    constexpr auto parse(std::format_parse_context& ctx) { return ctx.begin(); }
    auto format(const Sensor& s, std::format_context& ctx) const {
        return std::format_to(ctx.out(), "{} = {:.2f}", s.name, s.value);
    }
};

int main() {
    int id = 7;
    double val = 3.1415926;
    std::string unit = "V";
    std::string msg = std::format("sensor {}: value = {:.2f} {}", id, val, unit);
    std::println("{}", msg);                    // C++23：直接打印到 stdout
    std::cout << std::format("sensor {}: value = {:.2f} {}\n", id, val, unit);
    std::println("report: {}", Sensor{"temp", 36.5});  // 自定义类型
    return 0;
}
```

（若编译器暂不支持 C++23 `<print>`，把 `std::println` 换成 `std::cout << std::format(...)` 即可降级为 C++20。）

## 7. 总结
### 关键要点
1. **智能指针是 RAII 的标准实现**：unique_ptr 唯一所有权、零开销；shared_ptr 共享所有权、控制块 + 原子计数；weak_ptr 观察不持有、打破循环引用
2. **unique_ptr 是默认选择，shared_ptr 不是**：共享所有权有成本，仅在确需共享时使用；构造优先 make_unique / make_shared
3. **optional 表达"可能不存在"**：替代 -1/空串等哨兵值，配合 value_or 给出默认值
4. **variant 是类型安全的 union**：同一时刻恰好一种分支，std::visit + if constexpr 统一处理
5. **std::format 类型安全、可扩展、编译期校验**：替代 printf 与 iostream 拼接；std::print 再省掉 cout 样板
6. **`<=>` 默认化自动生成一致性比较**：一次声明得到全部六个比较运算符，减少手写重载
7. **lambda 是现代 C++ 的匿名函数**：捕获列表决定闭包状态，`[&]` 有悬垂风险；std::function 做类型擦除回调
8. **enum class 不污染命名空间、不隐式转整数**：类型安全从枚举开始；using 统一别名语法；noexcept 表达不抛承诺
9. **constexpr 把计算提前到编译期**：C++14 放宽函数体、C++20 consteval 强制编译期求值
### 跨语言对比：资源所有权
| 维度 | C++ 智能指针 | Rust 所有权 | Java GC | Go GC | C 手动 |
|------|-------------|------------|---------|-------|--------|
| 所有权模型 | unique_ptr 独占 / shared_ptr 共享 | 单一所有者 + 借用/生命周期 | 无所有权概念（可达性） | 无所有权概念（可达性） | 完全程序员负责 |
| 释放时机 | 作用域结束确定性释放 | 作用域结束确定性释放 | 不可预测（GC 周期） | 不可预测（GC 周期） | 程序员手工 free |
| 悬垂防护 | weak_ptr.lock() 运行时检测 | 借用检查器**编译期**拒绝 | GC 保证可达对象存活 | GC 保证存活 | 无防护 |
| 循环引用 | weak_ptr 打破 | 弱引用（Rc/RefCell 场景） | GC 处理 | GC 处理 | 无 |
| 线程安全 | 计数原子；对象访问需自行同步 | Send/Sync 编译期检查 | 有 GC 屏障/停顿 | 有写屏障/停顿 | 无 |
| 运行时开销 | 控制块 + 原子计数 | 编译期检查，运行期零 | 追踪、屏障、停顿 | 写屏障、停顿 | 零 |

一句话：C++ 用"类型 + 库"换确定性释放，Rust 用"编译器"换安全，GC 语言用"暂停"换省心，C 则把全部责任交给程序员——**本阶段的收获是学会像 C++ 一样在确定性与成本之间做选择**。
### 阶段验收标准
- 能用 unique_ptr/shared_ptr 替代裸 new/delete，代码中不再出现手写 delete
- 能解释 unique_ptr / shared_ptr / weak_ptr 的所有权关系，并说明何时该用哪一个
- 能用 std::format 替代 iostream 拼接和 printf 风格输出，并利用编译期校验
- 能写出 C++17/20 风格代码：auto、范围 for、lambda、optional、variant、`<=>`
- 能说出 enum class、using、noexcept、constexpr 的作用与典型使用场景
### 进入下一阶段前
确保能完成以下练习：
- 用 unique_ptr 管理对象，验证离开作用域自动释放，并尝试转移所有权
- 用 optional 表示查找结果，比较与返回 -1/空串两种写法的差异
- 用 std::format 重写一段 `std::cout << ... << ...` 的字符串拼接
- 用 lambda 定义 std::sort 的排序规则，并 capture 一个外部阈值做过滤
- 用 variant 表示设备/消息的多种状态，用 std::visit 统一处理
- 用 shared_ptr + weak_ptr 模拟共享资源与观察者，验证循环引用被打破
### 推荐项目
- **配置管理模块**：`Config` 类用 `std::unordered_map<std::string, Value>` 存键值，`optional` 表达缺失配置项，`std::format` 输出配置清单，`unique_ptr` 管理底层缓冲——覆盖本阶段一半以上知识点
- **状态类型建模 demo**：用 `variant` 建模设备状态/消息类型（如 Running/Faulted/Offline），`std::visit` 统一处理，`enum class` 定义状态码，`<=>` 定义状态优先级比较——roadmap 指定项目，直接服务状态机类工程
### 下一阶段
[异常、安全与工程规范阶段](../ph07-exception-safety/07-exception-safety.md) ——try/catch、异常安全等级（基本/强/不抛）、错误码体系、RAII 与异常安全资源封装。
