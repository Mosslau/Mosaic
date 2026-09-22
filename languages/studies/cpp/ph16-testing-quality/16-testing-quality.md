# C++ 测试、静态分析与代码规范阶段

> 面向工程质量闭环方向，本阶段把「写代码」升级为「可持续地交付正确代码」：单元测试框架（GoogleTest/Catch2）、静态分析（clang-tidy/cppcheck）、格式化（clang-format）、Sanitizer 工程化（ASan/TSan/UBSan）、覆盖率（gcov/lcov/llvm-cov）与 CI 接入，收敛成「一键测试 + 静态检查 + Sanitizer 复跑」的流水线。

## 1. 概述

本阶段定位：**建立 C++ 工程质量闭环**（roadmap ph16 目标）。它是整个路线的第 16 步：ph10 讲了构建与工具链基础（编译器、调试器、CMake），ph15 把 Sanitizer 当**复现工具**实测了「每种 UB 该用哪个工具抓」；本阶段把这些零散工具**工程化**——测试框架让「正确性」可重复执行，静态分析让「规范」自动强制，Sanitizer 矩阵让「无 UB」成为每次构建的验收条件，覆盖率让「测没测到」可视化，CI 把这一切钉死在每次提交上。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 单元测试 | GoogleTest / Catch2 的断言、用例组织、退出码语义；无框架环境下的最小断言框架同构演示（`ex01`） |
| 静态分析 | clang-tidy 检查族、配置（Checks/WarningsAsErrors/HeaderFilterRegex）、告警即失败门禁；cppcheck 分工（`ex02`） |
| 代码格式化 | clang-format 配置与 `--dry-run --Werror` 格式门禁（`ex03`） |
| Sanitizer 工程化 | 同一份源码 × normal/ASan/ASan+UBSan/TSan 构建矩阵；平台差异实测（`ex04`，承接 ph15 的工具结论） |
| 覆盖率 | llvm-cov source-based 三步流；gcov/lcov 路线对照（`ex05`） |
| CI 集成 | 四道闸门（格式 → 静态分析 → 测试矩阵 → Sanitizer+覆盖率）的 GitHub Actions 模板（`ex06`） |

这个阶段只涉及质量工具链的使用与工程化（测试框架、静态分析、格式化、Sanitizer 构建矩阵、覆盖率、CI 接入），**不涉及 UB 的系统分类与识别（ph15 未定义行为 UB 与内存安全阶段）、并发同步规则与内存序（ph08 并发编程阶段）、构建系统与调试器本身（ph10 构建、调试与工具链阶段）、设计模式与架构（ph17 设计模式与架构能力阶段）和性能剖析与 benchmark（ph18 性能优化与 Profiling 阶段）** — 那些是其他阶段的内容。

## 2. 来源与演变

C++ 没有内建测试与格式化设施（对比 Go 的 `go test`/`gofmt`、Rust 的 `cargo test`/`rustfmt`），质量工具链完全是**社区生态**长出来的——这决定了本阶段的学习对象是「一批独立工具的组合」而非「一个官方组件」。**设计哲学一句话：把每一次人工检查变成一条可重复执行的命令，把每一条命令钉进 CI——质量不靠自觉，靠流水线**。

单元测试框架的血脉来自 xUnit：Kent Beck 为 Smalltalk 写的 SUnit（约 1994）确立「TestCase + 断言 + 自动汇总」范式，JUnit（1997，Beck 与 Gamma）把它带到 Java，CppUnit（2000）是 C++ 的第一个移植；GoogleTest（2008，Google 内部 Project "gtest"）用「自动注册 + 非致命/致命断言分离」超越了 CppUnit 的手工注册，成为事实标准；Catch（2010）/ Catch2 用「header-only + SECTION 分支」提供了更轻的另一极。静态分析一侧，`lint`（1979，贝尔实验室）是祖师爷；clang-tidy（2015 随 clang-tools-extra 开源）基于 Clang AST 提供可编程的检查框架；cppcheck（2007）走「不依赖编译、独立解析」的轻量路线。clang-format（2013~2014，2014 随 Clang 3.4 作为新工具发布）终结了 C++ 社区的「大括号之争」——格式交给工具。覆盖率工具从 GCC 的 gcov（1990 年代）到 LTP 项目的 lcov（约 2002，Perl 封装出 HTML），再到 LLVM 的 source-based coverage（llvm-cov，2016 前后，按源码区域而非行计数）。CI 从 Jenkins（2011，前身 Hudson 2005）演进到 GitHub Actions（2019）的「流水线即代码」。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| lint（贝尔实验室） | 1979 | 静态分析概念诞生：编译器之外再查一遍 |
| SUnit / JUnit | 1994 / 1997 | xUnit 范式确立：TestCase + 断言 + 自动汇总 |
| CppUnit | 2000 | xUnit 移植到 C++（手工注册用例） |
| cppcheck | 2007 | 独立解析、无需编译数据库的轻量静态分析 |
| GoogleTest | 2008 | 自动注册、EXPECT/ASSERT 分离——C++ 测试事实标准 |
| Catch（→ Catch2 v2 / v3） | 2010 / 2016 / 2022 | header-only + TEST_CASE/SECTION 另一极 |
| clang-format | 2013~2014 | 格式自动化——2014 随 Clang 3.4 作为新工具发布 |
| clang-tidy | 2015 | 基于 AST 的可编程静态检查（随 clang-tools-extra 开源） |
| llvm-cov source-based coverage | ~2016 | 按源码区域精确计数，告别 gcov 行计数的优化失真 |
| GitHub Actions | 2019 | CI 配置入仓库（pipeline as code）成为主流 |

本文示例以 **C++20** 为基线（与 ph11~ph15 一致：roadmap 主线使用 C++20），验证工具链 **Apple clang 21.0.0（`c++`）+ Homebrew clang 21.1.8（`clang++`）**，质量工具均为 **Homebrew LLVM 21.1.8**（clang-tidy / clang-format / llvm-cov / llvm-profdata，位于 `/opt/homebrew/opt/llvm/bin/`）。本阶段示例除标注「未在本环境验证」者外均已实测。质量工具的命令行接口是各工具**最稳定**的部分之一（clang-tidy 的 `--config-file`、clang-format 的 `--style`/`--dry-run` 多年未变）——本阶段讲的「怎么配、怎么进 CI」长期有效，变的只是检查规则的默认集。

## 3. 语法与参数

> 本节代码块为**教学骨架**：为聚焦当前工具点做了简化。完整可运行文件见第 6 节与 [`examples/`](./examples/)，构建/运行命令与实测输出见 examples/README.md。

### 3.1 单元测试框架：GoogleTest 与 Catch2

单元测试框架的三件核心事：**组织用例**（TEST/TEST_CASE）、**断言**（EXPECT/REQUIRE）、**汇总成败为退出码**（0 全过、非 0 有失败——这是 CI 能接住的信号）。

**GoogleTest 核心用法**（完整文件 `examples/ex01-test-gtest.cpp`，本机未安装 GoogleTest，未在本环境验证）：

```cpp
// examples/ex01-test-gtest.cpp —— GoogleTest 真实版本（节选，未在本环境验证）
#include <gtest/gtest.h>

TEST(CalculatorTest, Add) {                  // TEST(套件名, 用例名)：全局自动注册
    EXPECT_EQ(Calculator::add(1, 2), 3);     // EXPECT_*：非致命断言，失败后继续执行
    ASSERT_NE(Calculator::add(1, 1), 0);     // ASSERT_*：致命断言，失败即中止本用例
}

TEST(CalculatorTest, DivideByZeroThrows) {
    EXPECT_THROW(Calculator::divide(1, 0), std::invalid_argument);  // 异常断言
}
```

**Catch2 v3 核心用法**（完整文件 `examples/ex01-test-catch2.cpp`，未在本环境验证）：

```cpp
// examples/ex01-test-catch2.cpp —— Catch2 v3 真实版本（节选，未在本环境验证）
#include <catch2/catch_test_macros.hpp>

TEST_CASE("Calculator 加减除", "[calculator]") {   // [tag]：可按标签过滤运行
    SECTION("加法") {              // SECTION：同一用例内独立分支，各自从头执行（免写 fixture）
        REQUIRE(Calculator::add(1, 2) == 3);       // REQUIRE：失败即中止（≈ ASSERT）
        CHECK(Calculator::add(-1, 1) == 0);        // CHECK：失败后继续（≈ EXPECT）
    }
    SECTION("除法") {
        REQUIRE_THROWS_AS(Calculator::divide(1, 0), std::invalid_argument);
    }
}
```

**两个框架怎么选**：

| 维度 | GoogleTest | Catch2 v3 |
|------|-----------|-----------|
| 断言 | `EXPECT_*`（非致命）/ `ASSERT_*`（致命） | `CHECK`（非致命）/ `REQUIRE`（致命） |
| 用例组织 | TEST / TEST_F（fixture 类共享准备代码） | TEST_CASE + SECTION（分支即独立用例） |
| 主函数 | 链接 `gtest_main` | 链接 `Catch2WithMain` |
| 招牌特性 | 参数化测试（TEST_P）、死亡测试 | SECTION 组合展开、BDD 风格（GIVEN/WHEN/THEN） |
| 典型场景 | 大项目、生态最广（与 CMake/CI 集成案例最多） | 中小项目、想要更少样板 |

**安装与接入**（两种方式，均未在本环境验证）：`brew install googletest` / `brew install catch2` 后直接链接；或 CMake FetchContent（推荐，锁版本、跨平台一致）：

```cmake
# CMake 接入 GoogleTest（FetchContent，未在本环境验证——需联网拉取）
include(FetchContent)
FetchContent_Declare(googletest
    URL https://github.com/google/googletest/archive/refs/tags/v1.15.2.tar.gz)
FetchContent_MakeAvailable(googletest)
add_executable(my_tests test_main.cpp)
target_link_libraries(my_tests PRIVATE GTest::gtest_main)
```

**本机无框架时的同构演示**（已验证）：`examples/ex01-mini-test.h` 用约 60 行实现同构模式——`MINI_TEST` 宏生成静态注册器（全局对象构造函数在 main 之前登记用例，GoogleTest 同原理）、`MINI_EXPECT_*` 断言计数、`RUN_ALL_TESTS` 汇总并返回退出码。它与真框架的差距在 fixture、参数化、死亡测试等进阶能力——但「用例 + 断言 + 退出码」的骨架一模一样，练手足够（已验证输出见 examples/README.md 示例 1）。

> 本阶段只用测试框架的基本断言与用例组织，**mock 框架（GoogleMock）与集成测试的分层设计属于 [ph17 设计模式与架构能力阶段](../ph17-design-patterns-architecture/17-design-patterns-architecture.md)**，这里只需理解「单元测试覆盖稳定逻辑」（roadmap 必会概念）。

### 3.2 静态分析：clang-tidy 与 cppcheck

静态分析在**不运行程序**的前提下检查源码。clang-tidy 是 Clang 生态的主力：基于编译同一份 AST（见 4.2），规则以「检查（check）」为单位按族组织。

**clang-tidy 用法与实测**（完整文件 `examples/ex02-tidy-demo.cpp` + `examples/ex02.clang-tidy`，已验证）：

```bash
# 1. 坏版本（默认，无宏）编译 + 运行：编译器自带 1 条 -Wrange-loop-construct（第一道静态分析），
#    警告不是错误——程序照常跑出结果（已验证：双编译器 -Wall -Wextra 各 1 条警告；该警告属 -Wall，无需额外开关）
c++ -std=c++20 -Wall -Wextra ex02-tidy-demo.cpp -o /tmp/ph16cpp-ex02-b && /tmp/ph16cpp-ex02-b
# 2. 坏版本给 clang-tidy：5 条告警（4 类规则，已验证，clang-tidy 21.1.8）
/opt/homebrew/opt/llvm/bin/clang-tidy -quiet ex02-tidy-demo.cpp --config-file=ex02.clang-tidy -- -std=c++20
# 3. 修复版 clang-tidy：零告警（-DEX02_FIXED）
/opt/homebrew/opt/llvm/bin/clang-tidy -quiet ex02-tidy-demo.cpp --config-file=ex02.clang-tidy -- -std=c++20 -DEX02_FIXED
# 4. 修复版编译 + 运行：双编译器零警告（已验证）
c++ -std=c++20 -Wall -Wextra -DEX02_FIXED ex02-tidy-demo.cpp -o /tmp/ph16cpp-ex02-f && /tmp/ph16cpp-ex02-f
```

实测告警（坏版本）：`cppcoreguidelines-special-member-functions`（自定义析构却没配拷贝/移动，对应 C.21）、`modernize-use-override`（重写虚函数未标 override，C.128）、`modernize-use-nullptr`（用了 NULL，ES.47，2 处）、`performance-for-range-copy`（范围 for 按值拷贝 string）。**教学点**：这份坏代码编译时编译器自己报 1 条 `-Wrange-loop-construct`——编译器告警是第一道静态分析，clang-tidy 是规则更多、可配置的第二道。

**`.clang-tidy` 配置解剖**（`examples/ex02.clang-tidy`）：

```yaml
Checks: >                    # 启用的检查：可列名单，也可用族通配（bugprone-*）与排除（-modernize-use-annotations）
  cppcoreguidelines-special-member-functions,
  modernize-use-nullptr,
  modernize-use-override,
  performance-for-range-copy
WarningsAsErrors: ''         # 设 '*' = 任何告警都非零退出——CI 门禁的关键一行
HeaderFilterRegex: ''        # 空 = 只查命令行给出的源文件；否则匹配到的头文件也查
CheckOptions:                # 单个检查的参数
  cppcoreguidelines-special-member-functions.AllowSoleDefaultDtor: true   # 豁免「基类仅 =default 析构」
```

**常用检查族速查**：

| 族 | 抓什么 | 例子 |
|----|--------|------|
| `bugprone-*` | 疑似 bug（逻辑错误、危险用法） | `bugprone-unchecked-optional-access`（实测会拦下未检查的 `.value()` 直取——project 因此把 `.value()` 改用 `value_or` 规避，`make tidy` 零告警，见 project/test_stl_utils.cpp） |
| `modernize-*` | 该用现代写法的地方 | `modernize-use-nullptr`、`modernize-use-override` |
| `performance-*` | 无谓的性能损耗 | `performance-for-range-copy` |
| `readability-*` | 可读性（命名、魔数等，主观性强） | `readability-magic-numbers` |
| `cppcoreguidelines-*` | C++ Core Guidelines 落地检查 | `cppcoreguidelines-special-member-functions`（C.21） |
| `concurrency-*` | 并发错误 | `concurrency-mt-unsafe` |

**工程接入三件套**：① 大项目先生成 `compile_commands.json`（CMake `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`），clang-tidy 才能拿到与真实构建一致的编译参数；② CMake 可直接挂检查：`-DCMAKE_CXX_CLANG_TIDY="clang-tidy;-warnings-as-errors=*"`（编译即检查，告警即失败）；③ 多文件并行用 `run-clang-tidy`（Homebrew LLVM 自带）。局部豁免用 `// NOLINT(检查名)` 行尾注释——豁免要具体点名，不裸写 `// NOLINT`。

**cppcheck**（本机未安装，以下未在本环境验证）：走「独立解析、不需要编译数据库」的轻量路线，典型用法 `cppcheck --enable=warning,performance,portability --std=c++20 src/`。与 clang-tidy 的分工：clang-tidy 跟着编译走（语义精确、需要编译环境），cppcheck 独立扫（零配置、快、对未完成/跨平台代码友好）。两者检查集不同，严肃项目**两个都跑**（roadmap 学习内容要求）。

> ⚠️ 检查族不是全开就好：如 `modernize-use-trailing-return-type`（强制尾置返回）、`bugprone-exception-escape`（main 里的 vector 分配也报）在多数项目要显式豁免——豁免理由写进配置注释（范例见 `exercises/sol-02.clang-tidy`）。

### 3.3 clang-format：格式化不应靠人工争论

clang-format 把「代码长什么样」变成仓库里一份 `.clang-format` 配置文件的**机械输出**（roadmap 必会概念：格式化不应靠人工争论——评审不再讨论缩进与空格）。

**配置与实测**（完整文件 `examples/ex03.clang-format` / `ex03-messy.cpp` / `ex03-formatted.cpp`，已验证）：

```yaml
# examples/ex03.clang-format —— LLVM 基底 + 常用覆盖（已验证，clang-format 21.1.8）
BasedOnStyle: LLVM            # 基底：LLVM / Google / Chromium / Mozilla / WebKit 五选一
IndentWidth: 4                # 缩进 4 空格
ColumnLimit: 100              # 行宽上限
PointerAlignment: Left        # int* p 而非 int *p
AllowShortFunctionsOnASingleLine: None   # 短函数不并一行——diff 友好
ReflowComments: false         # 不重排注释（保护文件头的验证说明）
```

```bash
# 1. 格式化（输出到 stdout；原地修改用 -i）
/opt/homebrew/opt/llvm/bin/clang-format --style=file:ex03.clang-format ex03-messy.cpp > /tmp/fmt.cpp
# 2. 格式门禁（CI 用法：只检查、不改文件，违规即非零退出）——已验证：
#    ex03-formatted.cpp 零输出退出码 0；ex03-messy.cpp 报 36 处违规退出码 1
/opt/homebrew/opt/llvm/bin/clang-format --style=file:ex03.clang-format --dry-run --Werror ex03-formatted.cpp
```

三条使用纪律：① `.clang-format` 放仓库根目录，不带 `--style` 时 clang-format 自动拾取；② CI 用 `--dry-run --Werror` 做**门禁**（只查不改），本地用 `-i` 落盘；③ 只格式化改动行用 `git-clang-format`（Homebrew LLVM 自带），老仓库整体重排会产生一次巨型 diff。

**包含排序：`SortIncludes` 与 `IncludeBlocks`**（21.1.8 实测）——`#include` 默认按字典序重排（`SortIncludes` 开）：`<vector>` / `<algorithm>` / `<cstdio>` 会被排成 `<algorithm>` / `<cstdio>` / `<vector>`（ex03-messy 的三行乱序 include 格式化后即此结果）。块怎么分由 `IncludeBlocks` 决定：

| 取值 | 行为 | 谁默认用 |
|------|------|---------|
| `Preserve` | 保留现有空行分组，只在组内排序 | LLVM / Chromium / Mozilla / WebKit 基底 |
| `Merge` | 合并成单个块再整体排序 | 手动启用 |
| `Regroup` | 按 `IncludeCategories` 重分组（主头文件最前、再系统头）后排序 | Google 基底 |

**局部格式化：`--lines` 与 `git-clang-format`**

```bash
# 1. 只格式化 120~140 行（1-based；可写多个 --lines=起:止 段；只能处理单个文件）
clang-format --style=file --lines=120:140 -i src/foo.cpp
# 2. git-clang-format：只格式化「相对某提交的改动行」——落地大 PR / 老仓库改造防巨型 diff
git-clang-format          # 默认相对 HEAD，就地重排工作区改动行
git-clang-format main     # 相对 main：只碰本分支动过的行
git-clang-format --diff   # 只打印 diff 预览，不落盘
```

实测（21.1.8）：`--lines=6:6` 只重排第 6 行所在的函数体（同作用域的语句会连带微调），其他函数原样不动——它按逻辑语句而非物理行判定，适合「刚写的一小片代码」快速落格式；仓库级门禁仍是全量 `--dry-run --Werror`。`git-clang-format` 补上纪律③的场景：老仓库整体重排会污染 review diff 与 git blame，只让「本次改动行」走格式，diff 干净。

**与编辑器/IDE 集成**：VS Code 的 C/C++（ms-vscode）与 clangd 扩展、CLion 都原生读 `.clang-format`（format on save 即 `-i` 语义）；Vim/Emacs 用 LLVM 自带的 `clang-format.py` / `clang-format.el`。入口再多配置只有一份——不带 `--style` 时都自动找仓库根的 `.clang-format`，**终端 / CI / IDE 三处同源**，这就是「格式不靠争论」的落地形态。

**五基底取舍（`BasedOnStyle`）与常用覆盖项**（表值为 clang-format 21.1.8 `--dump-config` 实测；ex03 = LLVM 基底 + 4 条覆盖，正是「取基底再微调」的样板）：

| 基底 | 缩进/行宽 | 指针对齐 | 花括号 | 气质/适用 |
|------|----------|----------|--------|-----------|
| LLVM | 2 / 80 | `Right`（int *p） | Attach 同行 | 最中立，LLVM 自家风格；无历史包袱的默认起步 |
| Google | 2 / 80 | `Left`（int* p） | Attach | Google C++ 指南落地；IncludeBlocks 直接 Regroup |
| Chromium | 2 / 80 | Left | Attach | Google 近亲：短函数 Inline、换行更克制 |
| Mozilla | 2 / 80 | Left | Mozilla（函数体另起） | Mozilla 项目风格 |
| WebKit | 4 / 0（不限宽） | Left | WebKit（全部另起） | WebKit 风格：4 空格 + 花括号全换行 |

| 常用覆盖项 | 默认 | 控制什么 | ex03 取值 |
|------------|------|----------|-----------|
| `IndentWidth` / `ColumnLimit` | 2 / 80 | 缩进空格数 / 行宽上限 | 4 / 100 |
| `PointerAlignment` | 依基底（LLVM 为 Right） | 星号贴类型还是贴变量 | Left |
| `BreakBeforeBraces` | Attach | 花括号挂行尾还是另起一行 | （默认） |
| `AlignConsecutiveAssignments` | 关 | 相邻赋值的 `=` 是否竖排对齐 | （默认关） |
| `AllowShortFunctionsOnASingleLine` | All | 短函数可否并成一行 | None（diff 友好） |
| `SortIncludes` / `IncludeBlocks` | 开 / Preserve | 见上「包含排序」 | （默认） |
| `ReflowComments` | Always | 长注释段落自动折行 | false（保护验证说明） |

> `AlignConsecutiveAssignments` 等对齐类选项在新版 clang-format 是对象型：写作 `AlignConsecutiveAssignments: {Enabled: true}`（旧布尔写法 21.1.8 实测仍接受）。

**两个反例区**（21.1.8 实测）：① **注释会被重排**——默认 `ReflowComments: Always` 把超长 `//` 注释按 ColumnLimit 折行：文件头里的一行编译命令会被拆成三行、没法再整行复制粘贴，所以 ex03 显式关掉它；② **宏会被重排**——`#define` 多行续行（`\`）的缩进与反斜杠对齐会被重排，普通宏无妨，`__VA_ARGS__` / `##` 拼接的复杂宏建议外包 `// clang-format off` … `// clang-format on` 原样保留（实测 off/on 区间的乱格式原样不动）。反向提醒：clang-format 只动排版不动语义，`-i` 批量落盘后跑一次构建是底线。

### 3.4 Sanitizer 工程化：同一份源码 × 四种构建

ph15 已实测「每种 UB 该用哪个工具抓」：vector/std::array 越界与 UAF/双删靠 **ASan**，C 数组越界/未对齐/空指针靠 **UBSan**，数据竞争靠 **TSan**（TSan 适合发现数据竞争，roadmap 必会概念）。本阶段把它工程化成**构建矩阵**（完整示例 `examples/ex04-sanitizer-matrix/`，已验证）：

```makefile
# examples/ex04-sanitizer-matrix/Makefile —— 四种构建变体（节选，已验证）
$(BUILD)/asan: $(SRC) | $(BUILD)
	$(CXX) $(CXXFLAGS) -fsanitize=address $(SRC) -o $@
$(BUILD)/asan-ubsan: $(SRC) | $(BUILD)
	$(CXX) $(CXXFLAGS) -fsanitize=address,undefined -fno-sanitize-recover=all $(SRC) -o $@
$(BUILD)/tsan: $(SRC) | $(BUILD)
	$(CXX) $(CXXFLAGS) -fsanitize=thread $(SRC) -o $@
check: matrix          # 自检：四种构建全部运行、零报告（退出码 0）才算过
```

工程化四条规则：

1. **ASan 与 TSan 不能同进程共存**（ph15 3.5：都拦截同一批运行时函数）——必须独立二进制、独立 CI 步骤；
2. **Sanitizer 构建的意义是复跑既有测试套件**：代码没 bug 时报告就该是零——零报告是验收标准而非「没起作用」（练习 3）；
3. **优化级别用 `-O1`**：比 `-O0` 更接近发布代码形状又保留调试信息；ph15 实测越界类报告在 `-O0`/`-O1`/`-O2` 三档均触发，「必须 `-O0`」的旧说法不准确（演示用 `-O0` 只为行号稳定）；
4. **平台差异要实测、写进构建脚本**——本机（macOS arm64）实测：

| Sanitizer | Apple clang 21.0.0 | Homebrew clang 21.1.8 |
|-----------|--------------------|-----------------------|
| ASan | ✅ 可用 | ❌ **运行时初始化即挂起**（连 hello world 都卡住，实测） |
| UBSan | ✅ 可用 | ✅ 可用 |
| TSan | ✅ 可用 | ❌ 崩溃（ph15 已记录） |
| LSan | ❌ 编译报错（`unsupported option '-fsanitize=leak'`） | ❌ 能编译但退出时挂起 |

结论：**本机 Sanitizer 构建一律用 Apple clang**；LSan 在 macOS 上整体不可用（泄漏检测用 `leaks` 命令或 Xcode Instruments），LSan 是 Linux CI 的福利——这正是「Sanitizer 全家桶放 Linux CI 跑」的原因（见 3.6 与 ex06）。

### 3.5 覆盖率：gcov/lcov 与 llvm-cov

覆盖率回答「测试碰到了哪些代码」。两条工具路线：

| 路线 | 工具链 | 特点 |
|------|--------|------|
| gcov 路线 | 编译 `--coverage`（旧名 `-fprofile-arcs -ftest-coverage`）→ 运行产 `.gcda` → `gcov` 出行覆盖；`lcov`+`genhtml` 聚合出 HTML | GCC 传统路线；优化后行计数会失真 |
| llvm-cov 路线（source-based） | 编译 `-fprofile-instr-generate -fcoverage-mapping` → 运行产 `.profraw` → `llvm-profdata merge` + `llvm-cov report/show` | 按**源码区域**精确计数，不受行布局影响；LLVM 推荐 |

**llvm-cov 三步流实测**（完整示例 `examples/ex05-coverage/`，已验证）：

```bash
# 1. 插桩编译 → 2. 运行收集 → 3. 出报告（Makefile 里一条 make report 串起来）
clang++ -std=c++20 -O0 -g -fprofile-instr-generate -fcoverage-mapping test_main.cpp -o /tmp/test_cov
LLVM_PROFILE_FILE=/tmp/cov.profraw /tmp/test_cov
llvm-profdata merge -sparse /tmp/cov.profraw -o /tmp/cov.profdata
llvm-cov report /tmp/test_cov -instr-profile=/tmp/cov.profdata     # 汇总表
llvm-cov show /tmp/test_cov -instr-profile=/tmp/cov.profdata       # 逐行计数
```

实测报告（llvm-cov 21.1.8 的 `report` 默认同时出行/区域/分支三列，数字见下）：`grade.h` 行/区域覆盖 **100%**、分支 90%，`test_main.cpp` 行 79.31% / 区域 73.33% / 分支 50%——行与区域缺口全在「失败打印」分支（只有测试失败才执行），TOTAL 行 86.36% / 区域 86.67% / 分支 72.22%。**覆盖率的价值是发现没测到的路，不是追 100% 的数字**：失败处理分支盖不到是健康的，反过来为凑数字写「只调用不断言」的测试是自欺欺人。工具链注意：profraw 格式版本与 llvm-cov 版本要匹配——同用 Homebrew LLVM 21.1.8 最稳（Apple clang 21.0.0 生成的 profraw 实测也能被读，但别赌跨大版本）。

gcov 路线本机实测（Apple clang）：`c++ --coverage` **分两步编译**（先 `-c` 再链接——一把梭生成的 `.gcno` 文件名带输出前缀、gcov 找不到），`gcov -n test_main.cpp` 报行覆盖 78.57%。`lcov`/`genhtml` 本机未安装（未在本环境验证），Linux CI 用法：`lcov --capture --directory build --output-file cov.info && genhtml cov.info -o html`（见 ex06）。

**行 / 区域 / 分支三类覆盖率的语义差别**（上面的实测数字就是 ex05 三列同出）：

| 覆盖类型 | 计数器挂在哪 | 回答的问题 | 粒度 / 成本 |
|----------|--------------|------------|-------------|
| 行覆盖 Line | 语句所在行 | 「这行代码执行过没有」 | 最粗 / 最便宜 |
| 区域覆盖 Region | 源码区域（条件、合流切出的连续区间） | 「这段区间走没走过」 | 中 |
| 分支覆盖 Branch | 每个条件的两侧（真/假、`&&`/`\|\|` 的各操作数） | 「每条路都验证过吗」 | 最细 / 最贵 |

gcov 路线默认只出行覆盖，`gcov -b` 才补分支；lcov 聚合出的 HTML 默认也不含分支（genhtml 需 `--branch-coverage`）——想看分支，gcov 系要显式开，本机 llvm-cov 21.1.8 的 `report` 默认直接给（见上实测）。

**为什么「行盖到了、分支没盖到」**：行覆盖只问「执行过没有」——一行代码里藏着多个条件时，行 100% 不代表每条路都验证过。ex05 的 grade.h 就是活例（实测 `llvm-cov show --show-branches=count` 的逐条件输出）：

```text
grade.h:12  if (score < 0 || score > 100) {      ← 9 次调用都执行了这行（行/区域 100%）
    Branch (12:9)  score < 0   [True: 0, False: 9]   ← 真半边一次都没发生过
    Branch (12:22) score > 100 [True: 1, False: 8]   ← 非法输入全靠这一侧进入
所有测试分数都 ≥ 0 → score<0 永不成立：行覆盖看不出，分支覆盖现原形（grade.h 分支 90%）
```

读分支缺口先问**业务含义**再决定动作：`score<0` 半边是「没测到的输入类」→ 补一个负分用例就满；失败打印分支是「故意不触发」→ 接受（见上）。三类覆盖从粗到细，多花的成本都花在「更早发现漏测的路」上。

### 3.6 CI 集成：把闭环钉死在每次提交

工具都齐了之后，最后一步是**自动化**——静态分析要纳入 CI（roadmap 必会概念），本地「记得跑」总会变成「忘了跑」。CI 流水线的设计原则是**快刀在前**：最便宜、最快的检查先跑，失败早反馈（完整模板 `examples/ex06-ci/github-actions.yml`，本机无 docker，未在本环境验证）：

```text
PR/push
  ├── job 1 格式门禁     clang-format --dry-run --Werror     （秒级，最先挂掉）
  ├── job 2 静态分析     clang-tidy（WarningsAsErrors='*'）  （分钟级）
  ├── job 3 测试矩阵     os × 编译器 × Debug/Release → ctest （主力）
  └── job 4 Sanitizer+覆盖率  ASan+UBSan / TSan 复跑测试 → gcov+lcov 出 HTML（最慢，放最后）
```

四个 job 的退出码语义完全一致——**任何一道闸门非零退出，PR 即红**。Makefile 的 `make check`（本阶段 project/）与 CI 的 job 是同一份逻辑的两种载体：本地一键全跑，CI 拆开并行。GitHub Actions 之外，GitLab CI（`.gitlab-ci.yml`）、Jenkins（`Jenkinsfile`）思路相同，都是「流水线即代码」。

**GitHub Actions 关键语法走读**（对照 `ex06-ci/github-actions.yml`；以下为云端行为，均未在本环境验证）：

```yaml
on:                          # 触发（ex06 只用了前两个）
  push: { branches: [main] } # push 限分支
  pull_request:              # 任何 PR（含 fork PR）
  schedule:                  # 定时 cron：只对默认分支生效，最小粒度 5 分钟
    - cron: '0 2 * * *'      # 每天 UTC 02:00 夜间全量重跑（最慢的 Sanitizer+覆盖率放夜里）
  workflow_dispatch:         # 手动触发按钮

jobs:
  test-matrix:
    strategy:
      matrix:                # os × cxx × build_type = 2×2×2 = 8 个并行组合，各自独立红/绿
        os: [ubuntu-latest, macos-latest]
        cxx: [g++, clang++]
        build_type: [Debug, Release]
    runs-on: ${{ matrix.os }}        # ${{ matrix.* }} 取当前组合的值
    steps:
      - run: cmake -B build -DCMAKE_BUILD_TYPE=${{ matrix.build_type }} \
             -DCMAKE_CXX_COMPILER=${{ matrix.cxx }}
      - run: cmake --build build -j && ctest --test-dir build --output-on-failure

  gate:                      # needs：聚合门禁——四道闸门全绿它才绿（ex06 未写，落地时加上）
    needs: [format, tidy, test-matrix, sanitizer-coverage]
    runs-on: ubuntu-latest
    steps:
      - run: echo "四道闸门全过"
```

要点：① job 默认**并行且无序**（ex06 四个 job 同时起跑）——「快刀在前」靠廉价 job 秒级失败的早反馈实现，不是执行顺序；要严格「格式过了才跑矩阵」就加 `needs:`，代价是整体反馈变慢；② matrix 一个组合失败只红它自己，不杀兄弟组合；③ 产物跨 job 传递用 `actions/upload-artifact`（ex06 末尾把 coverage-html 传上去，下载方用 `actions/download-artifact`），artifact 默认保留 90 天（`retention-days` 可调）。

**`ctest` 与 Makefile `make check`：两种载体的切换点**

| 载体 | 用例怎么登记 | 调用方式 | 谁在用 |
|------|-------------|----------|--------|
| Makefile `make check` | target 依赖把「编译 + 运行」串成一条链 | `make check`（退出码即结果） | 本阶段 examples/project（无 CMake 的轻量示例） |
| CTest | CMake `enable_testing()` + `add_test(NAME … COMMAND …)`（或 gtest_discover_tests 自动发现） | `ctest --test-dir build --output-on-failure` | ex06 模板（CMake 工程） |

切换点就是**工程有没有 CMake**：有 → 构建与测试都交给 CMake/CTest（`-j` 并行、失败摘要、免进目录）；没有 → Makefile `check` target 足够。两条路共享同一语义：**退出码即信号**——project/ 的 `make check` 与 CI 的 `ctest` 是同一道闸门的两种外壳。

**覆盖率阈值 fail 的落地写法**（加在覆盖率 job 末尾；未在本环境验证）：

```bash
# 1. gcov/lcov 路线：genhtml 自带阈值开关（lcov 1.14+），低于即非零退出
genhtml coverage.info --output-directory coverage-html \
  --branch-coverage --fail-under-lines 90 --fail-under-branches 80
# 2. llvm-cov 路线简易门禁：解析 TOTAL 行的区域覆盖列（21.1.8 在第 4 列，列序随版本会变，先 report 确认）
llvm-cov report build/test_cov -instr-profile=cov.profdata |
  awk '$1 == "TOTAL" { if ($4 + 0 < 90) { print "区域覆盖不足:", $4; exit 1 } }'
```

**ccache 缓存与 nightly cron**（模板片段，未在本环境验证）：

```yaml
      # matrix 8 组合 × 夜间 cron = 大量重复编译；ccache 跨 job/跨提交复用对象缓存
      - uses: actions/cache@v4
        with:
          path: ~/.cache/ccache            # Linux；macOS 是 ~/Library/Caches/ccache
          key: ccache-${{ runner.os }}-${{ matrix.cxx }}-${{ hashFiles('**/CMakeLists.txt') }}
      - run: |
          echo "CCACHE_DIR=$HOME/.cache/ccache" >> "$GITHUB_ENV"
          cmake -B build -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
```

**GitLab CI / Jenkins 对照**（GitLab 为例，与 ex06 逐行对照；语法以 GitLab 文档为准，未在本环境验证）：

| GitHub Actions（ex06） | GitLab CI（`.gitlab-ci.yml`） |
|---|---|
| `jobs:`（并行无序）+ `needs:` | `stages:`（有序，同 stage 内并行）+ `needs:`（13.4+ 可跳阶段序） |
| `on: push / pull_request` | `rules: if: $CI_PIPELINE_SOURCE == "push" / "merge_request_event"` |
| `on: schedule` | 项目 CI/CD → Schedules 定时触发 |
| `strategy.matrix` | `parallel: matrix`（13.3+） |
| `runs-on: ubuntu-latest` | `image: ubuntu:24.04`（跑在 runner 容器里） |
| `actions/upload-artifact` | `artifacts: paths:`（自动传给后续 stage，`expire_in` 控保留） |
| `actions/cache` | `cache: key: … paths: …` |

```yaml
# .gitlab-ci.yml 骨架（与上表对照；未在本环境验证）
stages: [format, tidy, test, sanitize]
test:
  stage: test
  image: ubuntu:24.04
  parallel: matrix:            # 对应 GitHub 的 strategy.matrix
    - CXX: [g++, clang++]
  script:
    - cmake -B build -DCMAKE_CXX_COMPILER=$CXX
    - cmake --build build -j && ctest --test-dir build --output-on-failure
```

Jenkins 是同一思路的老前辈（declarative `Jenkinsfile`：`stage` 顺序 + `matrix` 轴 + `archiveArtifacts` 收产物）；GitHub/GitLab 把「配置入仓库 + runner 托管」做成了开箱体验（演进见第 2 节：Jenkins 2011 → GitHub Actions 2019）。

## 4. 底层原理

### 4.1 测试金字塔：为什么单元测试是底座

测试按「范围 vs 成本」分层——越往上越接近真实、越慢越脆：

```text
        ▲ 少量          ┌────────────┐
        │               │  E2E 测试  │                                     ← 全链路，分钟~小时级，脆（环境依赖）
        │             ┌─┴────────────┴─┐
   数量 │             │    集成测试    │                                     ← 模块协作（roadmap 必会概念），秒~分钟级
        │           ┌─┴────────────────┴─┐
        │           │      单元测试      │                                     ← 稳定逻辑（roadmap 必会概念），毫秒级
        ▼ 大量      └────────────────────┘
                 越往下：越快、越稳、定位越准
```

单元测试覆盖**稳定逻辑**（纯函数、小类——ph16 ex01/project 的被测对象都是这一层）：输入输出确定、无环境依赖、失败即定位到函数。集成测试覆盖**模块协作**（接口契约、数据格式、生命周期配合）。倒金字塔（大量 E2E 兜底）是反模式：慢、脆、失败定位难。C++ 侧注意：可测试性从接口设计开始——纯函数最好测（F.8），依赖具体类不如依赖抽象接口（ph17 依赖注入思想的动机之一）。

### 4.2 静态分析如何工作：AST 与 CFG

clang-tidy 的检查器工作在编译器前端的数据结构上（所以它需要与真实构建一致的编译参数）：

```text
源码 ──词法/语法──▶ AST（抽象语法树：结构匹配）
                  │     例：modernize-use-override = 「虚函数 + 覆盖基类虚函数 + 未标 override」
                  │     → AST 模式匹配（AST Matcher）即可判定
                  └──语义──▶ CFG（控制流图：路径敏感）
                        例：bugprone-unchecked-optional-access = 沿 CFG 路径追踪
                        optional 的 has_value 状态（实测会拦下未检查的 .value() 直取——
                        project 因此改用 value_or 规避，见 test_stl_utils.cpp）
```

- **AST 层检查**：把「坏模式」表达为树模式（Clang 的 AST Matcher DSL），遍历 AST 命中即报——大多数 `modernize-*`、`readability-*` 在这一层，快而准；
- **CFG 层检查**：先把函数体展开成控制流图（基本块 + 分支边），再做路径敏感的数据流分析（沿每条可能路径传播「已初始化/已检查/已释放」等状态）——`bugprone-*` 的深水区在这里，能抓「某条路径上没检查就解引用」，代价是慢、有误报；
- **clang 静态分析器**（`scan-build`，clang-tidy 的 `clang-analyzer-*` 检查）是 CFG 路线的重度版：符号执行，按路径探索「除以零」「泄漏」等。cppcheck 则不同源：自写解析器 + token 流规则，不看编译参数，换来零配置。

**为什么配置里要 `HeaderFilterRegex`**：clang-tidy 分析时会把 `#include` 的头文件一并展开进 AST，但诊断默认只显示**主文件**里的（`HeaderFilterRegex: ''`——`ex02` 的 5 条用户告警全在主文件，本机实测）；把过滤器放宽成匹配自研头的正则后，头文件里的告警才会一起显示（用 /tmp 下的临时探针文件实测：头文件 `myhdr.h` 里的 `NULL` 用法过滤前不报、`HeaderFilterRegex: 'myhdr\.h'` 后报出）。libc++ 等系统头 clang-tidy 默认不产生诊断（实测 `ex02` 展开的 `<string>`/`<vector>` 零头文件告警）——过滤器的意义是把检查范围圈定在自有代码（如 project 的 `'stl_utils\.h'`），避免工程里每个头都开查时诊断量失控、把主文件的告警淹没。

### 4.3 Sanitizer 与覆盖率的插桩原理

两者都是**编译期插桩**：编译器在生成代码时嵌入探针，运行时探针汇报。

- **ASan**：堆/栈对象周围加「红区」，影子内存（shadow memory，每 8 字节应用内存对应 1 字节影子）标记每个字节是否可寻址；每次访存先查影子——越界/UAF 一碰红区即报（ph15 的 `heap-buffer-overflow`/`heap-use-after-free` 由此来）；
- **UBSan**：在 UB 可疑点（越界下标、未对齐访问、溢出）插入条件检查，命中即报（`-fno-sanitize-recover=all` 让它命中即中止而非继续）；
- **TSan**：为每次内存访问记录「哪个线程、有无同步边」，在线检测 happens-before 缺失（ph15 4.4）；
- **覆盖率**：gcov 路线在基本块边插计数器（优化后边与源码行的对应会漂移，所以失真）；llvm-cov 路线同时记录**源码区域映射**（`-fcoverage-mapping`）——计数器直接挂在「第 N 行第 M 列起止的区域」上，报告逐区域精确。

**ASan 的 shadow memory 布局**：ASan 在编译期为每次堆/栈分配在对象**两侧**多开一圈红区（不可寻址守卫），运行时维护一张 1:8 的影子表回答「这块内存能不能碰」——`malloc(8)` 在 ASan 下的真实形状（p 是返回给用户的首地址）：

```text
堆内存：   ┌──────────┬──────────┬──────────┐
          │  左红区    │ 8B 用户区  │  右红区    │   ← 对象两侧各垫一段不可寻址红区（大小运行时配）
          └──────────┴──────────┴──────────┘
影子内存：   0xfa        0x00        0xfb        ← 每 8B 应用内存 ↔ 1B 影子（影子地址 ≈ 应用地址 >> 3）
访问 p[2]（越界 4B 写）→ 先查影子命中 0xfb → 立即报 heap-buffer-overflow（ph15 3.1 的实测）
free(p) 后整块标 0xfd（freed，隔离期）→ 再访问报 heap-use-after-free（ph15 3.3 的实测）
```

影子字节值是运行时固定的魔法字节：0xfa 堆左红区 / 0xfb 堆右红区 / 0xfd 已释放 / 0xf1、0xf3 栈左、右红区 / 0xf9 全局红区；0x00~0x07 表示 8B 组内部分可寻址的碎区（对象尾巴不满 8B 的残段）。读报告认**错误类型名**（`heap-buffer-overflow` vs `stack-buffer-overflow`）即可，不必背值——1:8 的缩放正是 ASan「约 1/8 内存开销」的来源。对照：TSan 的 shadow 记录「每个地址最近由哪个线程、带没带同步边访问」（ph15 4.4），UBSan 无 shadow——条件检查就地插入。

**gcov 边计数 vs llvm-cov 区域计数：为什么优化后 gcov 失真**：

```text
同一条循环源码，两种插桩的「计数器挂点」不同：
gcov：     源码 ──▶ 基本块**边**（控制流转移）上插计数器
           -O0：边与源码行近似一一对应 → 行覆盖可读
           -O2：循环展开/合并/内联 → 边与行的映射漂移，「某行没执行」可能只是「边被优化没了」
llvm-cov： 源码 ──▶ -fcoverage-mapping 把计数器直接绑到「源码区域（行:列起止）」上
           优化只改 IR，区域↔源码位置的绑定由编译期元数据固定 → 报告不随优化级别漂移
```

所以 llvm-cov 的区域覆盖在 `-O1`/`-O2` 下仍能给出稳定的缺口定位；ex05 用 `-O0 -g` 只为逐行视图最好读（对应 3.5 的两条路线对照）。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 日常开发循环 | 写测试（3.1）→ 跑测试 → clang-tidy 随编译报规范问题（3.2）→ 提交前 clang-format -i（3.3） |
| 代码评审 | 格式不再进评审（3.3 门禁）；评审聚焦设计与语义；clang-tidy 报告作为客观依据 |
| 合并门禁（CI） | 四道闸门（3.6）；静态分析必须入 CI（roadmap 必会概念）；Sanitizer 复跑测试套件（3.4） |
| 排查「测试全过但线上崩」 | 补 ASan/UBSan/TSan 复跑（3.4）——单测过 ≠ 无 UB（承接 ph15） |
| 评估测试充分性 | llvm-cov 找没测到的分支（3.5），补边界用例 |
| 遗留代码整治 | `run-clang-tidy -fix` 批量现代化（modernize-*）；`git-clang-format` 只格式化改动行 |

**什么时候不用它**：

- mock 与集成测试的分层设计属 [ph17 设计模式与架构能力阶段](../ph17-design-patterns-architecture/17-design-patterns-architecture.md)——本阶段只要求「单元测试覆盖稳定逻辑」；
- 性能回归门禁（benchmark in CI）属 ph18 性能优化与 Profiling 阶段；
- 覆盖率不是 KPI：强追 100% 会逼出「只调用不断言」的假测试——覆盖率用于**找缺口**（3.5）。

**与其他语言的对比**（为 analysis/ 与 Tenet 合成积累素材）：

| 维度 | C++ | Rust | Go | Python |
|------|-----|------|----|--------|
| 测试 | 第三方框架（GoogleTest/Catch2） | 内建 `cargo test`（#[test]） | 内建 `go test` | pytest（事实标准） |
| 静态分析 | clang-tidy / cppcheck（生态拼合） | 内建 clippy | 内建 `go vet` | ruff / mypy |
| 格式化 | clang-format | 内建 rustfmt | 内建 gofmt（强制） | ruff format / black |
| 内存错误检测 | Sanitizer 插桩复跑 | 编译期排除（safe 子集） | race detector / GC | 运行时托管 |
| 覆盖率 | gcov / llvm-cov | cargo-llvm-cov | 内建 `-cover` | coverage.py / pytest-cov |

一句话：**C++ 的质量工具链是「生态拼合」**——每块都有成熟工具，但拼起来是你的责任；Rust/Go 把同一条链内建进工具链（约定优于配置）。这正是本阶段「闭环」二字的意义：C++ 开发者要自己把环闭上。

## 6. 代码示例

> 说明：ex01~ex05 均在本机（macOS arm64，Apple clang 21.0.0 + Homebrew clang 21.1.8，LLVM 工具 21.1.8）实际构建运行验证（已验证），默认构建 `-std=c++20 -Wall -Wextra` 双编译器零警告；ex06（CI）本机无 docker，未在本环境验证。完整可运行文件在 [`examples/`](./examples/)，此处展示关键片段。

### 示例 1：单元测试（examples/ex01-*）

对应 roadmap 学习内容「GoogleTest、Catch2」与练习「给核心类写测试」。

```cpp
// examples/ex01-test-mini.cpp —— 最小断言框架版（节选，与原文件逐字一致，已验证）
MINI_TEST(CalculatorTest, Add) {                 // 对应 GoogleTest: TEST(CalculatorTest, Add)
    MINI_EXPECT_EQ(Calculator::add(1, 2), 3);    // 对应 EXPECT_EQ
    MINI_EXPECT_EQ(Calculator::add(-1, 1), 0);   // 边界：正负相消
}
```

```bash
# 1. 编译（双编译器零警告）：
c++ -std=c++20 -Wall -Wextra ex01-test-mini.cpp -o /tmp/ph16cpp-ex01
# 2. 运行：3 用例全过，退出码 0（CI 信号）
/tmp/ph16cpp-ex01
```

GoogleTest / Catch2 真实版本分别见 `ex01-test-gtest.cpp` / `ex01-test-catch2.cpp`（本机未安装两框架，未在本环境验证，文件头含安装与构建命令）。

### 示例 2：clang-tidy 配置与输出（examples/ex02-*）

对应 roadmap 学习内容「clang-tidy、cppcheck」与练习「配置 clang-tidy」。

```cpp
// examples/ex02-tidy-demo.cpp —— 坏版本片段（节选）：触发 modernize-use-override
class Circle : public Shape {
public:
    explicit Circle(double r) : radius_(r) {}
    double area() const { return 3.14159265358979 * radius_ * radius_; }  // 应标 override
```

实测（clang-tidy 21.1.8）：坏版本 5 条告警（4 类规则：special-member-functions / use-override / use-nullptr ×2 / for-range-copy）；修复版（`-DEX02_FIXED`）零告警——关键配置 `AllowSoleDefaultDtor: true` 豁免「多态基类仅 =default 析构」的标准写法（C.35）。运行命令见 3.2。

### 示例 3：clang-format 与格式门禁（examples/ex03-*）

对应 roadmap 学习内容「clang-format」与必会概念「格式化不应靠人工争论」。

实测（clang-format 21.1.8）：`ex03-messy.cpp`（刻意写乱）`--dry-run --Werror` 报 **36 处** `-Wclang-format-violations`、退出码 1；格式化产物 `ex03-formatted.cpp` 零输出、退出码 0——这两个退出码就是 CI 格式门禁的全部逻辑。配置与命令见 3.3。

### 示例 4：Sanitizer 工程化矩阵（examples/ex04-sanitizer-matrix/）

对应 roadmap 学习内容「ASan、TSan、UBSan」与练习「开启 ASan/TSan 构建」，承接 ph15 的工具结论。

实测（Apple clang 21.0.0）：`make check` 四种构建（normal / ASan / ASan+UBSan / TSan）均输出 `parallel_sum=60`、退出码 0、零报告；`make demo-oob`（故意越界版）报 `ERROR: AddressSanitizer: heap-buffer-overflow` + `WRITE of size 4`、退出码 134。Makefile 全文含本机平台差异实测（Homebrew clang ASan 挂起 / LSan 不可用，见 3.4 表）。

### 示例 5：覆盖率报告（examples/ex05-coverage/）

对应 roadmap 学习内容「gcov/lcov」与练习「生成覆盖率报告」。

实测（clang++ 21.1.8 + llvm-cov 21.1.8）：`make report` 输出 `grade.h` 行/区域 100%、`test_main.cpp` 区域 73.33%（缺口是失败打印分支）、TOTAL 86.67%。命令见 3.5。gcov 路线对照（`c++ --coverage` 两步编译 + `gcov -n`）本机实测行覆盖 78.57%；lcov/genhtml 未在本环境验证（本机未安装）。

### 示例 6：CI 配置（examples/ex06-ci/github-actions.yml）

对应 roadmap 学习内容「CI」与推荐项目「C++ CI 模板」。未在本环境验证（本机无 docker）——四个 job（格式门禁 → 静态分析 → 测试矩阵 → Sanitizer+覆盖率）的结构与设计原则见 3.6，文件头注释含落地方式。

## 7. 总结

### 关键要点

1. **质量闭环 = 测试 + 静态分析 + 格式化 + Sanitizer 复跑 + 覆盖率，钉进 CI**——每一件单独都常见，闭成环才是本阶段的目标（roadmap 目标）
2. **测试框架三件事**：组织用例（TEST/TEST_CASE）、断言（EXPECT 非致命 / ASSERT 致命；Catch2 对应 CHECK/REQUIRE）、退出码即 CI 信号（3.1、ex01）
3. **单元测试覆盖稳定逻辑，集成测试覆盖模块协作**（测试金字塔，4.1）——可测试性从接口设计开始
4. **clang-tidy 配置三要素**：`Checks`（族通配 + 显式豁免）、`WarningsAsErrors: '*'`（告警即失败的 CI 门禁）、`HeaderFilterRegex`（挡住系统头告警洪水）；编译器告警是第一道静态分析，clang-tidy 是第二道（3.2、ex02）
5. **cppcheck 与 clang-tidy 互补**：独立解析零配置 vs 随编译语义精确，严肃项目两个都跑（3.2，未在本环境验证）
6. **格式化交给工具**：`.clang-format` 入仓库，CI 用 `--dry-run --Werror` 门禁，评审不再争论格式（3.3、ex03）
7. **Sanitizer 工程化四规则**：ASan⊥TSan 独立二进制；复跑既有测试套件零报告才算过；`-O1`（「必须 -O0」是旧说法，ph15 实测三档均触发）；平台差异实测入脚本——本机 Homebrew clang ASan 挂起、LSan 在 macOS 不可用（3.4、ex04）
8. **覆盖率用于找缺口，不是追 100%**：llvm-cov source-based 三步流；失败处理分支盖不到是健康的（3.5、ex05）
9. **CI 快刀在前**：格式（秒级）→ 静态分析 → 测试矩阵 → Sanitizer+覆盖率（最慢）；任何一道非零退出 PR 即红（3.6、ex06）
10. **C++ 质量工具链是生态拼合**——Rust/Go 内建的这条链，C++ 要自己闭上（5）

### 阶段验收清单

- [ ] 能**一键运行测试和静态检查**（roadmap 验收）：本阶段 project/ 的 `make check` 即样板——测试 → ASan+UBSan → TSan → clang-tidy → 格式门禁 → 覆盖率，退出码 0
- [ ] 能**解释测试失败原因**（roadmap 验收）：断言失败读 EXPECT 输出；Sanitizer 报告读错误类型与 READ/WRITE 大小；clang-tidy 告警按检查名查规则
- [ ] 能**让代码格式自动统一**（roadmap 验收）：写 `.clang-format`、本地 `-i`、CI `--dry-run --Werror`
- [ ] 能**配出 Sanitizer 构建矩阵**并说明 ASan⊥TSan 的原因与本机平台差异（3.4、练习 3）
- [ ] 能**生成并读懂覆盖率报告**：行/区域/分支覆盖的含义，缺口定位（3.5、练习 4）
- [ ] 能**写出四道闸门的 CI 配置**（格式 → 静态分析 → 测试矩阵 → Sanitizer+覆盖率，3.6）

### 跨语言对比

见第 5 节末的对比表——C++「生态拼合」vs Rust/Go「工具链内建」是本阶段最值得带走的一帧（为 analysis/ 与 Tenet 合成积累素材：Tenet 若定位系统语言，`cargo test`/`clippy`/`rustfmt` 三合一的「质量工具内建」是明确的对标方向）。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 5 题：给核心类写测试（★★）、配置 clang-tidy（★★）、开启 ASan/TSan 构建（★★）、生成覆盖率报告（★★★）、clang-format 格式化与格式门禁（★）——练习 1~4 与 roadmap ph16「练习」小节一一对应，练习 5 覆盖「学习内容」中的 clang-format。完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**带测试的 STL 工具库**——header-only 工具库（`ring_buffer` + `split`/`join`）+ 完整质量闭环（`make check` = 10 用例测试 × 三种构建 + clang-tidy 门禁 + 格式门禁 + llvm-cov 覆盖率，其中 `stl_utils.h` 行/区域覆盖 100%）。roadmap 的另一个推荐项目「C++ CI 模板」由 examples/ex06 的 GitHub Actions 配置覆盖。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`make clean && make check` 退出码 0、双编译器零警告、`make clean` 无残留）

### 下一阶段

[设计模式与架构能力阶段](../ph17-design-patterns-architecture/17-design-patterns-architecture.md) — 本阶段把「代码写对」闭环了（测试 + 静态分析 + Sanitizer + CI），ph17 回答「代码怎么组织」：工厂/策略/观察者/适配器、依赖注入、分层架构与模块边界——架构设计要服务测试和演进（本阶段「可测试性从接口开始」的伏笔在那里展开，mock = 注入接口的另一实现）。本阶段 project/ 的 `make check` 仍可当作日常开发的闭环模板复用到任何 C++ 项目（ph17 的代码层同样沿用 `-std=c++17 -Wall -Wextra` 零警告与退出码即 CI 信号的纪律）。
