# examples —— C 与 C++ / Python / Rust 互操作阶段完整示例

本目录是主文档第 6 章示例 1~6 的完整可运行版。**每个示例都是「C 动态库 + 至少一种语言的调用方」**，核心验证是：同一份 C 库被 C / C++ / Python / Rust 四种语言真实调用、输出一致。

验证环境（本机实测）：**Apple clang 21.0.0**（`cc` / `c++`，macOS arm64，ProductVersion 26.6.2）+ **Python 3.13.9**（ctypes）+ **rustc 1.92.0**（edition 2021）。全部 C 代码 `cc -Wall -Wextra -std=c11` 零警告，C++ 代码 `c++ -Wall -Wextra -std=c++17` 零警告，Rust 代码 `rustc -D warnings` 零警告。产物一律写 `/tmp/ph14-ex/`，`make clean` 清理，仓库零残留。Linux 差异：动态库后缀 `.so`、编译用 `-shared -fPIC`（见各文件头注释）。

## 一键构建与运行

```bash
make all      # 1. 构建并运行全部示例（输出即验证结果）
make ex01     # 2. 只跑某组（ex01 ~ ex06）
make clean    # 3. 清理 /tmp/ph14-ex
```

## 示例清单

| 组 | 文件 | 说明 | 验证状态 |
|----|------|------|----------|
| ex01 | `calc.h` / `calc.c` / `ex01-c-main.c` | C 动态库（libcalc.dylib）与 C 主程序：`nm -gU` 实测导出符号 `_calc_add/_calc_mul/_calc_div/_calc_strlen`，除零返回错误码 -1 | 已验证：零警告，退出码 0；add=42、div rc=0/q=42、div(1,0) rc=-1、strlen=5 |
| ex02 | `ex02-cpp-main.cpp` / `ex02-cpp-lib.cpp` / `ex02-c-main.c` / `ex02-bad-header.h` / `ex02-mangle-fail.cpp` | C++ 调 C（extern "C" 守卫）+ C 调 C++ 包装层（extern "C" 导出）+ 故意出错：忘加守卫 → 链接失败（Undefined symbols: `calc_add(int, int)`，NOTE 提示 missing 'extern "C"'） | 已验证：两个方向都零警告运行通过；mangling 演示按预期链接失败（其报错文本即教学内容） |
| ex03 | `ex03-py-ctypes.py` | Python ctypes 调 libcalc：显式 argtypes/restype、指针出参（byref）、错误码检查、字符串 c_char_p | 已验证：`python3 ex03-py-ctypes.py /tmp/ph14-ex/libcalc.dylib` 全部断言通过，退出码 0 |
| ex04 | `ex04-rs-ffi.rs` | Rust extern "C" 调 libcalc：`#[link(name="calc")]`、unsafe 调用、错误码、CString 传字符串 | 已验证：`rustc --edition 2021 -D warnings ... -l calc` 零警告，运行全部断言通过 |
| ex05 | `session.h` / `session.c` + `ex05-c-handle.c` / `ex05-cpp-handle.cpp` / `ex05-py-handle.py` / `ex05-rs-handle.rs` | opaque pointer + create/destroy API + 错误码/错误消息：四种语言各自 create → add×2 → total=42 → destroy，并复现「空 name → NULL + err=-1 + invalid argument」错误路径 | 已验证：四种语言输出一致（total=42、err=-1、msg=invalid argument），退出码 0 |
| ex06 | `bufio.h` / `bufio.c` + `ex06-c-ownership.c` / `ex06-py-ownership.py` / `ex06-rs-ownership.rs` | 跨语言所有权三种约定：① C 分配 C 释放（bufio_str_dup/free）② 调用方分配缓冲区 C 只写 ③ C 只读借用数组；另加 POD 结构体按值传递 | 已验证：C/Python/Rust 三侧输出一致（dup/caller buffer/sum=15/(40,60)），退出码 0 |

## 逐文件命令（可复现）

### ex01 —— C 动态库与导出符号

```bash
# 1. 编译动态库
cc -Wall -Wextra -std=c11 -dynamiclib calc.c -o /tmp/ph14-ex/libcalc.dylib
# 2. 编译 C 主程序并链接（-L 指向库目录, -lcalc 找 libcalc.dylib）
cc -Wall -Wextra -std=c11 ex01-c-main.c -L/tmp/ph14-ex -lcalc -o /tmp/ph14-ex/ex01
# 3. 运行
/tmp/ph14-ex/ex01
# 4. 实测导出符号（-gU: 只列全局导出; T = 文本段, 可被调用）
nm -gU /tmp/ph14-ex/libcalc.dylib
```

### ex02 —— C++ 调 C 与 C 调 C++ 包装层

```bash
# C++ 调 C（calc.h 自带 extern "C" 守卫）
c++ -Wall -Wextra -std=c++17 ex02-cpp-main.cpp -L/tmp/ph14-ex -lcalc -o /tmp/ph14-ex/ex02-cpp
/tmp/ph14-ex/ex02-cpp
# C 调 C++ 包装层（先编译 C++ 实现的动态库, 再让 .c 调用）
c++ -Wall -Wextra -std=c++17 -dynamiclib ex02-cpp-lib.cpp -o /tmp/ph14-ex/libcppwrap.dylib
cc  -Wall -Wextra -std=c11 ex02-c-main.c -L/tmp/ph14-ex -lcppwrap -o /tmp/ph14-ex/ex02-c
/tmp/ph14-ex/ex02-c
# 【故意出错】无 extern "C" 守卫 → 预期链接失败（不要期望生成可执行文件）
c++ -Wall -Wextra -std=c++17 ex02-mangle-fail.cpp -L/tmp/ph14-ex -lcalc -o /tmp/ph14-ex/ex02-mangle-fail
```

### ex03 —— Python ctypes 调 C

```bash
python3 ex03-py-ctypes.py /tmp/ph14-ex/libcalc.dylib   # argv[1] 换成你的库路径亦可
```

### ex04 —— Rust extern "C" 调 C

```bash
rustc --edition 2021 -D warnings ex04-rs-ffi.rs -L /tmp/ph14-ex -l calc -o /tmp/ph14-ex/ex04-rs
/tmp/ph14-ex/ex04-rs
```

### ex05 —— opaque pointer + create/destroy（四语言）

```bash
cc   -Wall -Wextra -std=c11 -dynamiclib session.c -o /tmp/ph14-ex/libsession.dylib
cc   -Wall -Wextra -std=c11 ex05-c-handle.c -L/tmp/ph14-ex -lsession -o /tmp/ph14-ex/ex05-c && /tmp/ph14-ex/ex05-c
c++  -Wall -Wextra -std=c++17 ex05-cpp-handle.cpp -L/tmp/ph14-ex -lsession -o /tmp/ph14-ex/ex05-cpp && /tmp/ph14-ex/ex05-cpp
python3 ex05-py-handle.py /tmp/ph14-ex/libsession.dylib
rustc --edition 2021 -D warnings ex05-rs-handle.rs -L /tmp/ph14-ex -l session -o /tmp/ph14-ex/ex05-rs && /tmp/ph14-ex/ex05-rs
```

### ex06 —— 跨语言所有权约定

```bash
cc   -Wall -Wextra -std=c11 -dynamiclib bufio.c -o /tmp/ph14-ex/libbufio.dylib
cc   -Wall -Wextra -std=c11 ex06-c-ownership.c -L/tmp/ph14-ex -lbufio -o /tmp/ph14-ex/ex06-c && /tmp/ph14-ex/ex06-c
python3 ex06-py-ownership.py /tmp/ph14-ex/libbufio.dylib
rustc --edition 2021 -D warnings ex06-rs-ownership.rs -L /tmp/ph14-ex -l bufio -o /tmp/ph14-ex/ex06-rs && /tmp/ph14-ex/ex06-rs
```

## 说明

- 主文档第 6 章内嵌片段摘自本目录文件（节选关键部分，完整文件以本目录为准），两者逐字一致。
- 全部运行产物写 `/tmp/ph14-ex/`；`make clean` 删除该目录与仓库内任何 `.o`/可执行文件，验证后仓库零残留。
- macOS 的 Mach-O 符号带下划线前缀（`_calc_add`），Linux ELF 不带（`calc_add`）；`nm` 输出格式因平台而异，但"T = 可调用全局符号、t = 文件局部符号、U = 未定义（需链接满足）"的含义一致。
- Python 侧运行请勿加 `-O`：示例用 `assert` 做断言，`-O` 会移除它们。
- 耗时/输出中无与机器相关的数字，四语言输出在任意 macOS/Linux arm64/x86-64 上应一致（int32_t 定宽、无字节序相关输出）。
