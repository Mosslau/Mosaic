# exercises —— C 与 C++ / Python / Rust 互操作阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。

四题与 roadmap ph14「练习」一一对应：练习 1「编译一个 C 动态库给 Python 调用」、练习 2「用 C++ 包装 C 接口」、练习 3「用 Rust 调用 C 函数」、练习 4「设计跨语言错误码」。共同纪律——**C 侧 `-Wall -Wextra -std=c11` 零警告、只用简单稳定类型（int32_t / const char *）、错误码 0 成功负数错误、头文件带 extern "C" 守卫**。参考实现在 `sol-*` 文件中，做完再看。

---

## 练习 1：编译一个 C 动态库给 Python 调用（★★）

- **目标**：从零写一个 C 动态库（闰年判断），编译成 .dylib，用 Python ctypes 调用并验证 4 个用例
- **要求**：
  - C 侧：`int32_t leap_is_leap(int32_t year)`，返回 **1 = 闰年、0 = 非闰年、-1 = 非法参数（year <= 0）**；头文件带 `extern "C"` 守卫；用 `cc -Wall -Wextra -std=c11 -dynamiclib` 编译（零警告）
  - Python 侧：`ctypes.CDLL` 加载后**必须显式声明 argtypes/restype**（不要依赖默认的 c_int 猜测）；4 个用例断言：`2000→1`、`1900→0`、`2024→1`、`0→-1`
  - 运行脚本不要加 `-O`（断言会被移除）
- **验收**：`python3` 运行输出 4 条断言全过、退出码 0；C 编译零警告；`-1` 错误路径被正确断言而非崩溃
- 提示：题面需要的 C 库极小，参考实现 `sol-01-py-ctypes.py` 是自包含脚本（内嵌 C 源码并在运行时编译到 /tmp）——你也可以手动编译后直接加载

## 练习 2：用 C++ 包装 C 接口（★★）

- **目标**：把 C 的 create/destroy 配对接口包装成 C++ RAII 类，杜绝忘记释放
- **要求**：
  - 给定 C 接口（opaque 句柄）：`ctr_create(label)` 返回句柄、`ctr_add`、`ctr_total`、`ctr_destroy`；create 失败返回 NULL
  - 写包装类 `Counter`：构造函数 create、析构函数 destroy（**RAII，禁止裸 new/delete 管理句柄**，C++ Core Guidelines R.11）；禁用拷贝；提供 `add` / `total` 成员
  - 演示释放确实发生：用一个"存活句柄计数"g_live，在作用域进出时打印它
- **验收**：`c++ -Wall -Wextra -std=c++17` 零警告；运行输出 total=42；**进入作用域 g_live=1、离开作用域 g_live=0**（证明析构触发了 destroy）；退出码 0
- 提示：`sol-02-cpp-wrap.cpp` 为单文件自包含——C 接口实现用 `extern "C"` 写在文件内（实际工程中那是 .c 文件，链接语义一致）；对照参考实现时注意"包装类"与"C 接口实现层"的分工

## 练习 3：用 Rust 调用 C 函数（★★★）

- **目标**：用 `extern "C"` + `unsafe` 调用 C 动态库，并把 C 的错误码映射为 Rust 的类型化结果
- **要求**：
  - 复用练习 1 的 leap 库（或自己写一个等价库），先编译 `libleap.dylib`
  - Rust 侧：`#[link(name = "leap")] extern "C" { fn leap_is_leap(year: i32) -> i32; }`；调用必须在 `unsafe` 块内
  - 写 `fn leap(year: i32) -> Result<bool, LeapError>`：`1 → Ok(true)`、`0 → Ok(false)`、`-1 → Err(...)`（C 的错误码不直接泄漏到 Rust 业务代码里）
  - 4 个用例断言，断言信息要有意义（用 assert_eq! / match，不要裸 unwrap）
- **验收**：`rustc --edition 2021 -D warnings` 零警告；运行输出 4 条断言全过、退出码 0
- 提示：`sol-03-rs-ffi.rs` 头部注释给了完整的两步命令（先 cc 编译 C 库、再 rustc 链接）；`-L` 指向库所在目录、`-l leap` 找 `libleap.dylib`

## 练习 4：设计跨语言错误码（★★）

- **目标**：为跨语言接口设计一套稳定、可追踪的错误码 + 错误消息，并在 C 中实现、自测
- **要求**（设计契约，写进头文件注释）：
  - **0 = 成功；负数为错误码**；数值与含义一一对应，**一经发布不再改值**（ABI 稳定优先）
  - **不使用 errno**：errno 是 C 的线程局部全局，ctypes / Rust FFI 读取麻烦且不可移植——错误码走 `err_out` 出参，消息走 `errstr` 函数（静态字符串，借用）
  - 实现一个小句柄 API 并让**每种错误都能被确定性触发**（如：空 label → BADARG、label 超长 → TOOLONG、push 超过上限 → FULL）；自测 main 逐一触发并断言 errstr 内容
  - 在注释里说明 Python / Rust 侧如何消费：Python `byref(c_int)` 读 err_out、`c_char_p` 读 errstr；Rust `*mut c_int` + `*const c_char`
- **验收**：`cc -Wall -Wextra -std=c11` 零警告；运行输出每个错误码的 errstr 与设计一致、PASS 计数全过、退出码 0

> **提示**：练习 1~4 依次对应主文档 3.6（Python ctypes）、3.5（C++ 调 C 与包装层）、3.7（Rust FFI）、3.4（错误码与错误消息）的知识与 examples/ 对应示例——先独立完成，再对照 `sol-*` 复盘。所有 sol 文件头的「验证环境/编译/运行/验证状态」块里的数字与输出均来自本机（Apple clang 21.0.0 + Python 3.13.9 + rustc 1.92.0，macOS arm64）实测。
