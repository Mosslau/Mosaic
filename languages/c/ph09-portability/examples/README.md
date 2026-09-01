# examples —— C 标准、编译器与可移植性阶段完整示例

验证环境：Apple clang 21.0.0（`cc`，macOS Darwin arm64）与 Homebrew clang 21.1.8，编译选项统一 `-Wall -Wextra -std=c11`，零警告。GCC 与 MSVC 未在本环境提供（macOS 的 `gcc` 实为 Apple clang），涉及 `_WIN32` 分支的代码已如实标注。

| 文件 | 说明 | 编译 | 运行 | 验证状态 |
|------|------|------|------|----------|
| `ex01-stdint-protocol.c` | 用 stdint.h 定义跨平台协议字段：`_Static_assert` 尺寸契约 + 逐字段 memcpy 上"线" + 位域布局警示 | `cc -Wall -Wextra -std=c11 ex01-stdint-protocol.c -o ex01` | `./ex01` | 已验证（协议头 16 字节断言通过） |
| `ex02-platform-abstraction.c` | 条件编译平台抽象：路径分隔符、sleep 封装，业务代码零 `#ifdef` | `cc -Wall -Wextra -std=c11 ex02-platform-abstraction.c -o ex02` | `./ex02` | 已验证（POSIX 分支）；`_WIN32` 分支**未在本环境验证（需 Windows）** |
| `ex03-type-widths.c` | 跨平台类型宽度探测：int/long/指针/int32_t/int64_t/size_t/intptr_t | `cc -Wall -Wextra -std=c11 ex03-type-widths.c -o ex03` | `./ex03` | 已验证（LP64 数据模型：long=8、指针=8） |
| `ex04-feature-macros.c` | 特征宏检测：`__STDC_VERSION__` 判标准版本、平台/架构宏；可换 `-std=` 对比 | `cc -Wall -Wextra -std=c11 ex04-feature-macros.c -o ex04` | `./ex04`；换 `-std=c99`/`-std=c17` 重编对比 | 已验证（C99/C11/C17 输出正确；另经 Homebrew clang 复核） |
| `ex05-portable-log.c` | 可移植日志库骨架：时间/文件/可变参数全用 ISO C，仅 getpid 用 `#ifdef` 封装 | `cc -Wall -Wextra -std=c11 ex05-portable-log.c -o ex05` | `cd /tmp && /path/to/ex05 && cat app.log` | 已验证（POSIX 分支）；`_WIN32` 分支**未在本环境验证（需 Windows）** |

## 说明

- 五个示例一一对应主文档第 6 章的示例 1~5；文档内嵌片段摘自这些文件（为便于排版节选关键部分，完整文件以 examples/ 为准）。
- 全部示例不含 Linux 专有 API（无 epoll、/proc 等）：ex01/03/04 纯 ISO C，ex02/05 的 POSIX 路径只用少量 POSIX 函数（usleep、getpid/access）且都收在 `#ifdef` 封装里——在 Linux/macOS/BSD 上可直接编译；`_WIN32` 分支（windows.h / process.h）需 Windows + MSVC 或 MinGW，未在本环境验证。
- 涉及字节序的细节（ex01 中 0xCAFE 以小端序落线）不做位级处理——那是 ph12 字节序、内存对齐与二进制格式解析阶段（roadmap 第 12 节）的内容。
- 运行产物（`ex01`~`ex05`、app.log）一律写 /tmp 或当前运行目录，验证后清理，不入仓库。
