# examples —— 构建工具链阶段完整示例

验证环境：Apple clang 21（`c++`，g++ 兼容），`-std=c++20 -Wall -Wextra` 编译全部零警告；`ar`/`nm`/`objdump` 为 LLVM 实现（Mach-O 格式），`make` 为 GNU Make 3.81，`cmake` 为 4.2.3。**全部产物输出到 `/tmp` 或 `build/` 子目录，验证后清理，仓库不落二进制**（本目录只含源码与构建描述文件）。

| 文件 | 说明 | 构建/运行 |
|------|------|-----------|
| `ex01-pipeline.cpp` | 编译流水线四阶段（预处理/编译/汇编/链接）演示源文件 | 见下方命令，`./ex01-pipeline` 输出 `sum=24` |
| `ex02-math.h` `ex02-libstat.cpp` `ex02-libmath.cpp` `ex02-main.cpp` | 静态库：`ar` 打包 + 链接 + 按需抽取（nm 验证） | `./ex02-app` 输出断言 pass |
| `ex03-text.h` `ex03-dynlib.cpp` `ex03-main.cpp` | 动态库：`-dynamiclib` 构建 + 运行时查找（DYLD_LIBRARY_PATH / rpath） | `DYLD_LIBRARY_PATH=. ./ex03-app` 输出断言 pass |
| `ex04-symbols.cpp` | 符号表观察：nm / objdump 读 T/t/D/S/b/U | `./ex04-app` 输出 `r=15` |
| `ex05-make/`（Makefile + calc.h/cpp + main.cpp） | Makefile 增量构建：目标-依赖-规则、touch 实测 | `make && make run` |
| `ex06-cmake/`（CMakeLists.txt + math.h/cpp + main.cpp + test_math.cpp） | CMake 多目标：库+可执行+测试、Debug/Release 双轨（可选主题） | `cmake -B build && cmake --build build`、`ctest` |

## 示例 1：编译流水线四阶段（ex01-pipeline.cpp）

一段同时含**宏**、**constexpr 函数**、**模板**、**static 函数**、**外部符号引用**的源码，四个命令依次观察中间产物（产物全部输出到 /tmp，可随时 `rm`）：

```bash
# 1. 预处理：宏展开、头文件文本插入。观察 ARRAY_LEN 被原位展开为 sizeof 表达式
c++ -std=c++20 -Wall -Wextra -E ex01-pipeline.cpp -o /tmp/ex01.i
# 2. 编译：生成汇编。观察模板实例化后的符号 __Z5twiceIiET_S0_（twice<int>）
c++ -std=c++20 -Wall -Wextra -S ex01-pipeline.cpp -o /tmp/ex01.s
# 3. 汇编：生成目标文件（Mach-O object）。nm 看符号：T=全局函数 t=static 函数 U=未定义
c++ -std=c++20 -Wall -Wextra -c ex01-pipeline.cpp -o /tmp/ex01.o
nm /tmp/ex01.o
# 4. 链接：解析未定义符号（printf 等来自 libc）、重定位，产出可执行文件
c++ -std=c++20 -Wall -Wextra ex01-pipeline.cpp -o /tmp/ex01-app
/tmp/ex01-app
```

本机实测输出要点（已验证）：

- `-E` 产物里 `for (int i = 0; i < static_cast<int>((sizeof(vals) / sizeof((vals)[0]))); ++i)` —— 宏被原位展开；
- `-S` 产物里出现 `__Z5twiceIiET_S0_` —— 模板 `twice<int>` 的实例化符号；
- `nm` 目标文件：`T __Z5clampiii`（全局函数）、`t __ZL13hidden_helperi`（static 函数）、`U _printf`（未定义，链接期解析）、`_main`；
- 链接后 `sum=24`、退出码 0。

## 示例 2：静态库（ex02 系列，ar + 按需抽取）

```bash
# 1. 分别编译两个库成员（.o 产物在 /tmp）
c++ -std=c++20 -Wall -Wextra -c ex02-libstat.cpp  -o /tmp/ex02-libstat.o
c++ -std=c++20 -Wall -Wextra -c ex02-libmath.cpp -o /tmp/ex02-libmath.o
# 2. ar 打包归档（r=插入/替换 c=无输出提示 s=生成索引表）
ar rcs /tmp/libex02.a /tmp/ex02-libstat.o /tmp/ex02-libmath.o
ar t /tmp/libex02.a        # 列出归档成员
nm /tmp/libex02.a          # 每个成员的符号：gcd/lcm 在成员 1，is_prime/factorial 在成员 2
# 3. 消费者链接（-L 指定库目录 -l 指定库名，libex02.a 对应 -lex02）
c++ -std=c++20 -Wall -Wextra ex02-main.cpp -L/tmp -lex02 -o /tmp/ex02-app
/tmp/ex02-app
# 4. 按需抽取验证：可执行文件里没有 is_prime/factorial（它们所在的成员未被引用）
nm /tmp/ex02-app | grep -i "prime\|factorial"     # 无输出 = 未并入
nm /tmp/ex02-app | grep -o "_Z3gcdii\|_Z3lcmii"    # gcd/lcm 在
```

本机实测输出要点（已验证）：`ar t` 列出 `__.SYMDEF SORTED`（LLVM ar 的符号索引成员）、`ex02-libstat.o`、`ex02-libmath.o` 三个条目；`nm` 显示 `libex02.a(ex02-libstat.o): T __Z3gcdii ...` 与 `libex02.a(ex02-libmath.o): T __Z8is_primei ...`；链接后运行输出 `gcd(48,36)=12  lcm(6,8)=24` 断言 pass；可执行文件符号表确认 is_prime/factorial 未并入——**静态库按成员（.o）粒度按需抽取**。

> 符号名 `__Z3gcdii` 带前缀下划线是 Apple/LLVM（Mach-O）惯例，Linux（GNU binutils，ELF）对应 `_Z3gcdii`。ABI/符号命名细节属于 [ph19 ABI、动态库与插件机制阶段](../../ph19-abi-dynamic-libs-plugins/19-abi-dynamic-libs-plugins.md)，这里只需会用 nm 辨认 T/t/U 即可。

## 示例 3：动态库（ex03 系列，构建 + 运行时查找）

```bash
# 1. 构建动态库（macOS 用 -dynamiclib；Linux 对应 -shared -fPIC，且 macOS 默认已 PIC）
c++ -std=c++20 -Wall -Wextra -dynamiclib -install_name @rpath/libex03.dylib \
    ex03-dynlib.cpp -o /tmp/libex03.dylib
nm -gU /tmp/libex03.dylib      # 导出符号：to_upper / count_vowels（及 libc++ 顺带的 tolower/toupper）
# 2. 消费者链接（记录依赖 @rpath/libex03.dylib）
c++ -std=c++20 -Wall -Wextra ex03-main.cpp -L/tmp -lex03 -o /tmp/ex03-app
# 3. 直接运行 → 失败：dyld 找不到库（这是教学点，不是 bug）
/tmp/ex03-app
# 4. 运行时指定查找路径 → 成功
DYLD_LIBRARY_PATH=/tmp /tmp/ex03-app
# 5. 或链接期写入 rpath → 直接运行
c++ -std=c++20 -Wall -Wextra ex03-main.cpp -L/tmp -lex03 \
    -Wl,-rpath,@loader_path/. -o /tmp/ex03-rpath
/tmp/ex03-rpath
otool -L /tmp/ex03-app        # 查看可执行文件依赖的动态库（Linux 用 readelf -d）
```

本机实测输出要点（已验证）：直接运行报 `dyld: Library not loaded: @rpath/libex03.dylib ... no LC_RPATH's found`（退出码 134）；`DYLD_LIBRARY_PATH=/tmp` 与 `-Wl,-rpath` 两种方式都运行成功，输出 `HELLO DYLIB vowels=3` 断言 pass。**动态库的符号解析推迟到运行时**——可执行文件里只有 `@rpath/libex03.dylib` 的依赖记录，找不到库就启动失败（Linux 上同理，用 `LD_LIBRARY_PATH`）。

## 示例 4：符号表（ex04-symbols.cpp，nm / objdump）

```bash
c++ -std=c++20 -Wall -Wextra -c ex04-symbols.cpp -o /tmp/ex04-symbols.o
nm /tmp/ex04-symbols.o        # 类型字母
objdump -t /tmp/ex04-symbols.o   # 带段信息（Mach-O 下 objdump 即 llvm-objdump；Linux GNU objdump 同语法）
objdump -h /tmp/ex04-symbols.o   # 段表：__text / __data / __common / __bss
c++ -std=c++20 -Wall -Wextra ex04-symbols.cpp -o /tmp/ex04-app && /tmp/ex04-app
```

本机实测输出要点（已验证，Apple/LLVM nm、Mach-O）：

| 源 | 符号 | nm 字母 | 说明 |
|----|------|---------|------|
| `int global_add(int,int)` | `__Z10global_addii` | `T` | 已定义全局函数（__text 段） |
| `static int hidden_util(int)` | `__ZL11hidden_utili` | `t` | 静态函数，仅本翻译单元 |
| `int g_counter = 5` | `_g_counter` | `D` | 非零初始化全局（__data 段） |
| `int g_zero = 0` | `_g_zero` | `S` | 零初始化全局（__common；Linux ELF 上是 `B`） |
| `static int s_hits = 0` | `__ZL6s_hits` | `b` | 静态变量（__bss，局部） |
| `std::printf` 引用 | `_printf` | `U` | 未定义，链接期从 libc 解析 |

`objdump -t` 输出 `l F __TEXT,__text`（局部函数）、`l O __DATA,__bss`（局部对象）等带段信息条目。字母含义跨平台微调（`S`/`B` 差异已如实标注），`T/t/U` 三种实现一致。

## 示例 5：Makefile 增量构建（ex05-make/）

`calc.h` 声明、`calc.cpp` 实现、`main.cpp` 入口，`Makefile` 显式声明每个目标的源文件与头文件依赖，产物隔离到 `build/`：

```bash
cd ex05-make
make              # 全量：mkdir build → 编译两个 .o → 链接 build/calc
make run          # 构建并运行
make clean        # rm -rf build
```

增量实测（已验证，GNU Make 3.81）：**注意 3.81 只比较秒级时间戳，touch 前先 `sleep 1`**（同一秒内 touch 会被当作"未更新"）：

- `sleep 1 && touch calc.cpp && make` → 只重编 `build/calc.o` 并重链接，`main.o` 未动；
- `sleep 1 && touch calc.h && make` → `calc.o` 与 `main.o` **都**重编（头文件依赖生效）；
- `sleep 1 && touch main.cpp && make` → 只重编 `build/main.o`；
- 无改动再 `make` → `make: Nothing to be done for 'all'.`

Makefile 用 `CXX := c++` 而非 `CXX ?= c++`：环境变量可能已导出 `CC`/`CXX`（本机验证环境即如此），`?=` 不会覆盖环境值；命令行 `make CXX=clang++-19` 仍可覆盖。

## 示例 6：CMake 多目标（ex06-cmake/，可选主题）

roadmap 学习内容中的 CMake，工程化形态见 project/；本示例演示最小多目标（静态库 + 可执行 + 测试）与 Debug/Release 双轨：

```bash
cd ex06-cmake
cmake -B build && cmake --build build     # 配置 + 构建（默认 Debug）
./build/app                               # gcd(48,36)=12 断言 pass
ctest --test-dir build --output-on-failure # 1/1 tests passed
cmake -B build-rel -DCMAKE_BUILD_TYPE=Release && cmake --build build-rel   # 双轨
rm -rf build build-rel                    # 产物全部在 build 目录，清理即净
```

本机实测输出要点（已验证，cmake 4.2.3）：Debug 与 Release 两个独立构建目录都构建成功、运行断言通过；`ctest` 1/1 通过；产物（`libmath.a`/`app`/`test_math`）全部落在 `build*` 目录，删除构建目录后仓库只剩源码与 CMakeLists.txt。

## 工具链可移植性说明（本机 vs Linux）

- 本机 `c++` 是 **Apple clang 21**，`nm`/`objdump`/`ar` 均为 **LLVM 实现**（`objdump` 即 llvm-objdump，命令名与 Linux GNU binutils 相同，输出格式不同：Mach-O vs ELF）；若某些发行版只装 `llvm-objdump` 不带 `objdump`，用 `llvm-objdump` 即可
- 符号字母 `T/t/U` 一致；零初始化全局本机显示 `S`（`__common`），Linux ELF 显示 `B`；符号名本机带前缀下划线（`__Z3gcdii` vs `_Z3gcdii`）
- 动态库：macOS `-dynamiclib` + `@rpath`/`DYLD_LIBRARY_PATH`；Linux `-shared -fPIC` + `LD_LIBRARY_PATH`。细节差异属 ph11 可移植性阶段
- `ar`/`make`/`cmake` 用法与 Linux 相同（`ar rcs`、GNU Make、CMake 生成器差异见主文档 4.1）

全部 6 个示例均已在本环境以 `-std=c++20 -Wall -Wextra` 编译零警告并运行验证（已验证）；验证用构建产物全部位于 /tmp 或 build/ 目录，仓库无 .o/.a/.dylib/可执行文件残留。
