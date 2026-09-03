# C++ 设计模式与架构能力阶段

> 面向「中大型 C++ 项目怎么组织」方向：从单点模式（工厂/策略/观察者/适配器）起步，经由依赖注入、接口设计与分层架构，学会用抽象管理模块边界与依赖方向——模式是沟通语言，架构服务于测试和演进。

## 1. 概述

本阶段是学习路线的第 17 步（roadmap ph17 目标：用恰当抽象组织中大型 C++ 项目）。前面 16 步把语言侧的基础铺完了：ph02 讲了类与继承（虚函数、多态的语法面），ph06 给了现代 C++ 工具箱（`unique_ptr`、`std::function`、lambda），ph12/ph13/ph14 把生命周期、RAII、const 承诺讲成接口语言，ph16 又把「可测试性从接口设计开始」这句话挂在嘴边——**本阶段就是把这些散件组装成「组织代码的方法论」**：什么时候该抽象出接口、抽象往哪个方向指、对象之间谁拥有谁、模块之间依赖怎么走。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 设计模式落地 | roadmap 点名的四个模式：工厂 / 策略 / 观察者 / 适配器——意图、结构、变体、C++ 特有写法与陷阱 |
| 现代 C++ 改写 | 虚函数 vs `std::function` 类型擦除的取舍；`unique_ptr` 所有权与模式结合；GoF 模式在 C++17 的「减肥」 |
| 依赖注入思想 | 构造注入、组合根（composition root）、手写 vs 框架、mock 依赖（兑现 ph16 伏笔） |
| 接口设计 | 接口隔离（ISP）、pimpl 编译防火墙、小接口 vs 胖接口 |
| 分层架构 | 逻辑分层、依赖方向规则、模块边界的物理化（头文件/命名空间/构建目标） |
| 事件驱动设计 | 同步回调、事件对象、发布-订阅、与异步事件循环的边界 |
| 心智模型 | 组合优于继承、依赖倒置、SOLID 在 C++ 的落地、「模式是沟通语言不是套模板」 |

这个阶段只涉及**对象级**的代码组织：roadmap §17 点名的四个模式与其直接变体、依赖注入、分层架构与模块边界、接口隔离与 pimpl、进程内同步的事件驱动设计，**不涉及模板/编译期形态的模式改写（CRTP、policy-based design——ph05 模板与泛型编程、元编程阶段）、并发与异步形态的事件驱动（线程安全通知、事件循环、actor——ph08 并发编程阶段）、模式引入的间接层的性能实测与基准（ph18 性能优化与 Profiling 阶段，目录待建）、跨动态库边界的稳定接口与插件 ABI（ph19 ABI、动态库与插件机制阶段，目录待建）、跨语言互操作层的接口设计（ph20 C++ 与 C / Python / Rust 互操作阶段，目录待建）和真实存储引擎内核（WAL/MemTable/SSTable/索引——ph22 存储引擎与数据库内核专项阶段，目录待建）** — 那些是其他阶段的内容。

## 2. 来源与演变

「设计模式」一词借自建筑学：Christopher Alexander 在 1970 年代提出「模式语言」（pattern language）——把反复出现的解决方案编码成带名字的模板。1987 年 Kent Beck 与 Ward Cunningham 把模式思想带进软件；1990 年 Erich Gamma、Richard Helm、Ralph Johnson、John Vlissides（后来人称 **Gang of Four，四人帮**，GoF）在 ECOOP 会议上发表论文《Design Patterns: Abstraction and Reuse of Object-Oriented Design》，1994 年出版同名专著——就是那本著名的「四人帮书」。**设计哲学一句话：模式是给反复出现的结构问题起名字并记录解决方案，让团队用同一个词汇表讨论设计**。

GoF 书把 23 个模式按目的分成三类：**创建型**（对象怎么产生——工厂在此）、**结构型**（对象怎么组合成更大结构——适配器在此）、**行为型**（对象间怎么协作与分配职责——策略、观察者在此）。这个三分法至今仍是行业词汇表。后续演进补上了架构级与组织级视角：POSA（Pattern-Oriented Software Architecture，1996 起）补架构模式（分层、管道等）；反模式运动（《AntiPatterns》，1998）给「常见错误做法」也起了名；GRASP（Larman）回答「职责该分配给谁」；Robert C. Martin 的 SOLID 五原则（2000 年代，缩写由 Michael Feathers 提出）把「面向接口、依赖倒置」提炼成工程格言。C++ 侧的独特演变是：原书示例本就是 C++/Smalltalk 写的，但 30 年后 C++ 自己的语法成熟，让一批模式「变薄」了——观察者退化成 `std::function` 列表、工厂退化成返回 `unique_ptr` 的普通函数、策略退化成可赋值的回调成员。**模式意图不变，载体随语言演进**，这是本阶段最重要的元认知。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Alexander 建筑模式语言 | 1977~1979 | 「模式」概念：命名 + 反复出现 + 解决方案 |
| Beck / Cunningham 引入软件 | 1987 | OOPSLA 报告：把模式语言用于面向对象程序 |
| GoF ECOOP 论文 | 1990 | 《Design Patterns: Abstraction and Reuse…》确立意图/结构/参与者/协作描述法 |
| 《Design Patterns》出版 | 1994 | 23 模式三分法（创建/结构/行为）成为行业通用语言 |
| POSA 卷 1 | 1996 | 补架构级模式（分层、管道、代理等） |
| 《AntiPatterns》 | 1998 | 「别这样做」与「这样做」配对，反模式入库 |
| GRASP / SOLID 成型 | 2001~2002 | 职责分配原则；SRP/OCP/LSP/ISP/DIP 五原则缩写 |
| 《Modern C++ Design》 | 2001 | policy-based design：用模板把策略搬到编译期（其边界属 ph05） |
| Boost.Signals2 | 约 2007 | 观察者工程化：连接对象自动断开、线程安全（本阶段只取其思路） |
| C++11/14 全面可用 | 2011~2014 | `unique_ptr`/`std::function`/lambda 让 GoF 可被现代载体重写 |
| C++17 | 2017 | 本阶段基线：`std::optional`/`string_view`/结构化绑定补齐教学所需 |

本文示例以 **C++17** 为基线（模式讨论的是结构与意图，对标准版本不敏感——C++17 已集齐本阶段所需的一切现代设施（`std::function`、`unique_ptr`/`shared_ptr`、`std::optional`、`string_view`、结构化绑定），且是现存大量 C++ 工程的实际基线；ph11~ph16 主线示例以 C++20 演示语言前沿，本阶段刻意回到更保守的工程基线，凸显「模式本身与语言新旧无关」），验证工具链 **Apple clang 21.0.0（`c++`）+ Homebrew clang 21.1.8（`clang++`）**，统一 `-std=c++17 -Wall -Wextra`。本阶段用到的语言设施（智能指针、`std::function`、lambda）自 C++11/17 定型后多年未变——**模式教学所依赖的语法是 C++ 最稳定的部分之一**，本笔记的写法长期有效。

## 3. 语法与参数

> 本节代码块为**教学骨架**：为聚焦单个模式做了裁剪。完整可运行文件见第 6 节与 [`examples/`](./examples/)，构建/运行命令见 examples/README.md（全部已验证：Apple clang 21 本机实测编译零警告、运行通过）。

### 3.1 先立框架：模式的两种载体与「组合优于继承」

模式是「结构方案」，载体是「语言工具」。C++ 里实现「运行时多态、可替换」有两种主流载体，另有第三种编译期载体：

```cpp
// 载体 A：抽象基类 + 虚函数（经典 GoF 形态）
class INotifier {
public:
    virtual ~INotifier() = default;
    virtual void notify(std::string_view message) const = 0;
};

// 载体 B：std::function 类型擦除（现代形态：同一个「接口」不需类层次）
using Notifier = std::function<void(std::string_view)>;
```

| 维度 | 抽象基类 + `unique_ptr` | `std::function` | 模板（编译期） |
|------|------------------------|-----------------|----------------|
| 声明成本 | 接口类 + 实现类 + 继承 | 一个别名 | 无额外类型 |
| 替换时机 | 运行期（虚调用） | 运行期（成员赋值） | 编译期（类型实例化，ph05 内容） |
| 状态捕获 | 靠派生类成员 | lambda 捕获，天然 | 靠模板参数 |
| 存储 | 多态对象在堆上（`unique_ptr`）或借引用 | 小对象内嵌、大对象堆回退（见 4.2） | 值存储，无间接 |
| 拷贝要求 | 多态对象禁拷贝更常见（C.67） | 目标须可拷贝（C++17 无移动版 `std::function`） | 值拷贝 |
| 典型用途 | 跨翻译单元稳定扩展、多虚函数接口 | 回调、单函数策略、事件监听 | 性能敏感、编译期已定 |

**组合优于继承**（GoF 第一条原则，roadmap 必会概念）为什么在 C++ 特别成立：继承让派生类**绑定**基类的实现细节（改了基类私有成员，所有派生类重编）、把「是一个」的关系写死在类型里、且多继承带来的菱形与歧义是 C++ 特有的复杂度；组合（持有成员对象/接口 + 转发调用）把关系降级为「有一个」，替换、装饰、测试都更容易。roadmap §17 的示例接口（通讯模块收敛出 `IComm`，纯虚 `Send`）正是「面向接口」的雏形——本阶段把它扩展成完整工具箱：

```cpp
// roadmap §17 示例的规范化写法（原文 IComm::Send，按仓库规范转 snake_case）
// struct Frame 的定义被省略——教学骨架，为聚焦接口形状而简化
class IComm {
public:
    virtual ~IComm() = default;
    virtual bool send_frame(const Frame& frame) = 0;  // 纯虚：实现方负责协议细节
};
```

什么时候继承仍然对？**抽象接口 + 实现**（本阶段大量使用，纯虚基类 = 契约不是实现复用）、需要 `dynamic_cast` 区分类型（RTTI 用法，谨慎）、以及「实现复用」场景（此时先问一句：能不能改成成员对象）。模板载体（policy-based design、CRTP）属于 ph05 模板与泛型编程、元编程阶段，本阶段只用运行期两种载体。

### 3.2 工厂：把「创建」从「使用」中拆出去

**意图**：客户代码不该知道（也不该负责）具体对象怎么造——把 `new` 收拢到一处，调用方只面对抽象。C++ 特有的大问题：**创建出来的对象谁拥有、谁释放**。所以 C++ 的工厂第一纪律是**返回 `unique_ptr` 而非裸指针**（R.11/R.20：用 `make_unique`，所有权随返回值显式转移；I.11：绝不通过裸指针传递所有权）：

```cpp
// 简单工厂：集中 if/switch（kind 是枚举或字符串）
class SimpleShapeFactory {
public:
    static std::unique_ptr<Shape> make(const std::string& kind, double a, double b) {
        if (kind == "circle")    return std::make_unique<Circle>(a);
        if (kind == "rectangle") return std::make_unique<Rectangle>(a, b);
        throw std::invalid_argument("unknown shape kind: " + kind);  // 失败要响亮
    }
};
```

| 工厂变体 | 结构 | 何时用 | 注意 |
|----------|------|--------|------|
| 工厂函数 | 自由函数 `make_xxx(...)` | 一个产品、参数直给 | 最简，先用它 |
| 简单工厂 | 静态分派 kind → 对象 | kind 集小且稳定 | kind 增多要改工厂本体（违背 OCP） |
| 注册表工厂 | 名 → `std::function` 创建器，运行期注册 | kind 集开放（插件、测试替换） | 见 ex01：新增类型不改工厂 |
| 抽象工厂 | 一族产品一套工厂接口 | 相关对象族需成套替换 | C++ 里场景比 Java 少，先别急着上 |

**注册表工厂**是 C++ 工程里最有价值的一种：`std::unordered_map<std::string, std::function<std::unique_ptr<Shape>()>>` + 注册函数（或静态注册引导对象），**新增产品类型 = 新增一个注册调用，工厂本体零改动**——开闭原则的直接落地（完整版 `examples/ex01-factory.cpp`）。教学增量：① 注册引导对象放在匿名命名空间、同一翻译单元内，避开静态初始化顺序问题；跨翻译单元的全局注册顺序不确定，工程上常用「显式注册函数在 main 开头调用」或「函数内静态注册表延迟初始化」；② 工厂里构造失败怎么办——`make_unique` 保证「先分配、失败自动清理」，不会出现半构造泄漏；③ 别把「工厂单例」和「产品单例」混为一谈，注册表是共享的服务对象，产品仍应每次新建。

> 本阶段只讲**运行期工厂**；**编译期选择（policy、if constexpr 分派）属于 ph05 模板与泛型编程、元编程阶段**，这里只需理解「运行期把创建收拢」这一种。

### 3.3 策略：算法族可替换

**意图**：把一组可互换的算法封装成独立单元，上下文持有策略、运行期可换——「算法」与「使用算法的代码」解耦。典型场景：协议解析（分隔符分帧 vs 长度前缀分帧，roadmap 练习 1 的场景）、日志格式、压缩/编码、校验算法。

**经典实现**（策略 = 抽象接口 + 派生实现，上下文用 `unique_ptr` 持有）：

```cpp
class ILogFormatter {  // 策略接口
public:
    virtual ~ILogFormatter() = default;
    virtual std::string format(const LogRecord& r) const = 0;
};

class Logger {  // 上下文
public:
    explicit Logger(std::unique_ptr<ILogFormatter> fmt) : fmt_(std::move(fmt)) {}
    void set_formatter(std::unique_ptr<ILogFormatter> fmt) { fmt_ = std::move(fmt); }
    // log() 内部只调 fmt_->format(...)，不知道具体是哪种格式
private:
    std::unique_ptr<ILogFormatter> fmt_;  // 上下文独占策略所有权
};
```

**现代实现**（策略 = 一个 `std::function` 成员）：算法多数是「一个函数一个输入一个输出」，为此建接口类 + 派生类是杀鸡用牛刀。`std::function` 让 lambda 直接成为策略，还能携带状态（捕获前缀、配置项）；策略注册表（名 → `std::function`，与 3.2 注册表同构）可运行期按名切换（完整版 `examples/ex02-strategy.cpp`）。取舍：

| 维度 | 虚函数策略 | `std::function` 策略 |
|------|-----------|----------------------|
| 策略形态 | 类 + 继承 | 任意可调用对象 |
| 携带状态 | 派生类成员 | lambda 捕获 |
| 多方法策略 | 支持（接口可含多个虚函数） | 一个可调用对象只对应一个调用点 |
| 空策略 | 需判空或空对象实现 | `operator bool` 判空，调用空 `std::function` 抛 `bad_function_call` |
| 拷贝/移动限制 | 类自己管（Rule of Five） | 目标须**可拷贝**（move-only lambda 装不进 C++17 的 `std::function`——陷阱） |

陷阱清单：① **move-only 捕获**（如捕获 `unique_ptr` 的 lambda）不能放进 `std::function`——C++17 没有移动版 `std::function`（C++23 才有），绕法是把捕获对象包进 `shared_ptr` 再捕获，或手写类型擦除；② **策略生命周期归上下文**：上下文持 `unique_ptr` 独占，多上下文共享同一策略对象用 `shared_ptr`，绝不能让上下文持他人管理生命周期的裸指针；③ **策略粒度**：以「一个算法一个入口」为粒度，不要把整个子系统塞成一个策略。

> 本阶段策略全部是**运行期**替换；**编译期固定算法族（模板策略、policy-based design）属于 ph05 模板与泛型编程、元编程阶段**，工程上「运行期可配置」与「编译期零开销」的选择本身也是架构决策。

### 3.4 观察者：状态变化通知与生命周期

**意图**：一对多依赖——一个 subject 状态变化时通知所有订阅者，subject 不认识订阅者的具体类型（面向回调/接口）。经典结构是 `Subject` 持有 `Observer*` 列表、`attach/detach/notify` 三件套；现代 C++ 里观察者接口常被 `std::function` 列表取代，订阅者就是一组 lambda。**但观察者的灵魂从来不是接口形式，而是生命周期**——这是 C++ 与 GC 语言最大的分野：

| 风险 | 场景 | 对策 |
|------|------|------|
| 悬挂指针 | 观察者先销毁，subject 仍持有其指针/回调 | RAII 退订 Token（句柄析构自动退订）；或约定销毁顺序 |
| 迭代器失效 | 通知期间回调里订阅/退订，改了正在遍历的列表 | 通知前拷贝快照；或标记后清理 |
| 异常传播 | 一个订阅者抛异常打断全体 | 通知循环内 try/catch 隔离（E.17 的务实面） |
| 重入 | 回调里再触发同 subject 状态变化 | 快照 + 明确「通知不重入」约定（深递归风险） |

```cpp
// 现代观察者 + RAII 退订 Token（完整版 examples/ex03-observer.cpp）
class WeatherStation {
public:
    using Listener = std::function<void(double celsius)>;
    class Subscription {  // 句柄：析构自动退订，禁拷贝可移动
        // ……实现见 examples/ex03-observer.cpp
    };
    Subscription subscribe(Listener listener);  // 返回句柄
    void unsubscribe(std::size_t id);
private:
    std::vector<Listener> listeners_;  // 通知时先拷贝快照再遍历
};
```

**变化检测是观察者的语义核心**：只应在「值真的变了」时通知（重复赋值同值不通知）——否则订阅者收到大量无意义回调（练习 2 的验收点）。工程化的观察者会引入**事件对象**（见 3.9）与**连接句柄**：Boost.Signals2 的 `connection` 就是「订阅即返回句柄、断开即安全」的成熟实现，本阶段的 Token 方案是其最小同构。深一层的问题：subject 不拥有观察者，谁保证观察者活得比订阅久？三条路线：① 销毁顺序纪律（subject 先亡）；② Token 由观察者持有，观察者析构先退订（成员声明顺序保证）；③ subject 存 `weak_ptr`、通知时 `lock()` 失效即清（观察者用 `shared_ptr` 自持）——三条的取舍正是「所有权归谁」的架构决策（4.3 展开）。

> 本阶段观察者限定为**同线程同步通知**；**跨线程安全通知（锁内回调、事件队列）与线程同步原语属于 ph08 并发编程阶段**，高性能事件循环与异步 IO（epoll/io_uring）属于 ph18 性能优化与 Profiling 阶段（目录待建）——本阶段只解决「单线程内一对多通知」这一种。

### 3.5 适配器：接口转换而不改源码

**意图**：让接口不兼容的两个类协作——新代码需要 `ILogSink`，老模块（第三方/历史代码，改不得）只有 `append_line`。适配器是**中间翻译层**：转接口，不转语义。

```cpp
// 对象适配器：组合老对象（引用），翻译成目标接口（完整版 examples/ex04-adapter.cpp）
class LegacySinkAdapter final : public ILogSink {
public:
    explicit LegacySinkAdapter(LegacyTextSink& legacy) : legacy_(legacy) {}
    void write(const std::string& level, const std::string& msg) override {
        legacy_.append_line(level + ": " + msg);  // 接口转换，语义不变
    }
private:
    LegacyTextSink& legacy_;  // 组合优先于继承（3.1）
};
```

| 变体 | 做法 | C++ 评价 |
|------|------|---------|
| 对象适配器 | 持老对象引用/指针，翻译调用 | 首选：组合、无菱形、老对象生命周期自管 |
| 类适配器 | 多重继承新老接口 | C++ 支持但少用：多继承复杂度 > 收益 |
| 函数适配器 | 单函数接口用 lambda/`std::function` 包装，不建类 | C++ 特有便宜做法：`std::function` 本身就是适配器（见 ex04 的 C 回调例子） |

C++ 特有的观察：**适配器可以薄到只是一层函数**。C 库的 `fputs(FILE*, ...)` 要接进面向对象的接口，一个捕获 `FILE*` 的 lambda 就是适配器，不必建类。标准库本身也充满适配思想：`std::stack` 是「把 `deque` 适配成后进先出语义」的容器适配器；`std::function` 把任意可调用对象适配成统一调用点。陷阱：① 适配器**转接口不转语义**——老接口缺的概念（如日志级别）要显式补齐或拒绝，不能静默丢弃；② 双层适配器是坏味道（说明中间层接口设计错了）；③ 永远先问「能不能改对源接口」——适配器是给「改不得」的代码用的，不是给自己的坏接口遮羞的万能胶。

### 3.6 依赖注入与组合根：依赖方向指向稳定抽象

依赖注入（DI）的思想一句话：**对象需要的依赖从外面给进来，而不是自己 new**。它是「依赖方向应指向稳定抽象」（roadmap 必会概念）的操作化——业务对象依赖 `IOrderStore`（抽象），具体 `MemoryStore` 只出现在**组合根**（composition root：程序里唯一组装对象图的地方，通常是 main 或启动函数）：

```cpp
// 构造注入：业务层只依赖接口（完整版 examples/ex05-di.cpp）
class OrderService {
public:
    OrderService(std::shared_ptr<IOrderStore> store,
                 std::shared_ptr<IPaymentGateway> gateway)
        : store_(std::move(store)), gateway_(std::move(gateway)) {}
    bool place(const Order& order) {
        if (!gateway_->charge(order.amount_cents)) return false;
        store_->save(order);  // 不知道背后是内存库还是文件库
        return true;
    }
private:
    std::shared_ptr<IOrderStore> store_;        // 共享所有权：报表服务也读它
    std::shared_ptr<IPaymentGateway> gateway_;
};
```

| 注入方式 | 做法 | 评价 |
|----------|------|------|
| 构造注入 | 依赖作为构造参数 | C++ 首选：依赖图一目了然、对象一旦构造即完整（C.41） |
| setter 注入 | 构造后 `set_dep(...)` | 允许「半构造」状态，C++ 里少用（违背 C.41） |
| 方法参数注入 | 依赖作为调用参数传入 | 纯函数/工具类友好，无状态可测 |
| 服务定位器 | 全局注册表按需取 | **反模式对照**：依赖图隐入全局状态，测试难、隐藏所有权 |

C++ 侧的关键判断：**手写组合根往往优于 DI 容器**。C++ 没有反射，Boost.DI 这类库靠模板在编译期织依赖图——省了样板但也藏了组装逻辑、报错在模板实例化深处；手写组合根（几十行 `make_*` 调用）显式、可断点、可读，对绝大多数 C++ 工程已经足够。什么时候才考虑容器：依赖成百上千、要按配置批量切换的巨型服务——C++ 里很少见。**生命周期由所有权类型表达**：单消费者独占用 `unique_ptr`（R.21：能 unique 不 shared），多消费者共享用 `shared_ptr`，不拥有只借用用引用/裸指针（R.3：裸指针是非拥有观察者）——组合根负责按此声明谁活多久，绝不在业务层里猜。DI 对测试的兑现正是 roadmap 验收「能通过接口 mock 依赖」：**mock 不是特殊技术，是注入接口的另一个实现**（ph16「可测试性从接口开始」的伏笔在此展开）。

### 3.7 接口隔离与 pimpl：小接口与编译防火墙

**接口隔离（ISP）**：客户端不应被迫依赖它用不到的方法。胖接口（fat interface）把十几个虚函数塞进一个类，实现方被迫写空实现或抛「不支持」，调用方被迫理解无关语义——这是 C++ 接口腐烂的头号形态。落地方案：**按角色拆小接口**，让实现类多重继承多个小接口，客户端各取所需：

```cpp
class IReadable {                          // 小接口 1：读
public:
    virtual ~IReadable() = default;
    virtual std::optional<std::string> get(const std::string& key) const = 0;
};
class IWritable {                          // 小接口 2：写
public:
    virtual ~IWritable() = default;
    virtual void put(const std::string& key, const std::string& value) = 0;
};
// 实现类可同时满足两个接口；只读客户端只依赖 IReadable
```

接口隔离的另一个 C++ 特有战场是**物理隔离**：pimpl（pointer to implementation，编译防火墙）。意图：头文件只暴露「指针成员 + 稳定接口」，私有实现细节（数据成员、include 的私有头）全部藏进 .cpp 里——改私有成员不再触发所有消费者的重编译，头文件依赖变薄（完整示例见 4.4 的物理视角）：

```cpp
// widget.h —— pimpl 头文件：用户看不到 Impl，include 依赖最少
class Widget {
public:
    Widget();                                  // 构造在 .cpp 中分配 Impl
    ~Widget();                                 // 必须在 Impl 完整处定义（unique_ptr 删除器）
    Widget(Widget&&) noexcept;                 // 移动也要在 .cpp 定义
    Widget& operator=(Widget&&) noexcept;
    Widget(const Widget&);                     // 拷贝：要么深拷贝 Impl，要么 =delete
    void draw() const;
private:
    struct Impl;                               // 前置声明即可
    std::unique_ptr<Impl> impl_;               // 每个对象一次堆分配
};
```

| 用 pimpl 的时机 | 不用 pimpl 的时机 |
|----------------|-------------------|
| 大型类、私有成员常变、被广泛 include | 小型值类（Rule of Zero，ph13）、热路径上的小对象 |
| 头文件是公共 API、要压编译时间/依赖 | 私有实现只在少数 .cpp 用 |
| 想隐藏实现（闭源、避免私有头泄漏） | 成员全是标准库类型、变也不影响编译 |

pimpl 陷阱：① `unique_ptr<Impl>` 的析构/移动若内联在头文件，会在 Impl 不完整处实例化删除器——编译错或 UB，所以**析构与移动必须在 .cpp 定义**；② 拷贝语义要自己定（深拷贝或禁拷贝），Rule of Five 逃不掉（C.21）；③ 每对象一次堆分配 + 每方法一次间接，热路径要掂量（性能实测属 ph18，目录待建）。pimpl 与「虚函数接口」是两种隔离：pimpl 隔离**编译依赖**，虚接口隔离**类型依赖**，可叠加使用。C++20 的 modules 能在语言层部分替代 include 依赖管理（属 ph06 现代 C++（C++11~C++23）阶段内容，此处不展开）。

### 3.8 分层架构与模块边界

分层是把「关注点」切成纵向切片，让每层只回答一类问题。数据库/存储类 C++ 工程的典型分层（本阶段 project/ 即此结构的 demo 版）：

```text
┌─ main.cpp         组合根：建对象、接线、启动（只有这里知道具体实现）       ┐
│      │ 只依赖 QueryEngine（组装层接口）                                  │
├─ 组装层 QueryEngine 注册表、规格校验、管道工厂、执行、事件               │
│      │ 只依赖 IExecutor / IStorage 抽象                                 │
├─ 执行层 IExecutor + 各执行节点（Scan/Filter/Project/Limit）             │
│      │ 只依赖 IStorage 抽象（叶子节点是唯一接触存储之处）                │
├─ 存储层 IStorage 契约 + MemoryTable 实现                                │
└─────────────────────────────────────────────────────────────────────────┘
```

**依赖方向规则**：高层依赖低层**抽象**、低层不反向依赖高层、同层尽量不互相依赖——依赖箭头自上而下单向。违反它的症状是**循环依赖**（头文件 A include B、B include A → 编译失败或脆弱的顺序耦合），三种断法：把共用的部分提成接口/数据、用依赖倒置让高层定义抽象而低层实现它、用事件把「A 调用 B」改成「A 广播、B 订阅」。roadmap 必会概念「**架构设计要服务测试和演进**」：分层让测试能逐层进行（存储换实现、执行器加节点、UI 换壳，都不炸其他层），也让演进有落脚点——本阶段 project/ 的「换一个 `MemoryTable` 实现只需改 `add_table` 一行」就是分层红利的最小演示。

**模块边界的物理化**：逻辑分层要落到物理边界才守得住——目录结构（每层一个目录）、命名空间（`storage::`/`executor::` 等）、**头文件所有权**（谁的头文件谁改，跨层 include 即跨层依赖，ph10 的构建目标拆分在此复用）。检查手段很朴素：`grep '#include'` 看依赖方向、`nm` 看符号归属（ph10 工具）、把「高层的 .cpp 直接 include 低层实现头」视为设计事故。分层不是越多越好：两层能讲清的事别拆五层——每多一层多一份间接与转发样板。

> 本阶段只要「接口 + 实现分层」的组织骨架，**真实存储引擎内核（WAL/MemTable/SSTable/Compaction/Buffer Pool）属于 ph22 存储引擎与数据库内核专项阶段（目录待建）**，这里用最小内存表演示的是「层怎么切、依赖怎么走」，不是引擎本身。

### 3.9 事件驱动设计：回调、事件对象与发布-订阅

事件驱动 = **控制流由「发生了什么」驱动，而不是由调用者顺序驱动**。本阶段的边界：进程内、单线程、同步派发；异步事件循环与线程模型属 ph08/ph18（见 3.4 的 blockquote）。三个基础概念先分清：

| 概念 | 是什么 | 例子 |
|------|--------|------|
| 事件 | 已经发生的事实（过去时） | 「订单已支付」「温度变到 21.5」 |
| 命令 | 将要做的意图（将来时，可拒绝） | 「取消订单」「关闸门」 |
| 消息 | 传输载体（事件或命令都经它传送） | 队列里的一条记录 |

**同步事件派发**的最小形态就是 3.4 的观察者。升级路径一：**事件对象化**——回调参数从「一长串散参数」升级为「事件结构体」（`struct OrderPaid { order_id; amount; paid_at; }`），新增字段不炸订阅方签名，订阅方只读自己关心的字段。升级路径二：**发布-订阅（pub/sub）**——观察者里 subject 直接引用订阅者（点对点）；发布-订阅中间加事件总线/通道，发布者不认识订阅者、订阅者按主题（topic）过滤，双方彻底解耦：

```cpp
// 事件总线的通道化设计：每类事件一个 std::function 列表（同 3.4 的 Token 管理）
class EventBus {
public:
    using EventId = std::size_t;
    EventId subscribe(const std::string& topic,
                      std::function<void(const Event&)> listener);  // Event 为基类，见下
    void publish(const std::string& topic, const Event& event);     // 同步广播
    // 实现要点：快照遍历 + 异常隔离（同 ex03）；Event 用类型擦除或 variant 承载
};
```

C++ 实现形态对照：直接回调列表（ex03，最简单）、按主题的事件总线（`unordered_map<string, vector<function>>`，演示级）、信号槽库（Boost.Signals2：连接句柄 + 线程安全 + 组合顺序，成熟但引入依赖）、命令队列（把事件入队再派发——跨线程边界，ph08）。陷阱：① **不要依赖回调的注册顺序**（同步派发顺序是当前实现细节）；② **重入**：回调里再次 `publish` 同一事件会导致递归深度不可控——约定「通知期间禁止重入」或用派发队列延后；③ 回调抛异常要隔离（3.4）；④ 事件对象该用**值语义**（拷贝安全），不要在事件里传裸指针引用易逝资源。

> 事件驱动在本阶段 = **同步、进程内、单线程**；**线程池派发、事件循环、异步 IO（epoll/io_uring、Boost.Asio 异步模型）属于 ph08 并发编程阶段与 ph18 性能优化与 Profiling 阶段（目录待建）**——先把同步事件写对，异步化是增量不是重写（ph09 已埋此伏笔）。

### 3.10 SOLID 在 C++ 的落地

SOLID 是五个设计原则的缩写，本阶段把 roadmap 点名的模式与架构主题挂到它下面收口：

| 原则 | 一句话 | C++ Core Guidelines 挂钩 | 本阶段落点 |
|------|--------|--------------------------|-----------|
| SRP 单一职责 | 一个类/函数只回答一个问题 | F.2/F.3（函数单一逻辑）、C.2 | 3.8 分层；「接口为什么拆」 |
| OCP 开闭原则 | 对扩展开放、对修改关闭 | I.*（接口显式） | 3.2 注册表工厂、3.3 策略 |
| LSP 里氏替换 | 派生类必须能替换基类而不破坏契约 | C.128（override）、C.135 等 | 3.1 载体选择、虚接口契约 |
| ISP 接口隔离 | 客户端不依赖用不到的方法 | I.4（精确强类型接口） | 3.7 小接口、pimpl |
| DIP 依赖倒置 | 高层不依赖低层，都依赖抽象 | R.20/I.11（所有权经接口） | 3.6 依赖注入、3.8 分层 |

C++ 落地时的三个特有坑：① **LSP 与 const 承诺**：基类接口标了 const（Con.2），派生类实现偷偷改状态或用 `mutable` 绕过——用 const 写进契约、靠 review 与工具守（ph14 的「接口即承诺」在此复用）；② **值切片**：按值传多态对象会切成基类子对象——多态对象必须经指针/引用传递（F.16 的例外，练习与 project 全程用 `unique_ptr<IExecutor>` 正是为躲此坑）；③ **override 语义**：漏写 `override` 的「重写」其实是隐藏（name hiding），基类接口变更会静默断掉派生——编译器不报错，ph16 的 clang-tidy `modernize-use-override` 门禁就是为抓这个。最后一条元纪律（roadmap 必会概念）：**SOLID 与模式都是沟通语言，不是套模板**——每引入一层抽象都该能回答「它服务哪个真实变化点」，为抽象而抽象（YAGNI 的张力）是比没有模式更贵的技术债。

## 4. 底层原理

### 4.1 虚函数与 vtable：两次间接的代价

带虚函数的对象在头部藏一个 **vptr**（虚表指针），指向该类的 **vtable**（虚函数表）。虚调用 = 先取 vptr → 再经 vtable 取函数指针 → 跳转，比直接调用多两次内存间接：

```text
对象 obj ──▶ vptr ──▶ vtable[0] ──▶ &Circle::area()      ← 虚调用路径
                          [1] ──▶ &Circle::name()
                          ...       析构函数（虚析构让 delete 走对析构器）
```

代价分两部分：**可预测的间接**（通常几纳秒）与**不可内联**（虚调用阻止跨调用点内联，这才是热路径上更大的损失）。因此工程纪律是：默认值语义直接调用（内联、无间接）；只在「运行期多态是需求本身」时上虚函数；模式引入的虚层先写对，性能账留给 ph18 用数据算（**模式开销的实测属 ph18 性能优化与 Profiling 阶段，目录待建**）。基类析构声明为 `virtual`（C.35）是为了让 `delete base_ptr` 走派生类析构——pimpl 的 `unique_ptr` 删除器同理，凡「经基类指针销毁」都必须虚析构。

### 4.2 std::function 的类型擦除：把「任意可调用」存成统一类型

`std::function` 内部是**类型擦除**：构造时把目标（lambda/函数指针/成员函数绑定）的调用约定「擦掉」，存进统一存储。存储策略 = **小对象优化（SBO）**：目标小（通常小于等于两三个指针）直接内嵌在 `std::function` 对象里，零堆分配；目标大（捕获多的 lambda）才退到堆上。调用 = 经内部函数指针跳转（等价于一次间接）。因此 `std::function` 的开销 ≈ 虚调用级别，但**换来了不建类层次的多态**（3.1 表格）。两个机制性推论：① `std::function` 要求目标**可拷贝**（拷贝语义要复制内嵌目标或深拷贝堆目标）——move-only 目标装不进去（C++17 的边界，3.3 已列）；② 空 `std::function` 调用抛 `std::bad_function_call`——不是 UB，但该判空（`operator bool`）。

### 4.3 所有权与对象图：模式里的指针往哪走

模式的正确性一大半是「谁拥有谁」的正确性。三类指针按所有权语义分工（R.20/R.21/R.3）：`unique_ptr` = 独占所有权（对象图里的树边：Context→Strategy、执行器节点→上游、pimpl→Impl）；`shared_ptr` = 共享所有权（对象图里的 DAG 边：两个服务共享同一存储）；裸指针/引用 = 非拥有观察（组合根注入的存储视图、subject 眼里的订阅者）。模式与所有权的固定搭配：工厂返回 `unique_ptr`（所有权随返回值转移，ex01）；策略被上下文 `unique_ptr` 独占（ex02）；**subject 不拥有观察者**——观察者生命周期自己管（3.4 的三条路线）；DI 注入用引用/shared_ptr 表达「借用/共享」（ex05）。反模式：裸指针容器（泄漏或悬挂二选一）、`shared_ptr` 环（互相引用永不释放——用 `weak_ptr` 断环）。一句总纲：**先在纸上画对象图的边，边上的所有权类型定了，泄漏与悬挂问题就消掉大半**。

### 4.4 物理分层：include 方向就是依赖方向

编译期视角下，「模块 A 依赖模块 B」的物理形态是 **A 的翻译单元 include 了 B 的头文件**。于是物理边界纪律有三条：① **include 方向 == 依赖方向**——高层 .cpp 只 include 低层接口头（`executor.h` 依赖 `storage.h` 的 `IStorage`，绝不 include `MemoryTable` 的实现细节）；② **接口头要薄**——pimpl 让公开头只剩 `unique_ptr<Impl>` 与函数声明，include 依赖从「十几个私有头」降到「标准库几个头」，改私有成员不触发全量重编；③ **头文件自包含**（SF.11：每个头 include 它用到的全部声明）+ `#pragma once`（SF.8）——自包含头之间如果形成环，就是 3.8 说的循环依赖在编译期的显影。构建目标（ph10 的 CMake/Makefile 拆分）是这条纪律的机器执行者：每个逻辑层一个目标，链接器报的未定义符号就是跨层依赖漏网的证据。

## 5. 使用场景

| 真实工程场景 | 用什么 | 为什么 |
|--------------|--------|--------|
| 多厂商设备/驱动，同一能力不同实现 | 工厂 + 适配器 | 创建收拢（工厂），历史/异构接口翻译（适配器） |
| 协议解析、编解码、序列化格式可替换 | 策略 | 换协议/格式 = 换策略对象，解析器本体不动 |
| UI 刷新、图表更新、配置热更新 | 观察者/事件 | 状态一变，所有关心者自动得到通知 |
| 业务依赖存储/网关/日志，测试要换假实现 | DI + 接口 | mock = 注入接口的另一实现（ph16 兑现） |
| 大型模块切分（通信/存储/业务） | 分层 + 接口隔离 | 依赖单向、边界可守、逐层可测（3.8） |
| 大类的头文件被广泛 include、编译慢 | pimpl | 编译防火墙，改私有成员不炸消费者 |

**什么时候不用它**（与上面同等重要）：① 单一实现、无替换需求时不上接口——接口的第一价值是「有第二个实现或 mock」，没有就 YAGNI；② 小范围局部逻辑直接调用更直白，模式是为「变化点」付的保费，没有变化点不投保；③ 算法编译期已定（性能敏感、类型唯一）用模板/直接调用，别上运行期策略（ph05 边界）；④ 跨线程通知别用裸回调——需要事件队列/锁内派发设计（ph08）；⑤ 虚调用与 `std::function` 的间接成本在热点里是否值得，先测量再下结论（ph18，目录待建）。

**与其他语言的对比**（为 analysis/ 与 Tenet 合成积累素材）：

| 维度 | C++ | Rust | Go | Java | Python |
|------|-----|------|----|------|--------|
| 接口形态 | 抽象基类 / `std::function` 类型擦除 | `trait` + 泛型（无继承式子类型） | `interface` 隐式满足（鸭子类型） | `interface` + 注解 | 鸭子类型（无接口关键字） |
| 组合 vs 继承 | 组合 + 虚接口 | 组合默认（无继承） | 组合默认（嵌入） | 继承常见（框架文化） | 继承常见 + mixin |
| DI 落地 | 手写组合根为主，容器少见 | 无反射，构造注入 + trait | 构造注入惯例，无容器文化 | 注解容器（Spring 级生态） | 装饰器/工厂为主 |
| 观察者 | `std::function` + Token | 回调 + 通道 | `chan` + goroutine 事件循环 | 监听器接口 + 事件对象 | 信号/回调 |
| 模式讨论热度 | 高（GoF 原书语言） | 中（偏好语言特性替代模式） | 低（惯例优先） | 高（企业架构文化） | 中 |

一句话：**C++ 的模式讨论最「方法论化」但最需要自己动手**——GoF 用 C++ 起家，而 C++ 的每个模式都有手写 vs 库 vs 语法替代三条路，选择权（和责任）都在开发者手里。

## 6. 代码示例

> 说明：`examples/`/`exercises/`/`project/` 全部代码**已验证**（Apple clang 21.0.0，`-std=c++17 -Wall -Wextra` 本机实测：编译零警告、examples/exercises 运行通过、`make test` 自测全绿）。完整可运行文件在 [`examples/`](./examples/)，此处展示关键片段。下列命令在 examples/ 目录内执行。

### 示例 1：工厂（examples/ex01-factory.cpp）

对应 roadmap 学习内容「工厂」与 3.2。注册表工厂 + 简单工厂对照：

```cpp
// examples/ex01-factory.cpp —— 节选：注册表工厂（新增类型不改工厂本体）
class ShapeFactoryRegistry {
public:
    static ShapeFactoryRegistry& instance() {
        static ShapeFactoryRegistry inst;  // 函数内静态：延迟初始化、线程安全
        return inst;
    }
    void register_kind(const std::string& kind, ShapeMaker maker) {
        makers_[kind] = std::move(maker);
    }
    std::unique_ptr<Shape> make(const std::string& kind, double a, double b) const {
        const auto it = makers_.find(kind);
        if (it == makers_.end()) throw std::invalid_argument("unknown shape: " + kind);
        return it->second(a, b);  // 类型已被擦进 std::function
    }
private:
    std::unordered_map<std::string, ShapeMaker> makers_;  // ShapeMaker = std::function<...>
};
```

```bash
# 1. 编译：
clang++ -std=c++17 -Wall -Wextra ex01-factory.cpp -o /tmp/ph17cpp-ex01
# 2. 运行（预期：断言行 + 三种形状面积，退出码 0）：
/tmp/ph17cpp-ex01
```

### 示例 2：策略（examples/ex02-strategy.cpp）

对应 roadmap 学习内容「策略」与 3.3。虚函数策略与 `std::function` 策略同台对照、按名切换：

```cpp
// examples/ex02-strategy.cpp —— 节选：std::function 即策略，运行期按名换算法
using LogFormatter = std::function<std::string(const LogRecord&)>;
// 注册表：plain / kv 两种策略；运行期 find 后 set_formatter 即切换
const std::unordered_map<std::string, LogFormatter> named_formatters{ /* ... */ };
```

```bash
# 1. 编译：
clang++ -std=c++17 -Wall -Wextra ex02-strategy.cpp -o /tmp/ph17cpp-ex02
# 2. 运行（预期：两种载体输出对照 + 断言行，退出码 0）：
/tmp/ph17cpp-ex02
```

### 示例 3：观察者（examples/ex03-observer.cpp）

对应 roadmap 学习内容「观察者」与 3.4。RAII 退订 Token + 快照遍历 + 回调异常隔离：

```cpp
// examples/ex03-observer.cpp —— 节选：订阅返回句柄，句柄析构自动退订
class WeatherStation {
public:
    class Subscription { /* 禁拷贝可移动；析构调 unsubscribe(id) */ };
    Subscription subscribe(std::function<void(double)> listener) {
        listeners_.push_back(std::move(listener));
        return Subscription(this, next_id_++);
    }
};
```

```bash
# 1. 编译：
clang++ -std=c++17 -Wall -Wextra ex03-observer.cpp -o /tmp/ph17cpp-ex03
# 2. 运行（预期：通知计数变化 + 异常隔离演示，退出码 0）：
/tmp/ph17cpp-ex03
```

### 示例 4：适配器（examples/ex04-adapter.cpp）

对应 roadmap 学习内容「适配器」与 3.5。对象适配器 + C 回调函数适配器：

```cpp
// examples/ex04-adapter.cpp —— 节选：老接口 append_line 适配成目标接口 ILogSink
class LegacySinkAdapter final : public ILogSink {
public:
    explicit LegacySinkAdapter(LegacyTextSink& legacy) : legacy_(legacy) {}
    void write(const std::string& level, const std::string& message) override {
        legacy_.append_line(level + ": " + message);  // 转接口、不转语义
    }
private:
    LegacyTextSink& legacy_;  // 组合优先于继承
};
```

```bash
# 1. 编译：
clang++ -std=c++17 -Wall -Wextra ex04-adapter.cpp -o /tmp/ph17cpp-ex04
# 2. 运行（预期：三种后端各一行输出 + 断言行，退出码 0）：
/tmp/ph17cpp-ex04
```

### 示例 5：依赖注入与组合根（examples/ex05-di.cpp）

对应 roadmap 学习内容「依赖注入思想」与 3.6。业务层只依赖接口、组合根组装、mock 可换：

```cpp
// examples/ex05-di.cpp —— 节选：组合根是全程序唯一知道「具体实现是谁」的地方
auto store = std::make_shared<MemoryOrderStore>();
OrderService checkout(store, std::make_shared<StubPaymentGateway>(true));   // 成功网关
OrderService failing(store, std::make_shared<StubPaymentGateway>(false));   // mock：失败网关
```

```bash
# 1. 编译：
clang++ -std=c++17 -Wall -Wextra ex05-di.cpp -o /tmp/ph17cpp-ex05
# 2. 运行（预期：下单成功/失败两行 + 断言行，退出码 0）：
/tmp/ph17cpp-ex05
```

## 7. 总结

### 关键要点

1. **模式 = 给反复出现的结构问题起名字**（roadmap 必会概念：模式是沟通语言，不是套模板）——先有变化点，再有模式，别反向套
2. **两个运行期载体**：抽象基类 + `unique_ptr`（多虚方法、跨 TU 扩展）vs `std::function`（单入口、lambda 捕获、免类层次）；编译期载体属 ph05（3.1）
3. **组合优于继承**：继承绑定实现与「是一个」类型关系，组合降级为「有一个」，替换/装饰/测试都容易（3.1）
4. **工厂三纪律**：返回 `unique_ptr`（R.11/R.20）、创建收拢到组合点、注册表工厂让新增类型不改工厂本体（3.2、ex01）
5. **策略 = 可替换算法**：上下文持策略（所有权归上下文），协议解析/格式输出是典型场景；move-only 目标装不进 C++17 的 `std::function`（3.3、ex02）
6. **观察者的灵魂是生命周期**：RAII 退订 Token、通知快照、异常隔离、变化检测（3.4、ex03）
7. **适配器转接口不转语义**：对象适配器组合优先；单函数接口用 lambda 适配，不建类（3.5、ex04）
8. **依赖方向指向稳定抽象**：构造注入 + 组合根，mock = 注入接口的另一实现（ph16 伏笔兑现）；C++ 手写组合根优于 DI 容器（3.6、ex05）
9. **接口要小、物理要薄**：ISP 拆小接口；pimpl 编译防火墙，析构/移动必须在 .cpp 定义（3.7）
10. **分层与依赖方向可守**：include 方向 = 依赖方向；循环依赖三种断法；架构设计要服务测试和演进（3.8、4.4）
11. **事件驱动先同步后异步**：事件对象 + 发布订阅解耦发布者订阅者；异步化是增量不是重写（3.9）
12. **SOLID 五个字母落到 C++ 规则**：SRP/OCP/LSP/ISP/DIP 各有 Core Guidelines 挂钩与特有坑（值切片、override 隐藏、const 承诺破坏）（3.10）

### 阶段验收清单

- [ ] 能**解释模块职责**（roadmap 验收）：随手指出 project/ 里 storage/executor/engine 三层各回答什么问题、依赖箭头往哪指
- [ ] 能**隔离硬件、协议和业务逻辑**（roadmap 验收）：能说出「协议解析该是业务层可替换的策略」「硬件差异该被接口 + 适配器挡住」「业务层不该知道存储是内存还是文件」
- [ ] 能**通过接口 mock 依赖**（roadmap 验收）：能讲清 ex05 里 mock 网关为什么不用改 `OrderService`；自己给练习 3 的 `KVClient` 换一个假存储
- [ ] 能画出对象图并标注每条边的所有权类型（unique/shared/裸观察），说出悬挂与泄漏的对应解法（4.3）
- [ ] 能说清虚函数 vs `std::function` 在「存储、捕获、拷贝、开销」四个维度上的差别（3.1/4.2）
- [ ] 能解释观察者生命周期三条路线（销毁顺序纪律 / RAII Token / weak_ptr）各自的适用前提（3.4）
- [ ] 能指出一段代码违反哪个 SOLID 字母并给出最小修正（3.10 表格）
- [ ] 能说清本阶段与 ph18（性能实测）的接口：模式间接层的开销由数据裁决（6 章示例可为 ph18 的热点分析对象）

### 跨语言对比

见第 5 节末的对比表——C++ 处于「模式讨论最方法论化、但每个模式都有手写/库/语法替代三条路」的位置；Rust 用 trait 与枚举消解掉一批模式（策略 → trait 对象或枚举分派、工厂 → 构造函数返回 impl Trait），Go 用隐式接口把「依赖方向」变成鸭子类型约定，Java 把 DI 与事件做成了框架文化。对 Tenet 合成的启示：**哪些模式应该被语言特性吸收（观察者 → 回调类型、工厂 → 所有权类型），哪些该留给开发者（分层、依赖方向）**——本阶段的对比是 analysis/ 的一手素材。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 4 题，与 roadmap ph17「练习」小节一一对应：策略模式封装协议解析（★★★）、观察者实现状态变化通知（★★★）、为存储引擎抽象 IStorage 接口（★★★）、为查询执行器抽象 IExecutor 接口（★★★）。每题要求 `clang++ -std=c++17 -Wall -Wextra` 零警告 + 退出码语义正确。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**查询执行器接口设计 demo**——接口 + 分层的小工程（`IStorage` → `IExecutor` → 组装层 `QueryEngine`），把本阶段几乎全部手法（接口抽象、分层与依赖方向、工厂组装、DI 注册表、完成事件、可诊断失败）收敛进一个可运行 demo（`make run`）与自测（`make test`）。roadmap 的另一个推荐项目「存储引擎模块分层 demo」的思路由 project/ 的 `IStorage` 抽象 + 练习 3 覆盖；**本项目是模块组织 demo，不是真引擎——真引擎内核属 ph22 存储引擎与数据库内核专项阶段（目录待建），README 中已注明边界**。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`make clean && make test` 退出码 0、双编译器零警告）

### 下一阶段

下一阶段是 **ph18 性能优化与 Profiling 阶段**（roadmap 第 18 节，目录待建，届时以 roadmap 为准）：本阶段引入的每层抽象都有代价——虚调用与 `std::function` 的间接、pimpl 的堆分配与转发、事件派发的快照拷贝、分层之间的调用开销；ph18 回答「怎么用数据裁决这些代价值不值」：perf/gprof/VTune/Tracy 剖面、CPU/内存 profile、cache locality、拷贝消除、分配次数优化，并会对本阶段遗留的「模式 vs 裸写」给出 benchmark 结论（本阶段 project/ 的执行器管道与 examples/ 的示例可直接作为 ph18 的热点分析对象——这就是本阶段与 ph18 的衔接：**先写对结构，再用数据决定要不要为性能绕开结构**）。
