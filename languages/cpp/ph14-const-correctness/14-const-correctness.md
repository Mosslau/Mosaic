# C++ const 正确性与接口设计阶段

> 面向高性能系统、存储引擎方向，本阶段把 const 从"关键字"升级为**接口设计语言**：顶层/底层 const 的类型规则、const 成员函数与 const 对象、const 引用参数（F.16）、mutable 的谨慎使用、逻辑 const 与物理 const 的区分，以及用 `string_view` / `span` 设计"观察不拥有"的只读视图接口——让"不会修改"成为编译器强制执行的接口承诺，而不是调用者的自觉。

## 1. 概述

本阶段定位：**掌握 const 正确性（const-correctness）的完整规则——区分顶层 const 与底层 const，能设计"接口即承诺"的 const 正确类（Con.2），用 const 引用参数减少不必要拷贝（F.16），谨慎使用 mutable（缓存/互斥锁/计数），分清逻辑 const 与物理 const，并用 `string_view` / `span` 设计只读视图接口**。它是整个路线的第 14 步：ph04 STL 阶段讲过 `string_view` / `span` 的用法基础，ph12 对象生命周期阶段讲过 `const&` 借用式接口与临时对象生命周期延长，ph13 Rule of 0/3/5 与 RAII 进阶阶段讲透了"资源类的内部实现"；本阶段把视角从"内部实现"转向**接口设计**——资源类的接口要不要标 const、返回什么句柄、参数怎么传，正是"move-only 类为什么天然 const 友好""RAII 类的接口如何设计"这些问题的答案。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 顶层 / 底层 const | `const int` / `const int*` / `int* const` / `const int* const` 的类型规则、拷贝与转换方向（`ex01`） |
| const 成员函数 | const 对象只能调 const 成员、const/非 const 重载、返回 `const&` 与可变句柄（Con.2，`ex02`） |
| const 引用参数 | 大对象输入用 `const&`（F.16）、按值 vs 引用的拷贝实测、sink 情形（`ex03`） |
| mutable 谨慎使用 | 缓存 / 互斥锁 / 计数的正当 mutable 场景；"物理可变、逻辑不变"（`ex04`/`ex05`） |
| 逻辑 const vs 物理 const | 位不变 ≠ 语义不变；const_cast 打破物理 const 与设计气味（正反例对照，`ex04`） |
| 只读视图设计 | `string_view` / `span<const T>` 观察不拥有、零拷贝、接口即承诺（`ex06`） |

这个阶段只涉及 const 在接口设计中的完整规则（顶层/底层 const、const 成员函数、const 引用参数、mutable、逻辑 const 与物理 const、只读视图接口设计），**不涉及 constexpr/consteval 编译期编程系统化（ph05 模板与泛型编程、元编程阶段 / ph06 现代 C++ 阶段）、volatile 与多线程内存序（ph08 并发编程阶段）、引用悬挂与临时对象生命周期延长的完整规则（ph12 对象生命周期、值类别与所有权深入阶段）、const_cast 引发未定义行为的系统归类（ph15 未定义行为 UB 与内存安全阶段）和测试/静态分析/代码规范系统化（ph16 测试、静态分析与代码规范阶段）** — 那些是其他阶段的内容。承接 ph04 STL 阶段（`string_view`/`span` 的用法基础）、ph12 对象生命周期阶段（`const&` 借用式接口、临时对象生命周期）与 ph13 Rule of 0/3/5 与 RAII 进阶阶段（资源类的内部实现）：ph04 回答了"视图怎么用"，本阶段回答"视图怎么作为接口承诺"；ph12 讲了"所有权如何通过类型体现"，本阶段讲"只读如何通过类型体现"；ph13 把资源类讲透后，本阶段把它升级为"const 正确的接口"。

## 2. 来源与演变

`const` 关键字诞生于 C（C89 引入），但 C 的 const 是"物理只读"且不能用于常量表达式（C99+ 里 `const int n = 5; int a[n];` 是可变长数组而非编译期常量，C89 下该写法是编译错误）；C++ 把 const 升级为**类型系统的一部分**——不仅约束对象，还约束指针层级（顶层/底层）、成员函数（`this` 指针 const 化），并配套发明了 `mutable` 与 `const_cast`。**设计哲学一句话：const 是编译期执行的接口契约——用类型系统把"不会修改"变成编译器强制，调用者无需读实现就能信任接口**。这套核心规则自 C++98 定型后二十多年没有实质变化，是 C++ 最稳定的部分之一；后续版本（C++11 的 constexpr、C++17 的 `string_view`、C++20 的 `span`）只是把"只读"的表达能力扩展到了编译期常量与零开销视图，没有改变 const 的类型规则。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| C89/C90 | 1989/1990 | `const` 进入 C：对象只读，但不可作编译期常量（C 语义的局限） |
| C++98 | 1998 | **const 成员函数（`this` 指针 const 化）、`mutable`、`const_cast` 进入语言**；顶层/底层 const 语义明确——与 C 的 const 分道扬镳 |
| C++11 | 2011 | `constexpr` 引入（编译期常量表达，本阶段不展开）；`std::begin`/`std::end` 按 const 重载；const 类型规则无变化 |
| C++14/17 | 2014/2017 | C++17 `std::string_view` 进入标准库——**只读视图成为一等接口元素**；`std::as_const` 补位 |
| C++20 | 2020 | `std::span` 进入标准库（连续内存只读/读写视图）；const 相关规则稳定无变化 |

本文示例以 **C++20** 为基线（与 ph11/ph12/ph13 一致：roadmap 主线使用 C++20，`-std=c++20` 是稳定度与功能的平衡点；本阶段用到的 `std::string_view` 需 C++17+、`std::span` 需 C++20，均在 C++20 内），验证工具链为 **Apple clang 21.0.0（`c++`）+ Homebrew clang 21.1.8（`clang++`）**，全部示例已在本环境实际编译运行验证（已验证）；GCC/MSVC 本机没有对应编译器，涉及这两家的行为如实标注「未在本环境验证」。const 的类型系统规则（C++98 定型）与只读视图（C++17/20 定型）是这门语言**最稳定**的部分——学会了长期复用，不会随编译器升级失效。

## 3. 语法与参数

> 本节代码块为**教学骨架**：为聚焦当前语法点做了简化（省略实现细节、行内注释为讲解所加，原文件含输出语句）。完整可运行版本见第 6 节与 [`examples/`](./examples/)（与源文件逐字一致），编译/运行命令见 examples/README.md。

### 3.1 顶层 const 与底层 const：const 的"层"是类型的一部分

const 修饰的位置决定它管什么（完整演示见 `ex01`）：

| 写法 | 顶层 / 底层 | 含义 | 可写吗 |
|------|------------|------|--------|
| `const int x` | 顶层（对象本身） | x 本身只读 | x 不可写 |
| `const int* p` | 底层（指向的对象） | *p 只读；p 可改指向 | `*p` 不可写 |
| `int* const q` | 顶层（指针本身） | q 不可改指向；*q 可写 | `q` 不可改 |
| `const int* const r` | 顶层 + 底层 | 指针与指向对象都只读 | 都不可写 |

**关键规则**：

1. **拷贝/推导时顶层 const 脱落、底层 const 保留**——`auto copied = x`（x 是 `const int`）推导为 `int`；`auto cp2 = p`（p 是 `const int*`）推导为 `const int*`（`ex01` [4]，`static_assert` 编译期验证）；
2. **转换方向是单向的**：非 const → const（权限收窄）隐式允许；const → 非 const（权限放大）被编译器拒绝，只能用 `const_cast`（而 `const_cast` 通常是设计气味，见 3.4/3.5）；
3. **函数参数的顶层 const 不影响函数类型**——`void f(const int)` 与 `void f(int)` 是同一个函数，不能靠顶层 const 重载（`ex01` [6]，`std::is_same_v<void(int), void(const int)>` 为 true）；
4. **底层 const 只约束"这条路径"**——`const int*` 指向的对象被别处修改时，只读路径看得到变化（`ex01` [2] 实测：value 从 7 改成 8，`*p` 读到 8）。这是"逻辑 const 的路径视角"，见 3.5。

```cpp
// examples/ex01-top-level-low-level-const.cpp —— 顶层/底层 const（节选，与原文件逐字一致）
    const int* p = &value;      // 底层 const：*p 只读；但 value 本身非 const
    ...
    value = 8;                  // 对象本身非 const，别处照改
    ...
    int a = 1;
    int* const q = &a;          // 顶层 const：q 本身不可改指向
    *q = 10;                    // 但 *q 可改（指向的对象非 const）
```

### 3.2 const 成员函数：const 对象的通行证（Con.2）

**不修改对象状态的成员函数应标 const（Con.2）**——`void f() const` 的语义是"f 承诺不改 *this"。由此推导出三条规则（完整演示见 `ex02`）：

1. **const 对象只能调 const 成员**：`const Sensor cs; cs.calibrate(...)` 是编译期错误——这是 const 正确性把"会不会改"变成编译期检查的机制；
2. **const 与非 const 重载是不同函数**：同一签名加 const 形成重载对，非 const 对象优先选非 const 版本（`ex02` [1][2] 实测），`std::as_const(s)` 强制走 const 版本（`ex02` [5]）；
3. **返回引用时 const 版本返回 `const&`**：getter 若返回成员引用，const 版本必须返回 `const T&`（只读句柄），非 const 版本返回 `T&`（可变句柄）——否则 const 对象通过 getter 拿到的可变句柄会绕开 const 保护（`ex02` [3][4]，`decltype` 断言两种类型）。

```cpp
// examples/ex02-const-member-functions.cpp —— const 成员函数（节选，与原文件逐字一致）
    const std::string& id() const { return id_; }
    std::string& id() { return id_; }
    double reading() const { return reading_; }
    ...
    void calibrate(double offset) { reading_ += offset; }
```

**判定口诀**：成员函数"会不会改对象"不是看实现细节，而是看**调用方的权限**——const 对象能不能调？能 → 标 const。标 const 后编译器帮你检查函数体（在 const 成员函数里写非 mutable 成员是编译错误）。

### 3.3 const 引用参数：输入参数的默认选择（F.16）

函数参数的 const 正确性由 **F.16** 定调：**"in" 参数——廉价拷贝类型按值传，其他按 `const&` 传**。大对象（`std::string` / `std::vector` / 自定义结构）按值传每次调用复制一次，`const&` 传零拷贝（`ex03` [1][2] 用 copy-ctor 计数实测：按值 1 次拷贝、`const&` 0 次）：

```cpp
// examples/ex03-const-reference-params.cpp —— const 引用参数（节选，与原文件逐字一致）
std::size_t sum_by_value(Payload p) {
    ...
}
...
std::size_t sum_by_const_ref(const Payload& p) {
    ...
}
...
    const std::string& r = std::string("motor") + "-v1";  // 临时对象生命周期延长（详见 ph12）
```

**三个要点**：

1. **`const&` 的只读承诺由编译器执行**——函数体内写 `p.data[0] = 0` 直接编译失败，接口即契约（`ex03` [4]）；
2. **`const&` 可绑定右值临时对象**——`f(std::string("a") + "b")` 无需先造具名变量（`ex03` [3]；临时对象生命周期延长的完整规则属 ph12）；
3. **sink 情形（函数要拥有数据）例外**：按值接收 + 调用方 `std::move`，一次移动零拷贝（`sol-02` 实测）——"要拿走"不是"只读"，不该用 `const&`。

> 本阶段只讲"输入参数怎么传"这一条线，**引用如何延长临时对象生命周期、`const&` 悬挂的完整规则属于 ph12 对象生命周期阶段**，这里只需理解 `const&` 传参是只读接口的默认写法。

### 3.4 mutable：物理可变、逻辑不变的合法出口

`mutable` 是 const 成员函数里唯一能修改的成员——它表达"**这个成员不属于对象的逻辑状态**"。正当场景恰好三类（完整演示见 `ex04`/`ex05`）：

| 场景 | 例子 | 为什么 mutable 正当 |
|------|------|-------------------|
| 缓存 | 懒计算缓存 `last_result_`（`ex04` [1]） | 缓存只影响性能，不影响"查询结果"这个逻辑语义 |
| 互斥锁 | `mutable std::mutex mu_`（`ex05` [3]） | 锁是线程安全的实现细节，不是被保护数据的逻辑状态 |
| 统计/计数 | 查询计数 `lookups_`（project/test） | 统计是观察行为，不是对象语义 |

**谨慎使用的判据**：改了这个成员，**调用方能观察到的"对象是什么"变了吗？** 变了 → 不是 mutable（设计错误）；没变（只是内部加速/同步/记录）→ 可以 mutable。反例：用 mutable 藏"对象状态被悄悄修改"（见 3.5 的 const_cast 气味——那是 mutable 的滥用面）。

```cpp
// examples/ex04-mutable-and-const-cast.cpp —— mutable 缓存（节选，与原文件逐字一致）
    bool is_prime(int n) const {
        if (last_n_ == n) {                       // 命中缓存：不再重算
            return last_result_;
        }
        ...
        last_n_ = n;                              // const 成员函数中允许改 mutable 成员
        last_result_ = compute_prime(n);
        return last_result_;
    }
```

实测（`ex04` [1]）：`is_prime(17)` 首次计算，再次查询命中缓存，新输入 18 重新计算——**逻辑结果稳定、物理位在变**。

### 3.5 逻辑 const 与物理 const：位不变 ≠ 语义不变

- **物理 const（physical const）**：对象的所有位不可变——`const Point p;` 后 `p.x` 不可写（`ex05` [1]）。这是编译器的字面保证。
- **逻辑 const（logical const）**：对象的**语义**不因 const 操作而变——`const` 成员函数承诺"调用方观察到的对象状态不变"，哪怕实现上改了 mutable 缓存位（`ex05` [2]）或加了锁（`ex05` [3]）。

两者冲突的经典场景正是 **const_cast**（ES.50：不要 cast away const）：

```cpp
// examples/ex04-mutable-and-const-cast.cpp —— const_cast 正反例对照（节选，与原文件逐字一致）
void sneaky(const int& v) {
    const_cast<int&>(v) = 999;       // 气味：const 承诺被静默撕毁
}
...
void update(int& v) {
    v = 300;
}
```

实测（`ex04` [2][3]）：`sneaky(x)` 之后 x 变成 999——调用方看到 `const&` 以为只读，实际被改，**接口承诺被静默撕毁**；同样的意图用 `update(int&)` 表达，零 cast、签名诚实。这就是"**const_cast 通常是设计气味**"（roadmap 必会概念）的实证：**需要修改就应该让签名说清楚，而不是借 const 撒谎再用 cast 圆谎**。

const_cast 真正"改真正 const 对象"时是**未定义行为**（ES.50 反例，`ex04` 危险路径实测）：O0 下写入只读段 → `Bus error: 10`（SIGBUS，退出码 138）；O2 下编译器常量折叠，写入不生效打印 42——两种表现都是 UB，编译器有权假设 const 不变量。合法（对象本身非 const）但仍是气味（破坏接口承诺）；唯一的正当边界是适配老式 C API 的极窄互操作场景，且必须注释说明。

> ⚠️ const_cast 修改"真正 const"对象是未定义行为（ph15 未定义行为 UB 与内存安全阶段会系统归类）。本阶段只需记住：**先问 mutable 能不能解决，再问签名是不是该改，const_cast 是最后手段且要注释**。

### 3.6 只读视图：观察不拥有的接口元素

只读视图（`std::string_view` / `std::span`）是"只读"在接口层的终极形态：**视图不拥有数据，只是 {指针, 长度}（或 {指针, 元素个数}）两个词**，零拷贝地观察别人的内存（完整演示见 `ex06`，用法基础属 ph04 STL 阶段）：

1. **一个只读接口零拷贝接受多种形态**：`count_vowels(std::string_view)` 同时接受 `std::string`、C 字面量、`string_view`（`ex06` [1]）——不用重载三遍；
2. **视图是"观察"，底层变视图跟着变**：`view = text` 后改 `text[0]`，view 看到变化（`ex06` [2]）——视图不拥有、不冻结；
3. **`span<const T>` 表示只读，`span<T>` 表示可写**：接口用哪个 span 就是什么承诺（`ex06` [3][4]）——只读接口写 `span<const double>`，需要修改才暴露 `span<double>`；
4. **视图的生命周期必须短于数据源**：`string_view` / `span` 悬挂是借用式接口的延伸（ph12 讲过的借用心智），悬挂后解引用属 UB（ph15 未定义行为 UB 与内存安全阶段）。

```cpp
// examples/ex06-readonly-view.cpp —— 只读视图（节选，与原文件逐字一致）
std::size_t count_vowels(std::string_view text) {
    ...
}
...
double average(std::span<const double> values) {
    ...
}
```

**接口设计口诀**：只读 → `string_view` / `span<const T>` / `const&` / 按值小对象；读写 → `T&` / `span<T>`；拥有 → 按值 / `unique_ptr`。**视图进接口 = 承诺"我只观察、不拥有、不改动"**——这正是 ph13 讲过的"所有权通过类型体现"在只读一侧的镜像。

## 4. 底层原理

### 4.1 编译器视角：const 是编译期概念，不是运行期标签

`const` 不改变对象的存储布局（`sizeof(const int)` 与 `sizeof(int)` 相同），它改变的是**编译器的假设**：

```text
const 对象声明
    │
    ├── 编译器建立"该对象不可变"的不变量
    │      ├── 允许常量折叠：读取 const 变量可直接用已知值（O2 下连内存都不读）
    │      └── 静态存储期 const（如 static const int）可能放只读段
    │           （macOS 上 const_cast 写入 → Bus error，实测退出码 138）
    ├── 任何"可能修改它"的路径被拒绝：非 const 引用/指针绑定、非 const 成员调用
    └── const_cast 是唯一逃逸口 —— 逃逸后：
           ├── 对象本身非 const → 合法但破坏接口承诺（设计气味）
           └── 对象本身 const → 未定义行为（编译器假设作废，表现不可预测）
```

这就是为什么 `const_cast` 修改真正 const 对象时"有时崩、有时悄悄不生效"——不是平台玄学，是**编译器有权按 const 不变量优化**（`ex04` 危险路径实测：O0 崩溃 / O2 打印 42）。

### 4.2 const 成员函数的本质：this 指针 const 化

`void f() const` 不是语法糖，而是**隐式 this 参数的类型变化**：

```text
void Sensor::calibrate(double offset)      →  this 是 Sensor*          （可改 *this）
double Sensor::reading() const             →  this 是 const Sensor*    （*this 只读）
                                             const 成员函数体内写非 mutable 成员 = 编译错误
```

```text
const 成员函数调用链
    const Sensor& s ──▶ s.reading()   （this: const Sensor* ──▶ 只读路径）
    Sensor& s        ──▶ s.reading()  （this: Sensor*      ──▶ 同样可调 const 成员）
                          s.calibrate()（需要 this: Sensor*，const 对象被编译期拒绝）
```

**const 是成员函数签名的一部分**（与参数/返回类型同级）：`decltype(&Sensor::reading)` 是 `double (Sensor::*)() const`，成员指针类型把 const 编码进去（`sol-01` 用它做编译期断言）——重载决议靠它区分 const/非 const 版本（3.2）。

### 4.3 顶层 const 与函数类型：为什么重载决议忽略它

函数类型只编码"参数类型与返回类型"，**参数的顶层 const 被剥掉**（`void f(const int)` 与 `void f(int)` 类型相同，`ex01` [6] 的 `static_assert` 实证）——原因：按值传参本来就是拷贝，调用方传的变量是否 const 不影响函数内部的行为契约，保留它只会制造"同名同参却重载失败"的困惑。**底层 const（`const int*` / `const int&`）则不同：它编码在参数类型里，参与重载决议**——`f(const int*)` 与 `f(int*)` 是两个不同的函数。这正是"顶层 const 是'值'的属性、底层 const 是'接口'的属性"的类型系统表达。

### 4.4 string_view / span 的布局：零开销视图的实现

```text
std::string_view          std::span<const double>
┌───────────┬────────┐   ┌───────────┬────────┐
│ 指针 data_ │ 长度 n  │   │ 指针 data_ │ 元素数 n│
└───────────┴────────┘   └───────────┴────────┘
   两词（16B on 64-bit）    两词（16B on 64-bit）
   不拥有：析构什么都不做     不拥有：析构什么都不做
```

视图只是"借来的眼睛"——构造零拷贝、传递零拷贝、析构零开销；代价是**生命周期必须短于数据源**（4.6 的警告）。`span<const T>` vs `span<T>` 的唯一区别是指针的底层 const：前者只能读，后者可写——**同一个类型，const 层级决定接口承诺**（3.6）。

## 5. 使用场景

**真实工程中的用途**：

- **存储引擎 / 数据库内核**：只读路径是接口设计的主干——SSTable 是不可变文件，读接口天然 `const`；RocksDB/LevelDB 的 `Get()`、`Iterator::Key()/Value()` 返回 Slice/string_view 这类只读视图（RocksDB/LevelDB 用自家 Slice，与 string_view 同思路，早于 C++17），把"读不写"变成类型强制；Buffer Pool 的 `const` 查询接口与 `mutable` 的锁/统计是"逻辑 const + 物理 mutable"的标准组合（承接 ph13 与 ph22 存储引擎阶段，目录待建）
- **配置与快照**：只读配置对象（本阶段 project 落地）——接口全 const、无修改方法、"改配置"只能构造新对象，拷贝即只读快照；设备状态快照模型同理：快照 = 不可变对象，天然可安全共享（roadmap 推荐项目②，project 扩展方向）
- **并发读**：`const` 成员函数 + `mutable std::mutex` 是线程安全读的标准骨架（`ex05` [3]）——"接口承诺不修改"与"实现要加锁"用 mutable 调和（承接 ph08 并发编程阶段的 RAII 锁）
- **跨库边界**：`const char*` / `string_view` 进出 C 库与日志/序列化层，零拷贝 + 只读承诺（C 库的 const 语义与 C++ 不同，属 ph11 可移植性阶段 / ph20 互操作阶段，目录待建）

**什么时候不用它**：

- 需要修改时不要硬标 const——用非 const 引用/`span<T>`/可变句柄，签名诚实比"看起来只读"重要（3.5 的正例对照）
- 需要拥有数据时不要用视图——`string_view`/`span` 只观察，拥有用 `std::string`/`std::vector`（ph04）；视图不能当"延迟拷贝"用（生命周期陷阱）
- 编译期常量用 `constexpr`（ph05/ph06），运行期才定、构造后不变用 `const` 成员——两者分工不同（本阶段只讲 const 成员，不展开 constexpr）

**与其他语言的对比**（为 analysis/ 与 Tenet 合成积累素材）：

| 维度 | C++ | Rust | Go | Java | Python |
|------|-----|------|-----|------|--------|
| 不可变声明 | `const` 成员/引用/指针层级 | `&T` / `let` 不可变绑定 | 无内建（惯例 + 冻结接口） | `final`（引用不可换、对象可变） | 惯例（下划线/冻结对象） |
| 只读视图 | `string_view` / `span`（零拷贝） | `&str` / `&[T]`（借用，编译期强制） | `[]byte` 切片可变、`string` 不可变 | 无内建（Collections.unmodifiable 包装） | `bytes` 不可变、memoryview 只读 |
| 编译期强制 | 编译器执行（`const` 成员/参数） | 借用检查器强制（最强） | 无（靠约定/文档） | 部分（final 引用） | 无（鸭子类型） |
| 改 const 的代价 | const_cast（UB 或气味） | 编译器拒绝（unsafe 才可） | 无此概念 | 反射可绕 | 无此概念 |

一句话：**C++ 的 const 是"编译器执行 + 开发者自律"的接口契约**——编译器强制"改不了"（const 成员/参数/引用），但逃逸口（const_cast）存在且滥用是设计气味；Rust 把同一思想做成借用检查器强制（`&T` 改不了就是改不了）；Go/Java/Python 把"只读"留给惯例与文档。C++ 的"编译器执行 + 逃逸口存在"意味着 const 正确性要靠**接口设计纪律**保证——这正是本阶段训练的能力。

## 6. 代码示例

> 说明：示例均在本机（macOS arm64，Apple clang 21.0.0 + Homebrew clang 21.1.8）实际编译运行验证（已验证），编译命令一律 `-std=c++20 -Wall -Wextra`，双编译器零警告、输出一致。**ex04 的 `-DPH14_CONST_UB` 是故意出错路径**：修改真正 const 对象是未定义行为，必须单独编译运行，实测 O0 下 Bus error: 10（SIGBUS，退出码 138）、O2 下常量折叠打印 42。完整可运行文件在 [`examples/`](./examples/)，此处展示关键片段。

### 示例 1：顶层 const 与底层 const（examples/ex01-top-level-low-level-const.cpp）

```cpp
// examples/ex01-top-level-low-level-const.cpp —— 顶层/底层 const（节选，与原文件逐字一致）
    const int* p = &value;      // 底层 const：*p 只读；但 value 本身非 const
    ...
    value = 8;                  // 对象本身非 const，别处照改
    ...
    int a = 1;
    int* const q = &a;          // 顶层 const：q 本身不可改指向
    *q = 10;                    // 但 *q 可改（指向的对象非 const）
```

```bash
c++ -std=c++20 -Wall -Wextra ex01-top-level-low-level-const.cpp -o /tmp/ph14-ex01 && /tmp/ph14-ex01
```

实测要点：`auto copied = cx` 推导为 `int`（顶层脱落）、`auto cp2 = cp` 推导为 `const int*`（底层保留）；`int* → const int*` 特征为 1、反向为 0；`void(int)` 与 `void(const int)` 类型相同（顶层 const 不进函数类型）。

### 示例 2：const 成员函数（examples/ex02-const-member-functions.cpp）

```cpp
// examples/ex02-const-member-functions.cpp —— const 成员函数（节选，与原文件逐字一致）
    const std::string& id() const { return id_; }
    std::string& id() { return id_; }
    ...
    const char* access() const { return "const access()"; }
    const char* access() { return "non-const access()"; }
```

```bash
c++ -std=c++20 -Wall -Wextra ex02-const-member-functions.cpp -o /tmp/ph14-ex02 && /tmp/ph14-ex02
```

实测要点：const 对象 `cs.access()` 走 const 重载、非 const 对象 `s.access()` 走非 const 重载；`decltype` 断言 `cs.id()` 为 `const std::string&`、`s.id()` 为 `std::string&`；`std::as_const(s).access()` 强制 const 路径。

### 示例 3：const 引用参数（examples/ex03-const-reference-params.cpp）

```cpp
// examples/ex03-const-reference-params.cpp —— const 引用参数（节选，与原文件逐字一致）
std::size_t sum_by_value(Payload p) {
    ...
}
...
std::size_t sum_by_const_ref(const Payload& p) {
    ...
}
...
    const std::string& r = std::string("motor") + "-v1";  // 临时对象生命周期延长（详见 ph12）
```

```bash
c++ -std=c++20 -Wall -Wextra ex03-const-reference-params.cpp -o /tmp/ph14-ex03 && /tmp/ph14-ex03
```

实测要点：按值传参打印 `copy-ctor`、`const&` 无拷贝；`const&` 绑定 `std::string("motor") + "-v1"` 临时对象成功（生命周期延长属 ph12）；函数体内修改 `const&` 实参是编译错误（接口即契约）。

### 示例 4：mutable 与 const_cast（examples/ex04-mutable-and-const-cast.cpp）

```cpp
// examples/ex04-mutable-and-const-cast.cpp —— mutable 缓存 + const_cast 正反例（节选，与原文件逐字一致）
    bool is_prime(int n) const {
        if (last_n_ == n) {                       // 命中缓存：不再重算
            return last_result_;
        }
        ...
        last_n_ = n;                              // const 成员函数中允许改 mutable 成员
        last_result_ = compute_prime(n);
        return last_result_;
    }
...
void sneaky(const int& v) {
    const_cast<int&>(v) = 999;       // 气味：const 承诺被静默撕毁
}
...
void update(int& v) {
    v = 300;
}
```

```bash
c++ -std=c++20 -Wall -Wextra ex04-mutable-and-const-cast.cpp -o /tmp/ph14-ex04 && /tmp/ph14-ex04
# 危险路径（故意出错，UB，勿裸跑）：
c++ -std=c++20 -Wall -Wextra -DPH14_CONST_UB ex04-mutable-and-const-cast.cpp -o /tmp/ph14-ex04-ub
/tmp/ph14-ex04-ub
```

实测要点：mutable 缓存"首次计算/命中缓存/新输入重算"交替（逻辑 const 成立）；`sneaky(x)` 后 x=999（const 承诺被破坏）；`update(y)` 后 y=300（诚实接口零 cast）；危险路径 O0 下 `Bus error: 10`（SIGBUS，退出码 138）、O2 下常量折叠打印 42——修改真正 const 对象是 UB（ES.50）。

### 示例 5：逻辑 const 与物理 const（examples/ex05-logical-vs-physical-const.cpp）

```cpp
// examples/ex05-logical-vs-physical-const.cpp —— 逻辑/物理 const（节选，与原文件逐字一致）
    std::size_t size() const {
        if (!computed_) {
            ...
            size_ = data_.size();
            computed_ = true;
        }
        ...
        return size_;
    }
...
    double average() const {
        std::scoped_lock lk(mu_);       // const 成员函数内加锁：锁是物理状态，须 mutable
        return count_ == 0 ? 0.0 : static_cast<double>(sum_) / count_;
    }
```

```bash
c++ -std=c++20 -Wall -Wextra ex05-logical-vs-physical-const.cpp -o /tmp/ph14-ex05 && /tmp/ph14-ex05
```

实测要点：懒缓存第一次算（物理位被写）、第二次命中（逻辑结果稳定）；`const` 成员函数内 `scoped_lock` 保护共享位（mutable 互斥锁）；`const int*` 只约束当前路径——别处改对象后只读路径看到新值（路径只读，对象非冻结）。

### 示例 6：只读视图设计（examples/ex06-readonly-view.cpp）

```cpp
// examples/ex06-readonly-view.cpp —— 只读视图（节选，与原文件逐字一致）
std::size_t count_vowels(std::string_view text) {
    ...
}
...
double average(std::span<const double> values) {
    ...
}
...
    std::string_view view = text;   // 视图借用 text 的字符
    text[0] = 'X';                  // 改的是 text（唯一拥有者）
```

```bash
c++ -std=c++20 -Wall -Wextra ex06-readonly-view.cpp -o /tmp/ph14-ex06 && /tmp/ph14-ex06
```

实测要点：`string_view` 一个接口零拷贝接受 `std::string` / C 字面量 / `string_view` 三种形态；视图是"观察"（底层变视图变）；`span<const double>` 覆盖 vector / C 数组 / 裸指针+长度；`span<const T>` 只读、`span<T>` 可写（接口即承诺）。

## 7. 总结

### 关键要点

1. **顶层 const 管对象本身，底层 const 管指向的对象**：拷贝/推导时顶层脱落、底层保留；`int* → const int*` 单向安全转换（权限收窄）；函数参数顶层 const 不进函数类型（`ex01`）
2. **不修改对象状态的成员函数应标 const（Con.2）**：const 对象只能调 const 成员；const/非 const 重载是不同函数；返回引用时 const 版本返回 `const&`（`ex02`）
3. **输入大对象优先用 const 引用（F.16）**：按值传大对象每次拷贝（实测 1 次），`const&` 零拷贝且只读承诺由编译器执行；sink 情形（要拥有数据）按值 + move（`ex03`/`sol-02`）
4. **mutable 是"物理可变、逻辑不变"的合法出口**：正当场景只有缓存、互斥锁、统计计数三类；判据是"改了这个成员，调用方能观察到的对象语义变了吗"（`ex04`/`ex05`）
5. **逻辑 const ≠ 物理 const**：位不变是字面保证，语义不变是接口承诺；`const int*` 只约束当前路径，不冻结对象本身（`ex05` [4]）
6. **const_cast 通常是设计气味**（正反例实测对照）：需要修改就让签名说清楚（非 const 引用），而不是借 const 撒谎再 cast 圆谎；修改真正 const 对象是 UB（O0 实测 SIGBUS 退出码 138、O2 常量折叠打印 42）
7. **只读视图 = 观察不拥有**：`string_view`/`span<const T>` 是 {指针, 长度/元素数} 两词，零拷贝；`span<const T>` 只读、`span<T>` 可写——接口用哪个 span 就是什么承诺（`ex06`）
8. **视图生命周期必须短于数据源**：悬挂解引用是 UB（承接 ph12 借用心智，系统归类属 ph15 未定义行为 UB 与内存安全阶段）
9. **const 是编译期概念**：编译器按 const 不变量做常量折叠与只读段放置；const_cast 逃逸后编译器假设作废（4.1）
10. **const 正确性三问**（设计接口时自检）：参数是只读吗 → `const&`/视图/按值小对象；成员函数改状态吗 → 标 const / 不标；要返回句柄吗 → `const&`（只读）/ `&`（可变）

### 阶段验收清单

- [ ] 能**解释顶层 const 和底层 const**：说出 `const int` / `const int*` / `int* const` / `const int* const` 各自的顶层/底层归属与可写性，解释拷贝时顶层脱落、底层保留（3.1、`ex01`）
- [ ] 能**设计 const 正确的类接口**：只读查询标 const、返回引用时 const 版本返回 `const&`、const/非 const 重载与可变句柄的取舍（3.2、练习 1）
- [ ] 能**减少不必要拷贝**：大对象输入用 `const&`（F.16），用拷贝计数实测按值 vs 引用的差异；sink 情形按值 + move（3.3、练习 2）
- [ ] 能**谨慎使用 mutable**：判断缓存/互斥锁/计数三类正当场景，解释"物理可变、逻辑不变"；知道 mutable 是特例不是默认（3.4、练习 4）
- [ ] 能**区分逻辑 const 与物理 const**：位不变 ≠ 语义不变；`const` 指针只约束路径（3.5、`ex05`）
- [ ] 能**识别 const_cast 气味**并给出正例重构：需要修改就明说（非 const 引用）；知道修改真正 const 对象是 UB（3.5、练习 5）
- [ ] 能**设计只读视图接口**：`string_view` / `span<const T>` 作参数，零拷贝接受多种形态，视图生命周期短于数据源（3.6、练习 3）

### 跨语言对比：不可变性与只读视图

| 维度 | C++ | Rust | Go | Java | Python |
|------|-----|------|-----|------|--------|
| 不可变声明 | `const` 成员/引用/指针层级 | `&T` / 不可变绑定 | 惯例（无内建） | `final`（引用不可换） | 惯例 |
| 只读视图 | `string_view` / `span` | `&str` / `&[T]`（借用强制） | `string` 不可变 / 切片可变 | unmodifiable 包装 | memoryview 只读 |
| 编译期强制 | 编译器执行 + const_cast 逃逸口 | 借用检查器强制（无逃逸） | 无 | 部分 | 无 |
| 违反的代价 | UB 或设计气味 | 编译期拒绝 | 无此概念 | 反射可绕 | 无此概念 |

一句话：**C++ 用"编译器执行 + 开发者自律"换 const 正确性的可迁移性**——规则学会了，Rust 的借用、Go 的惯例、Java 的 final 都能一眼看懂；本阶段训练的"接口即承诺"心智直接服务于 ph22 存储引擎阶段（目录待建）的只读路径设计（SSTable 不可变文件、Iterator 只读视图、配置快照）。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 5 题：给旧类补 const 成员函数（★）、用 const 引用优化函数参数（★★）、设计只读配置接口（★★★）、mutable 与逻辑 const 判断（★★）、const_cast 气味识别与只读视图（★★★）——练习 1/2/3 与 roadmap ph14「练习」小节的三个承诺（给旧类补 const 成员函数 / 用 const 引用优化函数参数 / 设计只读配置接口）一一对应，练习 4/5 覆盖「学习内容」与「必会概念」中的 mutable 谨慎使用、逻辑 const 与物理 const、只读视图设计与 const_cast 气味。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**配置读取只读接口**——header-only 的 `Config`（接口全 const、`get` 返回 `std::optional<std::string_view>`、mutable 查询统计、无 public 修改方法）+ 演示 CLI（查询/缺失/统计三命令）+ 自测（编译期 6 组静态断言：全部查询接口是 const 成员函数 + Rule of 0；运行期 16 组断言（7 个测试段落），含 **mutable 统计实测**与 **string_view 视图稳定性**；普通版 + ASan 版）+ Makefile，是 roadmap 推荐项目①「配置读取只读接口」的落地（推荐项目②「设备状态快照模型」以"拷贝即只读快照"为最小形态，见 project/README.md 扩展方向）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[未定义行为 UB 与内存安全阶段](../ph15-ub-memory-safety/15-ub-memory-safety.md) — ph15 目录已建，其下一阶段 ph16（测试、静态分析与代码规范阶段）也已落地（ph17（设计模式与架构能力阶段）已落地，roadmap 第 18~23 节仍在规划中、目录待建）。本阶段把"const 正确性"讲成接口设计语言（const 承诺 + 只读视图 + 逻辑/物理 const）；ph15 系统梳理 const 承诺被破坏的后果——`const_cast` 修改真正 const 对象的 UB（ph14 已实测 O0 Bus error / O2 常量折叠，ph15 归入"编译器假设无 UB"的总框架）、视图/引用悬挂后的解引用、use-after-move、数据竞争等全部 UB 分类，并用 ASan/UBSan/TSan 实测。届时本阶段的"视图生命周期必须短于数据源""const 不变量是编译器的优化前提"直接成为 ph15 判断"这行代码是否 UB"的依据。
