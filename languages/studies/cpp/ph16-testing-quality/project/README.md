# ph16 阶段项目：带测试的 STL 工具库

对应 roadmap ph16「推荐项目」第一个「带测试的 STL 工具库」（第二个「C++ CI 模板」由 examples/ex06 的 GitHub Actions 配置覆盖）。项目是一个 header-only 的 STL 风格小工具库（环形缓冲 `ring_buffer` + 字符串 `split`/`join`），配上 ph16 的完整质量闭环：**单元测试（mini 框架）+ ASan/UBSan/TSan 复跑 + clang-tidy 门禁 + clang-format 门禁 + llvm-cov 覆盖率**，全部收敛进 `make check` 一条命令。

## 需求

- `stl_utils.h` —— 工具库本体（header-only）：`ring_buffer<T>`（定容环形缓冲，写满覆盖最旧；空 pop 返回 `std::nullopt`、空 front 抛 `std::out_of_range`、零容量抛 `std::invalid_argument`）、`split`（单字符切分，连续/尾部分隔符产生空字段）、`join`（拼接，空序列返回空串）
- `test_stl_utils.cpp` —— 单元测试：10 个用例覆盖正常路径（FIFO 顺序、split/join）、异常路径（空 front、零容量）、边界（容量 1、覆盖最旧、空串、往返不变性）；用 examples/ex01 的 mini 断言框架（`-I../examples`）
- `.clang-tidy` —— 静态分析配置：`bugprone-*`/`modernize-*`/`performance-*` 三族 + 显式豁免清单（豁免理由写在注释里），`WarningsAsErrors: '*'` 告警即失败
- `.clang-format` —— 格式配置：LLVM 基底 + 4 空格缩进 + 行宽 100（与 examples/ex03 同策略）
- `Makefile` —— 一键闭环：`make check` = 测试 → ASan+UBSan 复跑 → TSan 复跑 → clang-tidy → 格式门禁 → 覆盖率报告，任何一环失败即非零退出；产物隔离 `build/`

## 功能清单

| 功能 | 说明 |
|------|------|
| `make test` | 常规构建 + 运行 10 个测试用例（退出码 0 = 全过） |
| `make asan` / `make tsan` | ASan+UBSan / TSan 构建并复跑同一套测试，零报告才算过 |
| `make tidy` | clang-tidy 静态分析，`WarningsAsErrors='*'` 门禁 |
| `make format-check` | clang-format `--dry-run --Werror` 格式门禁（只检查不改文件） |
| `make coverage` | llvm-cov source-based 覆盖率报告（三步流） |
| `make check` | 一键质量闭环（上述全部），CI 直接调它 |
| `make clean` | 清空 build/，仓库不落二进制 |

## 验收标准

- [ ] `make clean && make check` 退出码 0：10 个用例全过（三种构建各跑一遍）、clang-tidy 零用户告警、格式门禁零输出、覆盖率报告正常输出
- [ ] 覆盖率报告中 `stl_utils.h` 行/区域覆盖 100%（工具库被测透）；`ex01-mini-test.h` 的失败打印分支盖不到是健康的（只有测试失败才执行）
- [ ] 全部代码双编译器（Apple clang 21.0.0 + Homebrew clang 21.1.8）`-std=c++20 -Wall -Wextra` 零警告
- [ ] `stl_utils.h` 无裸 new/delete（R.11）、Rule of Zero（C.20）、查询函数全 const（Con.2）
- [ ] `make clean` 后 `build/` 不存在

## 扩展方向（可选）

- 把测试从 mini 框架迁移到 GoogleTest（`brew install googletest`，对照 examples/ex01-test-gtest.cpp），体验真框架的 fixture 与参数化测试
- 把 `make check` 搬进 CI：对照 examples/ex06-ci/github-actions.yml 写一个真实工作流（未在本环境验证）
- 给 `ring_buffer` 加并发读写接口（生产者/消费者），让 TSan 复跑真正有意义（承接 ph08）
- 覆盖率门槛化：CI 里解析 llvm-cov 输出，`stl_utils.h` 低于 100% 即失败（覆盖率不是越高越好，但「库代码」可以要求全测）
- 性能基准：加 Google Benchmark 对比 `ring_buffer` 与 `std::deque`（属 ph18 性能优化与 Profiling 阶段）

## 验证环境

- Apple clang 21.0.0（`c++`）+ Homebrew clang 21.1.8（`clang++`），`-std=c++20`；clang-tidy / clang-format / llvm-cov / llvm-profdata 均为 Homebrew LLVM 21.1.8（`/opt/homebrew/opt/llvm/bin/`）
- **Sanitizer 构建一律用 Apple clang**（Homebrew clang 21.1.8 的 ASan 运行时在本机初始化即挂起、TSan 崩溃——实测记录见 examples/ex04 Makefile 文件头）
- 验证状态：已验证（`make clean && make check` 退出码 0；双编译器零警告；`make clean` 无残留）
