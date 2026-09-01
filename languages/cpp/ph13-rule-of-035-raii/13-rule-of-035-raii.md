# C++ Rule of 0/3/5 与 RAII 进阶阶段

> 面向高性能系统、存储引擎方向，本阶段把"资源类怎么设计"讲透：五个特殊成员函数何时该手写、何时全交编译器（Rule of 0/3/5），如何用 RAII 把 FILE*、fd、malloc 内存等 C 资源封装成"构造即获取、析构即释放、异常也不漏"的现代 C++ 类型，以及自定义 deleter 与 `unique_ptr` 管理 C 资源的完整写法。

## 1. 概述

本阶段定位：**掌握资源类的完整设计规则——判断一个类是否需要自定义特殊成员函数（Rule of 0/3/5 抉择），能手写 RAII 资源封装（构造获取、析构释放、move-only、异常安全），能用自定义 deleter 与 `unique_ptr` 管理 FILE*/fd/malloc 等 C 资源，能在异常路径下保证资源零泄漏**。它是整个路线的第 13 步：ph03 内存模型阶段讲过五个特殊成员函数的基础与深拷贝/浅拷贝，ph12 对象生命周期阶段讲透了值类别、移动语义与"所有权通过类型体现"；本阶段把这些基础收束成**资源类设计的完整规则**——什么时候编译器生成的拷贝就是正确答案、什么时候手写析构就必须把五个都写对、什么时候 move-only 是最贴切的表达。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 特殊成员函数体系 | 析构/拷贝构造/拷贝赋值/移动构造/移动赋值的隐式生成条件、`=default` / `=delete` |
| Rule of 0/3/5 抉择 | 三条规则的完整判定：成员管理资源 → Rule of 0；持有裸资源 → Rule of 5；所有权唯一 → move-only |
| RAII 资源封装 | 手写资源类骨架：构造获取、析构释放、移动转移、拷贝删除、异常安全（R.1） |
| 自定义 deleter | 函数指针 / 仿函数 / lambda / 有状态 deleter，EBO 零开销（`ex04`） |
| unique_ptr 管理 C 资源 | `FILE*` / POSIX fd / malloc 的托管，释放函数编码进类型（`ex05`） |
| 异常安全资源释放 | 构造函数中途失败、copy-and-swap 强保证、基本保证对照（`ex06`） |

这个阶段只涉及资源类设计本身（五个特殊成员函数、Rule of 0/3/5 抉择、RAII 资源封装、自定义 deleter、`unique_ptr` 管理 C 资源、异常安全下的资源释放），**不涉及智能指针 API 全貌（`shared_ptr`/`weak_ptr` 的引用计数与弱引用语义，ph06 现代 C++ 阶段）、异常处理基础与错误码体系（try/catch、异常安全等级的系统分类，ph07 异常、安全与工程规范阶段）、const 正确性系统化（ph14 const 正确性与接口设计阶段）、UB 系统化梳理（use-after-move、悬空引用全分类、double-free 的更多形态，ph15，目录待建）和测试/静态分析/代码规范系统化（ph16，目录待建）** — 那些是后续阶段的内容。承接 ph03 内存模型阶段（五函数基础、深拷贝/浅拷贝）与 ph12 对象生命周期阶段（值类别、移动语义、所有权转移）：ph03 回答了"有哪些特殊成员函数、拷贝移动怎么发生"，本阶段回答"**什么时候要手写、什么时候交给编译器、手写时怎么保证异常安全**"；ph12 讲了"所有权如何通过类型体现"，本阶段把它落到资源类的完整实现上。

## 2. 来源与演变

Rule of 0/3/5 是 C++ 社区在**实践教训**中沉淀出来的设计纪律，不是语言标准的一部分——它回答的问题是"五个特殊成员函数到底该怎么写"。1990 年代 C++98 只有拷贝语义：手写拷贝构造/拷贝赋值/析构三件套是资源管理的唯一方式，于是有了 **Rule of Three**——"写了析构，就几乎总是需要写拷贝构造与拷贝赋值"（三者的职责一致：管理同一块资源）。2011 年的 C++11 引入右值引用与移动语义，三件套扩成五件套（Rule of Five），同时 `=default` / `=delete` 让"显式声明编译器默认行为"成为可能；同期的 RAII 实践发现，**只要把裸资源塞进 `unique_ptr` 等标准 RAII 类型，五个特殊成员就全都交给编译器生成**——这就是 Rule of Zero 的起源。**设计哲学一句话：特殊成员函数是编译器给资源管理的"默认实现"，Rule of 0/3/5 是"什么时候该接受默认、什么时候必须改写"的抉择指南**。C++17 保证拷贝省略（见 ph12）与 C++20/23 的新特性都不改变特殊成员函数的生成规则——这套规则是 C++ 最稳定的部分之一。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| C++98 | 1998 | 只有拷贝语义；Rule of Three 成形（手写析构 ⇒ 也要写拷贝构造/拷贝赋值）；资源管理全靠手写，漏写即泄漏/double-free |
| C++11 | 2011 | 右值引用与移动语义：三件套变五件套（Rule of Five）；`=default` / `=delete` 进入语言；`unique_ptr` / `shared_ptr` 进标准库，"Rule of Zero"成为可能 |
| C++14 | 2014 | `std::make_unique` 补位（C++11 只有 `make_shared`）；Rule of Zero 成为主流写法（用标准库成员替代裸资源） |
| C++17 | 2017 | 保证拷贝省略（见 ph12）；`std::string_view` 等借用类型普及，资源所有权与借用的边界更清晰 |
| C++20/23 | 2020/2023 | 特殊成员生成规则与 RAII 语义无变化；本阶段所有规则原样适用 |

本文示例以 **C++20** 为基线（与 ph11/ph12 一致：roadmap 主线使用 C++20，`-std=c++20` 是稳定度与功能的平衡点；本阶段用到的 `inline` 静态成员变量需 C++17+，`std::exchange` 需 C++14+，均在 C++20 内），验证工具链为 **Apple clang 21.0.0（`c++`）+ Homebrew clang 21.1.8（`clang++`）**，全部示例已在本环境实际编译运行验证（已验证）；GCC/MSVC 本机没有对应编译器，涉及这两家的行为如实标注「未在本环境验证」。特殊成员函数的隐式生成规则（C++11 定型）与 RAII（从 C++98 起就是 C++ 的核心）是这门语言**最稳定**的部分——二十多年没有实质变化，学会了长期复用。

## 3. 语法与参数

> 本节代码块为**教学骨架**：为聚焦当前语法点做了简化（省略实现细节、行内注释为讲解所加，原文件含输出语句）。完整可运行版本见第 6 节与 [`examples/`](./examples/)（与源文件逐字一致），编译/运行命令见 examples/README.md。

### 3.1 五个特殊成员函数与隐式生成规则

一个类有五个"特殊成员函数"由编译器按需隐式生成（C++ 标准术语），它们是资源管理的全部抓手：

| 特殊成员 | 隐式生成时机 | 默认行为 | 什么时候必须自己写 |
|----------|-------------|---------|-------------------|
| 析构函数 | 总是 | 逐成员析构 | 类持有裸资源（指针/句柄）需要释放时 |
| 拷贝构造 | 用户没声明任何拷贝/移动操作（声明析构不抑制拷贝的隐式生成；声明移动操作则拷贝被隐式删除） | 逐成员拷贝（浅拷贝！） | 裸资源需要深拷贝时 |
| 拷贝赋值 | 同上 | 逐成员拷贝赋值 | 同上 |
| 移动构造 | 用户没声明拷贝/析构/移动赋值 | 逐成员移动 | 持有裸资源需要转移所有权时 |
| 移动赋值 | 用户没声明拷贝/析构/移动构造 | 逐成员移动赋值 | 同上 |

**关键规则**：特殊成员不是"声明一个就全停"，精确规则是——声明**移动构造或移动赋值** ⇒ 拷贝构造/拷贝赋值被**隐式删除**（任何拷贝尝试是编译期错误）；声明**析构或任一移动函数** ⇒ 移动构造/移动赋值**不再隐式生成**；而声明**析构**（不写移动）时，**拷贝构造/拷贝赋值仍会隐式生成**——这正是"写了析构却没写拷贝"的类拷贝退化为逐成员浅拷贝的机制：`ex02` 的 `-DPH13_SHALLOW` 对照实验用 ASan 实测了这个后果：**double-free**。若析构之外再声明移动操作，拷贝会被编译器隐式删除（编译期拒绝，见 4.1）。

```cpp
// examples/ex02-rule-of-five.cpp —— Rule of Five（C.21）（节选）
class HeapBuffer {
public:
    explicit HeapBuffer(std::size_t n) : data_(alloc(n)), size_(n) {}
    ~HeapBuffer() { std::free(data_); }                 // 写了析构…
    HeapBuffer(const HeapBuffer& o) : data_(alloc(o.size_)), size_(o.size_) {
        std::memcpy(data_, o.data_, size_);             // …拷贝就必须深拷贝
    }
    HeapBuffer& operator=(const HeapBuffer& o) {        // …拷贝赋值也要写
        if (this != &o) {
            int* fresh = alloc(o.size_);                // 先造新资源再释放旧的
            std::memcpy(fresh, o.data_, o.size_);
            std::free(data_);
            data_ = fresh;
            size_ = o.size_;
        }
        return *this;
    }
    HeapBuffer(HeapBuffer&& o) noexcept                 // …移动也要写（noexcept，E.16）
        : data_(std::exchange(o.data_, nullptr)), size_(o.size_) {
        o.size_ = 0;
    }
    HeapBuffer& operator=(HeapBuffer&& o) noexcept {    // …移动赋值也要写
        if (this != &o) {
            std::free(data_);
            data_ = std::exchange(o.data_, nullptr);
            size_ = o.size_;
            o.size_ = 0;
        }
        return *this;
    }
    // 私有成员省略（data_/size_）
};
```

**`=default` 与 `=delete`**：显式声明编译器默认实现（`=default`，用于"写了析构但仍想用默认拷贝"或恢复被抑制的移动）或显式删除（`=delete`，表达"此类不可拷贝/不可移动"——`unique_ptr` 就是 move-only 的典型）。这是 C++11 之后表达"特殊成员函数的意图"的标准语法：

```cpp
File(const File&) = delete;             // 所有权唯一：禁止拷贝
File& operator=(const File&) = delete;
File(File&& o) noexcept = default;      // 显式恢复默认移动（成员是裸指针时要手写）
```

### 3.2 Rule of 0 / Rule of 3 / Rule of 5：何时手写、何时交给编译器

三条规则是同一问题的三个答案——**你的类自己管理资源吗？**

| 规则 | 适用条件 | 做法 | 对应 Core Guidelines |
|------|---------|------|---------------------|
| **Rule of 0** | 类不直接持有任何裸资源（成员都是 `string`/`vector`/`unique_ptr` 等值类型） | 一个特殊成员都不写，全部交给编译器 | C.20「能避免定义默认操作就避免」 |
| **Rule of 3** | （C++98 时代）持有裸资源且需要拷贝语义 | 手写析构 + 拷贝构造 + 拷贝赋值 | 已被 Rule of 5 取代 |
| **Rule of 5** | 持有裸资源需要完整值语义（拷贝 + 移动都要） | 五个全写：析构 + 拷贝构造/赋值 + 移动构造/赋值 | C.21「定义了任一就要全处理」 |
| **move-only 变体** | 持有裸资源且所有权唯一（文件、fd、连接） | 析构 + 移动构造/赋值，拷贝 `=delete` | R.1 + R.20（`unique_ptr` 同理） |

**判定口诀**（练习 1 的验收标准，`sol-01-rule-quiz.cpp`）：

1. **成员是否自己管理资源？是 → Rule of 0**——`struct Record { std::string key; std::vector<int> values; };` 编译器生成的拷贝是逐成员深拷贝、移动是逐成员移动，就是正确答案；
2. **类自己持有裸资源？是 → 析构 + 拷贝/移动**（C.21）——"写了析构就要考虑全部五个"；资源所有权唯一（文件、fd）时通常 **move-only**（拷贝 `=delete`）最贴切；
3. **要当多态基类？是 → public virtual 析构**（C.35），派生类回到 Rule of 0。

> 本阶段只讲"手写特殊成员函数"这一条线，**`shared_ptr` 的引用计数共享所有权与 `weak_ptr` 属于 ph06 现代 C++ 阶段**，这里只需理解 `unique_ptr`（独占）与手写 move-only 类是同一心智模型。

### 3.3 RAII 资源封装：手写资源类的完整骨架

RAII（Resource Acquisition Is Initialization，**资源获取即初始化**）是 C++ 资源管理的核心纪律（R.1：用 RAII 自动管理资源）：**资源的生命周期 = 持有它的对象的生命周期**——构造时获取资源（失败即抛异常，对象不产生），析构时释放资源（绝不抛异常，E.16），移动转移所有权（源置空，析构安全）。手写一个 RAII 资源类的骨架（完整版见 `ex03-raii-file.cpp`）：

```cpp
// examples/ex03-raii-file.cpp —— RAII 资源封装（R.1）（节选）
class File {
public:
    explicit File(const char* path, const char* mode)
        : fp_(std::fopen(path, mode)) {
        if (fp_ == nullptr) {
            throw std::runtime_error(std::string("无法打开: ") + path);  // 构造失败抛异常
        }
    }
    ~File() { if (fp_ != nullptr) std::fclose(fp_); }   // 析构释放，绝不抛（E.16）
    File(const File&) = delete;                         // 所有权唯一：禁止拷贝
    File& operator=(const File&) = delete;
    File(File&& o) noexcept : fp_(std::exchange(o.fp_, nullptr)) {}  // 移动：窃取 + 源置空
    File& operator=(File&& o) noexcept {
        if (this != &o) {
            if (fp_ != nullptr) std::fclose(fp_);
            fp_ = std::exchange(o.fp_, nullptr);
        }
        return *this;
    }
    // read / write / eof 等操作省略
private:
    std::FILE* fp_;
};
```

**四个不变式**（写任何 RAII 资源类都要守住）：

1. **构造失败抛异常**（E.2）——`fopen` 失败立即 `throw`，调用方拿不到半成品对象；
2. **析构永不抛异常**（E.16）——`fclose`/`close`/`free` 在析构里调用，栈展开时二次抛异常会 `std::terminate`；
3. **移动 `noexcept`**（E.16）——窃取指针 + 源置空，移动本身不可能失败；这直接决定 `std::vector` 扩容时是移动还是拷贝（见第 4 章）；
4. **被移动的对象处于"空句柄"态**——析构时判空，杜绝 double-free（`close(-1)` 是安全 no-op；`fclose(nullptr)` 标准上是未定义行为——多数实现宽容返回 EOF——所以正确写法是判空后再 `fclose`，如上方析构所示）。

**异常路径实测**（`ex03` 输出）：写入中途抛异常，`close（析构自动调用）` **先于** `捕获: 模拟处理失败` 打印——栈展开先析构局部对象、后进入 catch，这正是 RAII 在异常下兜底的机制。

### 3.4 自定义 deleter：删除策略是类型的一部分

`std::unique_ptr` 的第二个模板参数是 deleter——**释放策略被编码进类型**（完整版见 `ex04-custom-deleter.cpp`，sizeof 均为本机 arm64 实测）：

| deleter 形态 | `sizeof(unique_ptr)` | 说明 |
|--------------|---------------------|------|
| 默认（`delete`） | 8（一个裸指针） | 零开销 |
| 函数指针（`decltype(&fclose)`） | 16（指针 + 函数指针） | 类型占两词 |
| 无状态仿函数 / 无捕获 lambda | 8 | **空基类优化（EBO）**：零开销 |
| 有状态仿函数（带 label 等） | 16（指针 + 状态成员） | 大小随状态增长 |

```cpp
// examples/ex04-custom-deleter.cpp —— 自定义 deleter（节选）
struct WidgetDeleter {                                  // 无状态仿函数：EBO 零开销
    void operator()(Widget* p) const noexcept {
        std::printf("  WidgetDeleter: delete %p\n", static_cast<void*>(p));
        delete p;
    }
};
```

**选择指南**：释放动作只有"调哪个函数"这一个信息时用无状态仿函数或无捕获 lambda（零开销、推荐）；要带日志/配置等状态时用有状态仿函数；`shared_ptr` 的 deleter 走**类型擦除**（存进控制块），所以 `shared_ptr<Widget>` 可以挂不同的 deleter 而类型不变——与 `unique_ptr` 的"deleter 进类型"正好相反（完整对照见 `ex04` [6]）。

### 3.5 unique_ptr 管理 C 资源：不写 RAII 类的捷径

手写 RAII 类适用于"这个资源有业务接口"（如 `File` 要有 `read`/`write`）；如果只是"把 C 资源安全托管到作用域结束"，`unique_ptr` + 自定义 deleter 是更短的捷径（R.20：用 `unique_ptr` 表达独占所有权）。三类最常见的 C 资源（完整版见 `ex05-unique-ptr-c-resource.cpp`）：

```cpp
// examples/ex05-unique-ptr-c-resource.cpp —— unique_ptr 管理 C 资源（节选）
using FilePtr = std::unique_ptr<std::FILE, decltype(&std::fclose)>;  // FILE*：释放函数进类型

FilePtr open_file(const char* path, const char* mode) {
    FilePtr fp(std::fopen(path, mode), &std::fclose);
    if (fp == nullptr) throw std::runtime_error("无法打开文件");
    return fp;
}

struct FdCloser {                                   // POSIX fd：close 包装成无状态仿函数
    void operator()(int* p) const noexcept {
        ::close(*p);
        delete p;                                   // fd 装盒后随盒释放
    }
};
using UniqueFdBox = std::unique_ptr<int, FdCloser>;

using MallocPtr = std::unique_ptr<char, decltype(&std::free)>;  // malloc：free 作 deleter
```

**要点**：`open_file` 按值返回命名局部对象 `fp`，走 NRVO 或隐式移动，零拷贝所有权产出（注意这不是"保证省略"——保证省略只对返回 prvalue 生效，衔接 ph12）；异常路径下 deleter 在栈展开时自动调用（`ex05` [3] 实测：`close(fd=3)` 先于 `catch`）；malloc 内存同样可以交给 `unique_ptr` 托管。这正是 roadmap §13 示例 `using FilePtr = std::unique_ptr<FILE, decltype(&fclose)>;` 的完整展开。

### 3.6 异常安全下的资源释放：构造失败与强保证

资源类最隐蔽的坑在**异常路径**（完整版见 `ex06-exception-safety.cpp`）。第一类：**构造函数中途抛异常时，析构不会执行**（对象尚未构造完成），但**已构造完成的成员会逆序析构**——所以裸指针成员会泄漏，`unique_ptr` 成员自动释放：

```cpp
// examples/ex06-exception-safety.cpp —— 异常安全资源释放（节选）
class TwoSafe {                                      // 正例：unique_ptr 成员
public:
    explicit TwoSafe(bool fail) : a_(std::make_unique<Res>("A")) {
        if (fail) throw std::runtime_error("第二个资源获取失败");
        b_ = std::make_unique<Res>("B");
    }
private:
    std::unique_ptr<Res> a_;                         // 已构造成员在栈展开时自动释放
    std::unique_ptr<Res> b_;
};
```

实测（`ex06` [1][2]，用存活计数证明）：裸指针版本构造失败后 `Res 存活 = 1`（`A` 泄漏）；`unique_ptr` 版本存活归零。

第二类：**赋值操作的异常安全等级**。资源类的 `operator=` 若"先释放自己的、再拷贝"，拷贝抛异常就毁了原对象——**强保证（strong guarantee）用 copy-and-swap**：先在临时对象上完成全部可能失败的操作（拷贝），再 `noexcept` swap 换入（swap 只交换指针，绝不抛）：

```cpp
// examples/ex06-exception-safety.cpp —— 强保证：copy-and-swap（节选）
class Config {
public:
    Config& operator=(Config o) noexcept {   // 按值接收：拷贝在此完成
        swap(o);                             // 交换本身不抛
        return *this;
    }
    void swap(Config& o) noexcept { std::swap(name_, o.name_); }
    // …
};
```

实测（`ex06` [4]）：拷贝中途抛 `bad_alloc` 时 swap 未发生，`dst` 仍是 `original`——**强保证成立**。与之对照的基本保证（basic guarantee）只承诺"不泄漏、对象合法但可能已改"（`ex06` [5] 的 `Fragile::assign` 先清空再拷贝）。判定顺序：先保证不泄漏（基本），再尽量做到强保证（copy-and-swap），析构/swap 永远 `noexcept`。

## 4. 底层原理

### 4.1 编译器视角：特殊成员函数的隐式生成

特殊成员函数的隐式生成不是"默认就有"，而是**按需触发 + 依赖声明史**的规则（C++11 定型的规则表）：

```text
用户声明了什么特殊成员？
        │
        ├── 移动构造 / 移动赋值 ──▶ 拷贝构造 / 拷贝赋值被隐式删除
        │                            （任何拷贝尝试是编译期错误）
        ├── 析构（不写移动）──────▶ 移动构造 / 移动赋值不再生成；
        │                           拷贝构造 / 拷贝赋值仍隐式生成
        │                           （逐成员拷贝：值类型 = 深拷贝，裸指针 = 浅拷贝！）
        ├── 拷贝构造 / 拷贝赋值 ──▶ 移动构造 / 移动赋值不再生成；
        │                           另一个拷贝操作仍隐式生成
        └── 什么都没声明 ─────────▶ 按需生成全部五个
                                     ├── 成员不可拷贝（如 std::mutex）──▶ 拷贝被隐式删除
                                     └── 成员可拷贝 ──▶ 逐成员拷贝（值类型 = 深拷贝，裸指针 = 浅拷贝！）
```

这就是为什么"写了析构忘了拷贝"会静默退化为浅拷贝：编译器看到你声明了析构，就不再为你生成**移动**构造；但**拷贝构造仍会隐式生成**——**拷贝变成逐成员指针复制**，两个对象持有同一块内存，作用域结束 double free（`ex02` 的 ASan 实测）。只有当你额外声明了移动操作时，拷贝才会被编译器隐式删除（编译期拒绝）。理解这条规则，Rule of 5 就不再是"教条"而是"编译器规则的直接推论"。

### 4.2 栈展开：RAII 在异常下兜底的机制

```text
throw 抛出异常
    ▼
栈帧逐层弹出：先析构当前作用域的全部局部对象（声明逆序）
    │       │
    │   ┌───┴───────────────────────────────┐
    │   │ File f(kPath, "w");  ← 局部对象    │
    │   │ 析构 → fclose（RAII 兜底）          │
    │   └───────────────────────────────────┘
    ▼
找到匹配的 catch 块 → 进入 catch 处理
    ▼
异常处理完毕（若没找到 catch → std::terminate）
```

关键点：**析构发生在 catch 之前**（`ex03` [2] 实测 `close` 先于 `捕获:` 打印）。所以只要资源是 RAII 对象持有的，无论异常从哪一层抛出、穿过多少作用域，释放动作都必然执行——这就是"资源释放路径不应依赖手动调用 close"（roadmap 必会概念）的机制解释。

### 4.3 为什么移动必须 noexcept：vector 扩容的拷贝 vs 移动

`std::vector` 扩容时要把旧元素搬进新内存：如果移动构造是 `noexcept`，**直接搬**；如果可能抛异常，编译器**退化为拷贝**（拷贝失败时旧容器元素还在，可以回滚；移动失败则元素已丢失一半，无法回滚）。所以：

```text
class WithNoexceptMove {
    // 移动构造 noexcept：vector 扩容 = 逐元素移动（O(1) 每次）
};
class WithThrowingMove {
    // 移动构造可能抛：vector 扩容 = 逐元素拷贝（可能 O(n) 深拷贝）
};
```

**手写资源类的移动构造/移动赋值标记 `noexcept`，不只是"礼貌"，而是性能语义的一部分**——`HeapBuffer`（`ex02`）与 `File`（`ex03`）的移动都是 `noexcept` 的原因就在这里（E.16：析构、释放与 swap 永不失败）。

### 4.4 EBO：无状态 deleter 零开销的原理

`unique_ptr<Widget, WidgetDeleter>` 中，`WidgetDeleter` 是空类（无数据成员）。标准库通过**空基类优化**（EBO，empty base optimization）把 deleter 作为空基类继承，不占用额外字节——所以无状态 deleter / 无捕获 lambda 的 `unique_ptr` 与裸指针同尺寸（`ex04` [3][4] 实测 sizeof = 8）。函数指针 deleter 不能触发 EBO（函数指针有值），因此占两词（16 字节）。这是"自定义 deleter 零开销"的机制解释。

## 5. 使用场景

**真实工程中的用途**：

- **存储引擎 / 数据库内核**：Buffer Pool 的页句柄、WAL 的 fd、SSTable 的文件句柄全部用 RAII 管理——任何一次异常或 early return 都不允许漏掉 `close`/`fsync`（`ex03`/`project` 的直接应用）；LevelDB/RocksDB 的 `RandomAccessFile`/`WritableFile` 接口就是"RAII 文件句柄 + 显式 `Sync()`/`Close()`"的工程形态
- **连接与句柄类**：socket 连接、数据库连接、互斥锁（`std::lock_guard` 就是 RAII 锁，CP.20）——"获取即初始化、析构即释放"是并发/网络代码防泄漏的骨架（承接 ph08 并发、ph09 网络）
- **C 库互操作边界**：封装 C 库返回的 `FILE*`、`sqlite3*`、`zlib` 流等，用自定义 deleter 或手写 RAII 类把"谁释放"从调用方责任变成类型内置（`ex05`/`project`）
- **旧代码改造**：把"malloc + 多处 early return 手动 free"改造成 `unique_ptr` 托管——错误路径不再需要逐条配对 free（`sol-04` 实测三条路径差值全为 0）

**什么时候不用它**：

- 资源是"进程生命周期级"的（如全局配置、单例），不需要精确释放时机——RAII 的确定性销毁反而多余
- 只借用、不拥有：裸指针/`string_view`/`span` 表达借用（R.3），不套 RAII——RAII 是"所有权"的机制，不是"观察"的机制（衔接 ph12 借用式接口）
- 需要共享所有权时用 `std::shared_ptr`（ph06 的内容），不要手写引用计数——手写 RAII 类是"唯一所有权"的表达，不是"共享"的表达

**与其他语言的对比**（为 analysis/ 与 Tenet 合成积累素材）：

| 维度 | C++ | Rust | Go | Java | Python |
|------|-----|------|-----|------|--------|
| 资源释放机制 | RAII（析构绑定作用域，精确可预测） | Drop trait（作用域末，与 RAII 同源） | `defer`（函数级，手动指定顺序） | try-with-resources（显式声明） | `with` / context manager（显式声明） |
| 默认释放时机 | 编译器保证（析构必然执行） | 编译器保证（drop 必然执行） | 函数返回时（defer 栈） | 代码块结束时（显式） | 代码块结束时（显式） |
| 异常路径 | 栈展开自动析构（E.6） | 同样 drop（panic 时 unwinding） | defer 照常执行 | finally/close 照常执行 | `__exit__` 照常执行 |
| 拷贝语义 | 值类型深拷贝 + move（Rule 0/3/5 抉择） | move 语义 + 借用检查（编译期强制） | 值拷贝/引用，无所有权概念 | 引用语义，无所有权概念 | 引用计数 + GC，无所有权概念 |
| 手写释放的代价 | 漏写即泄漏/double-free（ASan 抓） | 编译器拒绝（所有权规则） | defer 顺序错误即 bug | 忘写 close 即泄漏 | 忘写 __exit__ 即泄漏 |

一句话：**C++ 的 RAII 是"编译器保证 + 开发者抉择"——释放必然发生（析构），但拷贝/移动语义要开发者按 Rule 0/3/5 抉择；Rust 把同一套思想做成编译期强制（drop + 所有权检查）；Go/Java/Python 用显式 `defer`/`try-with-resources`/`with` 把"释放时机"交给开发者手动声明**——C++ 处于"确定性 + 需自律"的位置，这正是它适合数据库内核、存储引擎的原因（本阶段训练"资源类设计"能力，是后面 ph22 存储引擎阶段 Buffer Pool/WAL 资源管理的直接前置，目录待建）。

## 6. 代码示例

> 说明：示例均在本机（macOS arm64，Apple clang 21.0.0 + Homebrew clang 21.1.8）实际编译运行验证（已验证），编译命令一律 `-std=c++20 -Wall -Wextra`，双编译器零警告、输出一致（ex02/ex04 仅指针地址不同，属正常）。**ex02 的 `-DPH13_SHALLOW` 是故意出错路径**：必须用 `-fsanitize=address` 编译运行，否则 double-free 是未定义行为。完整可运行文件在 [`examples/`](./examples/)，此处展示关键片段。

### 示例 1：Rule of Zero（examples/ex01-rule-of-zero.cpp）

```cpp
// examples/ex01-rule-of-zero.cpp —— Rule of Zero（C.20）：让编译器生成特殊成员函数（节选，与原文件逐字一致）
struct Widget {
    std::string id;
    Tracer tracer;
    std::vector<int> data;
};
// 编译期验证：Rule of Zero 类型自动获得全部五个特殊成员
static_assert(std::is_copy_constructible_v<Widget>);
static_assert(std::is_copy_assignable_v<Widget>);
static_assert(std::is_move_constructible_v<Widget>);
static_assert(std::is_move_assignable_v<Widget>);
static_assert(std::is_nothrow_destructible_v<Widget>);
```

```bash
c++ -std=c++20 -Wall -Wextra ex01-rule-of-zero.cpp -o /tmp/ph13-ex01 && /tmp/ph13-ex01
```

实测要点：`Widget` 成员全是值类型，编译器生成的拷贝是**逐成员深拷贝**（`b` 改 `data` 不影响 `a`）、移动是**逐成员移动**（源置空）；[1] 按值返回 0 拷贝 0 移动（返回命名局部对象走 NRVO；返回 prvalue 才是保证省略——详见 ph12）。

### 示例 2：Rule of Five（examples/ex02-rule-of-five.cpp）

```cpp
// examples/ex02-rule-of-five.cpp —— Rule of Five（C.21）（节选，与原文件逐字一致）
    // 拷贝构造：深拷贝（新内存 + 内容复制）
    HeapBuffer(const HeapBuffer& o) : data_(alloc(o.size_)), size_(o.size_) {
        std::memcpy(data_, o.data_, size_);
        std::printf("  copy    size=%zu data=%p (from %p)\n", size_,
                    static_cast<void*>(data_), static_cast<void*>(o.data_));
    }
    // 移动构造：窃取指针 + 源置空（noexcept，E.16）
    HeapBuffer(HeapBuffer&& o) noexcept
        : data_(std::exchange(o.data_, nullptr)), size_(o.size_) {
        o.size_ = 0;
        std::printf("  move    size=%zu data=%p (源已置空)\n", size_,
                    static_cast<void*>(data_));
    }
```

```bash
c++ -std=c++20 -Wall -Wextra ex02-rule-of-five.cpp -o /tmp/ph13-ex02 && /tmp/ph13-ex02
# 危险路径（故意出错，必须 ASan 编译，否则 double-free 是未定义行为）：
c++ -std=c++20 -Wall -Wextra -DPH13_SHALLOW -fsanitize=address -g \
    ex02-rule-of-five.cpp -o /tmp/ph13-ex02-shallow && /tmp/ph13-ex02-shallow
```

实测要点：正常路径深拷贝/移动全部正确；危险路径 ASan 报 `double-free … in ShallowBuffer::~ShallowBuffer()`，SIGABRT 退出码 134——**只写析构不写拷贝 = 浅拷贝 = double free**。

### 示例 3：RAII 文件封装（examples/ex03-raii-file.cpp）

```cpp
// examples/ex03-raii-file.cpp —— RAII 资源封装（R.1）（节选，与原文件逐字一致）
class File {
public:
    explicit File(const char* path, const char* mode)
        : fp_(std::fopen(path, mode)) {
        if (fp_ == nullptr) {
            throw std::runtime_error(std::string("无法打开: ") + path);
        }
        std::printf("  open  %s (%s)\n", path, mode);
    }
    ~File() {
        if (fp_ != nullptr) {
            std::fclose(fp_);
            std::printf("  close（析构自动调用）\n");
        }
    }
    File(const File&) = delete;             // 所有权唯一：禁止拷贝
    File& operator=(const File&) = delete;
    File(File&& o) noexcept : fp_(std::exchange(o.fp_, nullptr)) {
        std::printf("  move（句柄易主，源置空）\n");
    }
    // …
};
```

```bash
c++ -std=c++20 -Wall -Wextra ex03-raii-file.cpp -o /tmp/ph13-ex03 && /tmp/ph13-ex03
```

实测要点：[2] 异常路径下 `close（析构自动调用）` **先于** `捕获:` 打印（栈展开先析构再进 catch）；[3] 句柄 move-only，移动进容器后旧对象置空、析构安全。

### 示例 4：自定义 deleter（examples/ex04-custom-deleter.cpp）

```cpp
// examples/ex04-custom-deleter.cpp —— 自定义 deleter（节选，与原文件逐字一致）
// 方式 2：有状态仿函数（带配置/日志的删除策略）
struct LoggingFree {
    const char* label;
    void operator()(void* p) const noexcept {
        std::printf("  LoggingFree[%s]: free %p\n", label, p);
        std::free(p);
    }
};
// sizeof 实测（arm64）：默认/无状态仿函数/lambda = 8；函数指针/有状态 = 16
```

```bash
c++ -std=c++20 -Wall -Wextra ex04-custom-deleter.cpp -o /tmp/ph13-ex04 && /tmp/ph13-ex04
```

实测要点：无状态仿函数/无捕获 lambda 经 EBO 零开销（sizeof=8 与裸指针相同）；函数指针/有状态 deleter 占两词（sizeof=16）；`shared_ptr` 的 deleter 走类型擦除，与 `unique_ptr` 的"进类型"相反（共享所有权完整语义属 ph06）。

### 示例 5：unique_ptr 管理 C 资源（examples/ex05-unique-ptr-c-resource.cpp）

```cpp
// examples/ex05-unique-ptr-c-resource.cpp —— unique_ptr 管理 C 资源（节选，与原文件逐字一致）
FilePtr open_file(const char* path, const char* mode) {
    FilePtr fp(std::fopen(path, mode), &std::fclose);
    if (fp == nullptr) throw std::runtime_error("无法打开文件");
    std::printf("  fopen 成功（fclose 已绑定为 deleter）\n");
    return fp;
}
```

```bash
c++ -std=c++20 -Wall -Wextra ex05-unique-ptr-c-resource.cpp -o /tmp/ph13-ex05 && /tmp/ph13-ex05
```

实测要点：`FILE*` / POSIX fd / malloc 三种 C 资源统一用 `unique_ptr` + deleter 托管；[3] 异常路径下 `close(fd=…)` 先于 `catch`（deleter 在栈展开时兜底）。

### 示例 6：异常安全资源释放（examples/ex06-exception-safety.cpp）

```cpp
// examples/ex06-exception-safety.cpp —— 异常安全资源释放（节选，与原文件逐字一致）
// 正例：unique_ptr 成员 —— 构造中途抛异常，已构造成员逆序析构
class TwoSafe {
public:
    explicit TwoSafe(bool fail) : a_(std::make_unique<Res>("A")) {
        if (fail) throw std::runtime_error("第二个资源获取失败");
        b_ = std::make_unique<Res>("B");
    }
private:
    std::unique_ptr<Res> a_;
    std::unique_ptr<Res> b_;
};
// 强保证：copy-and-swap —— 先在新对象上完成全部可能失败的操作，再 noexcept 交换
    Config& operator=(Config o) noexcept {   // 按值接收：拷贝在此完成
        swap(o);                             // 交换本身不抛
        return *this;
    }
```

```bash
c++ -std=c++20 -Wall -Wextra ex06-exception-safety.cpp -o /tmp/ph13-ex06 && /tmp/ph13-ex06
```

实测要点：[1][2] 用存活计数证明裸指针成员构造失败泄漏（存活残留 1）、`unique_ptr` 成员零泄漏（存活归零）；[4] copy-and-swap 下拷贝失败时 `dst` 原封不动（强保证成立）；[5] 基本保证对照。

## 7. 总结

### 关键要点

1. **五个特殊成员函数**（析构/拷贝构造/拷贝赋值/移动构造/移动赋值）是编译器给资源管理的默认实现；**声明析构或任一移动函数 ⇒ 移动操作不再隐式生成；声明移动操作 ⇒ 拷贝被隐式删除；声明析构（不写移动）⇒ 拷贝仍隐式生成**——"写了析构忘了拷贝"会静默退化为浅拷贝（`ex02` ASan 实测 double-free）
2. **Rule of 0**（C.20）：成员都是值类型（`string`/`vector`/`unique_ptr`）时不写任何特殊成员——编译器生成的逐成员拷贝/移动就是正确答案
3. **Rule of 5**（C.21）：持有裸资源需要值语义时五个全写；**move-only** 变体（拷贝 `=delete` + 移动 `noexcept`）是文件/fd/连接等唯一所有权资源的最贴切表达
4. **多态基类必须 public virtual 析构**（C.35），派生类回到 Rule of 0；`=default` 显式要默认、`=delete` 显式禁拷贝/移动
5. **RAII 四不变式**：构造失败抛异常（E.2）、析构/释放/swap 永不抛（E.16）、移动 `noexcept`、被移动对象处于"空句柄"态（析构 no-op）
6. **异常路径由栈展开兜底**：析构先于 catch 执行（`ex03` 实测），所以资源只要被 RAII 对象持有，无论异常从哪层抛出都不漏释放
7. **自定义 deleter 是类型的一部分**：无状态仿函数/无捕获 lambda 经 EBO 零开销（sizeof=8），函数指针/有状态 deleter 占两词；`shared_ptr` 的 deleter 走类型擦除（属 ph06）
8. **`unique_ptr` 管理 C 资源**：`decltype(&std::fclose)` / `&std::free` 直接作 deleter；按值返回命名对象走 NRVO / 隐式移动，零拷贝所有权产出（保证省略只对返回 prvalue 生效，衔接 ph12）
9. **构造函数中途抛异常时析构不执行、已构造成员逆序析构**——裸指针成员泄漏（存活计数残留实测），`unique_ptr` 成员自动释放
10. **强保证 = copy-and-swap**：可能失败的操作（拷贝）都在 `noexcept` swap 之前完成；基本保证只承诺不泄漏、对象合法——先保证不泄漏，再尽量强保证

### 阶段验收清单

- [ ] 能**判断一个类是否需要自定义特殊成员函数**：按"成员是否管理资源 / 是否持有裸资源 / 是否多态基类"三问做出 Rule of 0 / Rule of 5 / move-only 抉择（3.2、练习 1）
- [ ] 能**用 RAII 防止资源泄漏**：写出完整资源类骨架（构造获取、析构释放、move-only、`noexcept`），并解释异常路径为什么由栈展开兜底（3.3、练习 2）
- [ ] 能**解释 Rule of 0 的价值**：值类型成员的逐成员拷贝/移动为什么就是正确答案、为什么"手写析构通常意味着要处理拷贝和移动"（3.2、练习 1）
- [ ] 能**用 `unique_ptr` + 自定义 deleter 管理 C 资源**：FILE*/fd/malloc 的托管写法，并解释 EBO 零开销与类型编码（3.4/3.5、练习 4）
- [ ] 能**实测异常安全**：构造中途失败零泄漏（存活计数）、copy-and-swap 强保证下目标原封不动（3.6、练习 5）
- [ ] 能**解释 `noexcept` 移动的性能语义**：vector 扩容为何在移动可能抛时退化为拷贝（4.3、练习 3）

### 跨语言对比：资源管理

| 维度 | C++ | Rust | Go | Java | Python |
|------|-----|------|-----|------|--------|
| 释放机制 | RAII（析构绑定作用域） | Drop（作用域末） | `defer`（函数级） | try-with-resources | `with`/context manager |
| 拷贝语义 | 值深拷贝 + move（Rule 0/3/5 抉择） | move + 借用检查（编译期强制） | 值拷贝/引用 | 引用语义 | 引用计数 + GC |
| 异常路径 | 栈展开自动析构（E.6） | unwind 时 drop | defer 照常执行 | finally 执行 | `__exit__` 执行 |
| 漏写释放的后果 | 泄漏/double-free（ASan 抓） | 编译器拒绝 | 顺序错即 bug | 泄漏 | 泄漏 |

一句话：**C++ 用"编译器保证析构必然执行 + 开发者抉择拷贝/移动语义"换来确定性的资源释放时机**——这是它适合数据库内核、存储引擎的核心原因；Rust 把抉择也交给编译器（所有权强制），GC 语言放弃精确时机换省心。本阶段训练的"资源类设计"能力直接服务于 ph22 存储引擎阶段（目录待建）的 Buffer Pool/WAL/SSTable 资源管理。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 5 题：判断类是否需要自定义特殊成员函数（★）、把 FILE* 封装成 RAII 类（★★）、把 POSIX fd 封装成 RAII 句柄并用 fcntl 实测关闭（★★★）、改造手动释放资源的旧代码（★★★）、异常安全的资源类（★★★）——练习 2/3/4 与 roadmap ph13「练习」小节的三个承诺（封装 FILE 指针 / 封装 socket 句柄 / 改造手动释放资源的旧代码）一一对应，练习 1/5 覆盖「学习内容」中的 Rule 抉择与异常安全资源释放。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**RAII 系统资源库（安全句柄封装）**——header-only 的 `raii/` 库（`CFile` 封装 `FILE*` + `UniqueFd` 封装 POSIX fd）+ 演示 CLI（write/read/copy 三子命令）+ 自测（编译期 `static_assert` move-only + 16 组运行期断言（8 个测试段落），含**异常路径 fd 计数归零**实测；普通版 + ASan 版）+ Makefile，是 roadmap 推荐项目①「RAII 系统资源库」的落地（推荐项目②「安全句柄封装」即本库形态）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[const 正确性与接口设计阶段](../ph14-const-correctness/14-const-correctness.md) — ph14 目录已建，是当前最后一个有目录的阶段（roadmap 第 15~23 节均为规划中，目录待建）。本阶段把"资源类的内部实现"讲透（特殊成员函数、RAII、异常安全）；ph14 在此基础上把视角转向**接口设计**——const 成员函数、顶层/底层 const、`const&` 参数、逻辑 const 与物理 const、只读视图（`string_view`/`span`），把"资源类不变量"用 const 表达成接口承诺；届时本阶段的"move-only 类为什么天然 const 友好""RAII 类的接口如何设计"会直接成为判断"这个接口要不要标 const"的依据。
