# ph10 阶段项目：C++ 工程模板（Makefile 版）

对应 roadmap ph10 推荐项目第一个「C++ 工程模板」（第二个「带 CI 的小型库」依赖远程 CI 平台，本机无法验证，作为扩展方向）。项目是 **core 库 + app 可执行 + tests 测试** 三层骨架，用 Makefile 组织多目标、增量构建与头文件依赖跟踪——正是 roadmap「学习内容」中 g++/Makefile/CMake 与「阶段验收」中"能构建多目标项目"的落地产物。core 库内容（统计工具）刻意从简，**本项目的重点是构建本身**：产物隔离、依赖声明、增量重编、Debug/Release 双轨。

## 需求

- `core/stats_utils.h` / `core/stats_utils.cpp` —— core 静态库：`mean` / `median` / `stddev`（总体）/ `min_max`，空输入抛 `std::invalid_argument`
- `app/main.cpp` —— app 可执行：从命令行参数读数字，输出统计结果；无参数/非法数字报错退出非零
- `tests/test_core.cpp` —— tests 测试目标：断言自测（全过退出码 0），覆盖四个函数的正常值与空输入异常路径
- `Makefile` —— 多目标增量构建：显式源/头依赖、产物隔离 `build/`、`test` / `release` / `clean` 目标

## 功能清单

| 功能 | 说明 |
|------|------|
| 多目标构建 | `all` 同时产出 `build/app` 与 `build/test_core`，共享 core 库目标 |
| 产物隔离 | 所有 `.o`/可执行输出到 `build/`，源码目录不落产物（`make clean` 即净） |
| 依赖声明 | 每个 `.o` 显式列出源文件与头文件：头文件改动才触发重编 |
| 增量构建 | `touch` 实测：改 `app/main.cpp` 只重编 app.o、改 `core/*.cpp` 只重编 stats_utils.o、改 `stats_utils.h` 三个 .o 都重编 |
| 测试目标 | `make test` 构建并运行断言自测 |
| Debug/Release 双轨 | `make`（默认 `-O0` 级别）与 `make release`（追加 `-O2 -DNDEBUG`），对比见主文档 3.7 |
| 零警告 | `-std=c++20 -Wall -Wextra` 全目标编译零警告 |

## 验收标准

- [ ] `make` 构建成功且零警告；`./build/app 1 2 3 4` 输出 `mean=2.500000 median=2.500000 stddev=1.118034 min=1.000000 max=4.000000`；无参数退出码 1
- [ ] `make test` 全部断言通过、退出码 0（含空输入抛异常 4 项）
- [ ] 增量实测：`sleep 1 && touch app/main.cpp && make` 只重编 `build/app.o`；`sleep 1 && touch core/stats_utils.h && make` 三个 `.o` 都重编；无改动时输出 `Nothing to be done`
- [ ] `make release` 零警告且行为一致（`./build/app 2 4 4 4 5 5 7 9` 的 `stddev=2.000000`）
- [ ] `make clean` 后仓库只剩源码与 Makefile（无 `.o`/可执行文件残留）
- [ ] 仅用标准库，无第三方依赖；无裸 new/delete（R.11）；传参与返回值遵循 F.16/F.20；空输入用异常（E.2）

## 扩展方向

- **给 core 库加 ctest**：把测试目标换成 CMake 组织（参考 examples/ex06-cmake），`enable_testing()` + `add_test` 注册
- **带 CI 的小型库**（roadmap 另一个推荐项目）：本模板 + GitHub Actions/GitLab CI，跑"构建 → 测试 → 覆盖率阈值（gcov/lcov，见练习 4）"——需要远程 CI 平台，本机未验证
- **`-G Ninja` 对比**：同一工程用 CMake + Ninja 后端对比构建速度（主文档 4.1）
- **依赖关系自动生成**：`g++ -MM` 生成头文件依赖到 `.d` 文件，Makefile `-include` 自动跟踪（本模板为教学显式手写依赖）
- 把 core 换成 ph09 的日志库/校验和模块，复用本模板的构建骨架

## 验证环境

- Apple clang 21（g++ 兼容），`-std=c++20 -Wall -Wextra`，GNU Make 3.81，全部产物在 `build/`
- 构建：`make`；测试：`make test`；Release：`make release`；清理：`make clean`
- 验证状态：已验证（编译零警告 + 全部断言通过 + 增量/头依赖 touch 实测 + 双轨构建通过；验证在 /tmp 副本中进行，仓库无产物残留）
