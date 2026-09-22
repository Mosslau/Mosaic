# C++ ABI、动态库与插件机制阶段

> 面向「二进制边界」方向：从 ABI 与 API 的区别起步，经由 name mangling、extern "C"、动态库构建、dlopen 运行期加载、符号可见性与版本兼容，到插件生命周期与所有权纪律——理解 C++ 源码在链接成库、被别的程序加载的那一刻，承诺了什么、又放弃了什么。

## 1. 概述

本阶段是学习路线的第 19 步（roadmap ph19 目标：理解二进制边界，能设计稳定插件接口）。前 18 步把「单个可执行文件里的 C++」讲完了：ph17 的分层与接口、ph18 的性能剖析，都默认编译器看得见所有调用点。**本阶段回答 ph18 末尾留下的问题：一旦代码跨过动态库边界——符号解析、mangled 名、vtable 布局、导出表与稳定接口——哪些「编译器白送」的保障失效了，插件接口该怎么设计才既稳定又不拖累性能**。它是 roadmap 第 20 节 C++ 与 C / Python / Rust 互操作阶段的二进制前哨站：所有跨语言绑定底层踩的都是本阶段的 C ABI 机制。

| 核心维度 | 覆盖内容 |
|----------|---------|
| ABI vs API | 源码契约 vs 二进制契约；二进制兼容与源码兼容的分野；为什么 C++ ABI 不如 C ABI 稳定 |
| name mangling | Itanium C++ ABI mangling 形态、重载/命名空间/模板如何进符号、demangle 工具（c++filt/__cxa_demangle）、Mach-O 与 ELF 的符号前缀差异 |
| extern "C" | C 链接声明、与 C++ 链接的符号形态对照、`__cplusplus` 头守卫、重载限制 |
| 动态库构建 | macOS dylib（install_name/@rpath）与 Linux .so（soname）对照、静态库 vs 共享库、PIC |
| 运行期加载 | dlopen/dlsym/dlerror/dlclose 流程；Windows LoadLibrary/GetProcAddress 对照；错误处理 |
| 符号可见性 | 默认全导出的问题、`-fvisibility=hidden` + `visibility("default")` 白名单策略、nm 验证 |
| 版本兼容 | 尾部追加 vs 头部插入、mangling 链接期护栏、接口版本号约定、ELF symbol versioning（机制） |
| 插件生命周期 | opaque 句柄、谁创建谁销毁、跨库 new/delete 红线、destroy 先于 dlclose、异常与静态对象不跨边界 |
| 心智模型 | C ABI 稳定、C++ ABI 不稳；插件边界用 C ABI；所有权约定比所有权推断可靠；符号兼容是动态库的命 |

这个阶段只涉及**进程内动态库与插件的二进制边界**：ABI 概念、mangling 与 extern "C"、动态库的构建/加载/符号控制、版本兼容策略、插件生命周期与所有权纪律，**不涉及把 C++ 能力暴露给其他语言（pybind11、C 包装层、Rust FFI 的完整设计——roadmap 第 20 节 C++ 与 C / Python / Rust 互操作阶段）、真实存储引擎内核中把存储层做成可插拔的商业级 C ABI（WAL/SSTable/Compaction 与 C ABI 的工程结合——roadmap 第 22 节存储引擎与数据库内核专项阶段），以及 AI 推理的插件生态（TensorRT/ONNX Runtime 的 plugin 接口体系——roadmap 第 23 节向量检索与 AI 推理引擎方向 C++ 阶段）** — 那些是其他阶段的内容。本阶段是它们的公共地基：跨语言绑定、存储引擎的可插拔后端、推理框架的算子插件，底层都是「一份稳定的 C ABI + 安全的对象生命周期」。

## 2. 来源与演变

ABI 的历史不是一部「标准委员会立法史」，而是一部「二进制世界的妥协史」。1980 年代 C 编译器在 Unix 上各自为政，直到 AT&T 发布 **System V ABI**（1988 年前后稳定为 System V Release 4 的 ELF 规范）才让「一个平台上所有 C 编译器产出的可执行文件互相兼容」成为约定——函数调用约定、寄存器用法、结构体布局对齐规则被写成一份所有人照做的文档。**设计哲学一句话：源码兼容靠编译器，二进制兼容靠 ABI——ABI 是编译器们私下握手约定的产物，谁不遵守，谁的程序就链接不上或跑错**。

C++ 出现后第一个难题就是 **name mangling**：函数重载要求「同名不同函数在符号表里必须有不同名字」，于是每家编译器各自发明编码规则（cfront 时代几乎无规则可言、符号互相撞车），g++ 的早期版本也与 C 编译器、与别的 C++ 编译器链接不兼容。1990 年代末 Itanium 编译团队着手设计一套完整的 **Itanium C++ ABI**（1999~2001 年成型），把名字编码（`_Z...`）、虚表（vtable）布局、RTTI 结构、异常展开信息统一成规范；GCC 3.x 起采用，Clang 出生即跟随——从此 Linux/macOS 上所有主流 C++ 编译器的二进制能互相链接。2000 年代 ELF 平台上又补上 **symbol versioning**（Sun 链接器首创、GNU ld 跟进，用 version script 给符号编版本），让 glibc 一类基础库可以「同一个库同时带新旧符号」滚动升级。

C++ 侧最影响日常的是 ABI 冻结与破裂的几次事件：C++11 标准库引入 `std::string` 的写时复制优化（libstdc++ 的 `_GLIBCXX_USE_CXX11_ABI` 双 ABI 之争，GCC 5.1 在 2015 年切换为 SSO 布局）——同一个头文件在两个 ABI 开关下编译出的类型布局不同，跨边界传递 `std::string` 就是二进制炸弹；macOS 侧 Apple 的 libc++ 自成一格（与 libstdc++ 不兼容），dyld（动态链接器）则一路从 dyld 1 演进到 dyld 3（2018 年起把符号解析预热成缓存，启动更快但「运行期查符号」的灵活性不变）。语言标准委员会自 C++11 后对标准库 ABI 保持极度保守——**标准库类型布局的稳定性是比语言特性更珍贵的资产，改布局等于把所有已编译程序砸一遍**。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| System V ABI | 1988~ | ELF 可执行/共享库格式、C 调用约定标准化——C ABI 的底座 |
| Itanium C++ ABI | 1999~2001 | mangling、vtable、RTTI、异常展开统一规范；GCC 3.x 采用、Clang 跟随，成为类 Unix 事实标准 |
| ELF symbol versioning | 1990s~2000s | Sun 首创、GNU ld 跟进：version script 给符号编版本，一个 .so 同时携带新旧符号滚动升级 |
| Apple dyld 2 / install_name | 2000s | macOS 动态库身份由内嵌 install_name 决定，`otool -L` 可查；同名符号由加载顺序裁决 |
| GCC 5 dual ABI | 2015 | libstdc++ 切换 SSO 版 `std::string`，`_GLIBCXX_USE_CXX11_ABI` 双 ABI 并存——标准库类型跨边界传递的著名教训 |
| C++11 后标准库 ABI 冻结 | 2011~ | 委员会对标准库类型布局零改动倾向：稳定布局 > 新特性 |
| Apple dyld 3 | 2018~ | 启动期符号解析预热缓存；运行期 dlopen/dlsym 语义不变 |
| macOS arm64 + Homebrew clang | 2020~ | 本环境的默认平台：Mach-O + dyld，与 Linux ELF 对照学习成为常态 |

本文示例以 **C++20** 为基线（ABI 与动态库机制与语言标准版本关系弱——mangling 自 Itanium 定型后稳定，库的链接与加载走平台工具链；C++20 仅决定示例语法面与 libc++ 运行时版本），验证工具链 **Apple clang 21.0.0（`clang++`）+ Homebrew clang 21.1.8（`/opt/homebrew/opt/llvm/bin/clang++`）**，macOS arm64 + libc++ + dyld，统一 `-std=c++20 -Wall -Wextra`。**双平台口径**：本机是 macOS，全部 dylib/dyld/dlopen/`nm -gU`/`otool` 操作**已验证**；Linux 的 `.so`/soname/`ld.so` 机制与 ELF symbol versioning 属 Linux 特性，本环境无法实测，凡涉及其命令一律标注「未在本环境验证」、只讲机制。好在这套知识的平台差异集中在「文件格式与工具名」一层，机制（extern "C"、dlopen、可见性、生命周期）完全互通，对照着学反而记得更牢。

## 3. 语法与参数

> 本节代码块为**教学骨架**：聚焦单个主题做了裁剪。完整可运行文件见第 6 节与 [`examples/`](./examples/)，构建/运行命令见 examples/README.md（6 个示例全部已验证：双编译器本机实测编译零警告、运行通过；文档内嵌片段标注来源文件与验证状态）。

### 3.1 ABI 与 API：同一个词，两种承诺

**API（Application Programming Interface）是源码层的契约**：头文件里函数怎么签名、类有哪些成员——调用方改一行 `#include`、重编一次就作数。**ABI（Application Binary Interface）是二进制层的契约**：编译出的代码怎么互相调用——函数在符号表里的名字、参数怎么传、结构体字段在偏移几、对象怎么销毁。API 变了，重编译就好；ABI 变了，**已编译的老程序**要么链接失败、要么带着错误假设跑出 UB。

| 维度 | API | ABI |
|------|-----|-----|
| 层级 | 源码：头文件里的声明 | 二进制：符号、调用约定、布局 |
| 变更代价 | 调用方重新编译 | 所有已发布二进制全部失效（除非双 ABI 并存） |
| C++ 侧稳定性 | 改函数体不影响；改签名要重编 | mangling/vtable/布局任一变化即破裂 |
| C 侧稳定性 | 同上 | 高：无 mangling、struct 布局可人为稳定 |
| 谁检查 | 编译器（类型检查） | 没人——链接器只对符号名，运行期靠约定与版本号 |

为什么 **C++ ABI 不如 C ABI 稳定**，三个机制性原因：**① mangling 把签名烙进符号名**（C 的 `int add(int,int)` 就叫 `add`，改签名链接照过；C++ 的 `_ZN4math3addEii` 里编码了参数类型，签名一变符号就消失，链接期报 undefined symbol——见 3.2）；**② vtable 布局与虚函数顺序、继承层级绑定**（基类加一个虚函数会把派生类 vtable 里的既有槽位往后推，已编译的派生类对象调用虚函数就会对错槽位）；**③ 标准库类型布局绑定编译器与标准库实现**（`std::string`/`std::vector` 的字段布局不是语言标准定的，libstdc++ 与 libc++ 就不同——跨 ABI 边界传一个 `std::string`，接收侧按自己的布局去读，就是越界读。这是 ph15 讲过的「类型别名/布局」在库边界的放大版）。

> ⚠️ 本阶段反复出现的一句话：**跨二进制边界只传 C 语言能表达的东西**——数值、指针、定长 struct、以 `\0` 结尾的 C 字符串。`std::string`、`std::vector`、异常、引用，全部不出边界。完整「跨语言/跨库传什么怎么传」的工程化设计属于 roadmap 第 20 节互操作阶段，这里只需要理解动机。

### 3.2 name mangling：签名如何变成符号

C++ 函数重载让「同一个名字」对应多个函数，链接器只认符号名——于是编译器把**函数签名编码进符号名**，这套编码就是 Itanium C++ ABI 的 mangling。读 mangled 名的起点不是背规则而是认骨架：

| 形态片段 | 含义 |
|----------|------|
| `_Z` | mangled 名起始（`Z` 之后是编码主体） |
| `N...E` | namespace/类限定（Nested name） |
| 数字+名字 | 名字及长度：`3add` = 长度 3 的 `add`；`4math` = `math` |
| `i`/`d`/`f` | 内建类型：int/double/float |
| `Ii`/`T_S1_` | 模板参数（`twice<int>` 编码为 `I i E`） |
| 尾随 `v`/`R...` 等 | void/引用等限定 |

examples/ex01 实测的三个例子（本机 Apple clang，双编译器一致）：

```cpp
// examples/ex01-mangling-demangle.cpp —— 实测：同一签名在 ELF 与 Mach-O 上
// mangling 规则完全相同（都照 Itanium ABI），区别只在 Mach-O 给最终符号再压
// 一层前缀下划线（nm 输出 __Z...，ELF 是 _Z...）；dladdr 拿到的 dli_sname
// 已是不带前缀的 Itanium 形态，可直接交给 __cxa_demangle
int math::add(int, int)        → _ZN4math3addEii    （demangle 回 math::add(int, int)）
int math::add(double, double)  → _ZN4math3addEdd    （重载靠它区分）
T math::twice<int>(int)        → _ZN4math5twiceIiEET_S1_
```

工程上不手写 mangled 名，而是用工具与运行期设施反解：**`c++filt`**（命令行 demangle，容忍 Mach-O 前缀）、**`__cxxabiv1::__cxa_demangle`**（`<cxxabi.h>`，运行期把符号名反解成人可读文本）、`nm`（看符号表，macOS 加 `-gU` 看导出、Linux 加 `-D`）。`dladdr`（macOS/POSIX，`<dlfcn.h>`）能在运行期从函数地址反查符号名——ex01 就是拿它把「编译器眼里的你」展示出来。

mangling 有一个常被忽视的红利：**签名变化 → 符号名整个变 → 旧调用方在链接期报 undefined symbol，而不是运行时静默错位**（ex01 断言部分直接演示了这一性质）。C 没有 mangling，`int add(int,int)` 改成 `double add(double,int)` 后旧调用方照样链接成功、运行期按旧约定读寄存器/栈——所以 C 边界只能靠接口版本号兜底（3.7）。**C++ 有链接期护栏，C 有更宽的自由度但责任更重**——这句话贯穿整个插件设计。

> 本阶段只读不写 mangled 名：你永远不需要手写 `_Z...`，但需要能在报错里认出它、用工具反解它。手写 mangling 编码器这类反向工程属于很偏的 niche，学习路线里不占位置。

### 3.3 extern "C"：关掉 C++ 的名字魔法

`extern "C"` 告诉编译器：这段声明/定义按 **C 链接**处理——不 mangling、符号名就是函数名（Mach-O 上再加一层 C 符号前缀 `_`）。它是 C++ 世界里通往「稳定 C ABI」的开关：

```cpp
// examples/ex02-math.h 的核心模式：头文件里声明一次，C/C++ 双编译器都可用
// C 编译器：无 __cplusplus → 看到纯 C 声明；C++ 编译器：看到 extern "C" 声明
#ifdef __cplusplus
extern "C" {
#endif
int math_add(int a, int b);   // C 链接：ELF 导出 math_add，Mach-O 导出 _math_add
#ifdef __cplusplus
}
#endif
```

三种链接形态对照（examples/ex02 用 `nm -gU` 实测，双编译器一致）：

| 声明方式 | 符号（ELF） | 符号（Mach-O，nm 所见） | 能不能重载 |
|----------|------------|------------------------|-----------|
| C 语言函数 | `math_add` | `_math_add` | 语言层面无重载 |
| `extern "C"` C++ 函数 | `math_add` | `_math_add` | 不能（同名的 extern "C" 只能有一个） |
| 普通 C++ 函数 | `_ZN4math3addEii` | `__ZN4math3addEii` | 能（重载即不同符号） |

为什么插件边界几乎总选 extern "C"：**① 符号可预测**——任何语言的 C ABI 绑定（roadmap 第 20 节互操作阶段里的 Python ctypes/Rust FFI）都能按名字找到；**② 不受编译器/标准库 ABI 影响**——C 的函数调用约定与 struct 布局几十年来在单平台上稳定；**③ dlopen 生态的惯例**——dlsym 按字符串找符号，mangled 名也能找（ex02 演示了 C++ 符号同样可链接可 dlsym），但宿主一旦依赖某个 mangled 名，就被绑死在该编译器/该版本上。注意 extern "C" 只改「名字与调用约定」，**不**改参数传递规则的 C++ 语义——`extern "C"` 函数里照样能用 `std::string` 局部变量，只是不能把 `std::string` 当参数跨边界传（3.1 的红线）。

extern "C" 使用中的常见陷阱，逐条说清就够避开工程上大多数事故：

| 陷阱 | 症状 | 正确做法 |
|------|------|---------|
| 在头文件里把 `#include` 也包进 `extern "C" { }` | 系统头里的 C++ 声明被错误套上 C 链接，链接怪错 | `extern "C"` 只包你自己的声明 |
| 对一组重载函数全标 `extern "C"` | 编译错误（C 链接不允许重载） | 重载函数无法走 C 链接，改不同名字 |
| 以为 extern "C" 让函数能传 C++ 类型 | 跨边界传 `std::string` 依然崩 | C 链接只管名字与调用约定，不管类型布局 |
| 实现处忘记与头文件链接方式一致 | ODR/链接不匹配，符号对不上 | 声明一次放头文件，实现与调用都 include |
| 用宏在不同平台伪造 `extern "C"` 拼写 | Windows 上 `extern "C"` 语义相同其实不需要宏；真正需要的是 `__declspec(dllexport/dllimport)` 的差异 | 平台差异用条件编译包导出宏，别动 extern "C" |
| 函数名起得太通用（`init`/`start`） | 多插件加载时撞名，解析顺序裁决（4.2） | 导出名带插件前缀（`ts_create`/`store_version`/`engine_get_api` 这类） |

还有一个冷门但救命的知识点：**`extern "C"` 可以反向用**——`extern "C++" { ... }` 在 C 链接区域内恢复 C++ 链接（极少用，但读别人代码见到能认出来）；以及 `extern "C"` 不影响函数是内联/模板还是 `constexpr`——那些是 C++ 语法面，与链接方式正交（所以头文件里模板可以照常存在，只是不能声明成 extern "C" 模板特化的形态，编译器会拒绝）。

### 3.4 动态库构建：dylib 与 .so 的对照

动态库（共享库）把「编译产物」与「加载时机」拆开：多个进程可以共享同一份磁盘上的机器码（省内存），也可以在不重编主程序的情况下升级或替换实现（插件机制的前提）。构建命令在两个平台上的差异只在**链接器选项与产物格式**：

```bash
# macOS dylib（examples/ex02/ex03/ex04/ex05 全部这样编，本机已验证）
clang++ -std=c++20 -Wall -Wextra -dynamiclib lib.cpp -o /tmp/libmath.dylib
# Linux .so（机制相同，本环境未验证——macOS 无 ELF；命令照常规写法给出）
# clang++ -std=c++20 -Wall -Wextra -fPIC -shared lib.cpp -o /tmp/libmath.so
# 查看依赖与库身份：
otool -L /tmp/host_bin        # macOS（已验证）：列出 host 依赖的 dylib 与 install_name
# readelf -d /tmp/host_bin    # Linux（未在本环境验证）：看 NEEDED/SONAME
```

| 主题 | macOS dylib（已验证） | Linux .so（未在本环境验证） |
|------|----------------------|---------------------------|
| 库文件格式 | `.dylib` | `.so` |
| 编译开关 | `-dynamiclib` | `-fPIC -shared`（`-fPIC` 位置无关代码几乎总是需要） |
| 库的「身份证」 | **install_name**：编译时内嵌的路径（默认=编译时的输出路径），dyld 按它找库 | **soname**：`-Wl,-soname,libfoo.so.1`，运行时链接器按它解析 |
| 宿主怎么记录依赖 | 链接时把 install_name 记进依赖表 | 链接时把 soname 记进 NEEDED |
| 查看 | `otool -L` / `otool -D` | `readelf -d` |
| 动态解析命令 | `install_name_tool -id/-change`、`@rpath`/`@loader_path` 占位 | `ldconfig`、`RPATH`/`RUNPATH`、`$ORIGIN` |

install_name 是本环境能实测的关键概念：examples/ex02 编译 `/tmp/libmath.dylib` 后 `otool -L` 看到宿主依赖的正是这个路径——**把 dylib 挪走，宿主启动即报找不到库**（dyld 按 install_name 找，不按「当初链接目录」找）。工程上普遍用占位符逃避绝对路径依赖：`-install_name @rpath/libfoo.dylib` 配合宿主的 `-rpath`（dyld 依次尝试 rpath 目录）。这套机制与 Linux 的 soname/RPATH 一一对应，但工具名完全不同——读 ph10 工具链阶段时「动态库怎么编」看的是编译器手册，本阶段看的是 dyld/ld.so 的查找规则。

dyld 在运行期按什么顺序找库（本机实测的部分 + 文档惯例）也要心里有数，因为「为什么我的程序在这台机器上找不到库」是动态库第一大运行期事故：

| 占位符/规则 | 含义 | Linux 对应（未在本环境验证） |
|------------|------|---------------------------|
| 绝对路径 install_name（ex02 默认） | 死路径，库里写死，挪动即崩 | 无对应（soname 配 ldconfig 缓存） |
| `@executable_path/...` | 相对宿主可执行文件所在目录 | `$ORIGIN` |
| `@loader_path/...` | 相对「正在加载这个库的那个二进制」的目录（库嵌库时关键） | 同上（按加载者区分） |
| `@rpath/...` + 宿主 `-rpath` | 相对宿主声明的 rpath 列表逐个试 | `RPATH`/`RUNPATH` |
| 系统标准目录 | `/usr/lib`、`/System/Library/Frameworks` 等 | `/usr/lib`、`/lib`、`ldconfig` 缓存 |

一句话记忆：**`@executable_path` 管宿主自己的库，`@loader_path` 管库又依赖的库**（插件再 dlopen 别的插件时是 loader）。examples 全部用 /tmp 绝对路径或直接 dlopen 绝对路径，恰恰是为了演示「install_name 写死」的机制；真实工程走 @rpath。

编译与链接还要分清两个问题：**① 链接期解析**（宿主编译时 `-L... -lmath`，链接器确认符号存在、记下依赖，运行期由 dyld 填地址）；**② 运行期解析**（dlopen/dlsym，宿主根本不需要 `-l`，见 3.5）。前者「链接期绑定」适合确定需要的库，后者「加载期/运行期绑定」才是插件与「热插拔」的地基。静态库（`.a`）介于源码与二进制之间：它把目标文件直接并入可执行文件，无运行期解析、无版本兼容问题，但也放弃了「升级库不动宿主」的自由（第 5 节对比展开）。

### 3.5 dlopen/dlsym/dlerror：运行期把库请进来

dlopen 家族是 POSIX 的插件运行时底座。三步曲加一个错误通道：

| 函数 | 作用 | 失败返回 |
|------|------|---------|
| `dlopen(path, flags)` | 把动态库映射进进程，返回句柄（引用计数 +1） | `nullptr` |
| `dlsym(handle, name)` | 按符号名查地址，返回可转成函数指针/变量的 `void*` | `nullptr` |
| `dlerror()` | 取最近一次 dlopen/dlsym/dlclose 的人类可读错误并清空状态 | `nullptr`（无错误） |
| `dlclose(handle)` | 引用计数 -1，归零才真正卸载 | 非 0（错误码） |

`dlopen` 的 flag：`RTLD_NOW` 加载时立即解析全部符号（早失败、早诊断），`RTLD_LAZY` 用到才解析（快一点，但符号缺失拖到调用时才炸）；`RTLD_LOCAL`（默认）/`RTLD_GLOBAL` 控制本库导出的符号是否进入全局符号表、能否被后续加载的库解析——插件默认用 `RTLD_NOW | RTLD_LOCAL`。examples/ex03 的主干代码：

```cpp
// examples/ex03-host.cpp —— 节选：dlopen 三步曲 + 错误处理
void* h = dlopen(path.c_str(), RTLD_NOW);
if (h == nullptr) { /* 用 dlerror() 给出可诊断信息后退出 */ }
auto kind = reinterpret_cast<int (*)()>(dlsym(h, "plugin_kind"));  // 约定签名，无编译期检查
// ……调用 kind()……
dlclose(h);   // 引用计数 -1；无人再用时库被真正卸载
```

**dlsym 的 void\* 转函数指针**是 POSIX 惯例（标准 C 里 `void*` 与函数指针互转严格说是未定义行为，但 POSIX dlsym 的实际用法就是 cast；clang 的 `-Wall -Wextra` 对此不告警）。接口签名「约定」而非「检查」——ex03 里两个插件 add/mul 遵循同一份接口注释，宿主对它们零重编译切换。Windows 的对应物语义一致、名字不同：`LoadLibrary`（dlopen）、`GetProcAddress`（dlsym）、`FreeLibrary`（dlclose）、`GetLastError` 或扩展错误机制（dlerror），且 Windows DLL 需要 `__declspec(dllexport/dllimport)` 显式标导出（与 3.6 的 Linux 式 `-fvisibility=hidden` 殊途同归——Windows 默认就隐藏）。

> 注意：dlopen 加载的符号查找、dlsym 拿到的地址、dlclose 的卸载时机，背后是 dyld/ld.so 的符号表与引用计数机制（第 4 章展开）。运行期解析让「换库不换宿主」成为可能，也让「找不到符号」从链接期推迟到运行期——**dlopen 边界的错误处理不是可选项**，ex03/ex05 宿主每一步失败都走 dlerror 并带符号名报错，就是这条纪律的落地。

### 3.6 符号隐藏与可见性：默认全导出是慢性病

不控制可见性时，动态库把**所有全局符号**都导出（Mach-O 与 ELF 默认行为）。这带来三类问题：**① 符号撞名**——宿主先加载的库 A 导出了 `init`，库 B 也导出 `init`，B 内部对 `init` 的调用可能被 dyld 解析到 A 的实现（同名符号由加载顺序裁决）；**② 接口失控**——内部实现细节成了事实 API，别人链接你的内部函数，你就再也不能改它；**③ 加载变慢**——动态符号表越大，解析负担越重。工程标准姿势是「**默认隐藏 + 白名单导出**」：

```cpp
// examples/ex04-visibility-lib.cpp —— 节选：白名单宏
#define EXPORT __attribute__((visibility("default")))
extern "C" EXPORT int store_version(void);   // 想开放的接口：显式放行
// 内部函数不写 EXPORT → -fvisibility=hidden 时不出现在导出表
```

```bash
# 编译（-fvisibility=hidden 把默认可见性收为 hidden）
clang++ -std=c++20 -Wall -Wextra -fvisibility=hidden -dynamiclib \
    ex04-visibility-lib.cpp -o /tmp/libstore.dylib
# 导出表验证（本机实测）：只剩白名单符号；去掉 -fvisibility=hidden 后，
# 内部函数（形如 __Z16ts_internal_impl… 的 mangled 名）也会冒出来
nm -gU /tmp/libstore.dylib
```

`nm -gU`（macOS 看导出、Linux 用 `nm -D`）因此成了**库接口的审计工具**：导出表就是你承诺的公共表面。白名单的收益一条条都对得上工程问题：导出集合小 → 撞名概率低 → 公共接口清单一目了然 → 宿主链接期依赖不到内部符号（ex04 宿主注释里演示了「声明了也链接不上」的护栏）。补充两点边界认知：**① 隐藏不是安全机制**——符号仍可用工具看、被逆向，它管的是「宿主编译/链接期不该依赖它」；**② Mach-O 上匿名命名空间符号本来就按 local 处理**，与可见性控制是两层事，别把「藏进匿名命名空间」当成 `-fvisibility=hidden` 的替代品。

### 3.7 版本兼容：动态库的升级只有两种

动态库升级时，接口改动落在哪一侧决定老宿主命运。先分清两条独立的兼容线：

| 改动 | 源码兼容？（重编译就行） | 二进制兼容？（老宿主直接跑） | 机制 |
|------|------------------------|---------------------------|------|
| 改函数体实现 | 是 | 是 | 不碰符号与布局 |
| 加一个非虚函数 | 是 | 是（多数平台） | 新符号入导出表，老符号不动 |
| 函数签名加/换参数 | 否（调用的要改） | **否**（C++：mangled 名变，链接期崩；C：链接过，运行期崩） | mangling / 调用约定 |
| struct 尾部追加字段 | 是 | **是**（老字段偏移不变） | 布局稳定 → 推荐方向 |
| struct 头部/中间插入字段 | 是 | **否**（后续字段全移位，老宿主读错位置） | 布局漂移 |
| 基类头部加虚函数 | 是 | **否**（vtable 槽位后移） | vtable 位置编码 |

二进制兼容的三种典型断裂，按「编译器帮不帮你」排：

| 断裂方式 | C++ 的护栏 | 后果 |
|----------|-----------|------|
| 改函数签名 | 有：mangling 变 → 链接期 undefined symbol（ex01 演示） | 早失败、可诊断 |
| 改 struct 布局 | 无：布局是约定不是符号 | 老宿主按老偏移读到脏数据（ex06 用 `api=2` 被读成 `1432778632` 做字节级演示） |
| 改 vtable（头插虚函数/继承变） | 部分：无符号级提示 | 虚调用对错槽位，跑错函数 |

> ⚠️ 老宿主通常是**已发布、不能重编译**的二进制——它可能装在几百万台设备上。所以 ABI 设计的黄金纪律是：**新字段往尾部加、新虚函数往尾加、签名从不改、struct 布局当宪法**。改接口版本号的代价永远小于制造一场二进制事故。

配套机制按平台分两层。**约定层（人人可用）**：插件导出接口版本号（如 `plugin_version_major/minor`），宿主加载后先校验再使用——major 不同=二进制不兼容拒绝加载，major 相同=尾部追加式演进放行（examples/ex06 把规则落地，exercises/sol-03 做了完整正反实验：v1 插件被明确拒绝、v2.0 因 minor 不足被拒、v2.1 通过）。**链接器层（Linux 专有）**：ELF **symbol versioning** 用 version script 给符号编版本，一个 `.so` 可以同时带 `foo@VER_1` 与 `foo@VER_2` 两代实现，老二进制继续解析到老符号、新二进制用新符号，glibc 就是这么滚动升级的——这是 3.6「导出表审计」在 Linux 上的终极形态。macOS 没有内建等价的符号版本机制，靠的是**库名/install_name 带版本号**（`libfoo.2.dylib`）与接口版本约定的组合拳。

```bash
# Linux ELF symbol versioning 示意（本环境未验证——Linux 链接器特性）
# ld --version-script=exports.map -shared -o libfoo.so.2 foo.o
# exports.map:
#   VER_2 { global: foo_new; foo_old; local: *; };
#   VER_1 { global: foo_old; } VER_2;
```

**这一层为什么重要**：C++ 的 mangling 护栏只在「签名变了」时起作用，struct 布局变化它无能为力（第二行）。所以版本检查必须管住 struct：接口版本号断言 + 「尾部追加」演进纪律，就是 C ABI 插件世界里手工实现的「弱版 symbol versioning」。project 的 `engine_api` 结构体带 `api_major/api_minor` 字段、宿主加载即校验，就是这套纪律在真实 demo 里的样子。

### 3.8 插件生命周期与所有权纪律：谁创建，谁销毁

插件边界上最贵的错误不是算错数，而是**资源在错误的一侧被释放**。三条红线 + 一条铁序：

**红线 1：new/delete 必须同一侧配对。** 插件里 `new` 出来的对象，必须由插件导出的销毁函数 `delete`。跨侧 delete 是未定义行为：两侧若来自不同的 runtime/堆（Windows 上每个 DLL 可以链不同的 CRT、各有各的堆——最典型的现场；macOS/Linux 共享 libc++ 与 libsystem 的 malloc 时「碰巧能活」，但那是运气不是承诺），释放指针进错堆，轻则泄漏重则崩溃。

**红线 2：对象用 opaque 句柄出边界。** 插件把完整类型藏在自己那一侧，宿主只见前向声明：

```cpp
// examples/ex05 两侧的约定：宿主永远拿不到完整定义
//   插件侧：  struct text_stats { std::vector<std::string> words; ... };  // 完整定义
//   宿主侧：  struct text_stats;   // 不完整类型：delete 与成员访问都被编译器禁止
//   入口：    extern "C" text_stats* ts_create(void);
//             extern "C" void ts_destroy(text_stats*);
```

opaque 的意义是把红线 1 从「口头约定」升级成「编译器强制」——宿主 `delete raw` 直接编译错误（ex05 注释里演示了这条错误），销毁的唯一合法路径是插件导出的 `ts_destroy`。project 的 `storage_engine` 是同一个形状：宿主握指针、引擎的 `create/destroy` 管内存。

**红线 3：C++ 异常不跨边界；静态对象生命周期不跨 dlclose。** 异常沿栈展开依赖各编译单元的异常展开表（Itanium ABI 的 `.eh_frame`）与运行库配合，跨 dylib 抛出/捕获在两侧编译器/选项不同时是 UB（本阶段规则：C ABI 函数体内 catch 干净、以错误码返回——这是 roadmap 第 20 节互操作阶段「异常到错误码转换」的雏形）；函数级 `static` 局部对象与全局对象的析构由退出期机制驱动，dlclose 卸载后对象的析构代码已不在内存，其析构函数调用就是跳到已卸载代码。

**铁序：先 destroy 所有插件对象，再 dlclose 句柄。** 顺序反过来，destroy 走到的是已经卸载的代码。examples/ex05 把三条红线 + 铁序全部落成可观察的代码：宿主侧 RAII 包装持 dlsym 来的 `ts_destroy` 并在析构时调用（等价于 `unique_ptr<T, Deleter>` 思路——RAII 跨过动态库边界依然成立，只是 deleter 从编译期符号变成运行期函数指针）；靠「成员按声明顺序构造、逆序析构」的语言保证把 destroy 排在 dlclose 之前，运行输出直接打印了两者的先后：

```text
[host ] 退出作用域：holder 先析构（destroy），DlHandle 后析构（dlclose）
[host ] ts_destroy() 在 dlclose 之前被调用     ← 顺序由 RAII 保证，人不会忘
```

> 本阶段的生命周期纪律在「宿主 ↔ 插件」一对一场景足够；**多插件共享对象、插件调用插件、卸载时仍有其他库引用它的符号**这些高阶场景牵涉符号交错与引用计数细节（第 4 章给出原理级认知），工程化兜底继续靠 version 检查 + 卸载顺序约定。plugin ABI 里 create/destroy 成对出现的固定形状（roadmap §19 示例代码 `extern "C" Plugin* CreatePlugin(); extern "C" void DestroyPlugin(Plugin*);`）就是本小节所有纪律的浓缩：**入口返回 opaque、销毁交给创建者那一侧**。

## 4. 底层原理

### 4.1 从源文件到动态库：两步链接把「符号解析」拆成两半

静态链接时代，符号解析在编译产物 `.o` 之间完成一次；动态库把这一刀切在**链接期**与**加载期**：

```text
库源文件 ──编译(-dynamiclib/-shared)──▶ .dylib/.so（含符号表+未解析引用表）
宿主源文件 ──编译──▶ .o ──链接(-lxxx)──▶ 可执行文件
                                              │  链接器只做两件事：
                                              │  1. 确认宿主引用的符号在库导出表里存在
                                              │  2. 把库的「身份证」(install_name/soname)记进依赖表
                                              ▼
运行 dlopen/启动 ──▶ dyld/ld.so 按身份证找到库、映射进内存、填好地址
```

关键认知：**链接器不做地址绑定**。宿主对 `math_add` 的调用在可执行文件里是「跳转到 GOT/桩，运行时由 dyld 填」的间接跳转，不是编译期写死的绝对地址。这层间接是后面所有机制（懒解析、ASLR、插件热替换）的共同前提——ph18 的结论在这里翻转：同一翻译单元里编译器看得见的间接几乎免费（被内联/去虚化），**跨库边界必须保留运行时间接，编译器无法消除它**。

### 4.2 Mach-O 与 ELF：符号表长在哪、导出表怎么查

两个平台的可执行格式都含一张**符号表**，把「符号名 → 地址」记下来供链接器与加载器使用。宿主侧看符号的三条命令对应三种视角：

| 命令 | 视角 | 说明 |
|------|------|------|
| `nm` / `nm -gU`（macOS）/ `nm -D`（Linux） | 静态看导出表 | `-g` 全局、`-U` 只要定义；`T`=导出文本符号、`t`=local、`U`=未解析引用 |
| `otool -L` / `readelf -d` | 看依赖表 | 列出宿主依赖的库与它们的身份证路径 |
| `strings` | 原始字符串 | 顺带能看 mangled 名在二进制里的字面存在 |

Mach-O 与 ELF 符号表还有个平台差异点：Mach-O 的符号名带下划线前缀（C 符号 `_math_add`、mangled 符号 `__Z...`），ELF 不带——所以同一 Itanium mangled 名在两平台的 `nm` 输出不同（ex01/ex02 实测），但 `c++filt` 与 dlsym 都懂得平台规则（dlsym 查 `math_add` 会自动匹配 `_math_add`，本机实测通过）。**符号表里还躺着「未解析引用」**（nm 里 `U` 开头）：库引用了别的库的符号，dyld/ld.so 要沿依赖链逐个解析——这解释了 3.6 的撞名问题：同名符号同时出现在已加载库里时，解析顺序（加载顺序）就是裁决顺序。

一张符号表里其实混着三类角色，理解它们各自的归宿，动态库的多数怪现象就能对号入座：

| 符号类别 | 例子（nm 标记） | 归宿 |
|----------|----------------|------|
| 本库定义并导出 | `T _math_add`（exported） | 进导出表，供其他二进制解析 |
| 本库定义但 local | `t`（匿名命名空间/static） | 不出导出表，库内部自用（3.6 的天然隐藏层） |
| 引用外部未定义 | `U _printf` | 进「未解析引用表」，加载时沿依赖链找 |
| 已解析的外部引用 | 加载后 GOT 填上地址 | 指向别的库的导出符号 |

dlopen 一个库时，dyld 不只映射这一个文件：它要先把该库自己的未解析引用沿**依赖链**逐层解析（库 A 依赖库 B、B 依赖 C……每个都先于 A 可用）。于是三个工程推论自然成立：**① 别用会「带进来」一堆依赖的插件**——插件依赖越少，加载越不易因缺符号失败（理想插件只依赖系统库）；**② dlclose 一个库，只在它的引用计数归零时真正卸载**——宿主与多个插件共享的库不会因为一个 dlclose 就消失，dyld 替每个库数着引用数；**③ 插件之间若共享状态，必须显式约定谁先加载、谁后卸载**——符号解析顺序与卸载顺序都是事实上的全局秩序，3.8 的「销毁先于 dlclose」在单宿主单插件场景是纪律，在多插件场景就是架构。

### 4.3 PIC 与 PLT/GOT：动态库凭什么能在任意地址跑

动态库要能被加载到进程地址空间的任意位置（ASLR 随机化 + 多进程共享同一份磁盘代码），代码就不能假设自己的地址——**位置无关代码（PIC, Position Independent Code）** 用「相对当前指令取地址」解决自身引用；对**外部符号**（调用宿主或其他库的函数、访问全局变量）则走两张表：**GOT**（Global Offset Table，记录外部符号的地址）与 **PLT**（Procedure Linkage Table，对外部函数的跳板）。一次跨库调用：

```text
宿主代码 ──call  PLT[math_add]──▶ PLT 桩（本库内，位置无关）
                                      │  首次：跳到解析器，dyld/ld.so 查 math_add 地址
                                      │        写进 GOT[math_add]，下次直接命中
                                      ▼
                                  GOT[math_add] ──▶ dylib/.so 里的 math_add 真身
```

ELF 的默认懒绑定正是把「首次调用时才解析」做进 PLT 桩（`RTLD_LAZY` 同源）；Mach-O/dyld 的绑定模型略有不同（dyld 在加载期做两阶段 bind，arm64 上默认全量绑定、没有 PLT 懒解析的等价物，但 stub binder 的间接层一样存在）。对程序员只有三条可操作的结论：**① 跨库调用的成本包含一次额外的间接跳转**（比同 TU 直调多个内存访问层次，ph18 实测同 TU 间接被编译器消灭、跨库则保留——所以热路径别把逐元素运算拆成跨库逐调用）；**② 懒解析把「缺符号」从加载期推迟到首次调用期**，要早失败就 `RTLD_NOW`；**③ PIC/PLT/GOT 是链接器与 dyld 的分工，程序员一般不直接碰**——但理解它才能解释「为什么 dlsym 拿地址、而不是硬编码地址」以及「为什么插件升级能生效」（新库映射到新地址，GOT 重新填）。

### 4.4 ASLR/PIE 与运行期解析：为什么插件边界必须「按名找址」

现代系统默认地址空间布局随机化（ASLR），可执行文件用 PIE 编译才能在随机基址上跑——这带来一个直接推论：**任何二进制都不能假设自己或别人的符号在固定地址**。编译期静态链接的地址在加载期全部要被重定位/绑定填过一遍；dlopen 的库更是「这次加载落在哪、符号地址是多少，运行时才知道」。这正是插件机制存在形式的底层原因：

| 层 | 固定地址假设 | 实际机制 |
|----|-------------|---------|
| 源码层 | 函数名 → 代码 | 编译器生成符号，人写名字 |
| 静态链接 | 符号名 → 固定地址 | 链接器排布，加载期重定位 |
| 动态绑定（链接期依赖） | 符号名 + 库身份证 → dyld 填 GOT | `-l` 链接 + install_name/soname |
| 运行期插件 | 符号名 + 路径 → dlopen 返回句柄 → dlsym 查名 | `dlopen` + `dlsym`，地址运行时才有 |

所以 dlsym 拿到的指针**只对本次加载有效**：dlclose 后指针悬空、再次 dlopen 可能映射到不同地址。3.8 的「销毁先于卸载」与这里的「指针随加载周期有效」是同一事实的两面——**插件世界里一切指针的生命周期都由「库的加载周期」框定**，这正是本阶段所有纪律（谁创建谁销毁、版本检查、dlclose 顺序）的总根源。

### 4.5 跨库调用成本：ph18 那句预告的兑现

ph18 ex06 的实测结论是「同翻译单元里编译器看得见的间接几乎免费」（直调/函数指针/虚函数被内联与去虚化收敛到同速）；当时预告说**跨过动态库边界则不同**。现在可以把它说完整：跨库调用的间接是 PLT/GOT（Mach-O 上是 stub binder）这层**运行时的、编译器无法消除的间接**——调用点看不到库的实现，去虚化/内联在本阶段根本无从谈起。所以跨库边界的成本结构是「一次间接跳转 + 可能的缓存未命中」，具体含义：

| 场景 | 跨库间接的代价 | 工程对策 |
|------|----------------|----------|
| 配置/启动路径的少量调用 | 可忽略（一次查表填地址后基本直接跳） | 无需操心 |
| 热路径上的**逐元素/逐行**跨库调用 | 每次调用都付间接层，且库实现通常是另一份代码、数据可能不在缓存 | 把接口粒度放大：逐元素运算留在库内整段完成，库边界只传「批」（与 ph18 的按行虚调用→按批调用同一课） |
| 首次调用 | 懒解析场景还要付一次符号解析 | 需要早失败/低延迟启动用 `RTLD_NOW`，把解析成本挪到加载期一次付清 |
| 边界两侧各持大状态、频繁互相回调 | 双方都过间接 + 状态互不可见，缓存与内联双输 | 重新审视边界划分：热交互的两个模块应留在同一二进制内 |

这条「边界在哪、成本就在哪」的判断与 ph18 的测量纪律是同一句话的两面：**先用数据点名热点（ph18），再看热点是否落在二进制边界上（本阶段）**——若在，改接口粒度或挪边界，而不是优化单个函数。动态库的性能税不是「用动态库就要付」的固定成本，而是**边界划分的函数**：划在低频接口处，税几乎为零；划在逐元素热路径上，税是结构性的。

## 5. 使用场景

**什么时候该用动态库/插件**，一张表说清选择逻辑：

| 场景 | 选什么 | 为什么 / 注意 |
|------|--------|--------------|
| 多个进程共享同一份库代码 | 动态库 | 磁盘/内存省一份；前提是接口稳定（ABI 冻结） |
| 需要独立升级库、不重发宿主 | 动态库（ABI 兼容的升级） | 只能做 3.7 里的「尾部追加式」演进，否则老宿主崩 |
| 插件生态：存储后端、算子、渲染器、AI 引擎 | dlopen/dlsym（ex03/ex05/project 的形状） | 第三方扩展点必须 C ABI + 版本检查 + opaque 生命周期 |
| 启动期依赖、符号必须早失败 | 链接期绑定 + `RTLD_NOW` 类语义 | 缺库尽早报，别拖到调用期 |
| 代码只被一个程序使用、无独立升级诉求 | 静态库 `.a` 或直接编译进去 | 免去 ABI 负担：编译进去的东西不存在二进制兼容问题 |
| 热路径上的逐元素运算 | 留在同 TU 内（别跨库拆） | 跨库间接跳转是 ph18「可见间接免费」的边界——PLT/GOT 那层运行时间接编译器消除不掉 |

工程上的「默认」是什么：**库面向独立生态（第三方要用、要独立升级）才值得为 ABI 付税**；库只是内部实现切分（ph10 的多目标构建、ph17 的分层），静态链接或统一构建常常更省事——ABI 冻结是持续的维护成本，接口每动一次都要评估二进制影响。插件机制则是「动态库 + 运行期加载」的极致形态：**把接口稳定做成业务承诺**（插件开发方与宿主开发方可能不同团队、不同发布节奏），这也是为什么 roadmap 把「设计稳定插件接口」写成本阶段验收。

**反模式清单**（本阶段知识点能帮你躲开的坑，多数是「为了解耦而解耦」）：① 两个模块其实同进程同发布、互相无第三方诉求，硬拆成插件——白付 ABI 冻结税 + dlopen 错误处理成本；② 把热路径拆成插件再逐元素回调——跨库间接的结构性成本（4.5）；③ 插件内部依赖一长串自家库——dlclose 的引用计数与依赖链让加载/卸载顺序变脆弱（4.2）；④ 用「宿主读插件文件名判断能力」——能力应该由接口与版本号表达，不是名字（project 的能力探测演示的就是反过来的做法）；⑤ 只有 create 没有 destroy 的插件——对象泄漏 + 跨边界释放隐患，create/destroy 成对是插件 ABI 的第一课（3.8）。判断口诀：**需要「独立升级、第三方扩展、运行时选择实现」三者之一，才谈动态库/插件**；只是内部代码切分，静态链接更省心。

**与其他语言的对比**（为 analysis/ 与 Tenet 合成积累素材）：

| 维度 | C++ | C | Rust | Go | Python |
|------|-----|----|------|-----|--------|
| 跨库对象生命周期 | opaque + 约定（谁创建谁销毁） | 同 C++（更原始的 malloc/free 约定） | `#[no_mangle]` + 类型擦除后同 C | 无动态库插件主流（cgo/plugin 包受限） | 扩展即 C 扩展（C ABI，roadmap 第 20 节主题） |
| 符号命名 | mangling（需 extern "C" 去魔法） | 原名导出 | 默认 mangling，需 `#[no_mangle]` + `extern "C"` | 导出表由链接器规则 | CPython 固定 ABI 约定 |
| 语言自带 plugin 机制 | 无，dlopen 全家桶是行业标准 | 无，同 C++ | 无，同 C++ | 标准库有 `plugin`（Linux-only、受限） | `importlib` 动态 import 是其「插件」形态 |
| 二进制兼容保障 | 无语言级保障（编译器/库 ABI 自行协商） | 无（C ABI 事实上最稳） | 无（同 C++，但类型系统把错误面收窄） | 无（gc 与运行时绑定进程） | 解释器兜底（错在解释层报异常） |

一句话：**C/C++/Rust 家族把「插件」做成一件需要自己立法的事**——语言不给二进制兼容承诺，于是 ABI、extern "C"、版本号、生命周期纪律就是你自己立的法律；Go/Python 各有自己的扩展或插件形态，但代价是把扩展方绑死在特定运行时上。Tenet 语言若想兼得，需要回答：**插件的稳定边界该由语言层强制（类似 extern "C" 的显式标记 + opaque 纪律进类型系统），还是继续留给工程约定**——本阶段的所有纪律清单就是这组答案的候选素材。

## 6. 代码示例

> 说明：`examples/` 与 `project/` 全部代码**已验证**（Apple clang 21.0.0 与 Homebrew clang 21.1.8 双编译器 `-std=c++20 -Wall -Wextra` 本机实测：编译零警告、运行通过、断言自测全绿；dylib/dlopen/nm/otool 等 macOS 动态库操作全部本机实测）；`exercises/` 参考实现**已验证**（Apple clang 21.0.0 本机实测，命令与输出见 `exercises/README.md`）。Linux ELF 专属命令（`.so`/soname/version script/`nm -D`）在文件中标注「未在本环境验证」。完整可运行文件在 [`examples/`](./examples/)，此处展示关键片段并给命令。下列命令在 examples/ 目录内执行。

### 示例 1：name mangling 与 demangle（examples/ex01-mangling-demangle.cpp）

对应 3.2 与 roadmap 学习内容「name mangling」。dladdr 运行时取真名 + `__cxa_demangle` 反解；演示重载/命名空间/模板的符号分道，并用「签名变化 → mangled 名变化」做 ABI 护栏断言：

```cpp
// examples/ex01-mangling-demangle.cpp —— 节选：dladdr 拿符号名，demangle 反解
Dl_info info{};
dladdr(reinterpret_cast<void*>(fn), &info);      // 地址 → 符号信息
char* dem = abi::__cxa_demangle(info.dli_sname, nullptr, nullptr, &status);
// 实测输出：math::add(int,int) → _ZN4math3addEii → math::add(int, int)
```

```bash
# 1. 编译并运行：
clang++ -std=c++20 -Wall -Wextra ex01-mangling-demangle.cpp -o /tmp/ph19cpp-ex01 && /tmp/ph19cpp-ex01
# 2. nm + c++filt 对照符号表：
nm /tmp/ph19cpp-ex01 | c++filt
```

### 示例 2：extern "C" 动态库（examples/ex02-math.h + ex02-extern-c-shared.cpp + ex02-host.cpp）

对应 3.3/3.4 与 roadmap 学习内容「extern C」「动态库构建」。`__cplusplus` 守卫头 + 同一源码里 extern "C" 与 C++ 符号并存，`nm -gU` 直接看两类形态：

```bash
# 1. 编译 dylib 并看导出符号（_math_add/_math_version 是 C 链接；__ZN4math3addEii 是 C++）：
clang++ -std=c++20 -Wall -Wextra -dynamiclib ex02-extern-c-shared.cpp -o /tmp/libmath.dylib
nm -gU /tmp/libmath.dylib | c++filt
# 2. 编译宿主并链接调用：
clang++ -std=c++20 -Wall -Wextra ex02-host.cpp -L/tmp -lmath -o /tmp/ph19cpp-ex02-host
/tmp/ph19cpp-ex02-host          # 预期输出两行 42
# 3. 看宿主依赖记录的 install_name：
otool -L /tmp/ph19cpp-ex02-host
```

### 示例 3：dlopen 加载插件（examples/ex03-plugin-add.cpp + ex03-plugin-mul.cpp + ex03-host.cpp）

对应 3.5 与 roadmap 学习内容「动态库加载」。同一 C ABI 接口两个插件，宿主运行期切换实现；dlopen 失败/dlsym 缺符号两条错误路径都给可诊断输出：

```bash
# 1. 编译两个插件与宿主：
clang++ -std=c++20 -Wall -Wextra -dynamiclib ex03-plugin-add.cpp -o /tmp/libop_add.dylib
clang++ -std=c++20 -Wall -Wextra -dynamiclib ex03-plugin-mul.cpp -o /tmp/libop_mul.dylib
clang++ -std=c++20 -Wall -Wextra ex03-host.cpp -o /tmp/ph19cpp-ex03-host
# 2. 运行（默认加载两个插件；也支持单插件）：
/tmp/ph19cpp-ex03-host
# 预期：add 插件 6.0+7.0=13.0、mul 插件 6.0*7.0=42.0、错误路径按预期输出
```

### 示例 4：符号可见性白名单（examples/ex04-visibility-lib.cpp + ex04-visibility-host.cpp）

对应 3.6。`-fvisibility=hidden` + `EXPORT` 宏的「默认隐藏 + 白名单导出」，`nm -gU` 对照有无 hidden 的导出表差异：

```bash
# 1. 白名单策略编译，导出表只剩 _store_version/_store_touch：
clang++ -std=c++20 -Wall -Wextra -fvisibility=hidden -dynamiclib ex04-visibility-lib.cpp -o /tmp/libstore.dylib
nm -gU /tmp/libstore.dylib
# 2. 对照：去掉 -fvisibility=hidden，内部函数也会出现在导出表：
clang++ -std=c++20 -Wall -Wextra -dynamiclib ex04-visibility-lib.cpp -o /tmp/libstore_all.dylib
nm -gU /tmp/libstore_all.dylib
# 3. 编译运行宿主：
clang++ -std=c++20 -Wall -Wextra ex04-visibility-host.cpp -L/tmp -lstore -o /tmp/ph19cpp-ex04-host
/tmp/ph19cpp-ex04-host
```

### 示例 5：插件生命周期与所有权（examples/ex05-plugin-object.cpp + ex05-lifecycle-host.cpp）

对应 3.8 与 roadmap 必会概念「谁创建谁销毁要约定清楚」「能避免跨库释放错误」。插件侧 new opaque 对象、宿主经 C ABI destroy，RAII 保证 destroy 先于 dlclose（运行输出的打印顺序可验证）：

```bash
# 1. 编译插件与宿主：
clang++ -std=c++20 -Wall -Wextra -dynamiclib ex05-plugin-object.cpp -o /tmp/libtextstats.dylib
clang++ -std=c++20 -Wall -Wextra ex05-lifecycle-host.cpp -o /tmp/ph19cpp-ex05-host
# 2. 运行（预期：summary 3 words, 20 chars；[host] 退出作用域 → ts_destroy → dlclose）：
/tmp/ph19cpp-ex05-host
```

### 示例 6：ABI 演进仿真（examples/ex06-abi-evolution.cpp）

对应 3.7 与 roadmap 学习内容「版本兼容」。尾部追加 vs 头部插入的 offsetof 对照、老宿主读错数据的字节级证据、插件接口 major/minor 版本检查规则落地：

```bash
# 1. 编译并运行：
clang++ -std=c++20 -Wall -Wextra ex06-abi-evolution.cpp -o /tmp/ph19cpp-ex06 && /tmp/ph19cpp-ex06
# 预期：v2_tail 老宿主读到 api=2（正确）；v2_mid 老宿主读到 1432778632（脏数据）；版本检查三行判定
```

## 7. 总结

### 关键要点

1. **ABI 是二进制契约，API 是源码契约**；ABI 破坏的代价是全部已发布二进制失效。C++ ABI 不稳的三个机制原因：mangling、vtable 布局、标准库类型布局（3.1）
2. **Itanium mangling 把签名烙进符号名**（`_ZN4math3addEii`），签名变符号就变 → 链接期护栏；读报错用 `c++filt`/`__cxa_demangle`/`nm`，不手写编码（3.2）
3. **Mach-O 符号带下划线前缀**（`_math_add`/`__Z...`），ELF 不带；同一 mangling 两平台 nm 输出不同，dlsym/dladdr 层自动处理（3.2/3.3，本机实测）
4. **extern "C" = 关掉名字魔法**：插件边界的公共函数几乎都走它；`__cplusplus` 守卫让头文件 C/C++ 双用（3.3）
5. **动态库的身份证**：macOS 是 install_name（`otool -L` 查、dyld 按它找），Linux 是 soname；产物挪位即找不到库（3.4，install_name 本机实测、soname 未验证）
6. **dlopen 三步曲 + dlerror 错误通道**：加载期/运行期解析让「换库不换宿主」成立，也让错误推迟到运行期——错误处理不是可选项（3.5/ex03）
7. **默认隐藏 + 白名单导出**：`-fvisibility=hidden` + `visibility("default")`；`nm -gU` 就是你的接口审计工具（3.6/ex04）
8. **二进制兼容只有一种安全改法：尾部追加**；头部插入/改签名/头插虚函数都是事故。C++ 的 mangling 护栏覆盖签名变化，struct 布局靠接口版本号兜底（3.7/ex06）
9. **谁创建谁销毁**：new/delete 同一侧配对、opaque 不完整类型让跨侧 delete 变成编译错误、异常与静态对象不跨边界、destroy 严格先于 dlclose（3.8/ex05/project）
10. **跨库间接是运行时间接**（PIC/PLT/GOT、ASLR 下按名找址），编译器无法消除——ph18「同 TU 可见间接几乎免费」的边界就在动态库墙上（4.1/4.3/4.4）

### 阶段验收清单

- [ ] 能**解释 ABI 破坏的原因**（roadmap 验收）：说出至少三条 C++ ABI 不稳定的机制性原因，并能判断「加一个非虚函数 / struct 尾部追加字段 / struct 头部插入字段 / 改函数签名」各属于源码兼容还是二进制兼容（3.1/3.7）
- [ ] 能**设计基础插件生命周期**（roadmap 验收）：画出 create → 使用 → destroy → dlclose 的完整顺序，讲清 opaque 句柄与「谁创建谁销毁」如何互相配合（3.8/ex05）
- [ ] 能**避免跨库释放错误**（roadmap 验收）：说出跨侧 delete 为什么是 UB（不同堆/runtime）、opaque 类型如何把错误挡在编译期、销毁先于卸载的顺序由什么机制保证（3.8）
- [ ] 能辨认 mangled 名并反解：看到 `_ZN4math3addEii` 知道是 `math::add(int,int)`，会用 c++filt/nm/__cxa_demangle 三件套（3.2）
- [ ] 能说明 extern "C" 与 C++ 链接的符号形态差异（ELF 与 Mach-O 两种前缀规则），以及为什么插件边界选 C ABI（3.3）
- [ ] 能用 dlopen/dlsym/dlclose 手写一个最小插件宿主并处理全部错误路径；说出与 LoadLibrary/GetProcAddress 的对应（3.5/ex03）
- [ ] 能跑通 `nm -gU` 验证白名单导出，解释「默认全导出」的三宗罪（撞名/接口失控/解析负担）（3.6/ex04）
- [ ] 能给自己的插件接口加 major/minor 版本检查并演示拒绝旧版本（3.7/ex06/sol-03）
- [ ] 能解释 ASLR/PIE 为什么让插件边界必须运行期按名找址、dlsym 指针为什么只对本次加载有效（4.4）

### 跨语言对比

见第 5 节末的对比表。给 analysis/ 与 Tenet 合成的启示：**稳定边界要么靠语言立法（extern "C" 显式标记、不完整类型禁止 delete、mangling 编译期护栏），要么靠工程约定（版本号、dlclose 顺序、C ABI 风格指南）**。C++ 选择两头都沾：mangling/opaque 给了编译器能抓的护栏，接口版本与生命周期则靠纪律——本阶段验证的正是「哪些护栏可以自动化、哪些必须人肉」。C 靠极简（无 mangling、无重载、无隐藏机制，换来事实上的最稳 C ABI）；Rust 用类型系统把可越过边界的错误面大幅收窄但 ABI 层面依旧同 C++；Go/Python 用运行时绑定换取「扩展不必自己立法」但失去独立二进制。Tenet 若做系统语言，插件边界设计可以直接借鉴本阶段清单：**显式 ABI 标记、opaque 强制、版本进接口**。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 3 题，与 roadmap §19「练习」小节一一对应：写一个动态库（★★★）、用 dlopen/LoadLibrary 加载插件（★★★）、设计插件版本检查（★★★）。每题要求 `clang++ -std=c++20 -Wall -Wextra` 零警告 + 退出码语义正确。完成 3 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**C ABI 插件式存储引擎 demo**——宿主 dlopen 加载存储后端插件，通过一份 `engine_api` 功能表（版本号 + 函数指针 + opaque 句柄）做 KV 操作；`mem_store`（内存 map，支持 del）与 `file_store`（append-only 日志，del 返回 UNSUPPORTED）两个后端能力不同，宿主按错误码探测能力而非按插件名特判（`make clean && make test` 双引擎自测全绿）。roadmap 另两个推荐项目——「查询执行算子插件 demo」与本项目共享全部插件边界手法、换一套算子接口（open/next/close）即可落地；「TensorRT plugin 接口阅读 demo」是阅读类任务——README 的扩展方向都给出了继续路径。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`make clean && make test` 退出码 0、双编译器零警告、destroy 先于 dlclose 的输出顺序可见）

### 下一阶段

下一阶段是 [**ph20 C++ 与 C / Python / Rust 互操作阶段**](../ph20-ffi-python-rust/20-ffi-python-rust.md)：本阶段学会的「C ABI + opaque + 版本检查 + 生命周期纪律」正是跨语言绑定的全部地基——把 C++ 能力暴露给 C/Python（pybind11）与 Rust（cxx/FFI）调用时，异常到错误码的转换、字符串与容器的所有权交接、跨语言构建与错误路径测试，都是把本阶段的边界纪律换一个接收方重讲一遍；届时 roadmap 的推荐项目「C++ 存储引擎暴露 C ABI」「Python 调用 C++ 向量检索库」会直接复用本阶段 project 的接口形状。


