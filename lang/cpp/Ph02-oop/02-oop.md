# C++ 面向对象 OOP 阶段

> 面向现代 C++、高性能系统、数据库内核方向，掌握类与对象、封装、继承、多态，以及构造/析构与接口设计。

## 1. 概述

C++ 面向对象阶段的定位是：**能设计清晰的类接口，用封装组织数据，用继承表达 is-a，用组合获得灵活性，用多态实现可扩展的接口**。本阶段延续存储引擎/数据库内核深度线，示例与练习围绕 Page、Block、Segment、IStorage、IIndex、IExecutor 等存储语义展开。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 类与访问控制 | `class`、`public`/`private`/`protected` |
| 构造与析构 | 默认构造、带参构造、析构函数、虚析构函数 |
| 成员与对象 | 成员函数、`this` 指针、`static` 成员、成员初始化列表 |
| 面向对象三特性 | 封装、继承、多态 |
| 多态机制 | `virtual`、`override`、纯虚函数、抽象类 |
| 设计取舍 | 组合优于继承、接口与实现分离 |

本阶段**不涉及**模板元编程、多重继承深入、智能指针与移动语义，这些内容归入后续阶段。目标是为 C++ 内存模型与 RAII 阶段打下类与对象生命周期的基础。

## 2. 来源与演变

| 阶段 | 代表 | 贡献 |
|------|------|------|
| Simula 67 | Dahl、Nygaard | 首次提出类、对象、继承 |
| C with Classes | Stroustrup，1979 | 在 C 中加入 class、构造/析构 |
| 现代 C++ | C++11/14/17 | `override`、默认/删除函数 |

C++ 的 OOP 强调**零成本抽象**：多态通过 vptr/vtable 实现，运行时开销仅一次间接调用；同时保留值语义与确定性析构，这是它与 Java、C# 等托管语言的本质差异。

## 3. 语法与参数

### 3.1 class 与访问控制

```cpp
class Counter {
public:
    explicit Counter(int start) : value_(start) {}
    void inc() { ++value_; }
    int value() const { return value_; }
private:
    int value_;
};
```

| 访问说明符 | 含义 | 典型用途 |
|-----------|------|---------|
| `public` | 任意代码可访问 | 接口、构造函数 |
| `private` | 仅类内部可访问 | 数据成员、实现细节 |
| `protected` | 类内部与派生类可访问 | 需要子类复用的实现 |

构造函数在对象创建时执行，用于**建立类不变量（class invariant）**；析构函数在对象销毁时执行，用于释放资源。若类管理资源，析构函数必须正确释放，这是 RAII 的核心。

### 3.2 成员初始化列表

成员初始化列表在构造函数体执行之前初始化成员，**比在函数体内赋值更高效、更准确**。

```cpp
class Page {
public:
    Page(int id, const std::string& payload)
        : id_(id), payload_(payload) {}
private:
    int id_;
    std::string payload_;
};
```

| 场景 | 说明 |
|------|------|
| const 成员 | 必须在初始化列表中初始化 |
| 引用成员 | 必须在初始化列表中绑定 |
| 无默认构造的成员 | 必须在初始化列表中传参构造 |
| 基类子对象 | 通过初始化列表调用基类构造 |

**重要**：初始化顺序**由成员在类中的声明顺序决定**，而不是初始化列表中的书写顺序。

### 3.3 this 指针与 static 成员

`this` 是指向当前对象的常量指针；`static` 成员属于类，不属于某个对象。

```cpp
class Logger {
public:
    explicit Logger(const std::string& name) : name_(name) {}
    void log(const std::string& msg) const {
        std::cout << "[" << name_ << "] " << msg << "\n";
        ++total_logs_;
    }
    static int total_logs() { return total_logs_; }
private:
    std::string name_;
    static int total_logs_;
};

int Logger::total_logs_ = 0;
```

- `static` 成员函数没有 `this` 指针，只能访问静态成员
- 在 `const` 成员函数中，`this` 的类型是 `const ClassName*`

### 3.4 继承

继承表达 **is-a** 关系。如果派生类只是复用代码，通常组合更合适。

```cpp
class StorageObject {
public:
    explicit StorageObject(int id) : id_(id) {}
    virtual ~StorageObject() = default;
    int id() const { return id_; }
private:
    int id_;
};

class Page : public StorageObject {
public:
    Page(int id, const std::string& data)
        : StorageObject(id), data_(data) {}
    size_t size() const { return data_.size(); }
private:
    std::string data_;
};
```

### 3.5 多态、virtual、override 与抽象类

多态通过基类指针/引用调用派生类实现的虚函数完成。抽象类包含纯虚函数，不能直接实例化，适合作为接口。

```cpp
class IStorage {
public:
    virtual ~IStorage() = default;
    virtual void put(const std::string& k, const std::string& v) = 0;
    virtual std::string get(const std::string& k) = 0;
};

class MemoryStorage : public IStorage {
public:
    void put(const std::string& k, const std::string& v) override { store_[k] = v; }
    std::string get(const std::string& k) override {
        auto it = store_.find(k);
        return it == store_.end() ? "" : it->second;
    }
private:
    std::unordered_map<std::string, std::string> store_;
};
```

| 关键字 | 作用 | 备注 |
|--------|------|------|
| `virtual` | 声明虚函数，支持动态分派 | 基类中声明，派生类可重写 |
| `override`（C++11） | 显式标记重写，编译器检查签名 | 推荐在派生类虚函数后加 `override` |
| `= 0` | 纯虚函数，类变为抽象类 | 抽象类不能实例化 |

**虚析构函数**：若类将作为多态基类使用，析构函数必须声明为 `virtual`，否则通过基类指针 `delete` 派生类对象会未定义行为。

## 4. 底层原理

### 4.1 vptr/vtable 与动态分派

含有虚函数的类对象通常包含一个隐藏指针 `vptr`，指向类的 `vtable`（虚函数表）。通过基类引用调用虚函数时，运行期通过 `vptr` 查找实际函数地址。

```cpp
class Base {
public:
    virtual void f() {}
    int x = 0;
};

class Derived : public Base {
public:
    void f() override {}
    int y = 0;
};
```

| 对象 | 内存开始处 | 随后数据 |
|------|-----------|---------|
| `Base` 对象 | vptr | `x` |
| `Derived` 对象 | vptr（指向 Derived 的 vtable） | `x`、`y` |

开销：每个对象多一个指针（64 位系统 8 字节）；每次虚函数调用多两次间接访问；内联优化通常失效。

### 4.2 构造与析构调用顺序

构造顺序：基类子对象 → 成员按声明顺序 → 派生类构造函数体。析构顺序严格相反。

```cpp
#include <iostream>

class Base {
public:
    Base()  { std::cout << "Base()\n"; }
    ~Base() { std::cout << "~Base()\n"; }
};

class Member {
public:
    Member()  { std::cout << "Member()\n"; }
    ~Member() { std::cout << "~Member()\n"; }
};

class Derived : public Base {
public:
    Derived()  { std::cout << "Derived()\n"; }
    ~Derived() { std::cout << "~Derived()\n"; }
private:
    Member m_;
};

int main() { Derived d; return 0; }
```

输出：

```text
Base()
Member()
Derived()
~Derived()
~Member()
~Base()
```

## 5. 使用场景

| 场景 | 涉及知识点 | 示例 |
|------|-----------|------|
| 数据建模 | class、访问控制、构造/析构 | Student、Page、Block |
| 接口抽象 | 抽象类、纯虚函数 | IStorage、IIndex、IExecutor |
| 可扩展设计 | 继承 + 多态 | 不同存储后端实现同一接口 |
| 共享状态 | static 成员 | 全局计数器、日志级别 |
| 资源管理 | 析构函数释放资源 | Buffer、文件句柄包装 |

不适合硬套 OOP 的场景：纯数值计算优先用自由函数 + 命名空间；只需数据聚合用 `struct`；频繁创建的小对象注意 vptr 内存开销。

## 6. 代码示例

### 示例 1：Student 类
```cpp
#include <iostream>
#include <string>

class Student {
public:
    Student(const std::string& name, int id, double score)
        : name_(name), id_(id), score_(score) {}

    void print() const {
        std::cout << name_ << " [" << id_ << "]: " << score_ << "\n";
    }
    bool passed() const { return score_ >= 60.0; }

private:
    std::string name_;
    int id_;
    double score_;
};

int main() {
    Student s{"Bob", 2001, 78.5};
    s.print();
    std::cout << (s.passed() ? "passed" : "failed") << "\n";
    return 0;
}
```

### 示例 2：Page / Block / Segment 建模（组合优先）
```cpp
#include <iostream>
#include <string>
#include <vector>

class Page {
public:
    explicit Page(const std::string& data) : data_(data) {}
    size_t size() const { return data_.size(); }
private:
    std::string data_;
};

class Block {
public:
    void add_page(const Page& page) { pages_.push_back(page); }
    size_t total_size() const {
        size_t sum = 0;
        for (const auto& p : pages_) sum += p.size();
        return sum;
    }
private:
    std::vector<Page> pages_;
};

class Segment {
public:
    void add_block(const Block& block) { blocks_.push_back(block); }
    size_t total_size() const {
        size_t sum = 0;
        for (const auto& b : blocks_) sum += b.total_size();
        return sum;
    }
private:
    std::vector<Block> blocks_;
};

int main() {
    Page p1{"row1"}, p2{"row2-data"};
    Block b;
    b.add_page(p1);
    b.add_page(p2);

    Segment s;
    s.add_block(b);
    std::cout << "segment total size: " << s.total_size() << "\n";
    return 0;
}
```

### 示例 3：Logger 与 static 成员
```cpp
#include <iostream>
#include <string>

class Logger {
public:
    explicit Logger(const std::string& module) : module_(module) {}

    void info(const std::string& msg) const {
        std::cout << "[INFO] [" << module_ << "] " << msg << "\n";
        ++log_count_;
    }
    static int log_count() { return log_count_; }

private:
    std::string module_;
    static int log_count_;
};

int Logger::log_count_ = 0;

int main() {
    Logger db{"storage"}, net{"network"};
    db.info("page flushed");
    net.info("connection opened");
    std::cout << "total logs: " << Logger::log_count() << "\n";
    return 0;
}
```

### 示例 4：IStorage / IExecutor 抽象接口
```cpp
#include <iostream>
#include <string>
#include <unordered_map>

class IStorage {
public:
    virtual ~IStorage() = default;
    virtual void write(int page_id, const std::string& data) = 0;
    virtual std::string read(int page_id) = 0;
};

class MemoryStorage : public IStorage {
public:
    void write(int page_id, const std::string& data) override {
        pages_[page_id] = data;
    }
    std::string read(int page_id) override {
        auto it = pages_.find(page_id);
        return it == pages_.end() ? "" : it->second;
    }
private:
    std::unordered_map<int, std::string> pages_;
};

class IExecutor {
public:
    virtual ~IExecutor() = default;
    virtual void execute(const std::string& plan) = 0;
};

class ScanExecutor : public IExecutor {
public:
    void execute(const std::string& plan) override {
        std::cout << "ScanExecutor running: " << plan << "\n";
    }
};

void run_plan(IExecutor& exec, const std::string& plan) { exec.execute(plan); }

int main() {
    MemoryStorage storage;
    storage.write(1, "page content");
    std::cout << "read: " << storage.read(1) << "\n";

    ScanExecutor scanner;
    run_plan(scanner, "table_scan users");
    return 0;
}
```

### 示例 5：学生管理系统
```cpp
#include <iostream>
#include <string>
#include <vector>

class Student {
public:
    Student(const std::string& name, int id, double score)
        : name_(name), id_(id), score_(score) {}

    void print() const {
        std::cout << name_ << " [" << id_ << "]: " << score_ << "\n";
    }
    bool passed() const { return score_ >= 60.0; }

private:
    std::string name_;
    int id_;
    double score_;
};

class StudentManager {
public:
    void add(const Student& s) { students_.push_back(s); }

    void print_all() const {
        for (const auto& s : students_) s.print();
    }

    void print_passed() const {
        for (const auto& s : students_)
            if (s.passed()) s.print();
    }

private:
    std::vector<Student> students_;
};

int main() {
    StudentManager mgr;
    mgr.add({"Alice", 101, 85.0});
    mgr.add({"Bob", 102, 55.0});
    mgr.add({"Carol", 103, 92.0});

    std::cout << "All students:\n";
    mgr.print_all();

    std::cout << "\nPassed students:\n";
    mgr.print_passed();
    return 0;
}
```

## 7. 总结

### 关键要点

1. **构造函数建立不变量，析构函数释放资源**：这是 C++ 对象生命周期的核心，也是 RAII 的入口
2. **成员初始化列表优于函数体内赋值**：更高效，且是 const/引用/无默认构造成员的唯一初始化方式
3. **初始化顺序按声明顺序，不是按初始化列表书写顺序**
4. **继承表达 is-a，组合通常更灵活**：复用代码优先考虑组合
5. **多态基类析构函数必须为 virtual，override 是防御性编程**：避免未定义行为并借助编译器检查重写
6. **抽象类即接口**：用纯虚函数定义契约，不同实现通过多态接入

### 核心对照：C++ vs Java 的 OOP

| 特性 | C++ | Java |
|------|-----|------|
| 继承模型 | 支持多重继承（需谨慎使用） | 单继承，接口可多实现 |
| 接口机制 | 纯虚函数抽象类 | `interface` 关键字 |
| 对象语义 | 值语义 + 指针/引用 | 引用语义（对象在堆上） |
| 析构 | 确定性析构，离开作用域即调用 | GC finalization，不可预测 |
| 内存管理 | 手动/RAII/智能指针 | 垃圾回收器 |

### 阶段验收标准

- 能设计清晰的类接口，正确选择 `public`/`private`/`protected`
- 能解释构造函数、析构函数和虚函数的作用与调用时机
- 能用成员初始化列表初始化对象，并说明初始化顺序
- 能用组合减少不必要的继承，用抽象类定义接口
- 能解释 vptr/vtable 与动态分派的基本原理

### 进入下一阶段前
确保能完成以下练习：
- 实现 `Student` 类，支持构造、打印、及格判断
- 用 `Page`/`Block`/`Segment`/`VectorIndex` 为存储引擎做简单建模
- 实现带 `static` 计数器的 `Logger` 类
- 设计 `IStorage`/`IIndex`/`IExecutor` 接口并给出实现
- 在管理类中用 `std::vector` 组合多个对象
- 给多态基类添加虚析构函数，并通过基类指针释放派生类对象

### 推荐项目
- **学生管理系统**：增删查改学生记录，使用 `std::vector<Student>` 和简单菜单
- **存储对象管理系统**：管理 Page/Block/Segment，支持按 ID 查询总大小，体验组合与类的设计

### 下一阶段

[C++ 内存模型阶段](../Ph03-memory-model/03-memory-model.md) — 对象生命周期、拷贝/移动语义与 RAII。
