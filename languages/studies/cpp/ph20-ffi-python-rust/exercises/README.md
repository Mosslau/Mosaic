# ph20 C++ 与 C / Python / Rust 互操作阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。题目与参考实现分离：本 README 只出题，答案在 `sol-*` 文件里，做完再看。

完成顺序建议：按 1~4 顺序完成。练习 1~3 与 roadmap §20「练习」小节一一对应（C++ 动态库给 Python 调用 / pybind11 包装类 / Rust 调 C++ C 接口），练习 4 是扩展题，落在 roadmap 必会概念「互操作测试必须覆盖错误路径」「字符串和容器跨语言传递需要转换层」上。参考素材：examples/ex01（C 包装层模式）、examples/ex02（ctypes）、examples/ex04（Rust FFI）——卡住先看 examples/ 的手法。

> ⚠️ 通用验收基线：C++ 侧 `clang++ -std=c++20 -Wall -Wextra` 零警告；Python 测试用 `/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3`；Rust 编译用 rustc 1.92.0（`export PATH="$HOME/.cargo/bin:$PATH"`）。动态库/可执行产物一律输出到 /tmp，仓库不落二进制。**验证状态说明**：练习 1/3/4 的参考实现已在本环境实测（标注「已验证」）；练习 2 依赖 pybind11（未 pip 安装），参考实现标「未在本环境验证」并给安装与构建命令。

## 练习 1：C++ 动态库给 Python 调用（★★★）

- **目标**：从零写一个 C ABI 动态库（一组 `extern "C"` 数值函数），用 Python ctypes 调用并断言结果与错误路径
- **要求**：
    - C++ 动态库导出 3 个函数：`tslib_sum(xs, n, *out)`（求和）、`tslib_norm2(xs, n, *out)`（L2 范数）、`tslib_max(xs, n, *out)`，签名形如 `int tslib_xxx(const double* xs, long n, double* out)`——返回 0 成功、非 0 错误码；输入是「指针 + 长度」（主文档 3.7：容器跨界只传这个）
    - 数值数组在 Python 侧用 `(ctypes.c_double * n)()` 构造；`out` 用 `byref(c_double)` 传
    - 库要覆盖两个错误路径：`xs`/`out` 为 NULL、`n <= 0`，用不同错误码表达并在 Python 侧断言
    - 用 `-dynamiclib`（macOS）编到 /tmp，Python ctypes `CDLL` 加载
- **验收**：Python 侧对 `{1,2,3,4}` 断言 sum=10、norm2≈5.477、max=4，退出码 0；对空指针/`n=0` 断言返回对应错误码而非崩溃；能口头解释「为什么数组要带长度、为什么用指针+长度而不是 vector」
- **提示**：C ABI 函数体内 `try/catch` 转错误码、先判空再进 try（ex01 手法）；NULL 与 `n<=0` 是两个不同错误码、测试要分别断言（参考实现 `sol-01-series-lib.cpp` + `sol-01-ctypes.py`）

## 练习 2：pybind11 包装类（★★★）

- **目标**：用 pybind11 把一个有状态的 C++ 类绑成 Python 类，Python 调用方拿到的是「类」而不是「句柄函数」
- **要求**：
    - C++ 类（如 `word_counter`：`add(name)` 累计计数、`total()` 返回总量、`distinct()` 返回不同词数）作为纯 C++ 核心，与绑定文件分开
    - 绑定文件用 `py::class_` + `.def(py::init<...>())` + `.def(...)`；成员函数返回 `std::string`/`size_t`
    - Python 测试：构造 → 加若干词 → 断言 `total()`/`distinct()`；至少一个方法内抛 `std::invalid_argument`，断言 Python 侧得到 `ValueError`（异常翻译）
    - 错误码一个都不用——对比练习 1 说明「pybind11 把异常翻译成 Python 异常，ctypes 只能拿错误码」
- **验收**：Python 测试全绿退出码 0；能解释 pybind11 与 ctypes 的错误表达差异（主文档 3.6）；能说出绑定付出的代价（每目标 Python 版本编译一次、依赖 pybind11 构建链）
- **提示**：`<pybind11/stl.h>` 这行别漏；`py::arg("...")` 让关键字参数可用；安装与构建命令照抄 examples/ex03 文件头（参考实现 `sol-02-word-counter.h` + `sol-02-bindings.cpp` + `sol-02-test.py`，**未在本环境验证**——pybind11 未 pip 安装）

## 练习 3：Rust 调 C++ C 接口（★★★）

- **目标**：Rust 用裸 `extern "C"` 调自己编译的 C++ dylib，错误码翻译成 `Result`，指针生命周期交给 RAII/Drop 之外的值语义
- **要求**：
    - C++ 动态库导出 2~3 个数值函数（如 `geo_dist_l2(a, b, dim, *out)` 距离、`geo_version()` 版本），错误码约定与练习 1 同构
    - Rust 单文件 `main.rs` 手抄 `extern "C"` 声明（无头文件可 include），版本检查先行，两个成功调用 + 一个错误路径调用（如 `dim <= 0`）
    - 错误码翻译成 `Result<T, i32>`（`?` 可用的形态），主函数对成功结果断言、对错误路径断言 `Err(code)`
    - 构建顺序：clang++ 编 dylib → `rustc -O main.rs -L /tmp -l geo` 直链 → 运行（无需 cargo）
- **验收**：运行输出断言全绿退出码 0；能说出每个 `unsafe` 块为何 unsafe、为什么把错误码翻译成 Result 后业务代码能零 unsafe（主文档 4.4）
- **提示**：`#[link]` 不写也行——rustc 的 `-L /tmp -l geo` 等价；注意 `c_long`/`c_int` 用 `std::os::raw` 导入；距离比较用差值的绝对值（参考实现 `sol-03-geo-lib.cpp` + `sol-03-rust.rs`，**已验证**）

## 练习 4：错误路径 + 字符串写回缓冲（扩展，★★★）

- **目标**：C ABI 库把格式化结果写进「调用者提供的 char 缓冲」，Python 覆盖「缓冲太小」「非法输入」两条错误路径——把 3.6 与 3.7 的纪律合进一个函数
- **要求**：
    - C++ 动态库导出 `tls_summarize(const double* xs, long n, char* out, long cap)`：把 `n=… sum=…` 这类文本**写进调用者缓冲**并保证 NUL 结尾；返回 0 或错误码
    - 缓冲语义显式化：`cap` 是缓冲容量；文本装不下（含 NUL）返回「缓冲太小」错误码且缓冲仍是合法 C 字符串（截断或留空，语义写进注释）
    - Python 侧 `ctypes.create_string_buffer(cap)` 分配缓冲，覆盖：正常写回（断言内容）、cap=0/过小（断言错误码且不崩溃）、xs 为 NULL
    - 顺带断言：**销毁对象/缓冲全部由 Python 侧完成**——库从不分配也不释放跨边界内存（谁分配谁释放的「调用者缓冲」形态）
- **验收**：全部断言退出码 0；能说明为什么「调用者给缓冲 + cap」比「库返回 malloc 指针」安全（零所有权转移，主文档 3.8 规则 2）
- **提示**：格式化用 `snprintf` 或 `std::snprintf`（返回「本应写入的长度」，用它判断是否截断）；NULL 与 cap 校验放在最前（参考实现 `sol-04-summarize.cpp` + `sol-04-ctypes.py`，**已验证**）

> **提示**：四个练习刻意与 examples 保持「同手法不同题目」——ex01/ex02 是 stats 引擎的完整教学演示，练习则逼你在空白库里独立走一遍同样的边界决策。做完对照 sol-* 复盘时，重点看你是否覆盖了错误路径、是否说清了每个签名上的所有权。
