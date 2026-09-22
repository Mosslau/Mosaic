# examples —— C 语言未定义行为 UB 与常见坑阶段完整示例

验证环境：Apple clang 21.0.0（`cc`，macOS Darwin arm64）。安全示例统一 `-Wall -Wextra -std=c11` 零警告；UB 演示按各自「运行前提」编译（`-fsanitize=address` 或 `-fsanitize=undefined -fno-sanitize-recover=all`），实测输出记录在下方表格与主文档第 6 章。

## 关于故意出错的代码

本阶段主题是"故意写错"——每个 UB 演示文件（ex01~ex04、ex06）都在**文件首行注释**写明了运行前提（必须用什么 Sanitizer 编译）。请严格遵守：

- **ex01/ex03（越界、use-after-free）**：必须用 `-fsanitize=address` 编译运行，否则裸跑会破坏相邻内存，行为不可预测。
- **ex02/ex06（整数溢出类）**：必须用 `-fsanitize=undefined -fno-sanitize-recover=all` 编译运行；不带的裸跑输出无意义（可能"碰巧正确"），且 `-O0`/`-O2` 结果不同。
- **ex04（未初始化变量）**：不会崩溃但输出垃圾值，务必用 `-Wall -Wextra` 编译看编译期警告（`-Wuninitialized` 实测 `-O0`~`-O2` 均触发）；运行时检测（Valgrind）需另行安装。
- 这些文件编译时**故意触发** `-Warray-bounds`/`-Wuninitialized` 等编译期警告——这也是教学点：编译器在编译期就能拦下一部分坑。它们不是"零警告代码"，请勿当作规范样板。
- **ex05 是唯一的安全示例**，可任意编译运行，是"边界检查三件套"的规范写法。

| 文件 | 说明 | 编译 | 运行 | 验证状态 |
|------|------|------|------|----------|
| `ex01-oob.c` | 数组越界写（UB 演示）：`arr[3]=100` 越界 1 个元素，ASan 复现 | `cc -Wall -Wextra -std=c11 -fsanitize=address -g ex01-oob.c -o ex01` | `./ex01`（报 `stack-buffer-overflow` 中止） | 已验证（ASan 报 `stack-buffer-overflow` + `WRITE of size 4`，退出码 134；编译期另触发 `-Warray-bounds`） |
| `ex02-overflow.c` | 有符号溢出 vs 无符号回绕（UB 演示）：先打印无符号回绕 `u=4294967295`（定义行为、UBSan 不报），再触发有符号溢出 | `cc -Wall -Wextra -std=c11 -fsanitize=undefined -fno-sanitize-recover=all -g ex02-overflow.c -o ex02` | `./ex02`（打印 `u = 4294967295` 后报 `signed integer overflow` 中止） | 已验证（UBSan 报 `signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'`，退出码 134） |
| `ex03-uaf.c` | use-after-free 与 double free（UB 演示）：free 后读取 + 重复 free | `cc -Wall -Wextra -std=c11 -fsanitize=address -g ex03-uaf.c -o ex03` | `./ex03`（报 `heap-use-after-free` 中止；删掉 printf 后单独复现 `attempting double-free`） | 已验证（ASan 报 `heap-use-after-free` + `READ of size 4`；double free 变体报 `attempting double-free`，退出码 134） |
| `ex04-uninit.c` | 未初始化变量（UB 演示）：条件依赖栈垃圾值 | `cc -Wall -Wextra -std=c11 -O1 -g ex04-uninit.c -o ex04` | `./ex04`（输出不确定值）；Valgrind：`valgrind --track-origins=yes ./ex04` | 部分验证（编译期 `-Wuninitialized` 警告实测触发，`-O0`~`-O2` 均触发；运行时输出垃圾值；**Valgrind 运行时检测未在本环境验证**——本机无 Valgrind） |
| `ex05-safe-str.c` | 安全字符串工具库 sstr（安全示例）：带容量 + 永远补 `\0`，超长输入截断而非溢出 | `cc -Wall -Wextra -std=c11 ex05-safe-str.c -o ex05` | `./ex05`（输出 `[hello, world! 0] len=15 cap=16`，追加被截断、len 停在 cap-1） | 已验证（`-Wall -Wextra` 零警告；加 `-fsanitize=address,undefined` 运行零报告） |
| `ex06-opt-levels.c` | 优化级别改变 UB 表现（UB 演示）：`(a+1)>a` 在 `-O0` 输出 0、`-O2` 输出 1 | `cc -Wall -Wextra -std=c11 -O0 ex06-opt-levels.c -o ex06o0`（`-O2` 同理）；UBSan 版见文件头 | `./ex06o0`（0）；`./ex06o2`（1）；`./ex06ub`（UBSan 报错中止） | 已验证（`-O0`→0、`-O1`/`-O2`→1；UBSan 报 `signed integer overflow` 并中止） |

## 说明

- 六个示例与主文档第 6 章示例 1~6 一一对应；文档内嵌片段摘自这些文件（为便于排版节选关键部分，完整文件以本目录为准）。
- 所有运行产物（`ex01`~`ex06*` 可执行文件）一律写 /tmp 或构建临时目录，验证后清理，不入仓库。
- Sanitizer 只是本阶段的**演示工具**：用它们"证明这段代码是 UB、报告长什么样"。工具链的工程化使用（CI 接入、静态分析、单元测试框架）是 ph11 Sanitizer / 静态分析 / 单元测试阶段的内容，本阶段不展开。
- 涉及字节序、对齐的位级处理细节（如把 record 从字节流里安全解出来）属 ph12 字节序、内存对齐与二进制格式解析阶段（roadmap 第 12 节），本阶段只演示"未对齐访问是 UB"本身。
