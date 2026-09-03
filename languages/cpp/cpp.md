# C++ 语言学习 Roadmap

> 面向现代 C++、高性能系统、数据库内核、存储引擎、向量检索和 AI 推理引擎方向，重点从对象生命周期、RAII、STL、并发、内存布局和工程化能力建立 C++ 系统工程思维。

## 1. C++ 基础语法阶段

> 📖 详细展开版见 [ph01-basic-syntax/01-basic-syntax.md](./ph01-basic-syntax/01-basic-syntax.md)

### 目标

能写简单 C++ 程序，理解 C++ 相比 C 在类型、库和抽象上的变化。

### 学习内容

- iostream、namespace、bool、const
- 控制流：if、switch、for、while（与 C 相同）
- auto 类型推导、范围 for（range-for）
- 引用、函数重载、默认参数
- new/delete、nullptr
- std::string、std::vector

### 必会概念

- 引用不是指针语法糖，语义上代表别名
- const 是接口设计的一部分
- 优先使用标准库类型而不是裸数组和 char 指针
- auto 在编译期推导类型，不损失运行时性能

### 示例

```cpp
#include <iostream>
#include <string>

int main() {
    std::string name = "C++";
    std::cout << "Hello, " << name << std::endl;
    return 0;
}
```

### 练习

- 输入输出练习
- 字符串处理
- 用 vector 改写数组程序
- 用 string 改写 C 风格字符串

### 阶段验收

- 能写出基础 C++ 程序
- 能说明引用、指针和值传递的区别
- 能使用 string 和 vector 解决基础问题

### 推荐项目

- 简单通讯录
- 词频统计工具

## 2. 面向对象 OOP 阶段

> 📖 详细展开版见 [ph02-oop/02-oop.md](./ph02-oop/02-oop.md)

### 目标

理解类、对象、封装、继承、多态和接口设计。

### 学习内容

- class、public/private/protected
- 构造函数、析构函数、成员函数
- this 指针、static 成员
- 封装、继承、多态、virtual、抽象类

### 必会概念

- 构造函数建立对象不变量
- 析构函数释放资源
- 虚析构函数用于多态基类
- 继承表达 is-a，组合通常更灵活

### 示例

```cpp
class Page  {
public:
    explicit Page (int index) : index_(index) {}
    void Start() const { std::cout << index_ << std::endl; }
private:
    int index_;
};
```

### 练习

- 学生类
- Page/Block/Segment/VectorIndex 建模
- Logger 类
- IStorage / IIndex / IExecutor

### 阶段验收

- 能设计清晰类接口
- 能解释构造、析构和虚函数
- 能用组合减少不必要继承

### 推荐项目

- 学生管理系统
- 存储对象管理系统

## 3. C++ 内存模型阶段

> 📖 详细展开版见 [ph03-memory-model/03-memory-model.md](./ph03-memory-model/03-memory-model.md)

### 目标

理解对象生命周期、拷贝、移动和资源管理。

### 学习内容

- 栈对象、堆对象
- 构造与析构顺序
- 深拷贝、浅拷贝
- 拷贝构造、拷贝赋值
- 移动构造、移动赋值
- 左值、右值、std::move

### 必会概念

- 对象生命周期决定资源释放时机
- 资源管理应绑定对象生命周期
- move 不移动本身，只允许移动语义生效
- 手写资源类要考虑异常安全

### 示例

```cpp
class Buffer {
public:
    explicit Buffer(size_t size) : data_(new char[size]) {}
    ~Buffer() { delete[] data_; }
private:
    char* data_;
};
```

### 练习

- 简单 String 类
- 动态数组类
- 支持移动构造的 Buffer
- 用 RAII 管理文件句柄

### 阶段验收

- 能解释深拷贝和浅拷贝风险
- 能说清五个特殊成员函数
- 能把手动资源管理改造成 RAII

### 推荐项目

- RAII 文件类
- 动态数组类

## 4. STL 标准库阶段

> 📖 详细展开版见 [ph04-stl/04-stl.md](./ph04-stl/04-stl.md)

### 目标

熟练使用 STL 容器、算法和迭代器写高效代码。

### 学习内容

- vector、array、deque、list
- map、unordered_map、set、unordered_set
- queue、stack、priority_queue
- std::span、std::string_view（零开销视图）
- sort、find、count、for_each、accumulate
- std::ranges（C++20 管道式操作）
- iterator、迭代器失效

### 必会概念

- 容器选择影响复杂度和内存布局
- vector 是默认优先选择的顺序容器
- unordered_map 依赖哈希质量
- string_view 和 span 不拥有数据，适合函数参数和只读视图
- std::ranges 让算法调用更简洁，错误信息比传统迭代器对更清晰
- 迭代器失效是常见 bug 来源

### 示例

```cpp
std::vector<int> nums = {3, 1, 5, 2};
std::sort(nums.begin(), nums.end());
```

### 练习

- 词频统计
- ID 查询表
- 优先级任务调度
- 用 STL 重写链表项目

### 阶段验收

- 能按场景选择合适容器
- 能解释常见操作复杂度
- 能避免迭代器失效

### 推荐项目

- LRU Cache
- 日志统计工具

## 5. 模板与泛型编程、元编程阶段

> 📖 详细展开版见 [ph05-templates/05-templates.md](./ph05-templates/05-templates.md)

### 目标

理解 C++ 的通用库能力，能写类型安全的泛型组件，能进行元编程代码编写。

### 学习内容

- 函数模板、类模板
- typename、template 消歧义规则
- 模板特化、偏特化
- 非类型模板参数
- concept、requires 子句（C++20 约束模板）
- 泛型容器和泛型算法
- 编译期计算和类型推导、代码生成

### 必会概念

- 模板在编译期实例化
- concept 在编译期约束模板参数，错误信息比 SFINAE 清晰可读
- 泛型代码应表达最小能力需求
- 复杂元编程编译期计算
- 编译期递归与 if constexpr
- 类型列表（typelist）与基本变换
- constexpr 函数

### 示例

```cpp
template <typename T>
T Max(T a, T b) {
    return a > b ? a : b;
}

template<unsigned N>
struct Factorial {
    static const unsigned value = N * Factorial<N-1>::value;
};
template<>
struct Factorial<0> {
    static const unsigned value = 1;
};
// Factorial<5>::value 在编译期就是 120
```

### 练习

- 泛型 Max
- 泛型 Stack
- 用 concept 约束泛型函数
- 简单 Optional
- 简单 TMP 模板元编程库

### 阶段验收

- 能写函数模板和类模板
- 能用 concept 约束模板参数，替代 enable_if / SFINAE
- 能用模板减少重复代码
- 能进行简单元编程开发

### 推荐项目

- 泛型 Ring Buffer
- 固定容量容器

## 6. 现代 C++（C++11~C++23）阶段

> 📖 详细展开版见 [ph06-modern-cpp/06-modern-cpp.md](./ph06-modern-cpp/06-modern-cpp.md)

### 目标

掌握 C++11 之后的现代写法，覆盖 C++17/20 关键特性，减少裸资源和样板代码。

### 学习内容

- auto、decltype、nullptr、范围 for
- lambda、std::function
- unique_ptr、shared_ptr、weak_ptr
- optional、variant、any
- std::format、std::print（C++20/23 类型安全格式化）
- <=> 三路比较运算符（C++20）
- constexpr、enum class、using、noexcept

### 必会概念

- unique_ptr 表示唯一所有权
- shared_ptr 表示共享所有权，但不是默认选择
- optional 表示可能不存在的值
- std::format 类型安全、可扩展，替代 printf 和 iostream 拼接
- <=> 可自动生成一致性比较，减少手写运算符重载
- enum class 避免传统枚举污染命名空间

### 示例

```cpp
auto sensor = std::make_unique<Sensor>();
sensor->Read();

// C++20 std::format
std::string msg = std::format("sensor {} value={}", id, val);
```

### 练习

- 用 unique_ptr 管理对象
- 用 optional 表示查找结果
- 用 std::format 重写字符串拼接
- 用 lambda 定义排序规则
- 用 variant 表示多种状态

### 阶段验收

- 能用智能指针替代裸 new/delete
- 能解释所有权关系
- 能用 std::format 替代 iostream 和 printf 风格输出
- 能写出 C++17/20 风格代码

### 推荐项目

- 配置管理模块
- 状态类型建模 demo

## 7. 异常、安全与工程规范阶段

> 📖 详细展开版见 [ph07-exception-safety/07-exception-safety.md](./ph07-exception-safety/07-exception-safety.md)

### 目标

写出可维护、可诊断、异常安全的 C++ 工程代码。

### 学习内容

- try/catch/throw
- 异常安全等级
- assert、错误码设计
- 日志、命名规范、头文件规范
- 命名空间与依赖管理

### 必会概念

- 构造失败可以用异常表达
- 析构函数不应抛出异常
- 异常和错误码要按边界统一
- 接口应清晰表达所有权和失败方式

### 示例

```cpp
try {
    Run();
} catch (const std::exception& e) {
    std::cerr << e.what() << std::endl;
}
```

### 练习

- 日志模块
- 配置读取模块
- 错误码体系
- 给已有项目补单元测试

### 阶段验收

- 能解释异常安全基本保证和强保证
- 能设计清晰错误处理策略
- 能维护统一代码风格

### 推荐项目

- 工程化配置库
- 异常安全资源封装

## 8. 并发编程阶段

> 📖 详细展开版见 [ph08-concurrency/08-concurrency.md](./ph08-concurrency/08-concurrency.md)

### 目标

能写安全的多线程 C++ 程序。

### 学习内容

- thread、mutex、lock_guard、unique_lock
- condition_variable、atomic
- future、async
- 线程池、生产者消费者
- 死锁、竞态条件、内存序基础
- std::jthread、std::stop_token（C++20 可中断线程）
- std::semaphore、std::latch、std::barrier（C++20 同步原语）
- 协程基础：co_await、co_return（C++20）

### 必会概念

- 数据竞争是未定义行为
- 锁的粒度影响性能和正确性
- RAII 锁能避免忘记 unlock
- condition_variable 必须配合条件谓词
- jthread 析构时自动 join，配合 stop_token 实现协作取消
- C++20 协程是无栈协程，编译器将函数体转换为可恢复状态机

### 示例

```cpp
std::thread t([] {
    std::cout << "worker" << std::endl;
});
t.join();
```

### 练习

- 多线程计数器
- 线程安全队列
- 生产者消费者
- 简单线程池
- 用 jthread + stop_token 实现可取消任务

### 阶段验收

- 能避免数据竞争和死锁
- 能用条件变量实现等待通知
- 能解释 atomic 和 mutex 的适用场景

### 推荐项目

- 异步日志系统
- 多线程任务调度器

## 9. 文件、网络与系统编程阶段

> 📖 详细展开版见 [ph09-files-network/09-files-network.md](./ph09-files-network/09-files-network.md)

### 目标

能用 C++ 写真实系统程序。

### 学习内容

- 文件读写、二进制文件
- JSON、配置文件
- socket、TCP/UDP、HTTP 基础
- Linux 系统调用
- 进程、线程、动态库、插件机制

### 必会概念

- IO 必须处理失败和超时
- 配置解析要给出可诊断错误
- 网络协议要处理边界和粘包
- 动态库接口要稳定

### 示例

```cpp
std::ifstream in("config.json");
if (!in) {
    throw std::runtime_error("open config failed");
}
```

### 练习

- 日志文件系统
- TCP echo server
- 简单 HTTP server
- 文件传输工具

### 阶段验收

- 能写文件和网络错误处理
- 能封装系统资源
- 能设计基础配置模块

### 推荐项目

- 配置中心客户端
- 文件同步工具

## 10. 构建、调试与工具链阶段

> 📖 详细展开版见 [ph10-build-toolchain/10-build-toolchain.md](./ph10-build-toolchain/10-build-toolchain.md)

### 目标

能管理 C++ 工程项目并定位复杂问题。

### 学习内容

- g++、clang++、Makefile、CMake
- C++20 Modules（import、export module）
- GDB、LLDB、Valgrind、ASan
- clang-tidy、clang-format
- gcov/lcov

### 必会概念

- CMake 管目标和依赖，不只是生成 Makefile
- Debug/Release/RelWithDebInfo 应分开使用
- Modules 替代 #include，提升编译速度和隔离性
- 静态分析能提前发现大量低级错误
- 格式化应自动化

### 示例

```cmake
cmake_minimum_required(VERSION 3.16)
project(MyApp)
set(CMAKE_CXX_STANDARD 17)
add_executable(app main.cpp)
```

### 练习

- 给项目写 CMake
- 用 ASan 查越界
- 用 clang-tidy 做静态检查
- 生成覆盖率报告

### 阶段验收

- 能构建多目标项目
- 能定位段错误和内存泄漏
- 能配置基础质量工具链

### 推荐项目

- C++ 工程模板
- 带 CI 的小型库

## 11. C++ 标准、编译器与可移植性阶段

> 📖 详细展开版见 [ph11-portability/11-portability.md](./ph11-portability/11-portability.md)

### 目标

理解 C++ 标准演进和编译器差异，避免不可移植写法。

### 学习内容

- C++11/14/17/20/23 特性边界
- GCC、Clang、MSVC 差异
- 标准库实现差异
- 平台宏与条件编译
- ABI 与标准的关系

### 必会概念

- 编译器支持和语言标准不是完全同步
- 标准库 ABI 可能影响二进制兼容
- 跨平台代码应隔离平台相关层
- 不要在公共接口暴露不稳定细节

### 示例

```cpp
#if defined(_WIN32)
// Windows path
#else
// POSIX path
#endif
```

### 练习

- 同项目用 GCC/Clang/MSVC 编译
- 为平台 API 写适配层
- 检查项目使用的 C++ 标准特性

### 阶段验收

- 能说明 C++17 和 C++20 的主要差异
- 能处理跨平台编译问题
- 能识别 ABI 风险

### 推荐项目

- 跨平台文件工具库
- 编译器兼容性实验项目

## 12. 对象生命周期、值类别与所有权深入阶段

> 📖 详细展开版见 [ph12-lifetime-value/12-lifetime-value.md](./ph12-lifetime-value/12-lifetime-value.md)

### 目标

深入理解对象何时创建、移动、销毁，以及表达式值类别。

### 学习内容

- prvalue、xvalue、lvalue
- 临时对象生命周期
- 返回值优化 RVO/NRVO
- 所有权转移和借用式接口
- 构造顺序与销毁顺序

### 必会概念

- 不要返回局部对象引用
- const 引用可延长临时对象生命周期，但边界有限
- 所有权应通过类型体现
- 值语义通常让代码更简单

### 示例

```cpp
std::string MakeName() {
    return "motor";
}
```

### 练习

- 分析临时对象生命周期
- 对比传值、引用、移动的性能
- 改造返回悬空引用的代码

### 阶段验收

- 能解释 move 后对象的状态约束
- 能分辨常见值类别
- 能设计不悬空的接口

### 推荐项目

- 值语义配置对象
- 所有权关系重构练习

## 13. Rule of 0 / 3 / 5 与 RAII 进阶阶段

> 📖 详细展开版见 [ph13-rule-of-035-raii/13-rule-of-035-raii.md](./ph13-rule-of-035-raii/13-rule-of-035-raii.md)

### 目标

掌握资源类设计，优先写 Rule of 0 的现代 C++。

### 学习内容

- Rule of 0、Rule of 3、Rule of 5
- RAII 资源封装
- 自定义 deleter
- unique_ptr 管理 C 资源
- 异常安全资源释放

### 必会概念

- 能用标准库成员管理资源时就遵守 Rule of 0
- 手写析构函数通常意味着也要考虑拷贝和移动
- RAII 是 C++ 工程代码的核心
- 资源释放路径不应依赖手动调用 close

### 示例

```cpp
using FilePtr = std::unique_ptr<FILE, decltype(&fclose)>;
FilePtr fp(fopen("data.txt", "r"), fclose);
```

### 练习

- 封装 FILE 指针
- 封装 socket 句柄
- 改造手动释放资源的旧代码

### 阶段验收

- 能判断一个类是否需要自定义特殊成员函数
- 能用 RAII 防止资源泄漏
- 能解释 Rule of 0 的价值

### 推荐项目

- RAII 系统资源库
- 安全句柄封装

## 14. const 正确性与接口设计阶段

> 📖 详细展开版见 [ph14-const-correctness/14-const-correctness.md](./ph14-const-correctness/14-const-correctness.md)

### 目标

用 const 表达接口承诺，提高可读性和可维护性。

### 学习内容

- const 对象、const 成员函数
- const 引用参数
- mutable 的谨慎使用
- 逻辑 const 与物理 const
- 只读视图设计

### 必会概念

- 不修改对象状态的成员函数应标 const
- 输入大对象优先用 const 引用
- const_cast 通常是设计气味
- const 能帮助调用者理解接口行为

### 示例

```cpp
class Sensor {
public:
    int Id() const { return id_; }
private:
    int id_ = 0;
};
```

### 练习

- 给旧类补 const 成员函数
- 用 const 引用优化函数参数
- 设计只读配置接口

### 阶段验收

- 能解释顶层 const 和底层 const
- 能设计 const 正确的类接口
- 能减少不必要拷贝

### 推荐项目

- 配置读取只读接口
- 设备状态快照模型

## 15. 未定义行为 UB 与内存安全阶段

> 📖 详细展开版见 [ph15-ub-memory-safety/15-ub-memory-safety.md](./ph15-ub-memory-safety/15-ub-memory-safety.md)

### 目标

识别 C++ 中常见 UB，写出更安全的底层代码。

### 学习内容

- 越界访问、悬空引用、重复释放
- use-after-move 语义风险
- 数据竞争
- 类型别名与对齐问题
- 未初始化变量

### 必会概念

- 数据竞争在 C++ 中是 UB
- 引用也可能悬空
- vector 扩容会使迭代器和引用失效
- Sanitizer 是日常开发工具

### 示例

```cpp
std::vector<int> v = {1, 2, 3};
int* p = v.data();
v.push_back(4); // p 可能失效
```

### 练习

- 修复悬空引用示例
- 用 ASan/UBSan 检查项目
- 梳理 vector 迭代器失效场景

### 阶段验收

- 能解释至少 5 种 C++ UB
- 能用工具定位内存错误
- 能设计避免悬空引用的接口

### 推荐项目

- C++ UB 示例集
- 安全容器使用指南

## 16. 测试、静态分析与代码规范阶段

> 📖 详细展开版见 [ph16-testing-quality/16-testing-quality.md](./ph16-testing-quality/16-testing-quality.md)

### 目标

建立 C++ 工程质量闭环。

### 学习内容

- GoogleTest、Catch2
- clang-tidy、cppcheck
- clang-format
- ASan、TSan、UBSan
- gcov/lcov、CI

### 必会概念

- 单元测试覆盖稳定逻辑，集成测试覆盖模块协作
- TSan 适合发现数据竞争
- 静态分析要纳入 CI
- 格式化不应靠人工争论

### 示例

```cpp
TEST(CalculatorTest, Add) {
    EXPECT_EQ(Add(1, 2), 3);
}
```

### 练习

- 给核心类写测试
- 配置 clang-tidy
- 开启 ASan/TSan 构建
- 生成覆盖率报告

### 阶段验收

- 能一键运行测试和静态检查
- 能解释测试失败原因
- 能让代码格式自动统一

### 推荐项目

- 带测试的 STL 工具库
- C++ CI 模板

## 17. 设计模式与架构能力阶段

> 📖 详细展开版见 [ph17-design-patterns-architecture/17-design-patterns-architecture.md](./ph17-design-patterns-architecture/17-design-patterns-architecture.md)

### 目标

用恰当抽象组织中大型 C++ 项目。

### 学习内容

- 工厂、策略、观察者、适配器
- 依赖注入思想
- 分层架构与模块边界
- 接口隔离
- 事件驱动设计

### 必会概念

- 模式是沟通语言，不是套模板
- 组合优先于继承
- 依赖方向应指向稳定抽象
- 架构设计要服务测试和演进

### 示例

```cpp
class IComm {
public:
    virtual ~IComm() = default;
    virtual bool Send(const Frame& frame) = 0;
};
```

### 练习

- 用策略模式封装协议解析
- 用观察者实现状态变化通知
- 为存储引擎抽象 IStorage 接口
- 为查询执行器抽象 IExecutor 接口

### 阶段验收

- 能解释模块职责
- 能隔离硬件、协议和业务逻辑
- 能通过接口 mock 依赖

### 推荐项目

- 存储引擎模块分层 demo
- 查询执行器接口设计 demo

## 18. 性能优化与 Profiling 阶段

### 目标

能基于数据定位性能瓶颈，而不是凭感觉优化。

### 学习内容

- perf、gprof、VTune、Tracy
- CPU profile、内存 profile
- cache locality
- 拷贝消除、移动语义
- 分配次数优化
- SIMD 友好的内存布局
- 向量距离计算 benchmark
- 查询执行热点分析

### 必会概念

- 先测量，再优化
- 算法复杂度优先于微优化
- 连续内存通常更利于缓存
- 过早优化会破坏结构

### 示例

```bash
perf record ./app
perf report
```

### 练习

- 对比 vector 与 list 遍历性能
- 优化 JSON/CSV 解析
- 减少热点路径内存分配

### 阶段验收

- 能输出 profile 证据
- 能解释热点函数
- 能验证优化前后差异

### 推荐项目

- 向量距离计算性能对比
- 列式扫描性能优化实验
- 高性能日志 / 数据文件解析器

## 19. ABI、动态库与插件机制阶段

### 目标

理解二进制边界，能设计稳定插件接口。

### 学习内容

- ABI 与 API
- name mangling
- extern C
- 动态库加载
- 版本兼容
- 插件生命周期

### 必会概念

- C++ ABI 不如 C ABI 稳定
- 插件边界尽量用 C ABI 或稳定包装层
- 谁创建谁销毁要约定清楚
- 动态库升级要考虑符号兼容

### 示例

```cpp
extern "C" Plugin* CreatePlugin();
extern "C" void DestroyPlugin(Plugin* plugin);
```

### 练习

- 写一个动态库
- 用 dlopen/LoadLibrary 加载插件
- 设计插件版本检查

### 阶段验收

- 能解释 ABI 破坏的原因
- 能设计基础插件生命周期
- 能避免跨库释放错误

### 推荐项目

- C ABI 插件式存储引擎 demo
- 查询执行算子插件 demo
- TensorRT plugin 接口阅读 demo

## 20. C++ 与 C / Python / Rust 互操作阶段

### 目标

能在跨语言系统中安全暴露 C++ 能力。

### 学习内容

- C 包装层
- pybind11
- Rust cxx/FFI
- CMake 跨语言构建
- 错误和内存所有权约定

### 必会概念

- 公共边界越简单越稳定
- 异常不要直接穿过 C ABI
- 字符串和容器跨语言传递需要转换层
- 互操作测试必须覆盖错误路径

### 示例

```cpp
extern "C" int add(int a, int b) {
    return a + b;
}
```

### 练习

- C++ 动态库给 Python 调用
- pybind11 包装类
- Rust 调 C++ C 接口

### 阶段验收

- 能明确跨语言所有权
- 能处理异常到错误码转换
- 能构建并测试跨语言调用

### 推荐项目

- Python 调用 C++ 向量检索库
- C++ 存储引擎暴露 C ABI
- Rust 调用 C++ 距离计算模块
- pybind11 包装 C++ 查询执行组件

## 21. 数据结构与算法阶段

### 目标

具备面试、工程建模和性能优化所需的数据结构基础。

### 学习内容

- 数组、链表、栈、队列、哈希表
- 二叉树、堆、图、并查集、Trie、LRU Cache
- 排序、二分、双指针、滑动窗口
- 递归、回溯、动态规划、贪心、BFS、DFS、Dijkstra

### 必会概念

- 数据结构选择决定复杂度上限
- STL 已提供很多生产级容器
- 算法题要关注边界条件
- 工程中要权衡可读性和性能

### 示例

```cpp
std::priority_queue<int> tasks;
tasks.push(10);
tasks.push(3);
```

### 练习

- LRU Cache
- 任务调度器
- 查询计划树 demo
- 内存池

### 阶段验收

- 能分析时间和空间复杂度
- 能用 STL 实现常见算法
- 能处理边界输入

### 推荐项目

- LRU 缓存库
- Bloom Filter
- SkipList MemTable
- HNSW toy implementation

## 22. 存储引擎与数据库内核专项阶段

### 目标

理解 C++ 在数据库内核、KV 存储和高性能存储引擎中的使用方式，能实现 Mini KV / Mini LSM 的核心模块。

### 学习内容

- WAL 日志、MemTable、SSTable
- Bloom Filter、Compaction
- B+Tree、Buffer Pool、LRU / Clock Cache
- Snapshot、MVCC 基础
- Iterator 抽象
- RocksDB / LevelDB 源码阅读

### 必会概念

- WAL 用于崩溃恢复
- SSTable 是不可变有序文件
- LSM 通过顺序写提升写入吞吐
- Compaction 是 LSM 的核心成本来源
- Bloom Filter 可以减少无效磁盘查询
- Buffer Pool 需要处理缓存命中、脏页、pin/unpin 和淘汰策略
- Iterator 是数据库内部连接 MemTable、SSTable、索引和执行器的重要抽象

### 示例

```cpp
struct WalRecord {
    uint64_t sequence;
    uint8_t type;
    std::string key;
    std::string value;
    uint32_t checksum;
};

class WalWriter {
public:
    explicit WalWriter(const std::string& path);
    bool Append(const WalRecord& record);
    void Sync();

private:
    int fd_{-1};
};

class Iterator {
public:
    virtual ~Iterator() = default;
    virtual bool Valid() const = 0;
    virtual void Next() = 0;
    virtual std::string_view Key() const = 0;
    virtual std::string_view Value() const = 0;
};
```

### 练习

- 实现 append-only WAL 写入与 replay
- 设计 SSTable block header 并实现 Mini SSTable writer / reader
- 为 SSTable 增加 Bloom Filter
- 实现 LRU Cache
- 用 Iterator 抽象 MemTable 和 SSTable 的 range scan

### 阶段验收

- 能解释 WAL、MemTable、SSTable、Compaction 的关系
- 能通过 WAL 恢复 put / delete 操作
- 能按 key 查询 SSTable
- 能完成基础 range scan
- 能解释 LSM 的读放大、写放大和空间放大
- 能说明 B+Tree 和 LSM 的适用场景差异
- 能读懂 LevelDB / RocksDB 中至少一个核心模块的调用链

### 推荐项目

- Mini WAL
- Mini SSTable
- Mini LSM KV
- 简化 B+Tree
- Buffer Pool toy
- LevelDB 源码分析

## 23. 向量检索与 AI 推理引擎方向 C++ 阶段

### 目标

面向向量数据库、RAG 检索、Faiss、CUDA/TensorRT 和推理服务，掌握 C++ 在 AI Infra 底层的使用方式。

### 学习内容

- L2 / Inner Product / Cosine 距离
- SIMD 距离计算
- HNSW、IVF / PQ 基础
- Faiss 使用与源码阅读
- metadata filter、向量索引持久化
- CUDA C++ 基础、TensorRT plugin 基础
- KV Cache / batching / serving runtime 概念

### 必会概念

- 向量检索核心是召回率、延迟、内存占用的权衡
- 暴力检索简单但成本高，ANN 用近似换性能
- HNSW 用图结构提升近似最近邻搜索效率
- IVF 通过聚类缩小搜索范围，PQ 通过量化降低存储成本
- SIMD 和连续内存布局会显著影响距离计算性能
- Faiss 是理解向量检索工程化的重要 C++ 项目
- 推理引擎关注 batch、显存、KV Cache、算子性能和服务延迟
- C++ 常用于 Python AI 系统背后的高性能扩展层

### 示例

```cpp
float L2Distance(const float* a, const float* b, size_t dim) {
    float sum = 0.0f;
    for (size_t i = 0; i < dim; ++i) {
        const float diff = a[i] - b[i];
        sum += diff * diff;
    }
    return sum;
}

struct SearchResult {
    int64_t id;
    float score;
};

class VectorIndex {
public:
    virtual ~VectorIndex() = default;
    virtual void Add(int64_t id, const std::vector<float>& vector) = 0;
    virtual std::vector<SearchResult> Search(
        const std::vector<float>& query,
        size_t top_k
    ) const = 0;
};
```

### 练习

- 实现 brute-force vector search
- 实现 L2 / cosine / inner product 三种距离计算
- 为距离计算写 benchmark 并尝试 SIMD 优化
- 实现 HNSW 的节点、邻接表和基础搜索流程
- 使用 Faiss 建立 IVF / HNSW 索引并测试召回率

### 阶段验收

- 能解释 L2、Cosine、Inner Product 的适用场景
- 能完成 brute-force topK 检索
- 能输出 recall、QPS、P95 延迟和内存占用
- 能解释 HNSW 的图搜索过程
- 能说明 IVF / PQ 的基本取舍
- 能用 Faiss 跑通一个向量检索 benchmark
- 能解释 SIMD 为什么能加速距离计算
- 能说明推理服务中 batching、KV Cache 和显存占用的关系

### 推荐项目

- brute-force vector search
- HNSW toy implementation
- Faiss benchmark
- SIMD 向量距离计算
- 向量索引持久化 demo
- TensorRT plugin demo
- 推理服务 batching 原型
- Python 调用 C++ 向量检索库

## 附录：阶段性项目验收标准

### 目标

用项目验证 C++ 能力，从语法使用走向工程交付。

### 学习内容

- 功能验收、性能验收、测试验收
- README、构建脚本、CI
- Sanitizer 和静态分析
- 项目分层和接口说明

### 必会概念

- 可构建、可运行、可测试、可维护才算完成
- 公共接口要有示例和错误说明
- 工程质量工具应自动化

### 示例

```text
验收项：
- cmake --build 通过
- ctest 通过
- ASan/UBSan 无错误
- clang-tidy 无高优先级问题
```

### 练习

- 给已有项目补 CI
- 给公共 API 补文档
- 用 Sanitizer 跑全量测试

### 阶段验收

- 能完成类和 STL 项目（初级）
- 能完成多模块 CMake 项目（中级）
- 能完成并发、网络、存储引擎、查询执行或向量检索方向项目（高级）

### 推荐项目

- C++ 工程模板
- Mini KV 工程模板
- 向量检索库工程模板

## 推荐学习顺序

```text
C++ 基础语法
→ 引用 / const / string / vector
→ 类和对象
→ 构造 / 析构 / RAII
→ STL 容器和算法（含 span / string_view / ranges）
→ 模板 / concept / 泛型组件
→ 智能指针
→ 移动语义
→ 现代 C++（format / <=> / optional / variant）
→ CMake / Modules / GDB / ASan / TSan
→ 并发 / atomic / jthread / 协程
→ 文件 / 网络 / Linux 系统编程
→ 性能优化 / Profiling / cache locality
→ ABI / 动态库 / 插件机制
→ C / Python / Rust 互操作
→ 存储引擎 / WAL / B+Tree / LSM
→ 查询执行 / 列式存储 / 向量化执行
→ 向量检索 / Faiss / HNSW
→ CUDA C++ / TensorRT / 推理引擎
```

## C++ 和 C 的重点区别

| 方向 | C | C++ |
| --- | --- | --- |
| 编程风格 | 面向过程 | 面向对象 + 泛型 + 函数式 |
| 字符串 | char 指针 | std::string |
| 动态数组 | malloc/free | std::vector |
| 资源管理 | 手动管理 | RAII + 智能指针 |
| 复用方式 | 函数、宏 | 类、模板、组合 |
| 错误处理 | 错误码 | 错误码 + 异常 |

## 项目路线

### 初级项目

- 计算器
- 学生管理系统
- 通讯录
- 文件统计工具
- 简单日志类

### 中级项目

- 动态数组类
- 简单 String 类
- 线程安全队列
- LRU Cache
- CSV/JSON 配置管理
- TCP echo server

### 高级项目

- 线程池
- HTTP server
- 内存池
- 事件驱动框架
- 插件系统
- Mini WAL
- Mini LSM KV
- Mini SQL Engine
- Mini Column Store
- HNSW toy implementation
- Faiss benchmark
- TensorRT plugin demo

## 对你最推荐的路线

如果目标是数据库内核、KV 库、向量库、AI 推理训练引擎和 Agent 高性能扩展，建议路线是：

```text
C++ 基础
→ 类和对象
→ 构造 / 析构
→ RAII
→ STL 容器和算法（含 span / string_view / ranges）
→ 模板 / concept
→ 智能指针
→ 移动语义
→ std::format / <=> / C++20 基础
→ CMake / Modules
→ GDB / ASan / TSan
→ 并发 / atomic / jthread / 协程
→ allocator / 内存池
→ Linux IO / mmap
→ WAL / B+Tree / LSM
→ 查询执行 / 列式存储
→ 向量检索 / Faiss / HNSW
→ CUDA C++ / TensorRT
→ pybind11 / C ABI / Rust 互操作
```

重点掌握：class、RAII、const、引用、vector、string、array、span、string_view、unique_ptr、move、template、concept、format、jthread、atomic、协程、CMake、Modules、GDB、ASan、TSan、perf、mmap、WAL、B+Tree、LSM、列式存储、向量化执行、HNSW、Faiss、CUDA C++、TensorRT、pybind11。
