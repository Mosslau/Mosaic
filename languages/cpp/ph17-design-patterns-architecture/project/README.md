# ph17 阶段项目：查询执行器接口设计 demo

对应 roadmap ph17「推荐项目」第二个「查询执行器接口设计 demo」（第一个「存储引擎模块分层 demo」的思路以本项目中的 `IStorage` 抽象 + 练习 3 覆盖）。**边界声明：本项目是「接口 + 分层」的模块组织 demo，不是真查询引擎**——无 SQL 解析器、无索引、无 WAL/MemTable/SSTable/Compaction/Buffer Pool，那些是 [ph22 存储引擎与数据库内核专项阶段](../../ph22-storage-engine-db-kernel/22-storage-engine-db-kernel.md)的内容。本项目只演示一件事：**中大型模块怎么靠接口、分层、工厂与依赖注入组织起来**（roadmap 阶段目标「用恰当抽象组织中大型 C++ 项目」）。

## 需求

做一个极小的内存表查询 demo：上层用「查询规格」（想要什么表、过滤条件、选哪些列、限量多少行）描述意图，引擎把它组装成一条**可执行执行器管道**并运行，全程除组合根外不出现任何具体表类型。数据与查询都是演示级（列值用字符串承载），重点在分层与接口。

## 功能清单

| 功能 | 说明 |
|------|------|
| 存储层（`storage.h/.cpp`） | `Row`（行）+ `IStorage`（存储契约：表名/行数/取行/列名）+ `MemoryTable`（内存表实现） |
| 执行层（`executor.h/.cpp`） | `IExecutor`（pull 模型：open/next/close/describe）+ 四个节点：`TableScanExecutor` / `FilterExecutor` / `ProjectExecutor` / `LimitExecutor`，节点组合即管道 |
| 组装层（`engine.h/.cpp`） | `QueryEngine`：注册表管理（DI 落点）、规格校验（未知列/未知表/非法操作符抛可诊断异常）、管道组装（工厂职能）、执行入口、完成事件 |
| 入口（`main.cpp`） | 演示模式（打印执行计划 + 结果行 + 完成事件）与自测模式（`--selftest`，退出码即 CI 信号） |
| `Makefile` | `make` / `make run` / `make test` / `make clean`，产物隔离 `build/` |

## 分层与依赖方向

```text
main.cpp（组合根：建表 → 注册 → 组装 → 执行）
   │  只依赖 QueryEngine + 建表辅助
   ▼
engine.h/cpp（组装层：注册表、规格校验、管道工厂、执行、事件）
   │  只依赖 IExecutor / IStorage 抽象
   ▼
executor.h/cpp（执行层：IExecutor 与四个节点）
   │  只依赖 IStorage 抽象（叶子节点 TableScan 是唯一接触存储之处）
   ▼
storage.h/cpp（存储层：IStorage 契约 + MemoryTable 实现）
```

依赖方向自上而下、单向；任何一层都不知道「更底层」的另一个具体实现（依赖方向指向稳定抽象——roadmap 必会概念）。`IExecutor` / `IStorage` 就是练习 3、4 接口抽象在项目里的落地；`FilterExecutor` 把条件实现成了注入的谓词（策略思想的变体）；`QueryEngine` 把「spec → 管道」做成了集中工厂（ex01 思想）；`set_listener` 的完成事件是事件驱动设计的最小形态（ex03 思想）。

## 验收标准

- [ ] `make clean && make test` 退出码 0：5 组自测用例（过滤+投影+限量 / 等值过滤 / 数值比较 / 数值比较排除 / 失败可诊断 ×3）全部 [通过]
- [ ] `make run` 打印三条查询的执行计划（如 `scan(users) -> filter(age >= 18) -> project(name, age) -> limit(3)`）与结果行，每条查询后打印完成事件（rows_in/rows_out）
- [ ] 双编译器 `clang++ -std=c++17 -Wall -Wextra` 零警告（Apple clang 21 / Homebrew clang 21）
- [ ] 代码无裸 new/delete（R.11）；基类析构 virtual（C.35）；重写全部 `override`（C.128）；查询类方法尽量 const（Con.2）；头文件 `#pragma once` 自包含（SF.8/SF.11）
- [ ] 未知列 / 未知表 / 非法操作符均抛 `std::invalid_argument` 且消息含上下文（ph09 纪律）
- [ ] 能口头讲清本项目的分层图与每条依赖方向，以及「为什么不把具体表类型传进执行器」

## 扩展方向（可选）

- **第二个存储实现**：写 `FileStorage`（把行追加到文本文件）或 `IndexedStorage`（内存中按列建索引），`add_table` 一行注册即换底层——`IStorage` 契约的替换价值立刻可见（衔接 [ph22 存储引擎与数据库内核专项阶段](../../ph22-storage-engine-db-kernel/22-storage-engine-db-kernel.md)）
- **谓词下推**：`LimitExecutor` 提示的 early stop 只是起点；把过滤条件「下推」进 scan 让 scan 直接跳过不满足的行（真引擎的优化骨架，性能实测属 ph18 性能优化与 Profiling 阶段，目录待建）
- **打印执行计划树**：`describe()` 目前是递归拼接的线性文本；改成真正的树形打印（缩进 + 分支）需要给每个节点加 `children()`——顺带练习接口演进
- **类型化列**：把 `Row` 的字符串值换成 `std::variant<int64_t, double, std::string>`，比较器由类型决定（不再需要 engine.cpp 里的字符串猜测）
- **事件对象化**：把完成事件从单回调升级为「事件对象 + 多订阅 + Token 退订」（ex03 全套手法），为 UI/日志/测试探针多路订阅做准备
- **组装自动化**：手写组合根已经很直白；若要体验容器，对照 Boost.DI 的手写 vs 框架取舍（见主文档 3.6）

## 验证环境

- 计划环境：macOS arm64，Apple clang 21.0.0（`c++`）+ Homebrew clang 21.1.8（`clang++`），C++17（libc++）
- 构建：`make`；运行：`make run` 或 `./build/query_demo`；测试：`make test` 或 `./build/query_demo --selftest`；清理：`make clean`
- 验证状态：**已验证**（Apple clang 21.0.0 本机实测：`make` 编译零警告、`make test` 自测全部通过、退出码 0）
