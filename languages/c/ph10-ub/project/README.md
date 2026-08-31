# ph10 阶段项目：C 常见坑示例库

对应 roadmap ph10「推荐项目」第一个「C 常见坑示例库」：把本阶段 10 类 UB 各写成"坏版本 + 好版本"两件套（坏版本用 Sanitizer 复现报告，好版本是修复后的安全写法），配 Makefile 一键编译/自检/逐个演示——既是复习工具，也是以后代码评审的检查清单（`./pitfall_catalog list` 就是清单本体）。

## 需求

实现一个命令行工具 `pitfall_catalog`：内置 10 类 UB 的目录表（名字/中文名/检测工具/识别要点），每类配有坏版本（`bad_demos.c`）与好版本（`pitfall_catalog.c`）。构建时统一开 ASan + UBSan（`-fno-sanitize-recover=all`），坏版本触发即被 Sanitizer 中止并打印报告；好版本全部零报告。

## 功能清单

- [x] 10 类 UB 目录：数组越界 / 空指针解引用 / 悬空指针·UAF·重复释放 / 有符号整数溢出 / 未初始化变量 / 类型双关·严格别名 / 未对齐访问 / 整数除零·INT_MIN/-1 / 非法移位 / 字符串缓冲区溢出（对应主文档 3.2~3.10）
- [x] `./pitfall_catalog list`：列出全部坑与检测工具（代码评审检查清单）
- [x] `./pitfall_catalog <名字>`：触发该坑坏版本，Sanitizer 报错中止（uninit/alias 两个运行时工具抓不到的坑会"跑完"并提示，见 README「检测工具的边界」）
- [x] `./pitfall_catalog <名字> good`：运行好版本（安全写法）
- [x] `./pitfall_catalog check`：依次运行全部 10 个好版本自检，退出码 0
- [x] `make demos`：循环逐个触发 10 个坏版本（每个被中止后继续下一个），演示报告
- [x] 主文件 `-Wall -Wextra` 零警告；坏版本文件单独编译并用 `-Wno-*` 抑制"故意触发的编译期警告"（`-Warray-bounds`/`-Wuninitialized`/`-Wfortify-source`——这些警告本身就是"编译期能拦一部分坑"的教学点）

## 验收标准

- [ ] `make clean && make` 构建成功：pitfall_catalog.c 零警告；bad_demos.c 的警告仅剩被 `-Wno-*` 抑制的"故意触发"项
- [ ] `make check`（即 `./pitfall_catalog check`）输出 10 行好版本结果 + `自检完成: 10 个好版本全部运行, 无 Sanitizer 报告`，退出码 0
- [ ] `make demos` 逐个触发坏版本：oob/null/uaf/overflow/align/divzero/shift/strbuf 各产生对应 Sanitizer 报告（关键行见下表），uninit/alias 无报告并打印「工具抓不到」提示
- [ ] `./pitfall_catalog list` 表格可读，10 行与主文档 3.2~3.10 一一对应
- [ ] `make clean` 清空全部产物（.o 与可执行文件）

## 关于故意出错的代码

本项目的坏版本全部是**故意写错的 UB 演示**，设计上依赖 Sanitizer 中止：构建默认 `-fsanitize=address,undefined -fno-sanitize-recover=all`，坏版本一触发即报错退出，**禁止去掉 Sanitizer 后运行**（裸跑可能崩溃或静默损坏数据）。验证环境：Apple clang 21.0.0（`cc`），macOS（Darwin arm64）。构建用 `-O0`——实测在 `-O1` 下 clang 会把被测试的内存访问常量折叠/死代码消除掉（如 strcpy 折叠成常量 printf），ASan 因此抓不到 stack-buffer-overflow；`-O0` 下全部报告稳定触发。

各坏版本的实测报告关键行（本环境实测，`make demos` 可见完整输出；本环境缺 llvm-symbolizer，ASan 栈帧未符号化）：

| 名字 | 检测工具 | 实测报告关键行 |
|------|---------|---------------|
| oob | ASan + UBSan | 组合构建下 UBSan 越界检查先报 `runtime error: index 3 out of bounds for type 'int[3]'`；单独 `-fsanitize=address` 时报 `ERROR: AddressSanitizer: stack-buffer-overflow` + `WRITE of size 4`（examples/ex01 实测） |
| null | UBSan | `runtime error: store to null pointer of type 'int'` |
| uaf | ASan | `ERROR: AddressSanitizer: heap-use-after-free` + `READ of size 4`（double free 变体另报 `attempting double-free`，删除演示里的 printf 后单独复现） |
| overflow | UBSan | `runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'` |
| uninit | 编译期 `-Wuninitialized` | 无运行时报告（MSan 需全程序插桩，属 ph11）；编译期警告 `variable 'x' is uninitialized when used here` 实测 `-O0`~`-O2` 均触发，在 examples/ex04 与 exercises 练习 3 中演示 |
| alias | 代码评审 | 无运行时报告（UBSan 不查严格别名）；本环境 `-O0`~`-O3` 实测均输出 1——"碰巧正确"正是 UB 危险之处，识别靠评审 |
| align | UBSan | `runtime error: load of misaligned address ... for type 'uint32_t' ... requires 4 byte alignment` |
| divzero | UBSan | `runtime error: division by zero`（裸跑 x86 上 SIGFPE、arm64 上可能静默得 0——实现/硬件差异） |
| shift | UBSan | `runtime error: left shift of 1 by 31 places cannot be represented in type 'int'` |
| strbuf | ASan + `-Wfortify-source` | `ERROR: AddressSanitizer: stack-buffer-overflow` + `WRITE of size 13`（编译期另有 `-Wfortify-source` 警告，已实测） |

## 检测工具的边界（教学点）

本库刻意保留两个"工具抓不到"的坑：**未初始化变量**（运行时 ASan/UBSan 都不查，Valgrind/MSan 才行）与**类型双关/严格别名**（UBSan 不查严格别名，只能靠 `-Wall` 的部分提示 + 代码评审）。坏版本跑完不报错、打印「没有 Sanitizer 报告?」——这正是 ph10「识别与规避」与 ph11「Sanitizer 工具链系统化」的边界：工具能抓的用工具，抓不到的靠规范与评审习惯。

## 扩展方向（可选）

- 给 `check` 增加断言：好版本输出与预期逐行比对，任一不符即非零退出——为 ph11 单元测试（Unity/CMocka）留骨架
- 用 `-fsanitize=thread`（TSan）验证多线程版本的数据竞争 —— 属于 ph11 Sanitizer / 静态分析 / 单元测试阶段的内容
- 把 `strbuf` 演示换成从网络/文件读入的不可信输入，结合 ph12 字节序、内存对齐与二进制格式解析阶段（roadmap 第 12 节，目录待建）做完整 record 解析的安全版本
- 把目录表导出为 JSON/文本清单，作为 code review checklist 生成器的输入（roadmap 练习「收集 10 个常见 UB 示例并修复」的可持续版本）

## 验证环境

- Apple clang 21.0.0（`cc`），macOS（Darwin arm64），`-Wall -Wextra -std=c11 -O0 -g -fsanitize=address,undefined -fno-sanitize-recover=all`
- 构建：`make`；自检：`make clean && make check`；演示：`make demos`；清单：`./pitfall_catalog list`
- 验证状态：已验证（构建零警告；`make check` 通过、退出码 0；10 个坏版本报告关键行全部实测，见上表；`-O1` 下 ASan 漏报 stack-buffer-overflow 的现象亦为实测发现并已在构建说明中记录）
