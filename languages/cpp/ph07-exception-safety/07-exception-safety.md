# C++ 异常、安全与工程规范阶段

> 面向高性能系统、存储引擎方向，本阶段从现代 C++ 进阶到工程级——写出可维护、可诊断、异常安全的 C++ 工程代码：错误处理有边界、资源释放有保证、代码风格可统一。

## 1. 概述
本阶段定位：**能写出可维护、可诊断、异常安全的 C++ 工程代码——用 try/catch/throw 表达低频失败，用异常安全三等级约束资源与状态，用 assert、错误码、日志与命名/头文件/命名空间规范把"写对"变成"必然"**。学完后不再用"裸指针 + 返回值哨兵"处理失败，能说清每个接口的失败方式与所有权，能维护一个多人协作、风格统一的中型工程。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 异常机制 | try/catch/throw、异常对象、catch 匹配与顺序 |
| 异常安全等级 | 基本保证 / 强保证 / 不抛保证（noexcept） |
| 强保证实现 | copy-and-swap、RAII 与栈展开配合 |
| 断言与错误码 | assert、static_assert、ErrCode 枚举与消息表 |
| 日志与诊断 | 日志级别、时间戳、统一格式 |
| 工程规范 | 命名规范、头文件规范、include guard |
| 组织与依赖 | 命名空间分层、依赖方向管理 |

**范围边界**：本阶段承接 ph06 现代 C++（智能指针、optional、std::format）；**不涉及**并发与线程（ph08）、文件/网络系统编程（ph09）、测试与静态分析深入（ph16），也不展开跨语言异常边界与 ABI（ph19），这些留给后续阶段。

## 2. 来源与演变
C++ 的异常机制在 C++98 标准中正式定型，但思想更早：1970 年代 Simula 的"信号"、Ada 的 exception 都是前身。C++ 选择"异常 + RAII"的组合，是因为只有异常能同时做到两件事——**把失败信息沿调用链向上传播**，以及**在传播途中保证资源被确定性释放**（栈展开调用析构）。这正是存储引擎最需要的属性：任何一层失败，都不允许泄漏文件句柄、锁或内存。
异常安全等级（exception safety guarantees）的概念由 **Herb Sutter** 在《Exceptional C++》（2000）中系统化：基本保证（basic guarantee）、强保证（strong guarantee）、不抛保证（no-throw guarantee）成为后来所有 C++ 代码审查的通用语言。C++11 引入 `noexcept` 说明符，把"承诺不抛"从注释变成编译器强制检查的契约，也让"移动构造是否 noexcept"成为决定容器性能的开关（呼应 ph03 的 vector 扩容）；C++17 起 `noexcept` 成为函数类型的一部分，旧式异常说明符 `throw()` 被移除。

| 阶段 | 代表 | 贡献 |
|------|------|------|
| 1970s | Simula / Ada | 异常处理的早期形态 |
| C++98 | ISO C++98 | 正式引入 try/catch/throw 与栈展开 |
| 2000 | Herb Sutter《Exceptional C++》 | 提出异常安全三等级、copy-and-swap |
| C++11 | ISO C++11 | noexcept 说明符、析构默认 noexcept、移动语义配合 |
| C++17 | ISO C++17 | noexcept 纳入函数类型、移除 throw() 说明符 |

演进主线是**把"失败处理"从程序员纪律变成语言契约**：错误码把责任留给调用方，异常把责任交给运行时，noexcept 再把"不抛"变成可验证的接口承诺——每一步都在减少"悄悄出错"的可能。

## 3. 语法与参数
### 3.1 try/catch/throw 与异常对象
`throw` 抛出一个**异常对象**（任意可拷贝类型，惯例是 `std::exception` 及其派生类）；`try` 块包裹可能抛异常的代码；`catch` 按类型匹配捕获。异常沿调用链向上传播，直到遇到匹配的 catch，或到达 `main` 之外导致程序终止。
```cpp
#include <iostream>
#include <stdexcept>
double divide(double a, double b) {
    if (b == 0.0) throw std::runtime_error("divide by zero");
    return a / b;
}
int main() {
    try {
        std::cout << divide(10, 2) << "\n";   // 正常路径
        std::cout << divide(1, 0) << "\n";    // 抛异常，后续语句跳过
        std::cout << "unreachable\n";
    } catch (const std::runtime_error& e) {   // 按引用捕获
        std::cerr << "caught: " << e.what() << "\n";
    } catch (const std::exception& e) {       // 基类兜底
        std::cerr << "generic: " << e.what() << "\n";
    }
    std::cout << "program continues\n";
    return 0;
}
```
要点：
- **按值抛出、按引用捕获**：`catch (const std::exception& e)` 避免拷贝与对象切片
- catch 按**声明顺序**匹配：派生类 catch 必须写在基类 catch 之前，否则永远轮不到
- **坑：滥用 `catch (...)`**——它能捕获一切但拿不到异常对象，只配做"记录后重新抛出/退出"的最后防线，平时用它掩盖错误会让 bug 无从诊断
### 3.2 异常安全三等级与 copy-and-swap
异常安全等级描述"一个操作抛出异常后对象处于什么状态"，是设计资源类时的通用语言：

| 等级 | 承诺 | 对调用方的意义 |
|------|------|---------------|
| 基本保证（basic） | 无资源泄漏、对象不变式保持、状态"合法但未指定" | 可继续使用，但内容可能变了 |
| 强保证（strong） | 操作要么完全成功，要么对象保持**调用前原状** | 失败 = 没发生过，天然支持重试/事务 |
| 不抛保证（no-throw） | 承诺绝不抛出 | 用于析构、swap、移动等关键路径 |

**copy-and-swap** 是实现强保证赋值的标准手法：`operator=` 按值接收参数（拷贝发生在进入函数体之前），然后只做 `noexcept` 的 swap——拷贝若失败，`*this` 尚未被触碰。核心写法如下，完整类见示例 2：
```cpp
StringBuf& operator=(StringBuf other) noexcept {  // 传值：拷贝先于函数体完成
    swap(other);        // 拷贝失败时异常发生在函数体外，*this 不变
    return *this;
}
void swap(StringBuf& other) noexcept { std::swap(data_, other.data_); }
```
要点：
- **强保证 ≠ 永不失败**：失败时对象状态不变，代价是"先拷贝后交换"，可能比就地修改慢
- copy-and-swap 同时消灭自赋值判断与拷贝/移动赋值重复代码；swap 必须 `noexcept`
- 容器操作默认只承诺基本保证（如 `std::vector::push_back` 可能移动元素）；接口文档应写明承诺哪一级
- **接口应清晰表达所有权与失败方式**：异常表达"会失败"、noexcept 表达"不会失败"、值/引用/unique_ptr 表达所有权——roadmap 必会概念
### 3.3 析构函数与 noexcept
自 C++11 起**析构函数默认 `noexcept(true)`**：析构里抛异常会直接调用 `std::terminate` 终止进程——因为栈展开期间析构再抛异常会造成"双重异常"，运行时无从处理。
```cpp
#include <iostream>
#include <stdexcept>
struct Bad {
    ~Bad() { throw std::runtime_error("dtor throws"); }  // 致命：默认 noexcept
};
int main() {
    try {
        Bad b;                    // 离开作用域析构抛出 → terminate
    } catch (...) {
        std::cout << "never reached\n";   // 程序在到达这里前已中止
    }
    return 0;
}
```
要点：
- **坑：析构函数抛异常导致 terminate**——析构中失败只能记录日志或吞掉，绝不能抛出
- `noexcept` 是接口契约：移动构造/移动赋值/swap 都应声明 noexcept（ph03 已见 vector 扩容依赖它）；noexcept 函数内抛出同样直接 terminate
- 不在析构中做可能失败的工作：需要"最后机会"保存数据时，提供显式的 `close()`/`flush()` 并检查返回值
### 3.4 构造函数异常与 RAII 配合
构造函数是唯一"失败后对象不存在"的场合：**构造失败用异常表达**，已构造完成的成员按逆序自动析构、不会泄漏——这正是 RAII 与异常的组合威力。
```cpp
#include <iostream>
#include <stdexcept>
class Connection {
public:
    Connection() { std::cout << "Connection acquired\n"; }
    ~Connection() { std::cout << "Connection released\n"; }
};
class Service {
public:
    explicit Service(int retries) : conn_() {        // 成员先构造
        if (retries < 0)
            throw std::invalid_argument("retries must be >= 0");
    }
private:
    Connection conn_;          // 已构造的成员：异常时自动析构
};
int main() {
    try {
        Service s(-1);         // 抛异常 → conn_ 自动析构，无泄漏
    } catch (const std::exception& e) {
        std::cerr << "caught: " << e.what() << "\n";
    }
    Service ok(3);             // 正常路径
    return 0;
}
```
要点：
- **必会概念：构造失败可以用异常表达**——替代"半初始化对象 + is_valid() 标志"的 C 风格写法
- 构造函数体内抛出，已构造成员与基类自动析构；释放只靠成员析构，因此成员应是 RAII 类型而非裸指针
- 构造失败时对象不进入作用域、析构不会被调用——"裸 new 先于异常出现"的写法是泄漏源
### 3.5 assert 与错误码设计
`assert` 检查**程序不变式**（应当永远为真），`static_assert` 在编译期检查；错误码是值语义的失败表达，零开销、可跨边界。分工：**assert 查内部错误、异常查外部失败、错误码服务底层与热路径**。
```cpp
#include <cassert>
#include <iostream>
enum class ErrCode : int {     // 错误码体系：枚举集中定义，杜绝魔法数字
    Ok = 0, NotFound = 1, InvalidParam = 2, IoError = 3,
};
int main() {
    static_assert(sizeof(ErrCode) == sizeof(int), "ErrCode must fit int");
    ErrCode e = ErrCode::NotFound;
    assert(e != ErrCode::Ok);                  // 内部不变式（debug 有效）
    std::cout << "code=" << static_cast<int>(e) << "\n";
    return 0;
}
```
要点：
- **assert 在 `NDEBUG` 下整条消失**：不能用于用户输入/运行期数据校验，那些交给异常或错误码
- 错误码枚举 + 消息表集中管理，转换用 `static_cast<int>`（enum class 不隐式转整数，见 ph06）
- **坑：错误码与异常混用**——同一层要么返回码要么抛异常，混用让调用方无所适从；边界统一策略见示例 3
### 3.6 日志与命名规范
日志是工程可诊断性的第一道防线：统一级别（DEBUG/INFO/WARN/ERROR）、统一格式（级别 + 时间戳 + 消息）、错误日志必须带上下文。命名规范让代码"一眼可读"，团队内必须统一：

| 类别 | 规范 | 示例 |
|------|------|------|
| 类型 / 类 | PascalCase | `ConfigLoader` |
| 函数 / 方法 | camelCase（或 snake_case，选一统一） | `loadConfig()` |
| 变量 | snake_case | `config_path` |
| 常量 | kCamel 或全大写 | `kMaxRetries` |
| 宏 | 全大写 + 下划线（尽量少用） | `PH07_MAX_RETRIES` |
| 私有成员 | 尾部下划线 | `max_retries_` |

日志规范要点：
- 级别可过滤：生产默认 INFO，排查问题开 DEBUG；ERROR 只表示"需要人介入"
- **错误日志必须含上下文**：`write failed: path=/tmp/x, errno=28` 而非孤立 `failed`；不打印密钥等敏感信息；日志是 IO 热点，实现时预留线程安全（见示例 4）
### 3.7 头文件规范与 include guard
多文件工程的头文件质量决定编译速度与可维护性：**自包含、防重复包含、只放声明**。
```cpp
// config.h —— 头文件自包含 + include guard
#ifndef TENET_CONFIG_H_
#define TENET_CONFIG_H_
#include <string>          // 用到的都要显式包含，不依赖"碰巧被间接包含"
namespace tenet {
struct Config {
    int port = 8080;
    std::string host = "127.0.0.1";
};
}  // namespace tenet
#endif  // TENET_CONFIG_H_
```
要点：
- **include guard（`#ifndef`+`#define`）与 `#pragma once` 二选一并在全工程统一**：guard 可移植性最强，`#pragma once` 更简洁、防宏名冲突
- 头文件必须**自包含且可独立编译**：`g++ -fsyntax-only config.h` 通过才算合格
- 头文件只放声明、内联函数与模板定义，实现放 `.cpp`，避免 ODR 违反
- **头文件内禁止 `using namespace std;`**：会把命名空间污染扩散给所有包含者
### 3.8 命名空间与依赖管理
命名空间防止符号冲突、表达归属；依赖管理决定"改动一个模块要重编/重测多少东西"。
```cpp
#include <iostream>
// 命名空间分层：库名::模块名（detail 表示内部实现，不对外承诺）
namespace tenet {
namespace config {
struct Config { int port = 8080; };
Config load(const char* path);          // 公开接口
namespace detail { constexpr int kMaxRetries = 3; }
}  // namespace config
}  // namespace tenet
namespace {                             // 匿名命名空间：本翻译单元内部链接
int file_local_counter = 0;
}
int main() {
    tenet::config::Config c;            // 完整限定；局部可用 using 引入
    std::cout << "port=" << c.port << "\n";
    return 0;
}
```
要点：
- 库代码永远放在自己的命名空间内；头文件不要 `using namespace`，.cpp 内可局部 `using tenet::config::Config;`
- **匿名命名空间**是"文件内 static"的现代写法：符号内部链接，不污染全局
- **依赖方向**：底层模块（error、util）不依赖上层业务；依赖环会让构建与单元测试寸步难行——用前向声明、接口抽象切断环

## 4. 底层原理
### 4.1 异常的实现机制
异常采用**表驱动**实现，正常路径零开销：编译器为每个"可能抛出"的函数生成异常表，运行时在 throw 时查表驱动**栈展开（stack unwinding）**——沿调用链逐帧查找匹配的 catch，沿途**按构造逆序调用析构**销毁栈上对象。GCC/Clang 遵循 **Itanium C++ ABI**：异常表位于 `.gcc_except_table`（含 LSDA——函数区域内需要析构的对象与 catch 类型信息），由 personality routine 在展开时查询。

| 阶段 | 做什么 | 成本 |
|------|--------|------|
| 编译期 | 生成异常表（LSDA / .gcc_except_table） | 代码体积少量增加 |
| 正常路径 | 无异常时零额外指令 | 零 |
| throw 路径 | 分配异常对象、查表、逐帧展开、调用析构、RTTI 匹配 | 昂贵（微秒级） |
| 捕获之后 | 恢复栈帧与寄存器，继续执行 | 与普通返回相近 |

**关键结论：异常是"正常路径零成本、失败路径昂贵"的机制**——适合低频失败（打开文件、配置错误），不适合热循环内的高频失败（那里用错误码）。
### 4.2 noexcept 与 terminate 的关系
`noexcept` 是编译器强制的承诺：**函数内一旦抛出，立即调用 `std::terminate()`（默认 abort 终止进程）**。注意标准允许实现**不展开栈**直接 terminate——所以 noexcept 函数抛出时，其栈上 RAII 对象的析构不一定执行。因此：
- 析构函数默认 `noexcept(true)`：栈展开期间再抛异常会造成双重异常，只能 terminate
- 移动构造/swap 声明 noexcept：容器扩容走移动而非拷贝（ph03 3.7）；移动真抛出时容器状态不可恢复
- `noexcept` 不是"省略 try/catch 的借口"：声明前必须确认函数体与所有被调用的非 noexcept 操作都不会抛
### 4.3 异常安全的 RAII 保证链
RAII 与异常的配合形成一条**环环相扣的保证链**：

| 环节 | 保证 |
|------|------|
| 构造成功 | 资源已获取；此后无论发生什么，析构必被执行 |
| 异常抛出 | 栈展开按构造逆序调用所有存活对象的析构 |
| 析构 noexcept | 展开过程自身不失败、不产生双重异常 |
| 结论 | 资源释放与错误传播**解耦**——这就是 C++ 不需要 finally 的原因 |

链条的每一环都依赖上一环：成员必须是 RAII 类型（否则构造中途失败会泄漏）、析构必须不抛（否则展开中断）、资源必须在构造中获取（否则存在未初始化窗口）。理解这条链，就理解了为什么"裸 new + try/catch + 手动 delete"是反模式。
### 4.4 copy-and-swap 为什么是强保证
以 `operator=(StringBuf other)` 为例，分三步论证：
1. **拷贝阶段**：传值参数在进入函数体之前完成拷贝（或移动）——若拷贝抛异常（如 `bad_alloc`），异常发生在调用处、`*this` 尚未被触碰，**对象保持原状**
2. **交换阶段**：swap 只交换指针与大小，且声明 `noexcept`——**不可能失败**
3. **释放阶段**：旧资源随参数 `other` 的析构释放，不依赖 `*this` 的状态

三步中只有第一步可能失败，而它发生在任何修改之前——所以赋值"要么成功、要么对象不变"，正是**强异常保证**。对比传统写法"先 delete 旧资源再拷贝新数据"：delete 之后拷贝失败，对象已半破坏，连基本保证都达不到。代价是强保证多一次拷贝（或依赖移动），大对象赋值常用"移动 + swap"折中。

## 5. 使用场景
| 场景 | 涉及知识点 |
|------|-----------|
| 打开文件/连接/锁等资源获取可能失败 | RAII + 构造函数抛异常 |
| 需要"要么成功要么原样"的赋值/事务操作 | copy-and-swap 强保证 |
| 底层系统调用、热路径高频失败 | 错误码设计（ErrCode + 消息表） |
| 跨模块边界的失败策略统一 | 错误码与异常分层（示例 3） |
| 程序不变式校验（内部逻辑） | assert / static_assert |
| 用户输入/参数校验（外部输入） | 前置条件异常 invalid_argument |
| 故障诊断与可观测性 | 日志模块（级别 + 时间戳） |
| 多文件工程组织与协作 | 头文件规范 + 命名空间 + 命名规范 |

**不适合**此阶段的事项：
- **并发下的异常**（ph08）：锁内抛出、线程函数未捕获异常导致 terminate，需与线程安全一起设计
- **跨语言异常边界 / ABI**（ph19）：**异常穿过 C 边界是未定义行为**，跨语言必须转换为错误码
- 热循环内高频失败用异常：失败路径微秒级成本，高频失败请用错误码
- 旧式异常说明符 `throw()`（C++17 已移除）：新代码只使用 `noexcept`/`noexcept(false)`

## 6. 代码示例
### 示例 1：异常安全资源封装（RAII 文件句柄 + 异常路径自动释放）
```cpp
// 编译：g++ -std=c++17 ex1_raii_file.cpp -o ex1
#include <cstdio>
#include <iostream>
#include <stdexcept>
#include <string>
class FileHandle {
public:
    explicit FileHandle(const std::string& path, const char* mode = "rb") {
        file_ = std::fopen(path.c_str(), mode);
        if (!file_) throw std::runtime_error("cannot open file: " + path);
        std::cout << "[open] " << path << "\n";
    }
    ~FileHandle() {
        if (file_) { std::fclose(file_); std::cout << "[close]\n"; }
    }
    FileHandle(const FileHandle&) = delete;              // 禁拷贝、允移动
    FileHandle& operator=(const FileHandle&) = delete;
    FileHandle(FileHandle&& other) noexcept : file_(other.file_) { other.file_ = nullptr; }
    FileHandle& operator=(FileHandle&& other) noexcept {
        if (this != &other) {
            if (file_) std::fclose(file_);
            file_ = other.file_;
            other.file_ = nullptr;
        }
        return *this;
    }
    size_t read(void* buf, size_t len) {
        if (!file_) throw std::logic_error("read on moved-from handle");
        return std::fread(buf, 1, len, file_);
    }
private:
    std::FILE* file_ = nullptr;
};
void process(const std::string& path) {
    FileHandle f(path);                  // 打开失败 → 异常，f 根本不存在
    char buf[64];
    size_t n = f.read(buf, sizeof(buf)); // 这里即使抛异常…
    std::cout << "read " << n << " bytes\n";
    // …f 的析构依然执行，句柄自动关闭（栈展开保证）
}
int main() {
    try {
        process("/tmp/no_such_file_ph07.txt");   // 异常路径
    } catch (const std::exception& e) {
        std::cerr << "caught: " << e.what() << "\n";
    }
    process("/etc/hosts");                        // 正常路径
    return 0;
}
```
### 示例 2：copy-and-swap 实现强异常保证的类
```cpp
// 编译：g++ -std=c++17 ex2_copy_swap.cpp -o ex2
#include <cstring>
#include <iostream>
#include <utility>
class StringBuf {
public:
    explicit StringBuf(const char* s = "") {
        size_ = std::strlen(s);
        data_ = new char[size_ + 1];
        std::strcpy(data_, s);
    }
    StringBuf(const StringBuf& other) : StringBuf(other.data_) {}  // 深拷贝
    StringBuf(StringBuf&& other) noexcept
        : data_(other.data_), size_(other.size_) {
        other.data_ = nullptr;
        other.size_ = 0;
    }
    ~StringBuf() { delete[] data_; }
    StringBuf& operator=(StringBuf other) noexcept {  // 强保证赋值
        swap(other);
        return *this;
    }
    void swap(StringBuf& other) noexcept {
        using std::swap;
        swap(data_, other.data_);
        swap(size_, other.size_);
    }
    const char* c_str() const { return data_ ? data_ : ""; }
    size_t size() const { return size_; }
private:
    char* data_;
    size_t size_;
};
int main() {
    StringBuf a("hello"), b("world");
    a = b;                                  // 拷贝赋值
    std::cout << "a=" << a.c_str() << "\n";
    StringBuf c("temp");
    c = std::move(b);                       // 移动赋值（走移动构造参数）
    std::cout << "c=" << c.c_str() << " b.size=" << b.size() << "\n";
    a = a;                                  // 自赋值安全（传值拷贝 + swap）
    std::cout << "self-assign ok: " << a.c_str() << "\n";
    return 0;
}
```
### 示例 3：错误码与异常的策略分层（底层错误码、上层异常）
```cpp
// 编译：g++ -std=c++17 ex3_error_layering.cpp -o ex3
#include <iostream>
#include <stdexcept>
#include <string>
// 底层：错误码体系 —— 贴近资源/系统层，零异常开销、可跨边界
enum class ErrCode : int {
    Ok = 0, NotFound = 1, InvalidParam = 2, IoError = 3,
};
struct Status {
    ErrCode code = ErrCode::Ok;
    std::string message;
    bool ok() const { return code == ErrCode::Ok; }
};
Status read_config_impl(const std::string& path) {  // 底层：返回错误码，不抛异常
    if (path.empty()) return {ErrCode::InvalidParam, "empty path"};
    if (path != "/tmp/ok.conf") return {ErrCode::NotFound, "no such file: " + path};
    return {ErrCode::Ok, ""};
}
// 上层：异常 —— 面向调用方表达"无法继续"的业务语义
class ConfigError : public std::runtime_error {
public:
    ConfigError(const std::string& msg, ErrCode code)
        : std::runtime_error(msg), code_(code) {}
    ErrCode code() const { return code_; }
private:
    ErrCode code_;
};
std::string load_config(const std::string& path) {   // 边界转换：错误码 → 异常
    Status st = read_config_impl(path);
    if (!st.ok())
        throw ConfigError("load config failed: " + st.message, st.code);
    return "ok";
}
int main() {
    try {
        load_config("/tmp/missing.conf");
    } catch (const ConfigError& e) {
        std::cerr << "ConfigError code=" << static_cast<int>(e.code())
                  << " msg=" << e.what() << "\n";
    }
    std::cout << "loaded: " << load_config("/tmp/ok.conf") << "\n";
    return 0;
}
```
### 示例 4：日志模块（级别 + 时间戳 + 线程安全预留）
```cpp
// 编译：g++ -std=c++17 ex4_logger.cpp -o ex4 -pthread
#include <chrono>
#include <ctime>
#include <iostream>
#include <mutex>
#include <string>
enum class LogLevel { Debug = 0, Info, Warn, Error };
class Logger {
public:
    static Logger& instance() {            // 简单单例（ph08 之前够用）
        static Logger inst;
        return inst;
    }
    void set_min_level(LogLevel lv) { min_level_ = lv; }
    void log(LogLevel lv, const std::string& msg) {
        if (lv < min_level_) return;                 // 级别过滤
        std::lock_guard<std::mutex> lock(mutex_);    // 线程安全预留
        std::cout << "[" << level_name(lv) << "] "
                  << timestamp() << " " << msg << "\n";
    }
private:
    Logger() = default;
    static const char* level_name(LogLevel lv) {
        switch (lv) {
            case LogLevel::Debug: return "DEBUG";
            case LogLevel::Info:  return "INFO";
            case LogLevel::Warn:  return "WARN";
            case LogLevel::Error: return "ERROR";
        }
        return "?";
    }
    static std::string timestamp() {
        std::time_t t = std::chrono::system_clock::to_time_t(
                            std::chrono::system_clock::now());
        char buf[32];
        std::strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", std::localtime(&t));
        return buf;
    }
    LogLevel min_level_ = LogLevel::Debug;
    std::mutex mutex_;
};
int main() {
    Logger& log = Logger::instance();
    log.set_min_level(LogLevel::Info);     // 过滤 Debug
    log.log(LogLevel::Debug, "this will be filtered");
    log.log(LogLevel::Info, "config loaded");
    log.log(LogLevel::Warn, "disk usage high");
    log.log(LogLevel::Error, "write failed: disk full");
    return 0;
}
```
### 示例 5：断言与防御式编程（assert / static_assert / 前置条件检查）
```cpp
// 编译：g++ -std=c++17 ex5_assert.cpp -o ex5
#include <cassert>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <vector>
static_assert(sizeof(int) >= 4, "int must be at least 32 bits");  // 编译期断言
class Config {
public:
    explicit Config(int max_connections) : max_connections_(max_connections) {
        if (max_connections <= 0)             // 前置条件：外部输入用异常（release 也生效）
            throw std::invalid_argument("max_connections must be positive");
    }
    int max_connections() const { return max_connections_; }
private:
    int max_connections_;
};
double safe_sqrt(double x) {
    assert(x >= 0.0);              // 前置条件：调用方保证（debug 检查）
    return std::sqrt(x);
}
int main() {
    std::cout << "sizeof(int)=" << sizeof(int) << "\n";
    try {
        Config c(0);               // 触发前置条件异常
    } catch (const std::invalid_argument& e) {
        std::cerr << "caught: " << e.what() << "\n";
    }
    std::cout << "sqrt(4)=" << safe_sqrt(4.0) << "\n";
    // safe_sqrt(-1.0);            // debug 构建触发 assert 中止；NDEBUG 下是 UB
    std::vector<int> v{1, 2, 3};
    assert(v.size() == 3);         // 后置条件/不变式
    std::cout << "vector ok\n";
    return 0;
}
```

## 7. 总结
### 关键要点
1. **异常是"低频失败"的机制**：正常路径零开销、失败路径微秒级——热循环高频失败用错误码
2. **异常安全三等级**：基本（不泄漏、状态合法）/ 强（要么成功要么原状）/ 不抛（noexcept）
3. **copy-and-swap 是实现强保证的标准手段**：传值拷贝（失败在修改前）+ noexcept swap
4. **析构函数永不抛异常**（默认 noexcept）：抛出即 terminate；失败只能记录或吞掉
5. **构造失败用异常表达**：已构造成员自动析构、无泄漏，替代"半初始化 + is_valid()"
6. **异常与错误码按边界统一**：底层错误码、上层异常，在边界处集中转换（示例 3）
7. **assert 查不变式、异常查输入**：assert 在 NDEBUG 下消失，不能用于用户输入校验
8. **noexcept 是接口契约**：移动/swap/析构声明 noexcept；noexcept 函数抛出直接 terminate 且栈可能不展开
9. **catch(...) 只做最后防线**：拿不到异常对象，滥用掩盖 bug；**工程规范决定可维护性**：统一命名、头文件自包含 + guard、命名空间分层与依赖方向
### 跨语言对比：错误处理策略
| 维度 | C++ 异常 | C 错误码 | Java 异常 | Go error | Rust Result |
|------|---------|---------|----------|----------|-------------|
| 失败表达 | throw 异常对象（类型化） | 返回 int/errno | throw 异常对象 | 返回 error 接口值 | 返回 Result\<T,E\> |
| 是否强制处理 | 不强制，漏接则 terminate | 易被忽略 | 检查型强制 / 非检查型可选 | 惯例必须检查 | 编译期警告（#[must_use]） |
| 错误信息 | what() + 异常类型 | errno + strerror | getMessage() + 类型 | Error() + 包装链 | Display + 类型化 E |
| 资源清理 | RAII 栈展开 | 手动 goto cleanup | finally / try-with-resources | defer | Drop trait |
| 正常路径开销 | 零（表驱动） | 零 | 零 | 零 | 零 |
| 失败路径开销 | 昂贵（栈展开） | 零（值返回） | 昂贵（栈展开） | 零 | 零 |

一句话：C++ 与 Java 用异常表达"低频、严重"的失败，C 与 Go 用返回值把失败变成显式数据，Rust 用 Result 把失败变成**编译期可见的类型**——**本阶段的收获是学会在 C++ 内部按边界选择并统一策略**。
### 阶段验收标准
- 能解释异常安全基本保证与强保证，并说明 copy-and-swap 为什么是强保证
- 能说出析构函数为何不抛异常、noexcept 函数抛出导致 terminate
- 能为一个模块设计清晰的错误处理策略：底层错误码 + 上层异常 + 边界转换
- 能写出统一风格的代码：命名规范、头文件 guard、命名空间分层
- 能完成日志模块、配置读取模块，并给已有代码补上单元测试
### 进入下一阶段前
确保能完成以下练习：
- 实现**日志模块**：级别过滤 + 时间戳 + 线程安全预留（互斥锁），支持输出到 stderr/文件
- 实现**配置读取模块**：文件 → 键值解析 → 类型转换，非法格式用异常/错误码明确表达
- 设计**错误码体系**：枚举集中定义 + 消息表 + 与异常的转换函数（练习示例 3 的分层）
- 给已有项目（如 ph06 的配置管理模块）**补单元测试**：正常路径 + 异常路径都要覆盖
- 用 copy-and-swap 重写一个管理裸资源的类，验证赋值失败时对象保持原状
### 推荐项目
- **工程化配置库**：INI/键值解析、类型转换与默认值、错误码体系 + 异常分层、日志接入、头文件规范与命名空间分层——覆盖本阶段几乎全部知识点，roadmap 指定项目
- **异常安全资源封装**：把文件/连接/内存池封装成 RAII 类，禁拷贝允移动、copy-and-swap 强保证赋值、异常路径自动释放——直接服务存储引擎的连接与 WAL 管理
### 下一阶段
[并发编程阶段](../ph08-concurrency/08-concurrency.md) ——std::thread、mutex、condition_variable、async/future、atomic。
