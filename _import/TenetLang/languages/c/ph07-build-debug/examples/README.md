# examples —— 构建与调试阶段完整示例

验证环境：Apple clang 17（gcc 兼容），`-Wall -Wextra -std=c11`；GDB 用 `-g`；CMake 3.31。

| 文件/目录 | 说明 | 构建 | 运行 |
|------|------|------|------|
| `ex01-makefile-project/` | 多文件项目 + Makefile（math_utils 复用 ph02） | `cd ex01-makefile-project && make` | `./app` |
| `ex02-static-lib/` | 静态库封装（libmath.a + user.c） | `cd ex02-static-lib && gcc -c math_utils.c && ar rcs libmath.a math_utils.o && gcc user.c -L. -lmath -o user` | `./user` |
| `ex03-dynamic-lib/` | 动态库（-fPIC -shared，复用 ex02 math_utils） | `cd ex03-dynamic-lib && gcc -fPIC -c math_utils.c && gcc -shared math_utils_pic.o -o libmath.so && gcc user.o -L. -lmath -o user_so` | `LD_LIBRARY_PATH=. ./user_so` |
| `ex04-gdb-debug.c` | GDB 调试段错误（故意越界，必须用 -g 编译后用 gdb 运行） | `gcc -g -Wall -Wextra ex04-gdb-debug.c -o crash` | `./crash`（预期段错误）；`gdb ./crash` 后 `run`/`bt`/`print` |
| `ex05-cmake-project/` | CMake 最小项目（STATIC 库 + 可执行） | `cd ex05-cmake-project && cmake -B build && cmake --build build` | `./build/app` |

## 说明

- **ex01 是 ex02/ex05 的基线**：math_utils.c/h/main.c 三个文件在 ex02/ex05 中复用（ex02 演示静态库、ex05 演示 CMake）
- **ex04 是故意出错示例**：`fill()` 的 `i <= len` 应为 `i < len`，用 GDB 的 `run`/`bt`/`print` 定位
- **运行产物**（`.o`、`.a`、`.so`、`app`/`user`/`crash`/`build/`）验证后清理，不入仓库

五个示例均已在 Apple clang 17（gcc 兼容）/ CMake 3.31 / GDB 下验证（已验证）。
