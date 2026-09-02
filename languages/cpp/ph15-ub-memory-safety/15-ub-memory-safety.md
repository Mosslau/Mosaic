# C++ 未定义行为 UB 与内存安全阶段

> 面向高性能系统、存储引擎方向，本阶段系统识别 C++ 中的未定义行为（undefined behavior, UB）——尤其 C++ 特有的内存安全缺口：容器引用/迭代器失效、use-after-move、对象生命周期悬空、数据竞争——并把 Sanitizer（ASan/UBSan/TSan）当复现工具实测每一种 UB 的真实报告。

## 1. 概述

本阶段定位：**能识别并避免 C++ 中最危险的一类错误——未定义行为**。它是整个路线的第 15 步：C 系 ph10 已在 C 语言层面讲过 UB 的四档行为分类与通用类别（越界、UAF、溢出、未初始化、严格别名、对齐——按 C 语义）；本阶段是 **C++ 版**——C++ 继承 C 的全部 UB 类别，又因引用、对象生命周期、移动语义、标准容器、多线程内存模型而多出五类 C++ 特有的悬空与失效。本阶段把 C 系 ph03 的“指针越界是 UB”（该埋线在 C 系 ph03 数组与指针阶段；C++ ph03 内存模型阶段讲对象生命周期，不含此条）、ph04 的“迭代器失效”、ph10 工具链阶段的 ASan/UBSan 用法、ph12 的“move 后状态约束”“不返回局部引用”、ph13 的 RAII、ph14 的“const 承诺被破坏是 UB”提升到同一个高度：**能解释原理、能用 Sanitizer 实测复现、能在代码评审中识别**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 越界访问 | vector / std::array / C 数组三种形态；ASan 与 UBSan 的覆盖差异；`at()` 与手动边界检查（`ex01`） |
| 悬空引用与失效 | 容器扩容引用/迭代器失效、容器先销毁引用悬空——C++ 特有的“引用也可能悬空”（`ex02`） |
| 释放类 | use-after-free 与重复释放的更多形态；RAII/unique_ptr 根治（`ex03`） |
| use-after-move | moved-from 状态“合法但未指定”；解引用 moved-from unique_ptr 是 UB（`ex04`） |
| 数据竞争 | 无同步读写同一对象是 UB；TSan 检测（`ex05`） |
| 类型别名与对齐 | 严格别名违规、union/指针双关、未对齐访问；`std::bit_cast` 正解（`ex06`） |
| 未初始化变量 | 不确定值读取；`-Wuninitialized` 与默认成员初始化器（练习 5、project） |
| 工具定位 | ASan/UBSan/TSan 只当**复现工具**；工具抓不到的部分靠规范与评审（ph16 讲工程化） |

这个阶段只涉及 C++ UB 的分类识别、语义核对与规避，以及把 Sanitizer 当**演示/复现工具**，**不涉及 Sanitizer 工具链的系统化与工程化（ph16 测试、静态分析与代码规范阶段）、并发同步的完整规则与内存序（ph08 并发编程阶段）、对象生命周期与值类别的完整规则（ph12 对象生命周期、值类别与所有权深入阶段）、const_cast 修改真正 const 对象的系统归类（ph14 const 正确性与接口设计阶段已实测）、整数溢出/除零/非法移位等数值类 UB（C 系 ph10 已按 C 语义覆盖，C++ 语义相同，本阶段不重复）和动态库边界的内存约定（ph19，目录待建）** — 那些是其他阶段的内容。承接 C 系 ph10（UB 的 C 语义与四档分类）、ph10 构建、调试与工具链阶段（ASan/UBSan 的编译/运行基础）、ph12（move 后状态约束、不返回局部引用、悬空引用的编译器告警）与 ph13/14（RAII 防 UAF；const 承诺被破坏是 UB）：C 系 ph10 回答了“C 里哪些写法是 UB”，本阶段回答“**C++ 多了哪些 UB、为什么、怎么用工具实测**”；ph12 讲的是“对象何时销毁”，本阶段讲“销毁后/移动后继续使用会怎样”；ph13 的 RAII 是本阶段大部分释放类 UB 的解药。

## 2. 来源与演变

C++ 的 UB 概念继承自 C，但随语言自身的特性（对象生命周期、引用、移动语义、模板）演化出新的 UB 形态。**设计哲学一句话：UB 是“标准不施加任何要求的行为”——编译器把“程序不含 UB”当作优化前提，代价是程序一旦越界，任何结果（含删除整段代码）都合法**。与 C 不同，C++ 的 UB 讨论必须连同**对象生命周期**（何时有效）与**标准库承诺**（容器何时失效、moved-from 是什么状态）一起读——这正是本阶段与 C 系 ph10 的分工：C 的 UB 是“内存与运算”，C++ 的 UB 是“内存 + 生命周期 + 容器 + 移动”。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| C++98 | 1998 | UB 概念随语言标准化（[intro.abstract]）；vector 扩容失效规则随 STL 定型；严格别名规则（[basic.lval]）确立 |
| C++11 | 2011 | **移动语义引入 → moved-from 状态规定为“合法但未指定”**（[lib.types.movedfrom]）；右值引用让“移动后误用”成为新 UB 类别 |
| C++17 | 2017 | `std::string_view` 进入标准库（借用式视图的悬挂风险浮出水面，ph04/ph12 已用）；保证省略 |
| C++20 | 2020 | **`std::bit_cast` 提供安全类型双关**（替代 reinterpret_cast/union 双关）；`span` 进入标准库 |
| 工具链 | 2009~ | TSan（2009）、ASan（2011）、UBSan（2015 前后）进入 GCC/Clang——UB 从“评审才能发现”变成“可实测复现” |
| libc++ 现状 | 2023~ | libc++ 引入 hardening 模式（`_LIBCPP_HARDENING_MODE`），但 `vector::operator[]` 仍不检查（本阶段实测，见 3.1） |

本文示例以 **C++20** 为基线（与 ph11~ph14 一致：roadmap 主线使用 C++20，`-std=c++20` 是稳定度与功能的平衡点；`std::bit_cast` 需 C++20），验证工具链为 **Apple clang 21.0.0（`c++`）+ Homebrew clang 21.1.8（`clang++`）**（标准库 libc++），全部示例与练习已在本环境实际编译运行验证（已验证）；TSan 实测以 Apple clang 为准（Homebrew clang 21.1.8 的 TSan 运行时在本机 arm64 上不稳定，实测崩溃，如实标注）。UB 的语义定义是 C++ 标准**最稳定**的部分之一（四档行为分类与严格别名自 C++98 至今未变）——本阶段讲的“哪些是 UB”长期有效，变的只是工具链抓取能力。

## 3. 语法与参数

> 本节代码块为**教学骨架**：为聚焦当前语法点做了简化，行内注释为讲解所加。完整可运行文件见第 6 节与 [`examples/`](./examples/)（与源文件逐字一致），编译/运行命令与实测报告见 examples/README.md 与各小节“实测”段。

### 3.1 越界访问：三种“数组形态”与两把工具的覆盖差异

C++ 容器与 C 数组一样**不做边界检查**：`v[i]` / `a[i]` 越界是 UB，编译器不拦、不报（标准库的 `operator[]` 契约就是“前置条件：i < size，否则 UB”）。与 C 系 ph10 的区别：C++ 有四种下标形态，检测工具的覆盖各不相同（本阶段实测）：

| 形态 | 越界时 | ASan | UBSan |
|------|--------|------|-------|
| `std::vector`（堆） | 越过堆分配区写入 → ASan 红区 | ✅ `heap-buffer-overflow` | ❌ 静默（`operator[]` 在库实现内部，未被插桩） |
| `std::array`（栈） | 越过栈对象 → ASan 红区 | ✅ `stack-buffer-overflow` | ❌ 静默（同上） |
| C 数组 `int c[3]`（栈） | 下标表达式被插桩 | ✅ | ✅ `index N out of bounds for type 'int[3]'` |
| `at()`（任何容器） | **越界抛 `std::out_of_range`——定义行为** | 无需 | 无需 |

```cpp
// examples/ex01-vector-oob.cpp —— 越界访问（节选，与原文件逐字一致）
    std::vector<int> v = {1, 2, 3};      // size=3, cap=3（实测 libc++ 精确分配）
    std::size_t idx = 3;                 // 运行期下标：编译器无法静态拦截（无 -Warray-bounds）
    std::printf("vec: size=%zu cap=%zu, 写 v[%zu]=100 ...\n", v.size(), v.capacity(), idx);
    v[idx] = 100;                        // UB: 越界写（ASan 报 heap-buffer-overflow）
```

实测（`ex01`，Apple clang 21.0.0）：`v[3] = 100`（size=3/cap=3）→ ASan 报 `heap-buffer-overflow` + `WRITE of size 4` + "located 0 bytes after 12-byte region"，退出码 134，**-O0/-O1/-O2 三档实测均触发**——越界写后紧跟对同一越界位置的 printf 读，写无法被优化器消除（“折叠漏报”的前提是整段访问无观察者，见 4.1；C 系 ph10 4.2 演示的是可整体折叠的表达式场景）。`std::array` 越界读 → ASan `stack-buffer-overflow`（`READ of size 4`）；C 数组运行期下标越界 → UBSan `index 3 out of bounds for type 'int[3]'`。结论：**vector/std::array 的越界靠 ASan，C 数组的越界靠 UBSan，两种工具都要用**；写代码时用 `at()` 或手动边界检查，让越界变成定义行为（异常/错误码），而不是指望工具兜底。

> ⚠️ libc++ 的 hardening 模式（`_LIBCPP_HARDENING_MODE=FAST/EXTENSIVE`）本阶段实测**不检查 `vector::operator[]`**（静默通过，与 libc++ 文档“operator[] 无检查”一致）；`at()` 是唯一的内建运行时护栏。不要假设“开了断言就有边界检查”。

**越界写为什么危险**（C 系 ph10 已详解，此处只给 C++ 视角）：越界写破坏相邻对象——在 vector 场景是**踩进别的堆对象或容器自身的 capacity 余量之外**，在 `std::array`/C 数组场景是**相邻栈变量甚至返回地址**。越界读则泄漏相邻数据。**off-by-one 是最常见来源**：`for (i = 0; i <= n; ++i)`、把 size 当下标、`size()` 返回 `size_t`（无符号）导致 `i < v.size() - 1` 在空容器下是巨数。

### 3.2 悬空引用与引用/迭代器失效：C++ 特有的悬空源

roadmap 必会概念：**引用也可能悬空**（roadmap 该小节共四条必会概念，此为第二条，第一条是“数据竞争在 C++ 中是 UB”）。C 的“悬空指针”靠程序员自觉（C 系 ph10 3.4）；C++ 的引用看似比指针安全（不能为空、不能重绑），但**引用不携带所有权**——容器管理元素的存储，于是引用/迭代器随容器的结构性修改而失效。悬空引用有三个来源：

1. **返回局部对象/临时对象的引用**（F.43）——ph12 已系统讲透（其 ex05-dangling：`-Wreturn-stack-address` 告警 + ASan 抓 `stack-use-after-return`），本阶段不重复；
2. **容器扩容重分配**：vector 存满后 `push_back` 会分配新缓冲区、迁移元素、释放旧缓冲区——**旧引用/指针/迭代器指向已释放的内存**（std 标准保证：重分配使指向元素的全部引用、指针、迭代器失效）；
3. **容器先于引用销毁**：引用指向容器堆缓冲区内的对象，容器 `delete`/出作用域后，引用指向已释放内存。

```cpp
// examples/ex02-dangling-container.cpp —— 扩容失效（节选，与原文件逐字一致）
    std::vector<int> v = {1, 2, 3};        // size=3, cap=3
    const int& r = v[0];                   // 引用元素
    const int* p = v.data();               // 指针元素
    std::printf("realloc: size=%zu cap=%zu, 持有 r/p 指向 v[0]\n", v.size(), v.capacity());
    v.push_back(4);                        // 触发重分配：cap 3 → 6（实测），旧缓冲区被释放
    std::printf("realloc: push_back 后 size=%zu cap=%zu（旧缓冲区已释放）\n", v.size(), v.capacity());
    std::printf("realloc: 读旧引用 r=%d ...\n", r);   // UB: 引用指向已释放的旧缓冲区
```

实测（`ex02`）：`{1,2,3}`（cap=3）`push_back(4)` 扩容 cap→6（libc++ 实测 2 倍增长），旧引用读 → ASan `heap-use-after-free` + `READ of size 4`，退出码 134（-O0~-O2 均触发）；容器 `delete` 后读引用 → 同上 + `READ of size 1`。**失效不是“崩溃预警”**：失效后使用是 UB，不保证崩——ASan 只是让它现形。

**安全姿势**（`ex02` 默认对照 + 练习 1/3）：扩容后每次现取下标（引用只活到本次调用）；`reserve` 预留容量消除隐性重分配；先按值拷贝再让容器走（值语义与容器解耦）；确需长期持有用值成员/索引，不缓存容器元素指针。**失效规则速查表**见练习 3 的 sol-03（push_back 扩容全失效 / erase 从修改点起失效 / 不重分配时修改点之前仍有效）。

### 3.3 use-after-free 与重复释放：C++ 的“释放”由谁负责

C++ 与 C 的释放问题同源（C 系 ph10 3.4），但 C++ 给出**根治思路**：RAII 让“释放”绑定对象生命周期，`delete` 只能在析构里发生——调用方没有“提前释放又继续用”的机会。裸 `new`/`delete` 保留 C 的全部坑（R.11：避免显式 new/delete）：

```cpp
// examples/ex03-uaf-double-free.cpp —— use-after-free（节选，与原文件逐字一致）
    int* p = new int(42);
    std::printf("uaf: *p=%d（delete 前）\n", *p);
    delete p;                              // p 成为悬空指针（dangling）
    std::printf("uaf: delete 后写 *p=1 ...\n");
    *p = 1;                                // UB: use-after-free（写已归还堆管理器的内存）
```

实测（`ex03`）：`delete p; *p = 1` → ASan `heap-use-after-free` + `WRITE of size 4`；`delete p; delete p` → `attempting double-free`，均退出码 134（-O0~-O2 与 ASan+UBSan 组合构建均触发）。**修复三档**（默认对照实测零报告）：① delete 后立即置空——`delete nullptr` 合法，重复 delete 无害（但置空只防当前别名）；② RAII——析构是唯一释放点，“忘了/重复释放”在结构上不可能；③ `unique_ptr`（R.20）表达独占所有权，ph13 已把五函数与 deleter 讲透，本阶段直接引用其结论：**手写资源类 = Rule of 0/3/5 的抉择（ph13），业务代码 = 交给标准库 RAII**。

### 3.4 use-after-move：moved-from 状态“合法但未指定”

C++11 移动语义引入后，被移动对象（moved-from）的语义由 **[lib.types.movedfrom]** 规定：**“合法但未指定”（valid but unspecified）**——可以安全析构、可以重新赋值、可以调用不依赖状态的操作，但**不能假设其内容**。注意 nuance：读 moved-from 对象本身通常**不是** UB（对象仍然有效），真正的风险是两种误用：

| 误用 | 性质 | 实测 |
|------|------|------|
| 把 moved-from 当“仍拥有数据”使用（如解引用被移走的 `unique_ptr`） | **UB**（解引用空指针） | UBSan `reference binding to null pointer of type 'int'`，退出码 134；裸跑 SIGSEGV 退出码 139 |
| 假设 moved-from 一定为空/一定不变 | 逻辑错误（多数实现置空，标准不保证） | libc++ 实测 `std::string` moved-from 后 size=0——“碰巧为空”换实现即错 |

```cpp
// examples/ex04-use-after-move.cpp —— moved-from 语义对照（节选，与原文件逐字一致）
        std::string a = "payload-0123456789";
        std::string b = std::move(a);      // 数据移给 b
        std::printf("    moved-from a: size=%zu（实测 libc++ 置空；标准只说“未指定”）\n", a.size());
        a = "reassigned";                  // 重新赋值合法 —— moved-from 不是“禁用对象”
```

**关键区分——哪些 moved-from 状态是“指定”的**：标准库类型分两类——`std::unique_ptr` 是少数**指定** moved-from 状态（保证为空，`get()==nullptr`，标准明确）；`std::string`/`std::vector` 等多数容器是**未指定**（实现通常置空，ph12 实测与本阶段实测一致，但“通常”不是承诺）。**使用纪律**（练习 4）：move 后只做三件事——析构 / 重新赋值 / 状态无关操作；需要“可再用”就重新赋值或 `reset`；若只是借用，在 move 之前完成。use-after-move 的系统归类正是 C++ 比 C 多出的 UB 家族——C 没有移动语义，这类坑在 C 系 ph10 里不存在。

### 3.5 数据竞争：C++ 内存模型下的 UB

两个线程无同步地读写同一非原子对象 = **数据竞争（data race）**，C++ 标准明确（[intro.races]）：数据竞争是**未定义行为**——不是“结果不确定”，是编译器可做任何假设（roadmap 必会概念）。C++ 的内存模型把“不同线程对同一内存的访问”用 happens-before 关系约束：没有同步（锁、atomic、线程建立/汇合）就没有 happens-before，竞争即 UB。ph08 并发编程阶段讲锁与 atomic 的用法，本阶段聚焦“**为什么竞争是 UB**”与 TSan 实测：

```cpp
// examples/ex05-data-race.cpp —— 竞态版本（节选，与原文件逐字一致）
    int shared = 0;
    auto bump = [&shared] {
        for (int i = 0; i < 100000; ++i) {
            ++shared;                      // 非原子读-改-写，无锁保护
        }
    };
    std::thread a(bump);
    std::thread b(bump);
    a.join();
    b.join();
```

实测（`ex05`，Apple clang 21.0.0，-fsanitize=thread）：TSan 报 `WARNING: ThreadSanitizer: data race` + `Write of size 4 ... by thread T2` / `Previous write of size 4 ... by thread T1`（同一地址的读改写无同步，报告给出冲突双方），退出码 134；`scoped_lock` 修复版（-DEX05_FIXED）TSan 零报告、输出确定 `shared=200000`。裸跑对照：**-O0** 下竞态版本退出码 0 但值不定（本机 6 次实测：122984 / 117974 / 120359 / 112912 / 126519 / 110862，均小于 200000）；**-O1** 下编译器按“无跨线程修改”假设把 `++shared` 累加优化进寄存器，本机 6 次实测恰为 200000（4.4）——两种“碰巧对”都不能证明无竞态，必须 TSan 复跑。工具边界：TSan 与 ASan 不能同进程共存（都拦截同一批运行时函数），工程化组合见 ph16；Homebrew clang 的 TSan 在本机 arm64 不稳定（实测崩溃），本阶段 TSan 验证以 Apple clang 为准。

### 3.6 类型别名与对齐：两类“看不见”的 UB

**严格别名规则**（[basic.lval]）：同一内存只能通过与其类型兼容的 glvalue 访问（`char`/`unsigned char` 系列例外）——`reinterpret_cast<uint32_t*>(&f)` 后解引用以 `uint32_t` 访问 `float` 对象是 UB（与 C 系 ph10 3.7 的 `*(float*)&u32` 同构）；C++ 比 C 更明确的一条：**union 读非活动成员是 UB**（[class.union]，只豁免 common initial sequence；C 工具链把 union 双关当扩展接受——GCC/Clang 文档明确允许 C 的 union type-punning，C++ 标准不给这个豁免）。**对齐规则**（[basic.align]）：通过未对齐地址访问对象是 UB——现代 arm64 硬件容忍未对齐访问（实测不崩），但 UBSan 一视同仁地报告。

```cpp
// examples/ex06-alias-align.cpp —— 双关与对齐（节选，与原文件逐字一致）
    auto* u = reinterpret_cast<std::uint32_t*>(&f);   // UB: 以 uint32_t 访问 float 对象
    std::printf("pun_ptr: bits=%08x\n", *u);          // “碰巧正确”的 UB 表现
```

实测（`ex06`）：指针双关 `-O0`/`-O2` 均输出 `3f800000`——与 `std::bit_cast` 正解相同，是**“碰巧正确”**的 UB 表现（本次 clang 未按别名假设重排；换代码形状/编译器/版本即可能不同，判断依据永远是标准）；union 双关同样静默、UBSan 零报告（工具抓不到）。未对齐访问（`buf+1` 上写 `uint32_t`）→ UBSan `store to misaligned address ... for type 'std::uint32_t' ... which requires 4 byte alignment`，退出码 134；同代码 arm64 裸跑实测正常——**硬件容忍 ≠ 不是 UB**。**正解**：位模式搬运用 `std::bit_cast`（C++20，要求 trivially copyable 且等大小）或 `memcpy`（编译器优化成单指令）；从字节流读字段先 `memcpy` 到对齐变量再读（黄金法则，承接 C 系 ph12 的字节流解析思路）。

### 3.7 未初始化变量：C++ 的两道编译期护栏

C++ 读内置类型的**不确定值**（indeterminate value）大多属 UB（[dcl.init]；`unsigned char` 系列例外）；比 C 更隐蔽的是**平凡类型成员的缺省初始化**——`struct Stats { int hits; int misses; }; Stats s;` 里 `s.hits` 未初始化，且多数编译器对“成员”不警告（-Wuninitialized 只能拦一部分局部变量）。C++ 的应对是两道编译期护栏（ES.20：总是初始化对象；ES.23：优先 `{}`）：

```cpp
// sol-05-uninit-fix.cpp —— 修复（节选，与原文件逐字一致）
    int x = 0;                           // 声明即初始化
    ...
        Stats s;                             // 默认成员初始化器接管：hits/misses 必为 0
```

实测（练习 5）：坏版本 `int x; if (x > 3)...` 编译触发 `warning: variable 'x' is uninitialized when used here [-Wuninitialized]`（-O0~-O2 均触发，Apple clang）；运行时输出垃圾值（非 ASan 构建实测 -248938240 等，运行间/换构建即变——“不确定值”的稳定性是栈布局巧合，不可依赖）；运行时 ASan/UBSan 都不查未初始化（MSan 需全程序插桩，本环境无）。修复版零警告、输出确定（`x=0`、`Stats` 的 hits/misses=0）。**结论：声明即初始化 + 默认成员初始化器，把“未初始化”从运行期问题变成编译期事实**——这是 C++ 相对 C 的进步（C 只能 `= {0}`/calloc，靠纪律）。

## 4. 底层原理

### 4.1 编译器假设无 UB：为什么 UB 随优化级别“变脸”

LLVM/GCC 的优化 pass 把**“程序不含 UB”当作推理前提**（as-if 规则 + 无 UB 假设）。两个与本阶段直接相关的假设：

- **越界假设**：`v[idx]` 不越界 → 越界写对“界内世界”没有可观察效果，理论上若该写**无任何后续观察者**，编译器可能把整段访问移除。但移除的前提是“没有观察者”：（ex01 实测）本示例越界写后紧跟对同一下标的 printf 读、写有观察者，`-O0`/`-O1`/`-O2` 三档 ASan 均报 `heap-buffer-overflow`（`WRITE of size 4`，退出码 134）；能被整体移除的 UB 形态需证明访问无观察者——C 系 ph10 4.2 的 `(a+1) > a` 是表达式层面的溢出假设折叠（非内存访问，不属 ASan 场景），与本示例不同；
- **严格别名假设**：两个不兼容类型的指针不指向同一内存 → load 可缓存、store 可重排（ex06 的指针双关没被重排是“碰巧”；ph14 ex04 的 const_cast 折叠是同一机制的实证：O0 下 Bus error、O2 下常量折叠打印 42）。

```text
UB 代码 ──编译器（-O1+）──▶ 按"无 UB"推理
                              ├── 越界写若有后续观察者 → 不消除（ex01：-O0~-O2 实测均报告）
                              ├── 别名违规被忽略（两次 load 可合并，实测未触发）
                              └── const 不变量被利用（ph14：O2 常量折叠，写入不生效）
        ──Sanitizer（-O0 演示）──▶ 检查点插桩，UB 命中即报告
```

**实践准则**：调试/演示用 `-O0 -g`，发布用 `-O2`；Sanitizer 复现统一 `-O0`（行号稳定、报告可控——本阶段越界/UAF/失效类示例 -O0~-O2 实测均报告，`-O0` 不是防漏报的必要条件）；**发布版崩、调试版不崩 → 第一反应查 UB，不是怀疑编译器**。

### 4.2 容器失效的机制：vector 扩容做了什么

vector 的存储是“动态数组”：容量（capacity）不足时，`push_back` 触发**重分配**——分配新缓冲区 → 移动/拷贝既有元素 → 释放旧缓冲区。旧引用/指针/迭代器指向的旧缓冲区被释放，解引用即 use-after-free：

```text
扩容前:  [ 引用 r / 指针 p ──▶ 旧缓冲区 {1,2,3} (cap=3) ]
push_back(4)
         ├── 分配新缓冲区 (cap=6, libc++ 实测 2 倍增长)
         ├── 迁移元素 1,2,3 → 新缓冲区
         └── 释放旧缓冲区 ──▶ r / p 悬空（ASan 报 heap-use-after-free）
```

**std 标准承诺**（[vector] 容量条款）：重分配使指向元素的**全部**引用、指针、迭代器失效；不重分配时，插入点之前的引用仍有效（但惯例是结构性修改后全部刷新）。erase/insert 的失效范围从修改点延伸到末尾（练习 3 的速查表）。**失效是“标准承诺”，不是“崩溃预警”**——失效后使用不保证崩，ASan 只是让它现形。

### 4.3 moved-from 的机制：移动转移了什么

move 转移**资源句柄**（如 string 的堆指针），源对象随后处于“合法但未指定”：它的**类不变量仍成立**（能析构、能赋值、size() 等成员可调用），只是内容不再承诺。这正是 [lib.types.movedfrom] 的设计意图——让“移动”与“销毁”解耦：源对象不是被摧毁，而是被掏空。两类状态的区别在实现层清晰可见：

```text
std::string a;  a = "payload...";            b = std::move(a);
  a 的堆指针 ──────────────转移──────▶ b 持有同一块堆缓冲
  a: size=0（libc++ 实测：置空）              b: 完整数据
     ↑ 未指定但合法：析构/重新赋值 OK             ↑ 新持有者：随便用

std::unique_ptr<int> up;  moved = std::move(up);
  up: get()==nullptr（**指定**：标准保证空）     moved: 持有 int
     ↑ 解引用即解引用空指针 → UB（UBSan 实测）
```

**为什么 unique_ptr 的 moved-from 是“指定空”而 string 不是**：unique_ptr 的资源就是“一个指针”，移走指针后置空是零成本的强保证；string 可以选择“转移缓冲”或“拷贝小字符串”，标准把细节留给实现（libc++ 置空，但标准不承诺）。程序只有一种安全写法：**不依赖 moved-from 内容**。

### 4.4 数据竞争为什么是 UB：内存模型的 happens-before

C++ 内存模型（[intro.races]）给每个内存访问定义“可见性”：两个访问若存在 happens-before 关系则有序，否则无先后。无同步的并发 `++shared` 是两个无顺序的读-改-写——编译器/CPU 可以任意交错、缓存、重排，结果连“两个线程各加一次”都不保证。**UB 而非“未指定”**意味着编译器可假设共享对象不被别线程改，从而把 `++shared` 优化成加载-加一-存储甚至消除——这正是“竞态 bug 换 -O2 才暴露”的原因。TSan 通过在每次访问时记录“谁碰过这个地址、有无同步边”来检测竞争（报告给出冲突双方：`Write ... by thread T2` / `Previous write ... by thread T1`）；锁（ph08 的 scoped_lock）与 atomic 建立 happens-before，是仅有的两种正解。

### 4.5 严格别名与对齐的对象模型视角

C++ 的类型系统按**动态类型**（对象的真实类型）约束访问：一个 `float` 对象只允许通过 `float`（或其兼容/字符类型）的 glvalue 访问——这是类型安全的延伸，让优化器能按类型做别名分析。**对齐是对象模型的硬约束**：`alignof(T)` 决定对象的地址低位，强转制造未对齐地址后，生成代码按对齐访问的假设被打破——arm64/x86 硬件大多容忍（慢或静默），但标准不保证，UBSan 的 alignment 检查（属 undefined 组）让它现形。`std::bit_cast` 的正解思路：**类型转换不经过内存访问**（拷贝位模式到新类型的对象），从根上绕开别名与对齐问题（要求源/目标 trivially copyable 且等大小，编译期检查）。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 存储引擎 / 数据库内核 | 迭代器/引用失效（遍历 MemTable/SSTable 时不得缓存元素地址）、vector 扩容、`string_view` 悬挂、字节流解析的对齐/别名（C++ 系 ph22 存储引擎阶段的日常） |
| 高性能服务 / 网络层 | 缓冲区越界、缓冲区与生命周期管理、跨线程共享对象的竞争（TSan 复跑） |
| 日志 / 序列化层 | 类型双关（bit_cast 正解）、未对齐读、`string_view` 借用生命周期 |
| 并发模块 | 数据竞争（无锁共享 = UB）、锁与 atomic 的 happens-before（承接 ph08） |
| 移动语义重构 | use-after-move：sink 参数、容器搬移后的源对象使用纪律（承接 ph03/ph12） |
| 代码评审与安全审计 | 本阶段 8 类 UB 的识别清单（见 project/ 的 `list`：ASan 抓的、UBSan 抓的、工具抓不到的） |
| 调试“发布崩、调试不崩” | 先怀疑 UB：`-O0`/`-O2` 双编译 + Sanitizer 复跑（4.1） |

**什么时候不用它**：

- Sanitizer 全流程 CI 与静态分析、单元测试框架属 **ph16 测试、静态分析与代码规范阶段**（GoogleTest/Catch2、clang-tidy/cppcheck、ASan/TSan/UBSan 工程化、gcov/CI）——本阶段只把它们当复现工具；
- 并发同步的完整规则（锁粒度、条件变量、内存序）属 ph08 并发编程阶段；
- 对象何时销毁、值类别、RVO/NRVO、`const&` 延长临时对象生命周期的完整规则属 ph12 对象生命周期阶段；
- 手写资源类的五个特殊成员函数与自定义 deleter 属 ph13 Rule of 0/3/5 与 RAII 进阶阶段；
- 数值类 UB（有符号溢出、除零、移位）C 系 ph10 已覆盖，C++ 语义相同，不重复。

**与其他语言的对比**（为 analysis/ 与 Tenet 合成积累素材；C 视角的完整对比表见 C 系 ph10 主文档）：

| 维度 | C++ | C | Rust | Go / Java |
|------|-----|---|------|-----------|
| 越界（容器/数组） | UB；`at()` 可选检查 | UB（不检查） | 编译期/panic | Go: panic；Java: 抛异常（无 UB） |
| 悬空引用/借用 | 可能（编译器部分告警 + ASan 抓） | 悬空指针靠纪律 | 借用检查器编译期拒绝 | 无（GC） |
| 释放错误（UAF/双释放） | 裸 delete 有；RAII/unique_ptr 根治 | 常见，靠工具 | 所有权编译期强制 | 无（GC） |
| 移动/转移后误用 | use-after-move（UB 或逻辑错） | 无移动语义 | move 后值不可用（编译期） | 无此概念 |
| 数据竞争 | **UB**（TSan 检测） | UB | 借用检查器 + Send/Sync | Go race detector / Java 内存模型+同步 |
| 安全定位 | 程序员负责 + RAII + Sanitizer 托底 | 程序员 + 工具 | 语言保证（unsafe 除外） | 运行时保证 |

一句话：**C++ 处于“精确控制 + 需自律”的位置**——RAII 与标准库消灭了一批 C 的坑（释放、大部分生命周期），但引用/迭代器/移动语义制造了新的 UB 面；Rust 把同样的三件事（借用、所有权、并发安全）做成编译期强制，GC 语言用运行时换掉悬空与竞争问题。C++ 工程实践 = **RAII 默认 + 容器纪律 + Sanitizer 复跑 + 评审清单**（project/ 的 `list` 即清单）。

## 6. 代码示例

> 说明：示例均在本机（macOS arm64，Apple clang 21.0.0 + Homebrew clang 21.1.8）实际编译运行验证（已验证），默认构建一律 `-std=c++20 -Wall -Wextra` **零警告**（双编译器）；输出一致性除 ex05（竞态值不定，见其文件头）外均已核对；故意出错变体按各文件首行注释的运行前提用 Sanitizer 编译（**UB 演示统一 -O0**——行号稳定、报告可控；实测越界/UAF/失效类示例在 -O0/-O1/-O2 下报告均触发，-O0 不是防漏报的必要条件，见示例 1）。完整可运行文件在 [`examples/`](./examples/)，此处展示关键片段（与原文件逐字一致）。

### 示例 1：越界访问（examples/ex01-vector-oob.cpp）

对应 roadmap 学习内容“越界访问”与练习“用 ASan/UBSan 检查项目”。

> 运行前提：三个故意出错变体必须按下方命令用 ASan（vector/std::array）或 UBSan（C 数组）编译运行，勿裸跑。

```cpp
// examples/ex01-vector-oob.cpp —— 越界访问：三种"数组形态"与两种检测工具的覆盖差异
    std::printf("[1] vector::operator[] 不做边界检查：越界访问是 UB（编译器不拦、不报）\n");
    std::printf("    运行时护栏由工具补：ASan 红区抓越界（变体 -DEX01_VEC_OOB）；\n");
    std::printf("    at() 是标准库自带的检查版：越界抛 std::out_of_range（定义行为）\n");
    {
        std::vector<int> v = {1, 2, 3};
        try {
            std::printf("    v.at(3) -> %d\n", v.at(3));   // 抛异常
        } catch (const std::out_of_range&) {
            std::printf("    v.at(3) 抛出 std::out_of_range（at() 检查边界）\n");
        }
    }
```

```bash
# 1. 默认（安全对照，零警告）：
c++ -std=c++20 -Wall -Wextra ex01-vector-oob.cpp -o /tmp/ph15-ex01 && /tmp/ph15-ex01
# 2. vector 越界写（故意出错，必须 ASan，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address -DEX01_VEC_OOB ex01-vector-oob.cpp -o /tmp/ph15-ex01-vec && /tmp/ph15-ex01-vec
# 3. std::array 越界读（故意出错，必须 ASan，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address -DEX01_STD_ARRAY ex01-vector-oob.cpp -o /tmp/ph15-ex01-arr && /tmp/ph15-ex01-arr
# 4. C 数组越界写（故意出错，必须 UBSan 并中止，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=undefined -fno-sanitize-recover=all -DEX01_CARRAY ex01-vector-oob.cpp -o /tmp/ph15-ex01-carr && /tmp/ph15-ex01-carr
```

实测报告关键行（退出码 134，-O0/-O1/-O2 三档实测均触发）：`ERROR: AddressSanitizer: heap-buffer-overflow` + `WRITE of size 4` + "located 0 bytes after 12-byte region"（越界写后紧跟同下标读、不会被折叠消除；演示统一 -O0 只为行号稳定、报告可控）。`std::array` 越界读 → `stack-buffer-overflow` + `READ of size 4`；C 数组运行期下标越界 → UBSan `runtime error: index 3 out of bounds for type 'int[3]'`。要点：**vector/std::array 越界靠 ASan、C 数组越界靠 UBSan**，`at()`/手动边界检查让越界变定义行为。

### 示例 2：悬空引用与容器失效（examples/ex02-dangling-container.cpp）

对应 roadmap 必会概念“引用也可能悬空”“vector 扩容会使迭代器和引用失效”与练习 1“修复悬空引用示例”。

> 运行前提：两个变体必须用 ASan 编译运行（-DEX02_REALLOC：扩容失效；-DEX02_CONTAINER_DEAD：容器销毁后引用），勿裸跑。

```cpp
// examples/ex02-dangling-container.cpp —— 悬空引用与迭代器/引用失效：容器生命周期是 C++ 特有的悬空源
    std::printf("[2] 预留容量：reserve 消除“写满才扩容”的隐性失效\n");
    {
        std::vector<int> v;
        v.reserve(4);                      // 一次性预留
        const int* p = v.data();           // reserve 后、写满前 data() 稳定
        for (int i = 0; i < 4; ++i) v.push_back(i);
        std::printf("    *p=%d（reserve(4) 内 push_back 不扩容，指针仍有效）\n", *p);
    }
```

```bash
# 1. 默认（安全对照，零警告）：
c++ -std=c++20 -Wall -Wextra ex02-dangling-container.cpp -o /tmp/ph15-ex02 && /tmp/ph15-ex02
# 2. 扩容后旧引用失效（故意出错，必须 ASan，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address -DEX02_REALLOC ex02-dangling-container.cpp -o /tmp/ph15-ex02-r && /tmp/ph15-ex02-r
# 3. 容器销毁后引用（故意出错，必须 ASan，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address -DEX02_CONTAINER_DEAD ex02-dangling-container.cpp -o /tmp/ph15-ex02-d && /tmp/ph15-ex02-d
```

实测报告关键行（退出码 134，-O0~-O2 均触发）：`ERROR: AddressSanitizer: heap-use-after-free` + `READ of size 4`（扩容失效）；`READ of size 1`（容器销毁后引用）。要点：扩容 = 新缓冲区 + 迁移 + 释放旧缓冲区（4.2）；安全姿势 = 现取下标 / reserve 预留 / 先拷贝再放容器走。

### 示例 3：use-after-free 与重复释放（examples/ex03-uaf-double-free.cpp）

对应 roadmap 学习内容“重复释放”与 C 系 ph10 练习 2 的 C++ 版（差异：RAII 根治）。

> 运行前提：两个变体必须用 ASan 编译运行（-DEX03_UAF：delete 后写；-DEX03_DOUBLE_FREE：双删），勿裸跑。

```cpp
// examples/ex03-uaf-double-free.cpp —— use-after-free 与重复释放：裸 new/delete 的生命周期误用
    std::printf("[1] delete 后立即置空：delete nullptr 是合法的（多次 delete 空指针无害）\n");
    {
        int* p = new int(42);
        delete p;
        p = nullptr;                       // 置空后，任何“忘了已释放”的重复 delete 都无害
        delete p;                          // 合法：delete nullptr
        std::printf("    delete 空指针两次 —— 无 UB、无崩溃（但置空只防当前别名）\n");
    }
```

```bash
# 1. 默认（安全对照，零警告）：
c++ -std=c++20 -Wall -Wextra ex03-uaf-double-free.cpp -o /tmp/ph15-ex03 && /tmp/ph15-ex03
# 2. delete 后写（故意出错，必须 ASan，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address -DEX03_UAF ex03-uaf-double-free.cpp -o /tmp/ph15-ex03-u && /tmp/ph15-ex03-u
# 3. 双重 delete（故意出错，必须 ASan，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address -DEX03_DOUBLE_FREE ex03-uaf-double-free.cpp -o /tmp/ph15-ex03-d && /tmp/ph15-ex03-d
```

实测报告关键行（退出码 134，-O0~-O2 均触发）：`heap-use-after-free` + `WRITE of size 4`（UAF）；`attempting double-free`（双删）。要点：delete 后置空只防当前别名；RAII/unique_ptr 让释放点唯一——**消灭裸 delete 是 C++ 的根治思路**（R.11，ph13 深入）。

### 示例 4：use-after-move（examples/ex04-use-after-move.cpp）

对应 roadmap 学习内容“use-after-move 语义风险”与练习 4。

> 运行前提：危险变体（-DEX04_DEREF_MOVED）必须用 UBSan 编译运行，勿裸跑。

```cpp
// examples/ex04-use-after-move.cpp —— use-after-move 语义：moved-from 状态“合法但未指定”
        auto up = std::make_unique<int>(42);
        auto moved = std::move(up);            // 所有权转移：up 保证为空（unique_ptr 指定语义）
        std::printf("deref: up 是否为空（moved-from unique_ptr）: %s\n",
                    up ? "否（异常！）" : "是");
        std::printf("deref: 解引用 moved-from 的 up ...\n");
        std::printf("deref: *up=%d\n", *up);   // UB: 解引用空指针（UBSan 在此中止）
```

```bash
# 1. 默认（语义对照，零警告）：
c++ -std=c++20 -Wall -Wextra ex04-use-after-move.cpp -o /tmp/ph15-ex04 && /tmp/ph15-ex04
# 2. 解引用 moved-from 的 unique_ptr（故意出错，必须 UBSan 并中止，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=undefined -fno-sanitize-recover=all -DEX04_DEREF_MOVED ex04-use-after-move.cpp -o /tmp/ph15-ex04-u && /tmp/ph15-ex04-u
```

实测报告关键行：UBSan `runtime error: reference binding to null pointer of type 'int'`（位于 libc++ unique_ptr.h 的 `operator*`），退出码 134；去掉 UBSan 裸跑实测 Segmentation fault（退出码 139）——两种表现都是 UB 的合法形态。默认对照（零警告）：moved-from `string` 实测 size=0 后可重新赋值（合法但未指定）；moved-from `unique_ptr` 保证为空。

### 示例 5：数据竞争（examples/ex05-data-race.cpp）

对应 roadmap 必会概念“数据竞争在 C++ 中是 UB”。练习 2 的 ASan/UBSan 复现只覆盖越界与 use-after-free、不覆盖数据竞争；TSan 复现由本示例承担（project/ 的 race 演示与本示例同源，TSan 与 ASan 不能同进程共存，见 project/README）。

> 运行前提：本文件两个变体都必须用 `-fsanitize=thread` 编译运行，勿裸跑。

```cpp
// examples/ex05-data-race.cpp —— 数据竞争：C++ 内存模型下的未定义行为
    auto bump = [&shared] {
        for (int i = 0; i < 100000; ++i) {
            ++shared;                      // 非原子读-改-写，无锁保护
        }
    };
    std::thread a(bump);
    std::thread b(bump);
```

```bash
# 1. 竞态版本（故意出错，必须 -fsanitize=thread）：
c++ -std=c++20 -Wall -Wextra -O1 -g -fsanitize=thread ex05-data-race.cpp -o /tmp/ph15-ex05 && /tmp/ph15-ex05
# 2. 修复版本（scoped_lock，TSan 零报告）：
c++ -std=c++20 -Wall -Wextra -O1 -g -fsanitize=thread -DEX05_FIXED ex05-data-race.cpp -o /tmp/ph15-ex05-f && /tmp/ph15-ex05-f
```

实测报告关键行（Apple clang 21.0.0）：TSan `WARNING: ThreadSanitizer: data race` + `Write of size 4 ... by thread T2` / `Previous write of size 4 ... by thread T1`，退出码 134；修复版零报告、`shared=200000`、退出码 0。裸跑对照：-O0 下值不定（本机 6 次实测：122984/117974/120359/112912/126519/110862，均 <200000）；-O1 下实测恰为 200000（编译器把累加优化进寄存器）——“碰巧对”不能证明无竞态。

### 示例 6：类型别名与对齐（examples/ex06-alias-align.cpp）

对应 roadmap 学习内容“类型别名与对齐问题”。

> 运行前提：未对齐变体（-DEX06_MISALIGN）必须用 UBSan 编译运行；两个双关变体是“工具抓不到”的演示，可编译运行但勿当规范。

```cpp
// examples/ex06-alias-align.cpp —— 类型别名与对齐：两类“看不见”的 UB 与正解
    std::printf("[1] 类型双关正解：std::bit_cast（C++20，定义行为）\n");
    {
        float f = 1.0f;
        std::uint32_t bits = std::bit_cast<std::uint32_t>(f);
        float back = std::bit_cast<float>(bits);
        std::printf("    bit_cast: bits=%08x back=%.1f\n", bits, static_cast<double>(back));
    }
```

```bash
# 1. 默认（正解对照：std::bit_cast / memcpy，零警告）：
c++ -std=c++20 -Wall -Wextra ex06-alias-align.cpp -o /tmp/ph15-ex06 && /tmp/ph15-ex06
# 2. 指针双关（故意出错：别名违规，工具抓不到，输出是“碰巧正确”的 UB 表现）：
c++ -std=c++20 -Wall -Wextra -O2 -DEX06_PUN_PTR ex06-alias-align.cpp -o /tmp/ph15-ex06-p && /tmp/ph15-ex06-p
# 3. union 双关（故意出错：C++ 中读非活动成员是 UB；可任意编译运行，勿当规范）：
c++ -std=c++20 -Wall -Wextra -O2 -DEX06_PUN_UNION ex06-alias-align.cpp -o /tmp/ph15-ex06-u && /tmp/ph15-ex06-u
# 4. 未对齐访问（故意出错，必须 UBSan 并中止，-O0）：
c++ -std=c++20 -Wall -Wextra -O0 -g -fsanitize=undefined -fno-sanitize-recover=all -DEX06_MISALIGN ex06-alias-align.cpp -o /tmp/ph15-ex06-m && /tmp/ph15-ex06-m
```

实测报告关键行：未对齐存储 → UBSan `runtime error: store to misaligned address ... for type 'std::uint32_t' ... which requires 4 byte alignment`，退出码 134（arm64 裸跑实测正常——硬件容忍 ≠ 不是 UB）；指针双关与 union 双关均无运行时报告，输出与 bit_cast 相同（3f800000）——“碰巧正确”的 UB，判断依标准。

## 7. 总结

### 关键要点

1. **UB 不是“结果不确定”，而是“编译器可做任何假设”**：判断依据是标准（[intro.abstract]），不是实测结果——“碰巧正确”（别名/竞态/垃圾值稳定）不能证明安全
2. **越界写通常比越界读更危险**：破坏相邻对象、容器元数据甚至返回地址；off-by-one 是最大来源；**vector/std::array 越界靠 ASan，C 数组越界靠 UBSan**，`at()` 让越界变定义行为（3.1、`ex01`）
3. **引用也可能悬空**：容器扩容重分配与容器销毁使引用/迭代器失效（std 标准保证）；失效后使用是 UB、不保证崩——现取下标 / reserve / 先拷贝三姿势（3.2、`ex02`、练习 1/3）
4. **失效是“标准承诺”不是“崩溃预警”**：push_back 扩容全失效、erase/insert 从修改点起失效；结构性修改后一律刷新（练习 3 速查表）
5. **释放交给 RAII**：裸 delete 保留 C 的全部坑（UAF/双删，ASan 实测）；delete 后置空只防当前别名；unique_ptr/析构让释放点唯一（3.3、`ex03`）
6. **moved-from 是“合法但未指定”**（[lib.types.movedfrom]）：可析构/重新赋值/状态无关操作，不可假设内容；unique_ptr 的 moved-from **指定为空**——解引用即 UB（UBSan/裸跑双实测）；使用纪律：move 后只做三件事（3.4、`ex04`）
7. **数据竞争是 UB**：无同步共享读写 = 编译器可做任何假设；TSan 实测冲突双方，`scoped_lock`/atomic 建立 happens-before 是正解；“碰巧对”必须 TSan 复跑（3.5、`ex05`）
8. **严格别名禁止双关**：reinterpret_cast 指针双关与 union 读非活动成员都是 UB（C++ 标准只豁免 common initial sequence）；位模式搬运用 `std::bit_cast`/memcpy（3.6、`ex06`）
9. **对齐是硬约束**：未对齐访问 arm64 也“只是容忍”——UBSan 让它现形；字节流解析先 memcpy 到对齐变量（3.6、`ex06`）
10. **未初始化用编译期护栏根治**：`-Wuninitialized` 拦局部变量、默认成员初始化器拦成员（ES.20）；运行时工具抓不到（3.7、练习 5）
11. **UB 的表现可能随优化级别变化**：ex05 竞态 -O0 裸跑丢失更新、-O1 下被优化成“恰好 200000”（3.5、4.4）；const 不变量被破坏在 -O2 下常量折叠（ph14 ex04）。但越界/UAF/失效类复现 -O0/-O1/-O2 实测均报告（3.1、`ex01`）——演示统一 -O0 只为行号稳定/报告可控；发布崩调试不崩 → 先查 UB（4.1）
12. **工具边界**：ASan 抓越界/UAF/双删，UBSan 抓对齐/空指针等逻辑型，TSan 抓竞争；别名与多数未初始化靠规范与评审——工程化属 ph16

### 阶段验收清单

- [ ] 能**解释至少 5 种 C++ UB**：说出触发代码、标准依据与后果（越界、容器悬空、UAF/双删、use-after-move、数据竞争、别名/对齐、未初始化）
- [ ] 能**用工具定位内存错误**：ASan 报越界/UAF/双删、UBSan 报未对齐/空指针、TSan 报竞争；读懂报告的错误类型、READ/WRITE 大小与冲突双方；知道 -O0 复现的缘由
- [ ] 能**设计避免悬空引用的接口**：不返回局部引用（ph12）、不缓存容器元素指针/迭代器、视图生命周期短于数据源（ph14）、move 后不假设内容
- [ ] 能**说清 moved-from 语义**：合法但未指定 vs unique_ptr 指定为空；不把 libc++ 实测的“置空”写成标准保证
- [ ] 能**区分“工具抓得到/抓不到”**：别名双关与多数未初始化靠规范与评审（-Wuninitialized、默认成员初始化器、bit_cast）
- [ ] 能在**代码评审中主动发现危险写法**：`v[i]` 无边界、扩容后持旧引用、裸 delete 后使用、moved-from 解引用、无锁共享、`reinterpret_cast` 双关、未初始化成员（对照 project/ 的 `list` 清单）

### 跨语言对比：UB 与内存安全

| 维度 | C++ | C | Rust | Go | Java |
|------|-----|---|------|----|------|
| 未定义行为 | 继承 C + 生命周期/容器/移动 UB | 广泛存在 | safe Rust 编译期排除（unsafe 同 C++） | 无（运行时） | 无（JVM 规范） |
| 容器越界 | UB（at() 可选检查） | 无容器（数组 UB） | 检查或 panic | panic | 抛异常 |
| 悬空引用/迭代器失效 | 可能（ASan 抓） | 悬空指针 | 编译期拒绝 | 无（GC） | 无（GC） |
| use-after-move | UB 或逻辑错误 | 无移动语义 | 编译期拒绝 | 无 | 无 |
| 数据竞争 | UB（TSan） | UB（TSan） | Send/Sync 编译期强制 | race detector | 内存模型 + 同步工具 |

一句话：**C++ 把 C 的“内存裸奔”升级为“RAII + 标准库 + 纪律”的自治模型**——释放类坑被 RAII 消灭，但引用/迭代器/移动语义制造的新 UB 面要求开发者把“容器失效规则”“moved-from 状态”“Sanitizer 复跑”内化成习惯；Rust 用编译期强制换掉同一批坑，GC 语言用运行时换掉悬空与竞争——C++ 是三者光谱中“零成本但需自律”的那一档（为 analysis/ 与 Tenet 合成积累素材）。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 5 题：修复“缓存容器元素指针”的悬空引用（★）、用 ASan 检查并修复越界与 use-after-free（★★）、梳理 vector 迭代器/引用失效场景（★★）、use-after-move 识别与 moved-from 纪律（★★★）、未初始化变量的识别与修复（★★）——练习 1/2/3 与 roadmap ph15「练习」小节的三个承诺（修复悬空引用示例 / 用 ASan/UBSan 检查项目 / 梳理 vector 迭代器失效场景）一一对应，练习 4/5 覆盖「学习内容」中的 use-after-move 语义风险与未初始化变量。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**C++ UB 示例集**——8 类 C++ UB 的“坏版本 + 好版本”两件套（坏版本用 Sanitizer 复现报告，好版本是安全写法），`./ub_catalog list` 是代码评审检查清单、`make check` 自检（ASan+UBSan 零报告 + race 的 TSan 零报告）、`make demos` 逐个演示；数据竞争因 TSan 与 ASan 不能同进程共存而独立成 `race_demo`。roadmap 的另一个推荐项目「安全容器使用指南」由 examples/ex02 安全对照与练习 1/3 覆盖。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`make clean && make check` 退出码 0、`make demos` 逐坑出报告、`make clean` 无残留）

### 下一阶段

[测试、静态分析与代码规范阶段](../ph16-testing-quality/16-testing-quality.md) — 本阶段把 UB 讲成了「能识别、能实测、能规避」的类别清单；ph16 把工具链系统化——ASan/TSan/UBSan 的工程化构建矩阵（本阶段「每种 UB 该用哪个工具抓、哪些工具抓不到」的结论在那里直接成为配置依据）、GoogleTest/Catch2 单元测试、clang-tidy/cppcheck 静态分析、clang-format 与 gcov/llvm-cov 覆盖率、CI 接入，建立「一键测试 + 静态检查 + Sanitizer 复跑」的工程质量闭环。
