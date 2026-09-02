# examples —— C++ 测试、静态分析与代码规范阶段完整示例

验证环境：macOS arm64，Apple clang 21.0.0（`c++`）+ Homebrew clang 21.1.8（`clang++`），C++20（libc++）；clang-tidy / clang-format / llvm-cov / llvm-profdata 均为 Homebrew LLVM 21.1.8（`/opt/homebrew/opt/llvm/bin/`）。ex01~ex05 已在本环境实际构建运行验证（已验证），双编译器 `-std=c++20 -Wall -Wextra` **零警告**；ex06（CI 配置）本机无 docker，**未在本环境验证**。**全部构建产物输出到 /tmp 或各自 build/，验证后清理，仓库不落二进制**。

## 本机工具探测结论（写文档前逐一实测）

| 工具 | 本机状态 | 说明 |
|------|---------|------|
| GoogleTest / Catch2 | ❌ 未安装（brew 无） | ex01 用自写 mini 断言框架演示**同构模式**（TEST/EXPECT/退出码语义一致），真实框架代码给出但标「未在本环境验证」 |
| clang-tidy 21.1.8 | ✅ 可用 | ex02 坏版本实测 5 条告警（4 类规则），修复版零告警 |
| clang-format 21.1.8 | ✅ 可用 | ex03 乱格式文件 `--dry-run --Werror` 报 36 处违规，格式化产物零违规 |
| cppcheck | ❌ 未安装 | 主文档 3.2 给出用法与和 clang-tidy 的分工，标「未在本环境验证」 |
| ASan（Apple clang） | ✅ 可用 | ex04 矩阵实测零报告 / 越界版报 `heap-buffer-overflow` |
| ASan（Homebrew clang） | ❌ 初始化即挂起 | 连 hello world 都跑不起来（卡在 `libc interceptors initialized` 之后）——**本机 Sanitizer 一律用 Apple clang** |
| UBSan（双编译器） | ✅ 可用 | ex04 `asan-ubsan` 构建实测零报告 |
| TSan（Apple clang） | ✅ 可用 | ex04 `tsan` 构建实测零报告 |
| TSan（Homebrew clang） | ❌ 崩溃 | ph15 已记录，本阶段未再使用 |
| LSan | ❌ 不可用 | Apple clang 编译即报 `unsupported option '-fsanitize=leak'`；Homebrew clang 能编译但退出时挂起——macOS 泄漏检测用 `leaks` 命令 / Instruments |
| llvm-cov / llvm-profdata 21.1.8 | ✅ 可用 | ex05 三步流实测出报告；Apple clang 生成的 profraw 实测也能读，但同版本最稳 |
| gcov（/usr/bin/gcov） | ✅ 可用 | Apple clang `--coverage` 两步编译（先 `-c` 再链接）实测出行覆盖率 |
| lcov / genhtml | ❌ 未安装 | 主文档 3.5 给出 Linux CI 用法，标「未在本环境验证」 |

| 文件 | 说明 | 构建/运行 | 验证状态 |
|------|------|-----------|----------|
| `ex01-mini-test.h` + `ex01-calculator.h` + `ex01-test-mini.cpp` | 单元测试：自写 mini 断言框架（TEST 注册 + EXPECT 断言 + 退出码汇总），与 GoogleTest 同构 | `c++ -std=c++20 -Wall -Wextra ex01-test-mini.cpp -o /tmp/ph16cpp-ex01 && /tmp/ph16cpp-ex01` | 已验证（双编译器零警告，3 用例全过，退出码 0） |
| `ex01-test-gtest.cpp` | Calculator 的 GoogleTest 真实版本（TEST/EXPECT_EQ/EXPECT_THROW/ASSERT_*） | 文件头含安装与构建命令 | 未在本环境验证（本机未装 GoogleTest） |
| `ex01-test-catch2.cpp` | Calculator 的 Catch2 v3 真实版本（TEST_CASE/SECTION/REQUIRE/CHECK） | 文件头含安装与构建命令 | 未在本环境验证（本机未装 Catch2） |
| `ex02-tidy-demo.cpp` + `ex02.clang-tidy` | clang-tidy：坏版本触发 4 类规则 5 条告警，`-DEX02_FIXED` 修复版零告警 | 见下「示例 2」 | 已验证（clang-tidy 21.1.8 实测） |
| `ex03-messy.cpp` + `ex03-formatted.cpp` + `ex03.clang-format` | clang-format：乱格式素材 + 配置 + 格式化产物；`--dry-run --Werror` 格式门禁 | 见下「示例 3」 | 已验证（乱版 36 处违规 exit 1，产物 exit 0） |
| `ex04-sanitizer-matrix/`（Makefile + main.cpp） | Sanitizer 工程化矩阵：同一份源码 × normal/ASan/ASan+UBSan/TSan 四种构建 | `make check` / `make demo-oob` / `make clean` | 已验证（4 构建零报告 exit 0；越界版 ASan 报 `heap-buffer-overflow`） |
| `ex05-coverage/`（Makefile + grade.h + test_main.cpp） | 覆盖率：llvm-cov source-based 三步流（插桩 → 收集 → 报告） | `make report` / `make show` / `make clean` | 已验证（grade.h 行覆盖 100%） |
| `ex06-ci/github-actions.yml` | CI 模板：格式 → 静态分析 → 测试矩阵 → Sanitizer+覆盖率 四道闸门 | 落地为仓库 `.github/workflows/ci.yml` | 未在本环境验证（本机无 docker） |

## 示例 1：单元测试（ex01-*）

```bash
# 1. mini 框架版（已验证，双编译器零警告）：
c++ -std=c++20 -Wall -Wextra ex01-test-mini.cpp -o /tmp/ph16cpp-ex01 && /tmp/ph16cpp-ex01
# 2. GoogleTest / Catch2 版：见 ex01-test-gtest.cpp / ex01-test-catch2.cpp 文件头（未在本环境验证）
```

本机实测（Apple clang 21.0.0）：输出 `[运行]/[通过] CalculatorTest.Add` 等 3 个用例 + `[汇总] 3 个用例，0 个失败`，退出码 0。要点：**测试程序的退出码就是 CI 信号**；`TEST` 用例靠全局注册器在 main 之前自动登记（GoogleTest 同原理）；`EXPECT`（失败后继续）与 `ASSERT`（失败即中止）的区别见 gtest 版注释。

## 示例 2：clang-tidy（ex02-tidy-demo.cpp + ex02.clang-tidy）

```bash
# 1. 坏版本（默认）：5 条告警（4 类规则）
/opt/homebrew/opt/llvm/bin/clang-tidy -quiet ex02-tidy-demo.cpp --config-file=ex02.clang-tidy -- -std=c++20
# 2. 修复版：零告警
/opt/homebrew/opt/llvm/bin/clang-tidy -quiet ex02-tidy-demo.cpp --config-file=ex02.clang-tidy -- -std=c++20 -DEX02_FIXED
# 3. 修复版双编译器编译验证（零警告）：
c++ -std=c++20 -Wall -Wextra -DEX02_FIXED ex02-tidy-demo.cpp -o /tmp/ph16cpp-ex02-f && /tmp/ph16cpp-ex02-f
```

本机实测（clang-tidy 21.1.8）坏版本 5 条告警：`cppcoreguidelines-special-member-functions`（自定义析构未配拷贝/移动，C.21）、`modernize-use-override`（重写未标 override，C.128）、`modernize-use-nullptr`（NULL → nullptr，ES.47，2 处）、`performance-for-range-copy`（范围 for 按值拷贝 string）。修复版零告警（关键配置项 `AllowSoleDefaultDtor: true` 豁免「多态基类只有 =default 析构」的标准写法）。教学点：坏版本编译时自带 1 条 `-Wrange-loop-construct`——**编译器告警是第一道静态分析，clang-tidy 是规则更多的第二道**。

## 示例 3：clang-format（ex03-messy.cpp / ex03-formatted.cpp / ex03.clang-format）

```bash
# 1. 格式化（输出到 stdout；-i 为原地修改）：
/opt/homebrew/opt/llvm/bin/clang-format --style=file:ex03.clang-format ex03-messy.cpp > /tmp/ph16cpp-ex03-fmt.cpp
# 2. 格式门禁（CI 用法：只检查不改文件，违规即非零退出）：
/opt/homebrew/opt/llvm/bin/clang-format --style=file:ex03.clang-format --dry-run --Werror ex03-formatted.cpp
# 3. 产物编译验证（双编译器零警告）：
c++ -std=c++20 -Wall -Wextra ex03-formatted.cpp -o /tmp/ph16cpp-ex03 && /tmp/ph16cpp-ex03
```

本机实测（clang-format 21.1.8）：`ex03-formatted.cpp` `--dry-run --Werror` 零输出、退出码 0；`ex03-messy.cpp` 同命令报 36 处 `-Wclang-format-violations`、退出码 1。要点：**格式化不需要人工对齐**——工具的权威输出即标准（roadmap 必会概念「格式化不应靠人工争论」）；`.clang-format` 放仓库根目录时不带 `--style` 自动拾取。

## 示例 4：Sanitizer 工程化矩阵（ex04-sanitizer-matrix/）

```bash
# 1. 四构建自检（normal / ASan / ASan+UBSan / TSan，全部应零报告）：
cd ex04-sanitizer-matrix && make check
# 2. 演示越界被 ASan 抓住（故意出错版，勿裸跑）：
make demo-oob
# 3. 清理：
make clean
```

本机实测（Apple clang 21.0.0）：`make check` 四种构建均输出 `parallel_sum=60`、退出码 0、零 Sanitizer 报告；`make demo-oob` 报 `ERROR: AddressSanitizer: heap-buffer-overflow` + `WRITE of size 4`（退出码 134）。要点：TSan 与 ASan **不能同进程共存**（ph15 3.5），必须独立二进制；**本机 Homebrew clang 21.1.8 的 ASan 运行时初始化即挂起**（实测，Makefile 文件头有记录），Sanitizer 构建一律用 Apple clang；LSan 在 macOS 不可用（Apple clang 编译报错，Homebrew 运行挂起）。

## 示例 5：覆盖率（ex05-coverage/）

```bash
# 1. 三步流一把梭（插桩编译 → 运行收集 → llvm-cov 报告）：
cd ex05-coverage && make report
# 2. 逐行视图（看每行执行计数）：
make show
# 3. 清理：
make clean
```

本机实测（clang++ 21.1.8 + llvm-cov 21.1.8）：报告 `grade.h` 行/区域覆盖 100%，`test_main.cpp` 73.33% 区域——缺口全在「失败打印」分支（只有测试失败才执行），TOTAL 86.67%。要点：覆盖率的价值是**发现没测到的路**；`gcov` 路线（`c++ --coverage` 两步编译 + `/usr/bin/gcov -n`）本机实测同样可行（test_main.cpp 行覆盖 78.57%、grade.h 100%），`lcov`/`genhtml` 本机未安装（未在本环境验证）。

## 示例 6：CI 配置（ex06-ci/github-actions.yml）

未在本环境验证（本机无 docker，无法跑 GitHub Actions runner）。要点看文件头注释：四个 job 各管一道闸门（格式 → 静态分析 → 测试矩阵 → Sanitizer+覆盖率），任何一道失败 PR 即红；落地位置是仓库根 `.github/workflows/ci.yml`。
