# ph15 阶段项目：C++ UB 示例集

对应 roadmap ph15「推荐项目」第一个「C++ UB 示例集」（第二个「安全容器使用指南」由 exercises 练习 1/3 与 examples/ex02 的安全对照覆盖）。项目是 **8 类 C++ UB 的“坏版本 + 好版本”目录库 + 命令行演示 + Makefile 一键编译/自检/逐个演示**——坏版本用 Sanitizer 复现报告，好版本是安全写法；`./ub_catalog list` 就是代码评审检查清单，`make demos` 就是复习演示。参照 C ph10 的「C 常见坑示例库」结构，但条目按 C++ 特有 UB 组织（use-after-move、容器悬空引用/失效等，不重复 C 的整数类坑）。

## 需求

- `ub_catalog.h` —— 目录条目结构（名称/中文名/检测工具/识别要点）+ 坏/好版本声明
- `bad_demos.cpp` —— 8 类 UB 的坏版本（故意出错）：越界（vector 下标越界写）、悬空引用（容器销毁后使用引用）、use-after-free、重复释放、use-after-move（moved-from 解引用）、类型双关·严格别名、未对齐访问、未初始化变量；每类与主文档 3.1~3.7 对应
- `catalog.cpp` —— 目录表 + 8 个好版本 + 命令行入口（`list` / `check` / `demos` / `<name> [good]`）；主文件零警告
- `race.cpp` —— 数据竞争坏/好版本（**TSan 专用**：TSan 与 ASan/UBSan 不能同进程共存，race 独立成二进制）
- `Makefile` —— 构建（ASan+UBSan，`-O0` 理由见文件头注释）+ 自检 + 逐个演示 + race（TSan）+ 清理，产物隔离 `build/`

## 功能清单

| 功能 | 说明 |
|------|------|
| 8 类 UB 坏/好两件套 | 坏版本触发即被 Sanitizer 中止并打印报告；好版本零报告（与主文档 3.1~3.7 一一对应） |
| `./ub_catalog list` | 列出全部坑与检测工具（代码评审检查清单，含 race 提示） |
| `./ub_catalog <name>` | 触发该类坏版本（Sanitizer 报错中止）；`<name> good` 运行好版本 |
| `make check` | 8 个好版本（ASan+UBSan 零报告）+ race 好版本（TSan 零报告），退出码 0 |
| `make demos` | 循环逐个触发坏版本（每个被中止后继续下一个），演示报告 |
| `make race` / `race-demo` | TSan 构建 / 演示数据竞争报告（Apple clang 21.0.0） |
| 工具边界教学 | alias/uninit 两个“工具抓不到”的坑会跑完并打印提示（见下） |
| 产物纪律 | 产物全在 `build/`，`make clean` 即净，仓库不落二进制 |

## 验收标准

- [ ] `make clean && make` 构建成功：catalog.cpp 零警告；bad_demos.cpp 仅剩被 `-Wno-uninitialized` 抑制的“故意触发”警告（编译期能拦一部分坑的教学点）
- [ ] `make check` 输出 8 行好版本结果 + `自检完成: 8 个好版本全部运行, 无 Sanitizer 报告（退出码 0）` + `good: shared=200000`，退出码 0
- [ ] `make demos` 逐个触发坏版本：oob/dangling/uaf/doublefree/uam/align 各产生对应 Sanitizer 报告（关键行见下表），alias/uninit 无报告并跑完打印提示，race 段 TSan 报 data race
- [ ] `./ub_catalog list` 表格可读，9 行（8 类 + race）与主文档 3.1~3.7 及 examples/ 一一对应
- [ ] `make clean` 清空全部产物（build/ 目录不存在）
- [ ] 全部代码 `-std=c++20`；主文件无裸 new/delete（R.11；坏版本是故意演示，行内注释标明）；双编译器（Apple clang 21.0.0 + Homebrew clang 21.1.8）主文件零警告

## 关于故意出错的代码

坏版本全部是**故意写错的 UB 演示**，设计上依赖 Sanitizer 中止：构建默认 `-fsanitize=address,undefined -fno-sanitize-recover=all -O0`，坏版本一触发即报错退出，**禁止去掉 Sanitizer 后运行**（裸跑可能崩溃或静默损坏数据）。构建统一 `-O0`——实测（examples/ex01）越界写在 `-O0`/`-O1`/`-O2` 三档 + ASan 下均报 heap-buffer-overflow、退出码 134，`-O0` 不是防漏报的必要条件；用 `-O0` 是为行号稳定、报告可控（真实项目的 Sanitizer CI 构建才用 `-O1`）。

各坏版本的实测报告关键行（本环境实测：Apple clang 21.0.0，macOS arm64，`make demos` 可见完整输出；本环境 ASan/UBSan 无法启动外部符号器（llvm-symbolizer spawn 失败 errno 9），报告栈帧未符号化，但错误类型/访问大小/行号信息完整）：

| 名称 | 检测工具 | 实测报告关键行 |
|------|---------|---------------|
| oob | ASan | `ERROR: AddressSanitizer: heap-buffer-overflow`（越界写落在 12 字节堆区之后，退出码 134） |
| dangling | ASan | `ERROR: AddressSanitizer: heap-use-after-free` + `READ of size 1`（退出码 134） |
| uaf | ASan | `ERROR: AddressSanitizer: heap-use-after-free` + `WRITE of size 4`（退出码 134） |
| doublefree | ASan | `ERROR: AddressSanitizer: attempting double-free`（退出码 134） |
| uam | UBSan | `runtime error: reference binding to null pointer of type 'int'`（unique_ptr.h 的 operator*，退出码 134；裸跑实测 SIGSEGV 139） |
| alias | 无运行时工具 | 无报告，`bits=3f800000`（碰巧正确）——识别靠评审与规范（UBSan 不查严格别名） |
| align | UBSan | `runtime error: store to misaligned address ... for type 'std::uint32_t' ... which requires 4 byte alignment`（退出码 134；arm64 裸跑“只是容忍”） |
| uninit | 编译期 `-Wuninitialized` | 无运行时报告，输出垃圾值（本二进制 ASan 构建下 3 次运行均 x=1 s.hits=1——同栈布局的“碰巧稳定”；非 ASan 构建实测不同值如 -248938240，运行间/换构建即变，不可依赖）；编译期警告在无 `-Wno-uninitialized` 时触发 |
| race | TSan（make race） | `WARNING: ThreadSanitizer: data race` + `Write of size 4 ... by thread T2` / `Previous write ... by thread T1`（退出码 134；好版本零报告、`good: shared=200000`） |

## 检测工具的边界（教学点）

与 C ph10 同构，本库刻意保留工具边界：**未初始化变量**（ASan/UBSan 都不查；编译期 `-Wuninitialized` 能拦局部变量、拦不到多数成员——默认成员初始化器才是根治）与**类型双关/严格别名**（UBSan 不查严格别名，只能靠规范与评审）跑完不报错、打印“无 Sanitizer 报告”提示；**数据竞争**需要 TSan，且 TSan 与 ASan/UBSan 不能同进程共存，故独立二进制。工具能抓的用工具，抓不到的靠规范与评审习惯——这是本阶段与 ph16 测试、静态分析与代码规范阶段的边界（ph16 讲工具链系统化与 CI 接入，目录已建）。

## 扩展方向（可选）

- 给 `check` 增加断言：好版本输出与预期逐行比对，任一不符即非零退出——为 ph16 单元测试（GoogleTest/Catch2）留骨架
- 把目录表导出为 JSON/文本清单，作为 code review checklist 生成器的输入（roadmap 练习「用 ASan/UBSan 检查项目」的可持续版本）
- 给 uninit/alias 条目补 clang-tidy/cppcheck 静态分析对照（`-Wuninitialized` 之外的第二道编译期防线，属 ph16）
- 加 `std::atomic` 修复版 race 演示（与 scoped_lock 对比适用场景，承接 ph08 并发编程阶段的 atomic 基础）
- 安全容器使用指南（roadmap 推荐项目②）：把 dangling/oob 的“好版本”扩展成带断言与文档的容器使用小库（exercises 练习 1/3 已覆盖核心场景）

## 验证环境

- Apple clang 21.0.0（`c++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），`-std=c++20`；TSan 实测用 Apple clang（Homebrew clang 21.1.8 的 TSan 运行时在本机 arm64 上不稳定，实测崩溃，未使用）
- 构建：`make`；自检：`make clean && make check`；演示：`make demos`；清单：`./ub_catalog list`；race：`make race && ./build/race_demo race`
- 验证状态：已验证（双编译器主文件零警告、输出一致；check 退出码 0；demos 逐坑出报告；clean 无残留）
