# C++ 对象生命周期、值类别与所有权深入阶段

> 面向高性能系统、存储引擎方向，本阶段把"对象何时创建、何时移动、何时销毁"与"表达式值类别"讲透：能分辨 lvalue / prvalue / xvalue，能预测临时对象何时析构、知道 const 引用延长生命周期的边界，能用编译器实测 RVO/NRVO 的生效条件，能设计"所有权通过类型体现、借用清晰、不悬空"的接口。

## 1. 概述

本阶段定位：**理解对象生命周期（何时创建、移动、销毁）与表达式值类别（prvalue / xvalue / lvalue），能用规则预测临时对象析构时机，能实测并解释 RVO/NRVO 的生效条件，能设计"所有权通过类型体现、借用式接口不悬空、值语义优先"的接口**。它是整个路线的第 12 步：ph01~ph03 已经能用类、会写五函数、懂左值右值入门；ph04/ph06 见过 `string_view`/`span`/`unique_ptr` 的用法；本阶段把这些"用法"背后的规则讲透——**值类别是表达式的属性，生命周期规则是标准的承诺，所有权通过类型表达**。学完本阶段，面对"这个引用什么时候悬空""按值返回到底拷贝几次""move 之后对象还能不能用"这类问题，能直接给出确定答案，而不是靠试错。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 值类别体系 | prvalue / xvalue / lvalue 主类别 + glvalue / rvalue 复合类别、`decltype((expr))` 判别、绑定规则 |
| 临时对象生命周期 | 完整表达式边界、临时物化、`const&` / `&&` 延长规则与边界 |
| 返回值优化 | RVO（保证省略）、NRVO、`return std::move` 反模式、`-O0/-O2/-O3` 与 `-fno-elide-constructors` 实测 |
| 所有权转移 | 移动承载所有权、`unique_ptr` 转移、sink 按值接收/产出、转移后状态约束 |
| 借用式接口 | `const&` / `string_view` / `span` / 裸指针（非拥有），所有权通过类型体现 |
| 构造与销毁顺序 | 作用域局部、派生类（基类→成员声明序→构造体）、函数局部静态、命名空间静态 |
| 接口设计 | 不返回局部对象引用（F.43）、const 引用延长边界有限、值语义优先 |

这个阶段只涉及对象生命周期与值类别的规则本身（何时创建/移动/销毁、表达式如何分类）、临时对象生命周期与延长规则、RVO/NRVO、所有权转移与借用式接口、构造与销毁顺序，**不涉及特殊成员函数的手写实现细节与 Rule of 0/3/5 的完整抉择（ph03 内存模型阶段已讲基础，ph13 Rule of 0/3/5 与 RAII 进阶阶段深入）、智能指针 API 全貌（shared_ptr/weak_ptr/自定义 deleter，ph06 现代 C++ 阶段）、const 正确性系统化（ph14 const 正确性与接口设计阶段）、UB 系统化梳理（use-after-move、悬空引用全分类、数据竞争，ph15 未定义行为 UB 与内存安全阶段）、动态库/插件边界的生命周期约定（[ph19 ABI、动态库与插件机制阶段](../ph19-abi-dynamic-libs-plugins/19-abi-dynamic-libs-plugins.md)）和协程/多线程下的对象生命周期（ph08 并发编程阶段）** — 那些是后续阶段的内容。承接 ph11 标准与可移植性阶段：本阶段大量结论依赖"标准承诺"（如 C++17 保证省略）与"编译器实测"（如 NRVO 是否生效），ph11 的 `-std=` 意识与多编译器对照方法直接复用——说到"C++17 起保证"就用 `-std=c++17/20` 编译验证，说到"编译器行为"就双编译器实测。

## 2. 来源与演变

值类别与生命周期规则是 C++ 最"理论"的部分，但它的每一次变化都对应真实工程痛点。1998 年的 C++98 只有 **lvalue / rvalue 简单二分**：lvalue 有名字可寻址，rvalue 是临时值——没有移动语义，按值返回只能拷贝，`std::vector` 扩容就是把元素逐个拷一遍。2011 年的 C++11 为了解决"拷贝太贵"，引入右值引用与移动语义，值类别随之从二分扩展为**五类完整分类**（新增 xvalue 亡值、glvalue/rvalue 复合类别）——**设计哲学一句话：值类别是 C++ 用类型系统表达"这个表达式能不能被移动、能不能被取地址"的机制**。2017 年的 C++17 把"纯右值返回的拷贝省略"从"常见优化"升级为**标准承诺**（保证拷贝省略），顺带正式定义了"临时物化"（temporary materialization）——此前"临时对象到底何时真正存在"依赖实现，此后成为标准语义。C++20/23 在值类别与生命周期上没有结构性变化，维持 C++17 的语义。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| C++98 | 1998 | lvalue/rvalue 二分；无移动语义；按值返回只能拷贝，拷贝省略是纯优化 |
| C++11 | 2011 | 右值引用、移动语义、`std::move`；引入 xvalue/glvalue 完整分类；"允许但不保证"的拷贝省略 |
| C++17 | 2017 | **保证拷贝省略**：prvalue 场景的省略写进标准；"临时物化"概念正式化（P0135R1） |
| C++20/23 | 2020/2023 | 维持 C++17 的值类别与生命周期语义，无结构性变化 |

本文示例以 **C++20** 为基线（与 ph11 一致：roadmap 主线使用 C++20，`-std=c++20` 是稳定度与功能的平衡点；RVO 的 C++14 对照实验单独标注），验证工具链为 **Apple clang 21.0.0（`c++`）+ Homebrew clang 21.1.8（`clang++`）**，全部示例已在本环境实际编译运行验证（已验证）；GCC/MSVC 本机没有对应编译器，涉及这两家的行为如实标注「未在本环境验证」。值类别分类（C++11 定型）与保证省略（C++17 定型）是 C++ 标准里**最稳定**的部分——十余年没有实质变化，学会了长期复用。

## 3. 语法与参数

### 3.1 值类别体系：prvalue / xvalue / lvalue

**必会概念：值类别是表达式的属性，不是对象的属性**——同一个对象出现在不同表达式里，类别可能不同。C++11 起有五类，其中三个是主类别：

| 主类别 | 含义 | 典型表达式 | 可绑定到 |
|--------|------|-----------|---------|
| lvalue（左值） | 有身份、可取地址 | 变量名、`*p`、`arr[0]`、`++x`、返回引用的函数调用 | `T&`、`const T&` |
| prvalue（纯右值） | 无身份、纯"值"，通常是临时对象或字面量 | `42`、`x++`、`x == 42`、`std::string("t")`、返回非引用的函数调用 | `T&&`、`const T&` |
| xvalue（亡值） | 有身份、但即将被移动——"即将消亡的值" | `std::move(x)`、`static_cast<T&&>(x)` | `T&&`、`const T&` |

复合类别：**glvalue = lvalue ∪ xvalue**（有身份的表达式，对应"可以取地址"），**rvalue = prvalue ∪ xvalue**（可移动的表达式，对应"可以被移动"）。分类可用两个正交问题描述：**有没有身份（能不能取地址）？能不能被移动？**

| 表达式 | 有身份？ | 可移动？ | 类别 |
|--------|---------|---------|------|
| `s`（变量名） | 是 | 否 | lvalue |
| `std::move(s)` | 是 | 是 | xvalue |
| `s + "!"`（临时结果） | 否 | 是 | prvalue |

**`decltype((expr))` 判别法**：在未求值上下文里，`decltype((expr))` 直接给出表达式的类别编码——lvalue → `T&`，xvalue → `T&&`，prvalue → `T`（无引用）。用这个技巧可以在编译期"问"任意表达式属于哪一类（完整可运行版见 `examples/ex01-value-categories.cpp`，实测输出）：

```cpp
// examples/ex01-value-categories.cpp —— 值类别判别（节选）
// 验证环境：Apple clang 21.0.0 与 Homebrew clang 21.1.8，C++20；已验证
template <typename T>
const char* describe() {
    if constexpr (std::is_lvalue_reference_v<T>) {
        return "lvalue";
    } else if constexpr (std::is_rvalue_reference_v<T>) {
        return "xvalue";
    } else {
        return "prvalue";
    }
}
#define SHOW_CATEGORY(expr) \
    std::printf("%-34s -> %s\n", #expr, describe<decltype((expr))>())
```

```text
# 本机实测（节选）：
s                                  -> lvalue
42                                 -> prvalue
std::move(s)                       -> xvalue
rref                               -> lvalue
"literal"                          -> lvalue
&x                                 -> prvalue
```

要点与两个"坑"：

- **坑 1：有名字的右值引用是 lvalue**——`std::string&& rref = std::move(s);` 之后，表达式 `rref` 本身是 lvalue（它有名字、可被取地址、可再被赋值）；只有 `std::move(rref)` 才把它变回 xvalue。这就是为什么"移动一次之后还要再 `std::move` 一次"的场景真实存在
- **坑 2：字符串字面量是 lvalue**——`"literal"` 的类型是 `const char[N]` 数组，数组在内存里有固定地址，所以是 lvalue，不是 prvalue；`"literal"` 不能直接绑定 `std::string&&`
- **绑定规则三条**：`T&` 只绑 lvalue；`T&&` 只绑 rvalue（prvalue/xvalue 都行）；`const T&` 三者通吃——这就是"临时对象可以传给 `const&` 参数但不能传给 `T&` 参数"的语法依据
- **坑 3：值类别不等于"对象在栈上还是堆上"**——栈上对象可以是 lvalue（变量名），堆上对象的解引用 `*p` 也是 lvalue；prvalue 通常是临时对象，但"临时对象"是生命周期概念，"prvalue"是表达式概念，两者相关但不相同

> 本阶段只把值类别当作"可判别、可解释"的语法事实使用，**模板参数推导、引用折叠、完美转发的完整规则属于 ph05 模板与泛型编程阶段**，这里只需理解"表达式分三类、绑定规则三条、`std::move` 是类别转换器"。

### 3.2 临时对象生命周期与 const 引用延长

**必会概念：临时对象的析构时机由标准规定，默认在"完整表达式"（full-expression，通常是当前语句）结束时销毁；绑定到 `const T&` 或 `T&&` 时，生命周期延长到引用离开作用域——但延长有明确边界**。完整规则（`[class.temporary]`）落到工程上就是三个可预测的场景（完整可运行版见 `examples/ex02-temp-lifetime.cpp`，实测输出）：

```cpp
// examples/ex02-temp-lifetime.cpp —— 临时对象生命周期（节选）
// 验证环境：Apple clang 21.0.0 与 Homebrew clang 21.1.8，C++20；已验证
Token make(const char* n) { return Token(n); }   // 按值返回：C++17 保证省略

// [1] 未绑定的临时对象：完整表达式结束时析构
make("expr-temp");                    // ctor → dtor（夹住本语句）

// [2] const& 绑定：延长到引用离开作用域
{ const Token& r = make("extended");  // 延长规则生效
  std::printf("  using r: %s\n", r.name.c_str());
}                                     // 作用域结束，临时对象才析构

// [4] 函数参数：临时对象活到调用语句结束
observe(make("arg-temp"));            // ctor → observe → dtor（调用后立即析构）
```

```text
# 本机实测（节选，完整输出见 examples/README.md）：
[1] 完整表达式边界：      before / ctor expr-temp / dtor expr-temp / after
[2] const& 绑定：         ctor extended / using r: extended / dtor extended / [2] scope end
[4] 函数参数：            ctor arg-temp / observe arg-temp / dtor arg-temp / [4] after call
```

边界（**延长不适用**的情形）：

- **函数返回引用**：`const Token& f() { return Token("x"); }`——临时对象在 return 语句的完整表达式结束时销毁，引用跨出函数即悬空（F.43，见 3.3 与 `examples/ex05-dangling.cpp`）
- **函数参数**：`observe(make("arg-temp"))`——作为参数传入的临时对象活到调用语句结束，调用期间安全；但如果函数把参数引用"存起来"逃逸出去，就悬空了
- **容器元素与 braced-init-list 引用成员**：容器（如 `std::vector`）元素的生命周期由容器管理，扩容/析构会让引用失效——与 ph04 迭代器失效同源；另一个"不延长"场景是 **braced-init-list 初始化引用成员**：`struct S { const Token& r; };` 之后 `S s{Token("x")};`，临时对象只活到完整表达式结束、`s.r` 随即悬空（C++ 里无法在表达式中直接构造临时数组，不存在"绑定到数组元素"的合法写法）

**绑定到临时对象的子对象（成员）时，延长的是整个完整临时对象**（实测 ex02 场景 5：`const Token& r = Holder{Token("sub")}.t;` 中 `Holder` 临时对象整体存活到引用离开作用域）——但只限于"绑定"这个动作直接作用的对象图，别把它推广成"引用能保活任意数据"。

### 3.3 RVO/NRVO 与保证拷贝省略

**必会概念：C++17 起，纯右值（prvalue）返回的拷贝省略是"保证"的（guaranteed copy elision）；命名对象的 NRVO 是"允许但不保证"的优化；`return std::move(w)` 会阻止 NRVO，是反模式**。三个术语：

| 术语 | 场景 | 是否保证 |
|------|------|---------|
| RVO（Return Value Optimization） | 返回 prvalue：`return Payload{};` | **C++17 起保证**（省略写进标准） |
| NRVO（Named RVO） | 返回命名对象：`Payload p; return p;` | **允许但不保证**（编译器/优化级别说了算） |
| 反模式 | `Payload p; return std::move(p);` | 必然不省略（xvalue 无法做 NRVO），且 clang 会告警 |

实测方法：给类型装上拷贝/移动计数器，按不同 `-O` 级别与 `-fno-elide-constructors` 编译运行（完整可运行版见 `examples/ex03-rvo-nrvo.cpp`，本机实测矩阵）：

```cpp
// examples/ex03-rvo-nrvo.cpp —— RVO/NRVO 实测（节选）
// 验证环境：Apple clang 21.0.0 与 Homebrew clang 21.1.8；已验证
Payload make_prvalue() { return Payload{}; }   // RVO：C++17 保证省略
Payload make_named()   { Payload p; return p; } // NRVO：编译器决定

// 本机实测（-O0 / -O2 / -O3 结果相同，默认构建零警告）：
//   [RVO prvalue]   ctor / got id=0 / dtor                 ← 0 拷贝 0 移动
//   [NRVO named]    ctor / got id=0 / dtor                 ← 0 拷贝 0 移动（clang 21 在 -O0 也做 NRVO）
// c++ -std=c++20 -fno-elide-constructors（NRVO 被关闭，保证省略关不掉）：
//   [NRVO named]    ctor / MOVE / dtor / got id=0 / dtor   ← 出现一次移动
// c++ -std=c++20 -DPH12_ANTIPATTERN（反模式，1 条预期告警）：
//   [return std::move]  ctor / MOVE / dtor / got id=0 / dtor ← 必然一次移动
//   warning: moving a local object in a return statement prevents copy elision [-Wpessimizing-move]
```

结论（实测支持）：

- **RVO 在 `-O0` 到 `-O3` 全程零拷贝零移动**，`-fno-elide-constructors` 也关不掉——因为 C++17 把它从"优化"升级成"语义"：prvalue 根本就是"直接构造在目标位置"的表达式，没有中间对象可省略
- **NRVO 依赖编译器**：本机 clang 21 在 `-O0` 也做 NRVO（结果零移动），但标准不保证——换编译器/换版本可能就多一次移动
- **`return std::move(p)` 是反模式**：clang 直接告警 `-Wpessimizing-move`（实测文本），因为移动调用把命名对象变成 xvalue，编译器失去 NRVO 机会
- **C++14 对照**：`-std=c++14 -fno-elide-constructors` 下 RVO/NRVO 都变成"ctor / MOVE / dtor / MOVE / dtor / got id=0 / dtor"两次移动——这就是 C++17 把保证省略写进标准的原因：**"按值返回"从"依赖优化"变成"标准承诺"**

**必会概念落地：不要返回局部对象引用（F.43）**——需要"返回一个对象"时按值返回即可：prvalue + 保证省略让返回值零拷贝直达调用方；返回引用只会得到悬空引用（见 `examples/ex05-dangling.cpp` 的实测告警与 ASan 抓取）。roadmap §12 的示例就是最小示范：

```cpp
std::string MakeName() {
    return "motor";   // 按值返回 prvalue：值语义 + 保证省略，安全且零拷贝
}
```

### 3.4 构造顺序与销毁顺序

**必会概念：对象按什么顺序构造、什么顺序析构，是标准规定的，不是"实现细节"**。四类对象的规则（完整可运行版见 `examples/ex04-order.cpp`，实测输出）：

| 对象 | 构造顺序 | 销毁顺序 |
|------|---------|---------|
| 作用域局部对象 | 声明顺序 | **逆序**（后声明的先析构） |
| 派生类对象 | 基类 → 成员（**声明顺序**）→ 构造函数体 | 构造体结束 → 成员逆序 → 基类 |
| 函数局部静态对象 | **首次调用**该函数时构造（只一次） | 程序退出时，按"构造完成"逆序 |
| 命名空间作用域静态对象 | `main` 之前（按声明序） | 程序退出时，与函数局部静态统一按"构造完成"逆序 |

```cpp
// examples/ex04-order.cpp —— 构造与销毁顺序（节选）
// 验证环境：Apple clang 21.0.0 与 Homebrew clang 21.1.8，C++20；已验证
struct Derived : Base {
    MemberB b_;          // 声明顺序：b_ 在前
    MemberA a_;
    Derived() : b_{}, a_{} { std::printf("  Derived body\n"); }
};

// 本机实测：
//   Base ctor / MemberB ctor / MemberA ctor / Derived body        ← 基类→成员声明序→构造体
//   Derived body end / MemberA dtor / MemberB dtor / Base dtor    ← 严格逆序
```

要点：

- **成员按声明顺序构造，与初始化列表的书写顺序无关**——把 `a_` 写在 `b_` 前面也不会先构造 `a_`；编译器对"初始化列表顺序与声明顺序不一致"会告警 `-Wreorder-ctor`（工程上应保持列表顺序与声明一致，零告警）
- **函数局部静态只构造一次**：第一次调用该函数时构造，之后复用（实测两次调用只出现一次 ctor）；程序退出时所有静态对象统一按"构造完成"逆序析构（实测：函数局部静态构造完成最晚 → 最先析构，命名空间静态最后析构）

> ⚠️ **静态初始化顺序陷阱（static initialization order fiasco）**：跨翻译单元的命名空间静态对象，构造顺序**未定义**——`a.cpp` 的静态对象依赖 `b.cpp` 的静态对象时，程序可能崩在 main 之前。工程上避免跨翻译单元依赖静态初始化顺序，需要时改用函数局部静态（首次使用初始化）或延迟初始化

- 析构顺序规则的另一面：**析构函数体执行时，成员仍全部存活**——ex04 实测 `Derived body end` 打印先于 `MemberA dtor`/`MemberB dtor`（成员在析构函数体**之后**才按声明逆序析构），析构函数体内读取成员值正常；真正需警惕的是成员之间按逆序析构（后声明者先析构）——后析构的成员不能假设声明在它之后的成员还活着

### 3.5 所有权转移：移动承载所有权

**必会概念：所有权应通过类型体现**——`std::unique_ptr<T>` 表达"独占所有权"，它只可移动不可拷贝；所有权转移就是一次移动。函数签名是所有权契约（完整可运行版见 `examples/ex06-ownership.cpp`）：

| 接口形态 | 类型表达 | 所有权语义 |
|---------|---------|-----------|
| `void sink(std::unique_ptr<T>)` | 按值接收 unique_ptr | **转移**：调用方把所有权交给函数，函数结束时对象随函数作用域析构 |
| `std::unique_ptr<T> make()` | 按值返回 unique_ptr | **转移**：所有权从工厂流向调用方（保证省略 + 移动，零拷贝） |
| `void borrow(const T&)` | 借用 `const&` | **借用**：只读访问，不拥有、不负责释放 |
| `void show(std::string_view)` | 借用视图 | **借用**：不拥有字符串数据 |
| `void sum(std::span<const int>)` | 借用视图 | **借用**：不拥有连续内存 |
| `T*`（裸指针） | 非拥有观察者（R.3） | **借用**：裸指针不表示所有权，只做观察 |

```cpp
// examples/ex06-ownership.cpp —— 所有权转移与借用式接口（节选）
// 验证环境：Apple clang 21.0.0 与 Homebrew clang 21.1.8，C++20；已验证
std::unique_ptr<Blob> make_blob(std::string p) {
    return std::make_unique<Blob>(std::move(p));   // 所有权产出：按值返回
}
// 本机实测：
//   [1] auto b = make_blob("motor");        → b 拥有 Blob
//   [3] sink(std::move(b));                 → 所有权交给 sink，之后 b == nullptr: yes
//   [5] Blob c = a;  c.payload += "!";      → 值语义：a 不变，c 独立（深拷贝）
```

**move 之后对象的状态约束**（roadmap 验收项）：被移动后的对象是"**合法但未指定**"（valid but unspecified）状态——可以安全析构、可以重新赋值，但不能假设其内容；实测中 `std::move(b)` 后的 `unique_ptr` 是 `nullptr`（`b == nullptr: yes`），但标准只保证"合法"，不保证"为空"。**继续使用被移动对象的内容是 use-after-move**，属于 ph15 未定义行为阶段系统梳理的范围，本阶段只要求：转移后访问新持有者，不要访问旧的。

### 3.6 借用式接口与值语义设计

**必会概念：值语义通常让代码更简单**——按值传递、按值返回、拷贝即深拷贝，调用双方都不需要讨论"谁拥有、谁释放"。工程上先问"能不能用值语义"，再问"要不要借用"，最后才考虑指针/所有权转移：

```cpp
// 值语义：调用方与函数之间没有所有权问题
std::string config_path(const std::string& base) {
    return base + "/config.json";   // 按值返回 prvalue：保证省略，零拷贝，绝不悬空
}
```

| 决策 | 什么时候用 | 为什么 |
|------|-----------|--------|
| 按值返回 / 按值传参（值语义） | 对象小、需要独立副本、调用方要"拥有"结果 | 保证省略 + 移动让值语义在 C++17 之后几乎零成本；接口最简单 |
| `const&` 借用参数 | 大对象只读访问、调用方持有数据 | 0 拷贝 0 移动；不产生所有权问题（前提：不把引用存出去） |
| `string_view` / `span` 借用视图 | 只读访问字符串/连续内存 | 不拷贝不拥有；但视图寿命必须短于数据源 |
| `unique_ptr` 转移所有权 | 对象有独占生命周期、需要堆上存储 | 所有权通过类型体现，转移 = 移动，杜绝手动 new/delete |
| 裸指针 / `shared_ptr` | 非拥有观察 / 真正共享 | 裸指针只做观察（R.3）；共享所有权是最后手段（ph06） |

**什么时候不用值语义**：对象很大且只需要"看"（用 `const&`/视图借用）；对象需要身份/别名语义（多个人引用同一个实例，如共享缓存）；对象生命周期需要独立于作用域（用 `unique_ptr` 转移）。判断口诀：**"读完即弃"用借用，"拷贝无妨"用值，"独立存活"用所有权转移**。完整的值语义 + 借用组合见 `project/`（值语义配置对象：不可变 Config + `string_view` 借用 + `with()` 按值分叉）。

## 4. 底层原理

### 4.1 值类别为什么存在：身份 × 可移动

值类别不是学术装饰，它对应编译器必须回答的两个问题：**这个表达式能不能取地址？能不能被移动？**

```text
                ┌──────────────────────────────────────────┐
                │              表达式（glvalue? rvalue?）      │
                └──────┬───────────────────────┬────────────┘
                   有身份（可取地址）           无身份（纯值）
                        │                         │
                ┌───────┴────────┐          ┌─────┴─────┐
             可移动（xvalue）   不可移动     可移动（prvalue）
             std::move(s)      lvalue      42, s+"!"
                └───────┬────────┘          └─────┬─────┘
                    │  rvalue：可被移动             │
                    └──────────────┬───────────────┘
                        glvalue：可取地址（lvalue ∪ xvalue）
```

- 编译器按表达式类别决定**重载决议**（`T&` vs `T&&` 参数选哪个）、**能否取地址**（lvalue/xvalue 可以，prvalue 不行）、**能否绑定引用**（见 3.1 三条）
- `std::move` 的真实身份是 `static_cast<T&&>`：它不移动任何数据，只是把表达式的类别从 lvalue 改成 xvalue，让"移动构造函数/移动赋值"被选中——真正的工作在移动构造/移动赋值体内（ph03 已讲）
- **临时物化（temporary materialization）**：prvalue 在没有被省略的情况下，需要"物化"成临时对象才有地址可绑定引用——C++17 把"哪些 prvalue 一定会物化"变成标准语义，这是保证省略能成立的前提

### 4.2 生命周期规则的标准依据

`[class.temporary]` 的核心规则落成时间线：

```text
prvalue 诞生 ──（绑定 const T& / T&& 时）──▶ 延长：活到引用离开作用域
     │
     └──（未绑定引用时）──▶ 完整表达式结束 ──▶ 析构
                            （含函数参数：调用语句结束即析构）
     │
     └──（函数返回引用时）──▶ return 语句完整表达式结束 ──▶ 析构（引用悬空）
```

延长规则的"边界有限"正体现在这条时间线上：**延长跟着"引用"走，不跟着"函数调用"走**——引用作为返回值或作为参数"逃逸"出它的作用域时，延长就失效了。这就是为什么"把临时对象传给 `const&` 参数"安全（参数引用在调用内有效），而"函数返回临时对象的引用"悬空（返回后引用逃逸出函数）。

### 4.3 保证省略的实现机制：返回槽

按值返回为什么能零拷贝？编译器为每个按值返回的函数预留**返回槽（return slot）**——调用方对象的内存位置：

```text
调用方:  Payload p = make_prvalue();
                    │
                    ▼
          ┌─ make_prvalue 的返回槽 = p 的位置 ─┐
          │  Payload{} 直接构造在这里（RVO）      │
          │  Payload p; return p;              │
          │  → p 本身就在返回槽里（NRVO）         │
          └───────────────────────────────────┘
```

- **RVO（prvalue）**：`return Payload{}` 的 prvalue 直接构造在返回槽 → 调用方 `p` 就是那个对象，全程一个对象、零拷贝零移动；C++17 起这是语义不是优化，`-fno-elide-constructors` 关不掉（实测见 3.3）
- **NRVO（命名对象）**：编译器把命名局部对象 `p` 直接放在返回槽 → 省略拷贝/移动；但 NRVO 要求编译器能证明"返回的就是这一个对象"（单一返回点、无分支），做不到时退化为移动——这就是"允许但不保证"
- **`return std::move(p)`**：`std::move(p)` 把 `p` 变成 xvalue，强制走移动构造，编译器失去 NRVO 机会——一次移动 + 一次析构，纯损失

### 4.4 所有权 = 对象生命周期管理资源

ph03 讲过 RAII：**资源生命周期绑定对象生命周期**。本阶段的增量是把它和移动语义接起来：资源（堆内存、文件句柄、锁）的所有权随"拥有它的对象"移动而转移——`unique_ptr` 的移动构造把裸指针从源对象搬到目标对象，源对象置空；析构时只有真正拥有资源的那个对象会释放。**"所有权通过类型体现"的底层机制就是特殊成员函数（移动）按值语义逐成员搬移资源句柄**，而手写裸指针则没有这个保障——这正是 ph03 五函数体系与 ph13 Rule of 0/3/5 的实践接口。

### 4.5 构造/销毁顺序的标准依据

- **成员声明顺序**：类的数据成员按声明顺序构造（`[class.base.init]`），初始化列表只决定"用什么值初始化"，不决定顺序——这是为了保证析构逆序时有确定的"最后构造者最先析构"
- **逆序析构**：后构造的先析构，保证嵌套资源按"获取的逆序释放"——栈式资源管理（RAII）的正确性基础
- **静态对象**：命名空间作用域静态在 `main` 前构造；函数局部静态首次调用时构造；退出时全部按"构造完成"逆序析构（实测 ex04 场景 4：函数局部静态构造最晚 → 最先析构）

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 工厂函数设计（`make_xxx`） | 按值返回 + 保证省略：零拷贝产出，绝不返回局部引用（3.3、ex03） |
| 解析器 / 配置加载 | 按值返回 prvalue（`parse()`），调用方直接拥有结果（3.3、project） |
| 大数据只读处理 | `const&` / `string_view` / `span` 借用，0 拷贝（3.6、ex06） |
| 独占资源转移（句柄、连接、缓冲区） | `unique_ptr` 转移所有权，sink 按值接收（3.5、ex06） |
| 观察临时对象何时析构 / 排查悬空引用 | 生命周期三规则 + 编译器告警 + ASan（3.2、ex02/ex05） |
| 判断"按值返回要拷几次" | RVO/NRVO 实测矩阵（3.3、ex03） |
| 排查构造/析构顺序问题（静态初始化依赖） | 构造/析构顺序规则 + 静态初始化顺序陷阱（3.4、ex04） |
| 值语义配置/快照对象 | 不可变值对象 + 借用式查询（project） |

**不适合**此阶段的事项：

- **特殊成员函数手写与 Rule of 0/3/5 抉择**（ph13 Rule of 0/3/5 与 RAII 进阶阶段）：本阶段只要求"能用移动承载所有权"，手写五函数与完整规则留给 ph13
- **const 正确性系统化**（ph14 const 正确性与接口设计阶段）：本阶段的 `const&` 借用是"用到了 const"，不展开 const 成员函数/顶层底层 const 体系
- **UB 系统化梳理**（ph15 未定义行为 UB 与内存安全阶段）：本阶段只处理与值类别/生命周期直接相关的悬空引用与 use-after-move 概念，不展开全部 UB 分类
- **智能指针 API 全貌**（ph06 现代 C++ 阶段）：shared_ptr/weak_ptr、自定义 deleter 已在 ph06 讲过，本阶段只用 unique_ptr 讲所有权转移
- **协程/多线程下的生命周期**（ph08 并发编程阶段）：本阶段全部讨论限定在单线程、栈式生命周期内

**跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：

| 维度 | C++ | Rust | Go | Java | Python |
|------|-----|------|-----|------|--------|
| 值类别 | 五类（lvalue/prvalue/xvalue…）显式语法 | move 语义的借用检查（值类别由借用检查器管理） | 值类型 vs 引用类型（slice/map 是引用语义） | 全引用，原始类型例外 | 全引用 + 引用计数 |
| 临时对象寿命 | 完整表达式 + 延长规则（标准规定） | 借用检查器强制"借用不超所有权" | 编译器逃逸分析决定栈/堆 | GC 管，开发者不感知 | 引用计数归零即销毁 |
| 返回局部对象 | 按值 + 保证省略（标准承诺） | 返回所有权（move）或借用（&） | 值拷贝或逃逸到堆 | 引用，无悬空 | 引用计数，无悬空 |
| 悬空引用 | 可能（编译器告警 + ASan 抓） | 编译期拒绝 | 可能（slice 引用底层数组被 GC 后…） | 不可能（GC） | 不可能（引用计数） |
| 所有权表达 | 类型约定（unique_ptr/裸指针/视图） | 语言强制（owned/borrow） | 值语义 + GC，无显式所有权 | 无概念 | 无概念 |

一句话：**Rust 把 C++ 的"值类别 + 生命周期 + 所有权"三件套做成了编译期强制；C++ 靠类型约定 + 工程纪律；Go/Java/Python 用 GC 换掉悬空引用问题，代价是放弃精确的销毁时机**——C++ 的"精确控制 + 需自律"定位在这三者的光谱中一目了然。

## 6. 代码示例

> 说明：示例均在本机（macOS arm64，Apple clang 21.0.0 + Homebrew clang 21.1.8）实际编译运行验证（已验证），编译命令一律 `-std=c++20 -Wall -Wextra`；ex01~ex04、ex06 双编译器零警告。**ex05 是故意出错示例**：默认构建零警告，危险路径（`-DPH12_DANGLING`）需 `-fsanitize=address` 编译 + `ASAN_OPTIONS=detect_stack_use_after_return=1` 运行（macOS 的 ASan 默认不检测 use-after-return），命令见 examples/README.md。完整可运行文件在 [`examples/`](./examples/)，此处展示关键片段。

### 示例 1：值类别判别（examples/ex01-value-categories.cpp）

```cpp
// examples/ex01-value-categories.cpp —— 值类别判别（节选，实测输出见 3.1）
int x = 42;
std::string s = "hello";
std::string&& rref = std::move(s);   // 右值引用
SHOW_CATEGORY(x);                    // lvalue
SHOW_CATEGORY(std::move(s));         // xvalue
SHOW_CATEGORY(rref);                 // lvalue —— 有名字的右值引用是 lvalue
SHOW_CATEGORY("literal");            // lvalue —— 字符串字面量是 lvalue
```

```bash
c++ -std=c++20 -Wall -Wextra ex01-value-categories.cpp -o /tmp/ex01 && /tmp/ex01
```

### 示例 2：临时对象生命周期（examples/ex02-temp-lifetime.cpp）

```cpp
// examples/ex02-temp-lifetime.cpp —— 临时对象生命周期（节选）
{ const Token& r = make("extended");   // 延长到作用域结束
  std::printf("  using r: %s\n", r.name.c_str());
}                                     // 这里才析构
observe(make("arg-temp"));            // 参数临时对象：调用语句结束即析构
```

```bash
c++ -std=c++20 -Wall -Wextra ex02-temp-lifetime.cpp -o /tmp/ex02 && /tmp/ex02
```

本机实测输出（节选）：`[2] const& 绑定` 段打印 `ctor extended / using r: extended / dtor extended / [2] scope end`——`dtor` 出现在 `scope end` 之前，证明延长生效；`[4] 函数参数` 段打印 `ctor arg-temp / observe arg-temp / dtor arg-temp / [4] after call`——临时对象在调用语句结束时析构。完整输出见 examples/README.md。

### 示例 3：RVO/NRVO 实测（examples/ex03-rvo-nrvo.cpp）

```bash
c++ -std=c++20 -Wall -Wextra -O0 ex03-rvo-nrvo.cpp -o /tmp/ex03-O0 && /tmp/ex03-O0
c++ -std=c++20 -Wall -Wextra -O2 ex03-rvo-nrvo.cpp -o /tmp/ex03-O2 && /tmp/ex03-O2
c++ -std=c++20 -Wall -Wextra -DPH12_ANTIPATTERN ex03-rvo-nrvo.cpp -o /tmp/ex03-anti && /tmp/ex03-anti
```

本机实测：`-O0/-O2/-O3` 下 `[RVO prvalue]` 与 `[NRVO named]` 都是 `ctor / got id=0 / dtor`（零拷贝零移动）；`-DPH12_ANTIPATTERN` 构建产生 1 条预期告警 `-Wpessimizing-move`，`[return std::move]` 输出 `ctor / MOVE / dtor / got id=0 / dtor`（必然一次移动）。矩阵与 C++14 对照见 examples/README.md。

### 示例 4：构造与销毁顺序（examples/ex04-order.cpp）

```cpp
// examples/ex04-order.cpp —— 构造与销毁顺序（节选）
struct Derived : Base {
    MemberB b_;          // 声明顺序决定构造顺序
    MemberA a_;
    Derived() : b_{}, a_{} { std::printf("  Derived body\n"); }
};
```

```bash
c++ -std=c++20 -Wall -Wextra ex04-order.cpp -o /tmp/ex04 && /tmp/ex04
```

本机实测（节选）：派生类输出 `Base ctor / MemberB ctor / MemberA ctor / Derived body`，析构严格逆序 `Derived body end / MemberA dtor / MemberB dtor / Base dtor`；函数局部静态两次调用只构造一次，程序退出时全部静态按"构造完成"逆序析构。完整输出见 examples/README.md。

### 示例 5：悬空引用（examples/ex05-dangling.cpp，故意出错）

```cpp
// examples/ex05-dangling.cpp —— 故意出错：返回局部对象/临时对象的引用（节选）
// 运行前提：危险路径必须用 -fsanitize=address 编译，并用
//   ASAN_OPTIONS=detect_stack_use_after_return=1 运行（macOS 默认不检测 use-after-return）
#if defined(PH12_DANGLING)
const std::string& bad_local() {
    std::string s = "local-dangling";
    return s;                       // 告警：reference to stack memory ... returned
}
#endif
```

```bash
c++ -std=c++20 -Wall -Wextra ex05-dangling.cpp -o /tmp/ex05 && /tmp/ex05                     # 默认零警告
c++ -std=c++20 -Wall -Wextra -DPH12_DANGLING -fsanitize=address -g ex05-dangling.cpp -o /tmp/ex05-danger
ASAN_OPTIONS=detect_stack_use_after_return=1 /tmp/ex05-danger
```

本机实测：危险路径编译产生 3 条预期告警（`-Wreturn-stack-address` 三种写法）；ASan 运行报 `ERROR: AddressSanitizer: stack-use-after-return`（读取已销毁的 `std::string` 内部状态时抓取）；不设 `ASAN_OPTIONS` 时程序"看似正常"直接通过——**这正是悬空引用的危险：不保证崩，可能悄悄读到垃圾数据**。

### 示例 6：所有权转移与借用式接口（examples/ex06-ownership.cpp）

```cpp
// examples/ex06-ownership.cpp —— 所有权转移与借用式接口（节选）
std::unique_ptr<Blob> make_blob(std::string p) {
    return std::make_unique<Blob>(std::move(p));   // 所有权产出
}
void sink(std::unique_ptr<Blob> b) {
    b->touch();                                    // 所有权转移（sink）：函数结束释放
}
void borrow(const Blob& b) {
    b.touch();                                     // 借用：不拥有
}
```

```bash
c++ -std=c++20 -Wall -Wextra ex06-ownership.cpp -o /tmp/ex06 && /tmp/ex06
```

本机实测输出：`[1]` 按值返回后 `borrow(*b)` 正常；`[3] sink(std::move(b))` 后 `b == nullptr: yes`（转移后源对象为空）；`[5]` 值语义拷贝后 `a=original  c=original!`（副本修改不影响原件）。

## 7. 总结

### 关键要点

1. **值类别是表达式的属性，不是对象的属性**：lvalue（有身份）/ prvalue（无身份纯值）/ xvalue（有身份且可移动）；glvalue = lvalue ∪ xvalue，rvalue = prvalue ∪ xvalue；`decltype((expr))` 在编译期判别（lvalue→`T&`、xvalue→`T&&`、prvalue→`T`）
2. **两个经典坑**：有名字的右值引用是 lvalue（要再移动需再 `std::move`）；字符串字面量是 lvalue（`const char[N]` 数组）
3. **绑定规则三条**：`T&` 只绑 lvalue，`T&&` 只绑 rvalue，`const T&` 通吃——"临时对象能传给 `const&` 不能传给 `T&`"的语法依据
4. **临时对象默认在完整表达式结束时析构**；绑定 `const T&` / `T&&` 延长到引用离开作用域；绑定子对象延长整个临时对象
5. **延长有边界**：不跨函数返回（返回引用即悬空）、不跨函数参数（参数临时对象调用结束即析构）、不作用于容器/数组元素——**const 引用延长生命周期但边界有限**
6. **C++17 起 prvalue 返回的拷贝省略是保证的**（`-O0`~`-O3` 全程零拷贝，`-fno-elide-constructors` 关不掉）；NRVO 允许不保证；**`return std::move(p)` 是反模式**（clang 实测告警 `-Wpessimizing-move`）
7. **不要返回局部对象引用（F.43）**：按值返回 + 保证省略零拷贝直达调用方；返回引用只会悬空（`-Wreturn-stack-address` 告警 + ASan 抓 `stack-use-after-return`，均为本机实测）
8. **构造顺序：基类 → 成员声明序 → 构造体**，析构严格逆序；初始化列表书写顺序不影响成员构造顺序；函数局部静态首次调用构造、退出时全部静态按"构造完成"逆序析构；跨翻译单元静态初始化顺序未定义（陷阱）
9. **所有权应通过类型体现**：`unique_ptr` 独占（转移=移动）、`const&`/`string_view`/`span`/裸指针借用（R.3 不拥有）；move 后对象"合法但未指定"，实测 `unique_ptr` 转移后为 `nullptr`
10. **值语义通常让代码更简单**：按值返回/传参 + 保证省略近乎零成本，接口无所有权讨论；"读完即弃"用借用、"拷贝无妨"用值、"独立存活"用所有权转移

### 阶段验收清单

- [ ] 能**分辨常见值类别**：用 `decltype((expr))` 判别 lvalue/prvalue/xvalue，能解释 `rref`（有名字的右值引用）和 `"literal"`（字符串字面量）为什么是 lvalue（3.1、练习 2）
- [ ] 能**预测临时对象析构时机**：完整表达式边界、`const&`/`&&` 延长、函数参数不跨语句、绑定子对象延长整个临时对象（3.2、练习 1）
- [ ] 能**解释 move 后对象的状态约束**：合法但未指定；`unique_ptr` 转移后为空（实测）；use-after-move 属 ph15（3.5、练习 5）
- [ ] 能**设计不悬空的接口**：按值返回替代返回局部引用、借用式参数替代裸指针、`string_view` 寿命短于数据源（3.3/3.6、练习 4）
- [ ] 能**实测并解释 RVO/NRVO**：保证省略 vs NRVO vs `return std::move` 反模式，-O 级别与 `-fno-elide-constructors` 的影响（3.3、示例 3）
- [ ] 能**说清构造与销毁顺序**：基类/成员声明序/构造体、逆序析构、函数局部静态与命名空间静态（3.4、示例 4）

### 跨语言对比：生命周期与所有权

| 维度 | C++ | Rust | Go | Java | Python |
|------|-----|------|-----|------|--------|
| 悬空引用 | 可能（告警 + ASan 抓） | 编译期拒绝 | 可能（slice 借用底层数组） | 不可能（GC） | 不可能（引用计数） |
| 销毁时机 | 精确可控（完整表达式/作用域/延长规则） | 作用域末（drop） | GC（不确定） | GC（不确定） | 引用计数归零（基本即时） |
| 所有权 | 类型约定（unique_ptr/裸指针/视图） | 编译期强制（owned/borrow） | 值语义 + GC | 无概念 | 无概念 |
| 返回局部对象 | 按值 + 保证省略（标准承诺） | 返回所有权或借用 | 值拷贝或逃逸到堆 | 引用 | 引用计数 |

一句话：**Rust 把 C++ 的"值类别 + 生命周期 + 所有权"做成编译期强制，C++ 靠类型约定与工程纪律，GC 语言用回收器换掉悬空引用问题但失去精确销毁时机**——C++ 处于"精确控制 + 需自律"的位置，这正是它适合数据库内核、存储引擎的原因，也是本阶段训练"接口不悬空"能力的意义。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 5 题：预测并验证临时对象生命周期（★）、值类别判定（★★）、对比传值/引用/移动的拷贝与移动次数（★★）、改造返回悬空引用的代码（★★★）、所有权接口重构（★★★）——练习 1/3/4 与 roadmap ph12「练习」小节的三个承诺一一对应，练习 2/5 覆盖「学习内容」中的值类别与所有权转移/借用式接口。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**值语义配置对象**——Rule of Zero 的 `Config`（拷贝深拷贝、移动廉价）+ "构造后不可变 + `with()`/`merged_with()` 按值返回新对象"的值语义设计 + `find()` 借用式查询（`string_view` 在对象存活期内稳定）+ CLI（load/get/clone/merge）+ 10 组 33 条断言自测（普通版 + ASan 版）+ Makefile，是 roadmap 推荐项目①「值语义配置对象」的落地。roadmap 推荐项目②「所有权关系重构练习」以 `sol-05` 为最小形态、作为 project 的扩展方向（见 project/README.md 扩展方向）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[Rule of 0/3/5 与 RAII 进阶阶段](../ph13-rule-of-035-raii/13-rule-of-035-raii.md) — ph13 目录已建，其下一阶段 ph14（const 正确性与接口设计阶段）也已完成，再下一阶段 ph15（未定义行为 UB 与内存安全阶段）亦已落地，ph16（测试、静态分析与代码规范阶段）也已落地（ph17（设计模式与架构能力阶段）已落地，roadmap 第 18~23 节均已落地）。本阶段讲清了"对象何时创建/移动/销毁、值类别如何分类、所有权如何通过类型体现"；ph13 在此基础上深入资源类设计的完整规则——何时必须手写特殊成员函数、Rule of 0/3/5 的抉择、自定义 deleter、`unique_ptr` 管理 C 资源、异常安全下的资源释放；届时本阶段的"move 后状态约束""构造/析构顺序"会直接成为判断"这个类要不要手写析构"的依据。
