# examples —— C++ 设计模式与架构能力阶段完整示例

验证环境（计划）：macOS arm64，Apple clang 21.0.0（`c++`）+ Homebrew clang 21.1.8（`clang++`），C++17（libc++）。**全部示例已验证**（Apple clang 21.0.0，`-std=c++17 -Wall -Wextra` 本机实测：5 个示例编译零警告、运行通过）；代码写法以 `clang++ -std=c++17 -Wall -Wextra` 能过为目标（零警告写法：无裸 new/delete、Rule of Zero/Five、`override`、`enum class`、`nullptr`、`const&` 传参——C++ Core Guidelines 要点）。**构建产物一律输出到 /tmp，验证后清理，仓库不落二进制**。以下编译/运行命令均在 examples/ 目录内执行。

| 文件 | 说明 | 构建/运行 | 验证状态 |
|------|------|-----------|----------|
| `ex01-factory.cpp` | 工厂模式：简单工厂 → 注册表工厂（unique_ptr 所有权、开闭原则、注册表可枚举） | `clang++ -std=c++17 -Wall -Wextra ex01-factory.cpp -o /tmp/ph17cpp-ex01 && /tmp/ph17cpp-ex01` | 已验证（本机实测） |
| `ex02-strategy.cpp` | 策略模式：虚函数策略 vs std::function 策略 + 按名选择策略注册表 | `clang++ -std=c++17 -Wall -Wextra ex02-strategy.cpp -o /tmp/ph17cpp-ex02 && /tmp/ph17cpp-ex02` | 已验证（本机实测） |
| `ex03-observer.cpp` | 观察者模式：一对多状态通知 + RAII 退订 Token（防悬挂）+ 通知快照 + 回调异常隔离 | `clang++ -std=c++17 -Wall -Wextra ex03-observer.cpp -o /tmp/ph17cpp-ex03 && /tmp/ph17cpp-ex03` | 已验证（本机实测） |
| `ex04-adapter.cpp` | 适配器模式：对象适配器（Legacy → 目标接口）+ C 回调函数适配器 | `clang++ -std=c++17 -Wall -Wextra ex04-adapter.cpp -o /tmp/ph17cpp-ex04 && /tmp/ph17cpp-ex04` | 已验证（本机实测） |
| `ex05-di.cpp` | 依赖注入与组合根：业务层只依赖接口，组合根组装，mock 可替换（兑现 ph16 可测试性伏笔） | `clang++ -std=c++17 -Wall -Wextra ex05-di.cpp -o /tmp/ph17cpp-ex05 && /tmp/ph17cpp-ex05` | 已验证（本机实测） |

## 示例 1：工厂（ex01-factory.cpp）

对应主文档 3.2 与 roadmap 学习内容「工厂」。

```bash
# 1. 编译：
clang++ -std=c++17 -Wall -Wextra ex01-factory.cpp -o /tmp/ph17cpp-ex01
# 2. 运行（预期：断言行 + 三种已注册形状的面积 + 全部通过，退出码 0）：
/tmp/ph17cpp-ex01
```

教学要点：① 工厂把「怎么创建」从「怎么使用」拆出去——调用方只依赖 `Shape` 接口；② 工厂返回 `unique_ptr<Shape>`，所有权随返回值转移（R.20），无需 delete；③ 注册表工厂（`std::function` 作工厂函数）让「新增类型」只加一个注册 lambda，工厂本体零改动——开闭原则；④ 注册表可枚举、可运行期增删，这是 switch 式简单工厂做不到的。

## 示例 2：策略（ex02-strategy.cpp）

对应主文档 3.3 与 roadmap 练习「用策略模式封装协议解析」（载体技术同款：策略 = 可替换算法）。

```bash
# 1. 编译：
clang++ -std=c++17 -Wall -Wextra ex02-strategy.cpp -o /tmp/ph17cpp-ex02
# 2. 运行（预期：两行 PLAIN/KV + 带前缀行 + 按名选中的 KV 行 + 全部通过，退出码 0）：
/tmp/ph17cpp-ex02
```

教学要点：① 策略 = 算法族封装为可替换单元，上下文持策略、运行期可换；② 两种载体对照：抽象基类（类型稳定、可跨 TU 扩展）vs `std::function`（值语义、lambda 捕获状态、免类层次）——取舍见主文档 3.3 表格；③ 策略按名切换 = 策略注册表（与 ex01 工厂注册表同构）。

## 示例 3：观察者（ex03-observer.cpp）

对应主文档 3.4 与 roadmap 学习内容「观察者」、练习「用观察者实现状态变化通知」。

```bash
# 1. 编译：
clang++ -std=c++17 -Wall -Wextra ex03-observer.cpp -o /tmp/ph17cpp-ex03
# 2. 运行（预期：温度变更日志 + 退订后不再通知 + 异常被隔离 + 全部通过，退出码 0）：
/tmp/ph17cpp-ex03
```

教学要点：① 一对多通知：subject 只持回调，不认识具体订阅者；② C++ 第一大坑是「观察者销毁后 subject 仍握着指针」——本示例用 RAII 退订 Token（析构自动退订）把「记得退订」变成编译器保证；③ 通知期间订阅列表可能被回调修改 → 快照拷贝防迭代器失效；④ 一个订阅者抛异常不该打断全体 → try/catch 隔离（E.17 的务实面）。

## 示例 4：适配器（ex04-adapter.cpp）

对应主文档 3.5 与 roadmap 学习内容「适配器」。

```bash
# 1. 编译：
clang++ -std=c++17 -Wall -Wextra ex04-adapter.cpp -o /tmp/ph17cpp-ex04
# 2. 运行（预期：三种后端各输出一行 + 全部通过，退出码 0）：
/tmp/ph17cpp-ex04
```

教学要点：① 适配器让「新代码的目标接口」与「改不得的老接口」协作——接口转换、语义不变；② 对象适配器持老对象引用（组合优先于继承，roadmap 必会概念）；③ 单函数接口可用函数适配器（自由函数/C 回调包进接口），不必建类；④ 适配器是「转接口」不是「补设计」——老接口语义缺口（如没有级别概念）要由适配器显式补齐，别把适配器当万能胶掩盖坏接口。

## 示例 5：依赖注入与组合根（ex05-di.cpp）

对应主文档 3.6 与 roadmap 学习内容「依赖注入思想」、验收「能通过接口 mock 依赖」。

```bash
# 1. 编译：
clang++ -std=c++17 -Wall -Wextra ex05-di.cpp -o /tmp/ph17cpp-ex05
# 2. 运行（预期：下单成功/失败两行 + 全部通过，退出码 0）：
/tmp/ph17cpp-ex05
```

教学要点：① 业务层只依赖接口（IOrderStore / IPaymentGateway），具体实现只在**组合根**（main 组装处）出现一次；② 构造注入是 C++ 主流注入方式——依赖从参数进，可见、可换、可 mock；③ 生命周期由所有权类型表达：单消费者用 `unique_ptr`，多消费者共享用 `shared_ptr`（R.21）；④ mock 不是特殊技术——注入接口的另一实现而已（ph16「可测试性从接口开始」在此兑现）。
