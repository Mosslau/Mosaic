# examples —— C++ 与 C / Python / Rust 互操作阶段完整示例

验证环境（实测）：macOS arm64，Apple clang 21.0.0（`clang++`/`clang`，默认 PATH）+ Homebrew clang 21.1.8（仅 dylib 交叉编译核对）、Python 3.13.12（`/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3`）、rustc/cargo 1.92.0（`export PATH="$HOME/.cargo/bin:$PATH"`）、cxx crate 1.0.199（cargo fetch 拉取成功）。**已在本环境实测**：ex01（C 包装层 + C 宿主，双 clang 交叉）、ex02 ctypes、ex04 rustc 直链与 ex04-cxx-bridge（cxx 双向桥）、ex05、ex06 的 Makefile 兜底路径。**未在本环境验证**：ex02-cffi 与 ex03（pybind11 未 pip 安装）、ex06 的 CMake 路径（本机未装 cmake）——这三处的安装与构建命令都已写在文件头。代码写法以零警告为目标（C++ `-Wall -Wextra`、C 宿主 `-Wall -Wextra`、Rust 无警告）；C 包装层 create/destroy 里的 new/delete 是「谁创建谁销毁」教学主题，注释已说明。**动态库/可执行/cargo target 一律输出到 /tmp 或构建后清理，仓库不落二进制**。以下命令在 examples/ 目录内执行。

| 文件 | 说明 | 验证状态 |
|------|------|----------|
| `ex01-stats-core.h` + `ex01-stats-c-api.h` + `ex01-stats-wrap.cpp` + `ex01-host-main.c` | C 包装层全流程：C++ 核心类 → opaque + 错误码 → C 宿主 include 链接调用；双编译器交叉 | 已验证（Apple clang 21.0.0 与 Homebrew clang 21.1.8 均零警告、运行断言全绿） |
| `ex02-stats-ctypes.py` | Python ctypes 调同一 C ABI：签名声明 + RAII 包装 + 错误路径 | 已验证（Python 3.13.12） |
| `ex02-stats-cffi.py` | 同库的 cffi ABI 模式版本：声明字符串即文档 | 未在本环境验证（cffi 未 pip 安装；`python3 -m pip install cffi` 后即可跑） |
| `ex03-greeter.h` + `ex03-greeter-bindings.cpp` + `ex03-test.py` | pybind11 绑 C++ 类：`py::class_` + STL 自动转换 + 异常自动翻译 | 未在本环境验证（pybind11 未 pip 安装；安装与构建命令见文件头） |
| `ex04-stats-ffi.rs` | Rust extern "C" 裸 FFI 调同一 C ABI：单文件 rustc 直链 + RAII 壳 + Result 翻译 | 已验证（rustc 1.92.0） |
| `ex04-cxx-bridge/` | cxx crate 双向桥（完整 cargo 工程）：Rust↔C++ 互相调用 + 类型翻译 | 已验证（cxx 1.0.199，首次构建需网络拉取 crate，本机成功） |
| `ex05-error-host.cpp` | 异常 → 错误码：NULL/空样本/NaN 三条错误路径逐条触发并断言 | 已验证（Apple clang 21.0.0） |
| `ex06-cmake-cross-build/` | CMake 跨语言构建目标图 + 无 CMake 等价 Makefile | CMake 路径未在本环境验证（未装 cmake）；Makefile 路径已验证（make test 退出码 0） |

> 依赖关系：ex02/ex04/ex05 都消费 ex01 编出的 `/tmp/libvtest.dylib`，请先跑 ex01 步骤 1。ex06 的 Makefile 会自动从 `../ex01-*` 重建该库。全部产物在 /tmp 或构建目录，examples/ 不落二进制。

## 示例 1：C 包装层 + C 宿主（ex01-*）

对应主文档 3.1 与 roadmap 学习内容「C 包装层」。C++ `running_stats` 类（`std::vector` + 异常）被擦成 C 能表达的三种东西：opaque 句柄、extern "C" 函数、int 错误码。C 宿主 include 头链接调用，并断言空样本错误路径：

```bash
# 1. 编 dylib（Apple clang，C++20）：
clang++ -std=c++20 -Wall -Wextra -dynamiclib ex01-stats-wrap.cpp -o /tmp/libvtest.dylib
# 2. 编 C 宿主并运行（预期：count=3 mean=4.0 rc=0 err_empty=2，退出码 0）：
clang -std=c11 -Wall -Wextra ex01-host-main.c -L/tmp -lvtest -o /tmp/ph20-ex01-host
/tmp/ph20-ex01-host
# 3.（可选）Homebrew clang 交叉编译核对：
/opt/homebrew/opt/llvm/bin/clang++ -std=c++20 -Wall -Wextra -dynamiclib ex01-stats-wrap.cpp -o /tmp/libvtest_hb.dylib
clang -std=c11 -Wall -Wextra ex01-host-main.c -L/tmp -lvtest_hb -o /tmp/ph20-ex01-host-hb && /tmp/ph20-ex01-host-hb
# 4.（可选）看导出表：_vtest_stats_*（C 链接）与 __ZN5vtest…（内部 C++ mangled）并存：
nm -gU /tmp/libvtest.dylib
```

教学要点：① 头文件 `__cplusplus` 守卫包 `extern "C"`，C/C++ 双编译器各读各的形态；② **opaque** 让任何一侧想 `delete` 句柄都被编译器拒绝（不完整类型）；③ **谁创建谁销毁**——new/delete 只发生在包装层，跨侧释放是红线；④ **异常在 extern "C" 函数体内 catch 干净**，`std::runtime_error`→`VTEST_ERR_EMPTY`、`std::invalid_argument`→`VTEST_ERR_VALUE`、`catch(...)`→`VTEST_ERR_INTERNAL`，边界上只有错误码；⑤ 三个错误码常量（`VTEST_ERR_*`）就是这份 C ABI 的「失败词汇表」，C/Python/Rust 三种接收方各自翻译成本语言的失败表达（3.6）。

## 示例 2：Python ctypes / cffi 调同一 C ABI（ex02-*）

对应主文档 3.2 与 roadmap 练习「C++ 动态库给 Python 调用」。先跑 ex01 步骤 1 编出 dylib：

```bash
# 1. ctypes（已验证）：
/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3 ex02-stats-ctypes.py
# 预期：mean via ctypes = 4.0, empty-index err = 2 / ctypes driver OK，退出码 0
# 2. cffi（未在本环境验证——cffi 未安装）：
#    安装：python3 -m pip install cffi，再运行：
#    python3 ex02-stats-cffi.py
```

教学要点：① `CDLL` 运行期按名字加载 dylib，ctypes 是「无编译胶水」路径；② **`argtypes`/`restype` 是类型安全护栏**——不声明时指针默认当 `int`，arm64 上 8 字节指针截断即段错误；③ 句柄在 Python 侧只是 `c_void_p` 整数，不能释放——RAII 收口：类包装 + `__del__` 调 destroy（3.8）；④ 错误路径（空样本 → 错误码 2）也走了断言，证明「失败跨了语言还是失败、且可预测」（3.6）；⑤ cffi 把 C 声明写成字符串、加载期解析——声明即文档、签名错误加载期暴露，是 ctypes 的对照面。

## 示例 3：pybind11 绑 C++ 类（ex03-*）

对应主文档 3.3 与 roadmap 练习「pybind11 包装类」。**pybind11 未在本环境 pip 安装，本示例标「未在本环境验证」**；安装与构建命令（写全，供读者环境执行）：

```bash
# 1. 安装 pybind11（选择目标解释器）：
/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -m pip install pybind11
# 2. 编译扩展模块（在 examples/ 目录内；产物进当前目录 Python 才能 import）：
PY=/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3
EXT=$($PY -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')
clang++ -std=c++20 -Wall -Wextra -O3 -shared -fPIC $($PY -m pybind11 --includes) \
    ex03-greeter-bindings.cpp -o greeter"$EXT"
# 3. 运行测试：
/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3 ex03-test.py
```

教学要点：① `py::class_<T>` + `.def(py::init<Args...>())` 把 C++ 类原样变成 Python 类——**没有 opaque、没有错误码**，这是它与 ex01/ex02 的根本差异；② `<pybind11/stl.h>` 让 `std::vector<std::string>` ↔ Python `list[str]` 自动拷贝转换（3.7 转换层的自动化形态）；③ `std::invalid_argument` 由 pybind11 自动翻译成 Python `ValueError`（3.6 异常翻译表）；④ 代价是必须为每个目标 Python 版本编译一次扩展，且只有 Python 这一侧受益——若同时服务 C/Rust 生态，C 包装层仍是共同底座。

## 示例 4：Rust FFI 与 cxx 双向桥（ex04-*）

对应主文档 3.4 与 roadmap 练习「Rust 调 C++ C 接口」。两条互补路径，均已实测。先跑 ex01 步骤 1 编出 dylib：

```bash
# 1. 裸 extern "C" 单文件（rustc 直链，已验证）：
export PATH="$HOME/.cargo/bin:$PATH"
rustc -O ex04-stats-ffi.rs -L /tmp -l vtest -o /tmp/ph20-ex04
/tmp/ph20-ex04
# 预期：rust FFI OK: count=3 mean=4.0 empty_err=2，退出码 0
# 2. cxx 双向桥（子目录 cargo 工程，已验证；首次构建拉取 cxx crate 需网络）：
cd ex04-cxx-bridge && cargo run
# 预期：cpp_sum = 15 / cpp_describe = hello Alice, from Rust / cpp_compose(7) = 22
```

教学要点：① 裸 FFI 的签名与 C 头**手抄一致**（Rust 没有头文件可 include，注释里对照 ex01-stats-c-api.h）；② 所有 FFI 调用 `unsafe`，用 RAII 壳（`Drop` 调 destroy）与 `Result<T, i32>` 把 unsafe 面收到最小——业务代码零 unsafe（4.4）；③ cxx 的 `#[cxx::bridge]` 声明三类东西：`unsafe extern "C++"`（Rust 调 C++）、`extern "Rust"`（C++ 回调 Rust）、共享 struct；构建期 cxxbridge 生成桥接代码，类型自动翻译（`&Vec<i64>` ↔ `rust::Vec<int64_t>`），`cpp_describe` 的输出证明「Rust→C++→Rust」完整闭环（4.5）；④ 手工 extern "C" 与 cxx 的选择：单向小接口用裸 FFI，双向深类型互操作用 cxx。

## 示例 5：异常 → 错误码 → 错误路径（ex05-error-host.cpp）

对应主文档 3.6 与 roadmap 必会概念「异常不要直接穿过 C ABI」「互操作测试必须覆盖错误路径」。先跑 ex01 步骤 1：

```bash
# 1. 编译并运行错误路径宿主：
clang++ -std=c++20 -Wall -Wextra ex05-error-host.cpp -L/tmp -lvtest -o /tmp/ph20-ex05
/tmp/ph20-ex05
# 预期：err(NULL)=1 err(empty)=2 err(nan)=3 ok_add=0，然后 error-translate OK，退出码 0
```

教学要点：① 三个错误码对应三种 C++ 侧失败——空指针（判空，不进 try）、空样本（`std::runtime_error`）、NaN 输入（`std::invalid_argument`），「哪个异常 → 哪个错误码」是 API 设计的一部分；② 若某条异常漏网穿过 extern "C"，会一路跑到 C 的栈帧上无人 unwind——轻则 `terminate` 重则 UB，所以每条边界都 `catch(...)` 兜底；③ **互操作测试覆盖错误路径**不是加分项——错误翻译代码只在错误路径执行，这条路径不测等于没测。

## 示例 6：CMake 跨语言构建（ex06-cmake-cross-build/）

对应主文档 3.5 与 roadmap 学习内容「CMake 跨语言构建」。一个 CMakeLists 把「C++ 包装层静态库 + C 宿主 + Python 侧测试」编排进同一目标图。**本机未安装 CMake，CMake 构建标「未在本环境验证」**；同目录 Makefile 是等价编排（命令与 ex01/ex02 实测一致，已验证）：

```bash
# 1. CMake 路径（需要 cmake；macOS 可 brew install cmake）：
#    cd ex06-cmake-cross-build
#    cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure
# 2. 无 CMake 等价路径（已验证）：Makefile 自动从 ../ex01-* 重建库并跑 C 宿主 + ctypes 测试：
cd ex06-cmake-cross-build && make clean && make test && make clean
```

教学要点：① CMake 的价值是**编排不是替代**——C++ 库 `add_library`、C 宿主 `add_executable`、ctypes 路径零编译只要 `find_package(Python3)`、pybind11 路径才要扩展目标；② ex04-cxx-bridge 的 build.rs 演示了 Rust 侧的同类编排（`cxx_build::bridge` 把 C++ 源与生成桥一起编译）；③ 两种编排对比能看出跨语言构建的共同形状：**每个编译器各管各的产物，构建系统只负责把它们连进同一张目标图**（4.6）。

## 验证状态汇总

| 示例 | 工具链 | 状态 |
|------|--------|------|
| ex01（dylib + C 宿主） | Apple clang 21.0.0 + Homebrew clang 21.1.8 | 已验证（双编译器零警告、断言全绿） |
| ex02 ctypes | Python 3.13.12 | 已验证 |
| ex02 cffi | Python 3.13.12 + cffi（未安装） | 未在本环境验证 |
| ex03 pybind11 | clang++ + pybind11（未安装） | 未在本环境验证 |
| ex04 rustc 直链 | rustc 1.92.0 | 已验证 |
| ex04-cxx-bridge | cargo 1.92.0 + cxx 1.0.199 | 已验证（首次需网络拉取 crate） |
| ex05 错误路径宿主 | Apple clang 21.0.0 | 已验证 |
| ex06 CMake 路径 | cmake（未安装） | 未在本环境验证 |
| ex06 Makefile 兜底 | make + 上述工具链 | 已验证（make test 退出码 0） |
