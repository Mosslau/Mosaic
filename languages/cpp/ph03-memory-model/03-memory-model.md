# C++ 内存模型阶段

> 面向现代 C++、高性能系统、数据库内核方向，掌握对象生命周期、拷贝/移动语义与 RAII 资源管理。

## 1. 概述

C++ 内存模型阶段的定位是：**从"怎么用 OOP"推进到"对象怎么活"——掌握五函数（拷贝构造/拷贝赋值/移动构造/移动赋值/析构）与 RAII**。确定性析构、移动语义和 RAII 是 C++ 区别于所有其他语言的核心竞争力。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 对象存储 | 栈对象、堆对象、构造与析构顺序 |
| 拷贝语义 | 浅拷贝危害、深拷贝实现、拷贝构造/拷贝赋值 |
| 移动语义 | 左值/右值、std::move、移动构造/移动赋值 |
| 资源管理 | RAII、异常安全、Rule of 5 / Rule of 0 |
| 底层机制 | noexcept 与 vector 扩容、RVO/NRVO、编译器自动生成规则 |

本阶段**不涉及**模板、allocator 和多线程内存模型。目标是为 STL 容器和智能指针打下对象生命周期管理基础。

## 2. 来源与演变

| 阶段 | 代表 | 贡献 |
|------|------|------|
| C 时代 | K&R C、ANSI C | malloc/free 手动管理，无构造/析构概念 |
| C++98 | ISO C++98 | 拷贝构造、拷贝赋值、析构形成"三函数法则"（Rule of 3） |
| C++11 | ISO C++11 | 引入移动语义、右值引用、= default / = delete、Rule of 5 |
| 现代 C++ | C++14/17/20 | 拷贝省略强制化、std::optional 等值语义类型、Rule of 0 成为默认 |

C 的 malloc/free 把资源管理全部压在程序员身上。C++98 通过确定性构造/析构将释放绑定到对象生命周期，但临时对象拷贝代价高。C++11 移动语义让临时资源可被"窃取"。Rule of 3 → Rule of 5 → Rule of 0，复杂度逐步收敛到库作者。

## 3. 语法与参数

### 3.1 栈对象与堆对象

```cpp
#include <iostream>
#include <string>

struct Widget {
    std::string name;
    Widget(const std::string& n) : name(n) {
        std::cout << "Widget(" << name << ") constructed\n";
    }
    ~Widget() { std::cout << "Widget(" << name << ") destroyed\n"; }
};

int main() {
    Widget sa("stack-a");              // 栈对象，离开作用域自动析构
    Widget* hp = new Widget("heap");   // 堆对象，必须手动 delete
    delete hp;                         // 忘记此行 → 内存泄漏
    return 0;
}
```

| 存储位置 | 创建方式 | 生命周期 | 释放 | 性能 |
|----------|---------|---------|------|------|
| 栈 | 局部变量、值传递 | 离开作用域自动析构 | 编译器自动调用析构 | 极快，仅移动栈指针 |
| 堆 | `new` / `std::make_unique` | 存活到 `delete` 或智能指针析构 | 手动或智能指针释放 | 涉及 malloc/free，慢于栈 |

栈对象应作为默认选择。堆对象推荐用 `std::make_unique<T>()` 创建，原则是"new 不直接出现在用户代码中"。

### 3.2 构造与析构顺序

构造顺序：基类子对象 → 成员按声明顺序 → 构造函数体。析构严格相反。ph02 4.2 演示过单对象，这里补充数组：

```cpp
#include <iostream>
struct Tracer {
    int id;
    explicit Tracer(int i) : id(i) { std::cout << "Tracer(" << id << ")\n"; }
    ~Tracer() { std::cout << "~Tracer(" << id << ")\n"; }
};
int main() {
    std::cout << "--- enter block ---\n";
    { Tracer arr[] = { Tracer(1), Tracer(2), Tracer(3) }; }
    std::cout << "--- exit block ---\n";
    return 0;
}
```

输出：`Tracer(1) Tracer(2) Tracer(3) ~Tracer(3) ~Tracer(2) ~Tracer(1)`，与"后构造先析构"一致。

### 3.3 浅拷贝的危害与深拷贝

浅拷贝逐成员拷贝指针本身，而非指针指向的内容。当两个对象中的指针指向同一块堆内存，析构时发生 **double-free**（完整演示见示例 1）。解决方式是在拷贝构造/赋值中为新对象分配独立堆内存——下文五函数体系给出完整实现。

### 3.4 五函数体系

| 函数 | 签名 | 调用时机 | 编译器自动生成条件 |
|------|------|---------|--------------------|
| 析构函数 | `~X()` | 对象销毁时 | 未声明移动操作时自动生成 |
| 拷贝构造 | `X(const X&)` | `X b = a;`、传值参数、按值返回 | 未声明移动操作时自动生成 |
| 拷贝赋值 | `X& operator=(const X&)` | `b = a;` | 未声明移动操作时自动生成 |
| 移动构造 | `X(X&&) noexcept` | `X b = std::move(a);` | 未声明任何拷贝/移动/析构时 |
| 移动赋值 | `X& operator=(X&&) noexcept` | `b = std::move(a);` | 未声明任何拷贝/移动/析构时 |

**Rule of 5**：需要手写析构/拷贝构造/拷贝赋值之一时，考虑手写全部五个。析构释放资源，拷贝做深拷贝，移动转移所有权后清空源对象。

**Rule of 0**：若所有成员都是标准库类型/智能指针，则一个都不手写——编译器自动生成的版本就是正确的。这是现代 C++ 的默认推荐。

关键实现模式（完整可运行版见示例 2）：
- 拷贝构造：`data_ = new char[other.size_+1]; std::strcpy(data_, other.data_);`
- 拷贝赋值：自赋值检查 → 分配新内存 → 释放旧内存 → 拷贝数据
- 移动构造：`data_ = other.data_; other.data_ = nullptr;`（窃取 + 清空源对象）
- 移动赋值：释放自身旧资源 → 窃取源对象资源 → 清空源对象
- 析构：`delete[] data_; data_ = nullptr;`

### 3.5 左值、右值与 std::move

```cpp
int  x = 42;            // x 是左值——有名字、可取地址
int& lref = x;          // 左值引用绑定到左值
int&& rref = 42;        // 右值引用绑定到右值（字面量）
std::string s1 = "hello";
std::string s2 = std::move(s1);  // static_cast<T&&>，s1 变为"合法但未指定"
```

| 值类别 | 含义 | 示例 | 可绑定到 |
|--------|------|------|---------|
| 左值 (lvalue) | 有身份、可寻址 | 变量名、`*p` | `T&` |
| 纯右值 (prvalue) | 无身份临时值 | 字面量 `42`、返回非引用的函数调用 | `T&&` / `const T&` |
| 亡值 (xvalue) | 即将消亡的左值 | `std::move(x)` 的结果 | `T&&` |

**std::move 不移动任何东西**——只做 `static_cast<T&&>`，使移动重载被重载决议选中。真正转移在移动构造函数体内完成。移动后源对象必须仍可安全析构，通常将指针成员置 `nullptr`。

### 3.6 RAII：资源获取即初始化

RAII 是 C++ 最重要的资源管理惯用法：**构造获取资源 + 析构释放资源 + 异常安全**。即使发生异常，栈展开也确保析构被调用。

```cpp
// C 风格：手动管理，异常不安全 —— fopen/fclose 可能因提前 return 或异常跳过
// C++ RAII 风格：构造打开 + 析构自动关闭，异常安全
// 核心模式：将资源生命周期绑定到对象，禁止拷贝但允许移动（完整实现见示例 4）
```

RAII 的典型应用：`std::ifstream` 析构自动关闭、`std::lock_guard` 析构自动解锁、`std::unique_ptr` 析构自动 delete。理解了 RAII 就理解了 C++ 为什么不需要 finally。

### 3.7 noexcept 对移动语义的影响

移动构造/赋值必须标记 `noexcept`，否则 STL 容器扩容时出于"强异常保证"会退化为拷贝。`std::vector` 扩容时，若元素的移动构造为 `noexcept` 则走移动（高效），否则走拷贝（安全但慢）。示例 5 在综合演示中给出了可运行的对比验证。

## 4. 底层原理

### 4.1 编译器自动生成规则

| 用户声明 | 后果 |
|---------|------|
| 未声明任何特殊成员 | 编译器生成全部五函数（逐成员拷贝/移动/析构） |
| 声明析构函数 | 拷贝操作仍生成（C++11 起废弃，为兼容保留）；移动操作**不生成** |
| 声明移动操作 | 拷贝操作被隐式删除 |
| 声明拷贝操作 | 移动操作不生成 |
| `= default` | 显式要求编译器生成默认版本 |
| `= delete` | 显式禁止该操作 |

### 4.2 RVO/NRVO 返回值优化

编译器在按值返回局部对象时，可直接在调用方的内存位置构造对象，省略拷贝/移动。C++17 起纯右值返回的拷贝省略是强制要求。

```cpp
#include <iostream>

struct Widget {
    Widget()                    { std::cout << "default ctor\n"; }
    Widget(const Widget&)       { std::cout << "copy ctor\n"; }
    Widget(Widget&&) noexcept   { std::cout << "move ctor\n"; }
};

Widget make_widget() {
    Widget w;
    return w;        // NRVO：w 直接构造在返回槽，无拷贝/移动
}

Widget make_temp() { return Widget(); }  // RVO：C++17 强制省略

int main() {
    std::cout << "--- NRVO ---\n";
    Widget w1 = make_widget();
    (void)w1;
    std::cout << "--- RVO ---\n";
    Widget w2 = make_temp();
    (void)w2;
    return 0;
}
```

**关键结论**：按值返回局部对象时不要写 `return std::move(w)`——这会阻止 NRVO。

### 4.3 Rule of 5 / Rule of 0 的设计抉择

| 策略 | 场景 | 特殊成员函数 |
|------|------|------------|
| Rule of 0 | 成员全是 RAII 类型（`std::string`、`std::vector`、`std::unique_ptr`） | 一个都不手写 |
| Rule of 3 | 管理裸资源，C++98 风格 | 手写析构/拷贝构造/拷贝赋值 |
| Rule of 5 | 管理裸资源且需要移动 | 手写全部五函数 |

Rule of 0 是目标，Rule of 5 是手段。业务代码遵循 Rule of 0；底层库（容器、文件包装、内存池）才需要 Rule of 5。

## 5. 使用场景

| 场景 | 涉及知识点 | 示例 |
|------|-----------|------|
| 资源包装 | RAII、Rule of 5、noexcept | 文件句柄、socket、互斥锁 |
| 动态容器 | 深拷贝、移动语义 | 动态数组类、String 类 |
| 缓冲区管理 | 移动构造/赋值、noexcept | 布隆过滤器位数组、缓存缓冲区 |
| WAL 日志 | RAII 文件类、析构保证 flush | 数据库 WAL writer |
| 消除拷贝 | 移动语义、std::move、RVO | 工厂函数返回大对象 |
| 异常安全 | RAII、析构释放 | 事务式资源管理 |

不适合本阶段：线程间共享（归入并发）；自定义分配器（归入高级内存管理）；类型擦除（需模板 + 虚函数）。

## 6. 代码示例

### 示例 1：浅拷贝危害演示（double-free）

```cpp
#include <cstring>
#include <iostream>

struct DangerString {
    char* data_;
    explicit DangerString(const char* s) {
        data_ = new char[std::strlen(s) + 1];
        std::strcpy(data_, s);
    }
    ~DangerString() { delete[] data_; }
    // 无拷贝构造/拷贝赋值 → 编译器逐成员浅拷贝
};

int main() {
    std::cout << "=== shallow copy double-free demo ===\n";
    DangerString s1("hello");
    std::cout << "s1.data_ = " << (void*)s1.data_ << "\n";
    {
        DangerString s2 = s1;  // 浅拷贝：两个 data_ 指向同一地址
        std::cout << "s2.data_ = " << (void*)s2.data_ << " (same as s1)\n";
    }  // s2 析构，释放 data_
    std::cout << "s1.data_ = " << (void*)s1.data_ << " (dangling)\n";
    return 0;
}  // s1 析构，double-free → 运行时 crash
```

### 示例 2：完整 String 类（五函数 + 测试）

```cpp
#include <cstring>
#include <iostream>
#include <utility>

class String {
public:
    explicit String(const char* s = "") {
        size_ = std::strlen(s);
        data_ = new char[size_ + 1];
        std::strcpy(data_, s);
        std::cout << "ctor: \"" << data_ << "\"\n";
    }
    String(const String& other) : size_(other.size_) {
        data_ = new char[size_ + 1];
        std::strcpy(data_, other.data_);
        std::cout << "copy ctor: \"" << data_ << "\"\n";
    }
    String& operator=(const String& other) {
        std::cout << "copy assign: \"" << other.data_ << "\"\n";
        if (this == &other) return *this;
        char* tmp = new char[other.size_ + 1];
        std::strcpy(tmp, other.data_);
        delete[] data_;
        data_ = tmp;
        size_ = other.size_;
        return *this;
    }
    String(String&& other) noexcept
        : data_(other.data_), size_(other.size_) {
        std::cout << "move ctor\n";
        other.data_ = nullptr;
        other.size_ = 0;
    }
    String& operator=(String&& other) noexcept {
        std::cout << "move assign\n";
        if (this == &other) return *this;
        delete[] data_;
        data_ = other.data_;
        size_ = other.size_;
        other.data_ = nullptr;
        other.size_ = 0;
        return *this;
    }
    ~String() {
        std::cout << "dtor: " << (data_ ? data_ : "(moved-from)") << "\n";
        delete[] data_;
    }
    const char* c_str() const { return data_ ? data_ : ""; }
    size_t size() const { return size_; }
private:
    char* data_;
    size_t size_;
};

int main() {
    std::cout << "--- copy ---\n";
    String s1("hello");
    String s2 = s1;                    // 拷贝构造
    String s3("world");
    s3 = s1;                           // 拷贝赋值

    std::cout << "\n--- move ---\n";
    String s4 = std::move(s1);         // 移动构造，s1 被移空
    std::cout << "s1 after move: \"" << s1.c_str() << "\" (size=" << s1.size() << ")\n";
    String s5("temp");
    s5 = std::move(s4);                // 移动赋值
    std::cout << "s4 after move: \"" << s4.c_str() << "\" (size=" << s4.size() << ")\n";

    std::cout << "\n--- self-assign ---\n";
    const String& ref = s2;
    s2 = ref;                          // 自赋值安全
    String* ptr = &s2;
    s2 = std::move(*ptr);              // 自移动安全
    std::cout << "s2 after self tests: \"" << s2.c_str() << "\"\n";

    std::cout << "\n--- destroying ---\n";
    return 0;
}
```

### 示例 3：动态数组类（布隆过滤器位数组语义）

```cpp
#include <algorithm>
#include <cstring>
#include <iostream>
#include <utility>

class DynArray {
public:
    explicit DynArray(size_t cap = 0)
        : data_(cap > 0 ? new int[cap] : nullptr), capacity_(cap), size_(0) {}
    ~DynArray() { delete[] data_; }

    DynArray(const DynArray& other)
        : capacity_(other.capacity_), size_(other.size_) {
        data_ = capacity_ > 0 ? new int[capacity_] : nullptr;
        std::copy(other.data_, other.data_ + size_, data_);
    }
    DynArray& operator=(const DynArray& other) {
        if (this == &other) return *this;
        int* tmp = other.capacity_ > 0 ? new int[other.capacity_] : nullptr;
        std::copy(other.data_, other.data_ + other.size_, tmp);
        delete[] data_;
        data_ = tmp; capacity_ = other.capacity_; size_ = other.size_;
        return *this;
    }
    DynArray(DynArray&& other) noexcept
        : data_(other.data_), capacity_(other.capacity_), size_(other.size_) {
        other.data_ = nullptr; other.capacity_ = 0; other.size_ = 0;
    }
    DynArray& operator=(DynArray&& other) noexcept {
        if (this == &other) return *this;
        delete[] data_;
        data_ = other.data_; capacity_ = other.capacity_; size_ = other.size_;
        other.data_ = nullptr; other.capacity_ = 0; other.size_ = 0;
        return *this;
    }
    bool push(int val) {
        if (size_ >= capacity_) return false;
        data_[size_++] = val;
        return true;
    }
    int at(size_t i) const { return (i < size_) ? data_[i] : -1; }
    size_t size() const { return size_; }
    size_t capacity() const { return capacity_; }
private:
    int* data_;
    size_t capacity_;
    size_t size_;
};

int main() {
    DynArray buf(5);
    buf.push(10); buf.push(20); buf.push(30);

    DynArray copy = buf;                       // 深拷贝
    std::cout << "copy[0]=" << copy.at(0) << " copy[1]=" << copy.at(1) << "\n";

    DynArray moved = std::move(buf);           // 移动构造
    std::cout << "buf.size() after move: " << buf.size() << "\n";
    std::cout << "moved.size(): " << moved.size() << "\n";

    return 0;
}
```

### 示例 4：RAII 文件句柄（WAL 日志管理）

```cpp
#include <cstdio>
#include <iostream>
#include <string>
#include <utility>

class WalWriter {
public:
    explicit WalWriter(const std::string& path) {
        file_ = std::fopen(path.c_str(), "ab");
        if (!file_) std::fprintf(stderr, "error: cannot open %s\n", path.c_str());
    }
    ~WalWriter() { if (file_) { std::fflush(file_); std::fclose(file_); } }
    // 禁止拷贝，允许移动
    WalWriter(const WalWriter&) = delete;
    WalWriter& operator=(const WalWriter&) = delete;
    WalWriter(WalWriter&& o) noexcept : file_(o.file_) { o.file_ = nullptr; }
    WalWriter& operator=(WalWriter&& o) noexcept {
        if (this != &o) { if (file_) { std::fflush(file_); std::fclose(file_); } file_ = o.file_; o.file_ = nullptr; }
        return *this;
    }
    bool append(const std::string& key, const std::string& value) {
        if (!file_) return false;
        std::fprintf(file_, "%s\t%s\n", key.c_str(), value.c_str());
        return true;
    }
    bool flush() { return file_ && std::fflush(file_) == 0; }
    explicit operator bool() const { return file_ != nullptr; }
private:
    std::FILE* file_ = nullptr;
};

int main() {
    const char* path = "/tmp/ph03_wal_test.log";
    {
        WalWriter wal(path);
        if (!wal) { std::cerr << "failed to open WAL\n"; return 1; }
        wal.append("key1", "value1");
        wal.append("key2", "value2");
        wal.flush();
        std::cout << "WAL records written\n";
    }  // wal 析构自动 fclose

    std::cout << "--- WAL file content ---\n";
    std::FILE* f = std::fopen(path, "r");
    if (f) { char buf[256]; while (std::fgets(buf, sizeof(buf), f)) std::cout << buf; std::fclose(f); }
    return 0;
}
```

### 示例 5：RVO 与 noexcept 综合演示

```cpp
#include <iostream>
#include <vector>

struct Tracker {
    int id;
    explicit Tracker(int i) : id(i) { std::cout << "ctor " << id << "\n"; }
    Tracker(const Tracker& o) : id(o.id) { std::cout << "copy " << id << "\n"; }
    Tracker(Tracker&& o) noexcept : id(o.id) {
        std::cout << "move " << id << "\n";
        o.id = -1;
    }
    ~Tracker() { std::cout << "dtor " << id << "\n"; }
};

Tracker create(int i) { Tracker t(i); return t; }          // NRVO
Tracker create_rvo(int i) { return Tracker(i); }           // RVO

int main() {
    std::cout << "=== NRVO ===\n";
    Tracker t1 = create(1);
    std::cout << "\n=== RVO ===\n";
    Tracker t2 = create_rvo(2);
    std::cout << "\n=== vector with noexcept move ===\n";
    std::vector<Tracker> v; v.reserve(1);
    v.emplace_back(3);
    std::cout << "resize (will move due to noexcept):\n";
    v.emplace_back(4);  // 扩容 → 移动旧元素（因 noexcept）
    std::cout << "\n=== done ===\n";
    return 0;
}
```

## 7. 总结

### 关键要点

1. **浅拷贝是隐式陷阱**：管理堆资源的类必须定义拷贝操作，否则 double-free
2. **五函数是一个体系**：手写一个时考虑手写全部（Rule of 5）；能用标准库成员时一个不写（Rule of 0）
3. **std::move 只做类型转换**：`static_cast<T&&>` 使移动重载被选中，真正转移在函数体内完成
4. **RAII 是 C++ 工程基石**：构造获取 + 析构释放 + 异常安全，无需 finally
5. **noexcept 决定 vector 扩容**：noexcept 移动 → 移动扩容；否则降级为拷贝
6. **RVO/NRVO 优于 std::move**：`return w;` 触发优化，`return std::move(w);` 阻止优化

### 跨语言对比：资源管理

| 维度 | C++ | C | Java | Rust |
|------|-----|----|------|------|
| 资源释放时机 | 确定性析构（离开作用域） | 手动 free | GC 不可预测 | 所有权 + Drop trait |
| 拷贝语义 | 深/浅拷贝/移动，程序员控制 | 手动实现 | 引用语义为主 | Clone trait 显式声明 |
| 移动语义 | C++11 右值引用、std::move | 无 | 无 | 默认移动（所有权转移） |
| 异常安全 | RAII + 栈展开 | 无异常机制 | try-with-resources | Drop 在 panic 时执行 |
| 默认策略 | Rule of 0 | 无 | 依赖 GC | 编译期所有权检查 |

### 阶段验收标准

- 能解释深拷贝/浅拷贝风险，用手写 String 类演示
- 能说清五函数签名、调用时机和自动生成条件
- 能把 fopen/fclose 改造成 RAII 封装类
- 能解释 std::move 的实际作用、移动后源对象状态
- 能说明 noexcept 移动为何影响 vector 扩容
- 能演示 RVO/NRVO 并解释"不要给 return 加 std::move"

### 进入下一阶段前

确保完成以下练习：
- 实现简单 String 类（含五函数）、动态数组类、支持移动的 Buffer 类
- 用 RAII 封装文件句柄，实现 WAL 日志追加与自动关闭
- 将 ph02 中裸 new/delete 改造成 RAII 风格

### 推荐项目

- **RAII 文件类**：封装 std::FILE*，追加写入、flush、自动关闭，禁拷贝允移动
- **动态数组类**：push、at、size + 五函数，布隆过滤器位数组/缓存缓冲区语义

### 下一阶段

[STL 标准库阶段](../ph04-stl/04-stl.md)——容器选择、迭代器、算法、lambda、string_view/span 零开销视图。
