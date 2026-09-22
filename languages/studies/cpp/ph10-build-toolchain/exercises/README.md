# exercises —— 构建工具链阶段练习

完成顺序建议：按 1~5 顺序完成。参考实现在 `sol-*` 文件中（练习 1、5 为多文件解，在 `sol-01-cmake/`、`sol-05-make/` 目录里），做完再看。验证环境：Apple clang 21（g++ 兼容），`c++ -std=c++20 -Wall -Wextra`；练习 1 需 CMake、练习 3 需 clang-tidy、练习 4 需 gcov（lcov 可选）。练习 1~4 与 roadmap ph10「练习」小节的四项承诺一一对应，练习 5（Makefile 增量构建）对应 roadmap「学习内容」中的 g++/Makefile。

## 练习 1：给项目写 CMake（★★）

- **目标**：把一组多文件源码组织成 CMake「库 + 可执行」多目标工程，Debug/Release 双目录构建
- **要求**：
  - 任选一个 3 个文件以上的小库（如 text_utils：`to_upper` + `count_vowels`），拆成库目标 + 可执行目标
  - `add_library(... STATIC ...)` + `add_executable(...)` + `target_link_libraries(app PRIVATE lib)`，依赖必须显式声明
  - `set(CMAKE_CXX_STANDARD 20)` + `CMAKE_CXX_STANDARD_REQUIRED ON` + `CMAKE_CXX_EXTENSIONS OFF`
  - 库与可执行都加 `-Wall -Wextra`（`target_compile_options`）；头文件可见性用 `PUBLIC`
- **验收**：`cmake -B build && cmake --build build` 零警告、`./build/app` 断言通过；`cmake -B build-rel -DCMAKE_BUILD_TYPE=Release && cmake --build build-rel` 同样通过；`rm -rf build build-rel` 后目录只剩源码与 CMakeLists.txt
- **提示**：漏写 `target_link_libraries` 会报 `undefined reference`；两种构建类型用两个独立 build 目录，别在一个目录里反复切

## 练习 2：用 ASan 查越界（★★）

- **目标**：故意写一个堆越界程序，用 AddressSanitizer 定位并修复
- **要求**：
  - 用 `new[]` 分配数组后在越界位置写入（如循环条件 `i <= n` 写 `p[n]`）
  - 先普通编译确认"编译零警告、运行可能不崩"——这正是 ASan 的价值
  - 再用 `-fsanitize=address -fno-omit-frame-pointer -g` 编译运行，读报告：错误类型（heap-buffer-overflow）、操作（WRITE of size 4）、位置（哪个函数）
  - 修复后重跑：ASan 不再报错
- **验收**：能复述"为什么普通编译发现不了、ASan 一击命中"；修复后 ASan 运行退出码 0
- **提示**：`-fno-omit-frame-pointer` 保证回溯可用；ASan 构建配 `-O0/-O1`，别与 `-O2` 混用

## 练习 3：用 clang-tidy 做静态检查（★★）

- **目标**：对一段"能编译、能运行"但藏着反模式的代码跑 clang-tidy，至少修 3 条警告
- **要求**：
  - 准备一段含 4 类反模式的代码：下标循环（→ range-based for）、冗长迭代器类型（→ auto）、`NULL`（→ nullptr）、`for (const T x : ...)` 值拷贝（→ const&）
  - 命令：`clang-tidy sloppy.cpp -checks='-*,modernize-loop-convert,modernize-use-auto,modernize-use-nullptr,performance-for-range-copy' -- -std=c++20`
  - 用 `--fix` 自动修复后复检零警告；再以 `-Wall -Wextra` 编译确认零警告
- **验收**：能列出修复前的警告清单（规则名 + 行号 + 建议）；修复后 clang-tidy 复检与编译器编译都零警告
- **提示**：**坑：不给编译参数（`--` 后）时 clang-tidy 按默认旧标准分析，误报一片**；规则集先小范围（几类 modernize/performance）再逐步扩大，别一次全开

## 练习 4：生成覆盖率报告（★★★）

- **目标**：对带分支的函数开 `--coverage` 插桩，跑测试后出 gcov 报告，读"哪些行没被测试跑到"
- **要求**：
  - 写一个 4 分支函数（如 `classify(score)` 返回 A/B/C/D）与调用它的 main，**刻意只测其中 3 个分支**
  - 编译：`c++ -std=c++20 -O0 -g --coverage sol.cpp -o sol`（覆盖率构建必须 `-O0 -g`，勿与 `-O2` 混用）
  - 运行生成 `.gcda`，再 `gcov <生成的.gcno>` 出文本报告；找 `#####` 未覆盖行
  - （可选）装 lcov 出 HTML 报告：`lcov --capture --directory . --output-file coverage.info && genhtml coverage.info --output-directory html`
- **验收**：能解释 gcov 报告里 `#####` 的含义；给未覆盖分支补一个用例后覆盖率提升/达 100%
- **提示**：本机 Apple clang 的 `.gcno` 命名为"可执行名-源文件名"（如 `sol-sol.gcno`），`gcov` 要显式传该文件名；Linux GCC 是"源文件名.gcno"，`gcov sol.cpp` 即可——命令差异如实记录

## 练习 5：Makefile 增量构建（★）

- **目标**：给多文件项目写 Makefile：目标-依赖-规则完整，头文件依赖声明正确，用 touch 实测增量构建
- **要求**：
  - 三个文件：`calc.h` 声明 + `calc.cpp` 实现 + `main.cpp` 入口；Makefile 显式列出每个 `.o` 的源与头依赖
  - 产物隔离到 `build/` 子目录（`mkdir -p build`）；`make clean` 只删 `build/`
  - 变量用 `CXX := c++`、`CXXFLAGS := -std=c++20 -Wall -Wextra`（用 `:=` 而非 `?=`：环境已导出 CC/CXX 时 `?=` 不会覆盖）
- **验收**：`make` 零警告、`make run` 断言通过；**touch 实测**：`sleep 1 && touch calc.cpp && make` 只重编 calc.o、`sleep 1 && touch calc.h && make` 两个 .o 都重编、无改动时输出 `Nothing to be done`；`make clean` 后无残留
- **提示**：GNU Make 3.81 只比较秒级时间戳，touch 与上次构建落在同一秒会被当作"未更新"，先 `sleep 1` 再 touch

> **提示**：参考实现仅作对照，先独立完成再复盘。sol-02 是"故意出错的参考实现"——它演示的是"写 bug → ASan 定位 → 修复"的完整过程，不是可直接照抄的答案；sol-03 的修复前代码片段在题目里，sol-03-tidy.cpp 是修复后版本。进阶玩法（可选）：给 sol-01 的 CMake 工程加 ctest 注册与 `enable_testing()`；用 `-G Ninja` 对比构建速度；用 `nm` 给 sol-05 的可执行文件画一份"符号表 + 依赖"清单。
