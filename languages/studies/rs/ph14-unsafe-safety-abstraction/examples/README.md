# examples —— Unsafe Rust 与安全抽象阶段完整示例

对应主文档 `14-unsafe-safety-abstraction.md` 第 6 章示例 1~6。全部为纯 std 单文件（`rustc --edition 2021 -D warnings` 直接编译，零第三方依赖），产物统一输出 `/tmp/`，仓库零二进制残留。

验证环境：rustc 1.92.0 + Apple clang 21.0.0（macOS arm64），**全部已验证**（ex04 为「故意编译失败」，验证的是错误码）。

| 文件 | 对应示例 | 说明 | 编译 | 运行 |
|------|---------|------|------|------|
| `ex01-unsafe-keyword.rs` | 示例 1 | unsafe 关键字：unsafe 块、unsafe fn、五类 unsafe 操作（裸指针解引用/调用 unsafe fn/调用 extern fn/union 字段访问），最小 unsafe 边界 | `rustc --edition 2021 -D warnings ex01-unsafe-keyword.rs -o /tmp/ex01` | `/tmp/ex01` |
| `ex02-raw-pointers.rs` | 示例 2 | 裸指针全套：创建/判空/解引用/`as` 转换/`addr_of!`/`add`/`offset`/`offset_from`/`read`/`write`/比较 | `rustc --edition 2021 -D warnings ex02-raw-pointers.rs -o /tmp/ex02` | `/tmp/ex02` |
| `ex03-ub-demo.rs` | 示例 3 | **未定义行为（UB）演示（故意出错，首行注释写明运行前提）**：同一源码两种编译形态行为不同——部分未初始化读取（O3 折叠 poison）+ 移位溢出（debug panic vs release 静默出值） | `rustc --edition 2021 -C overflow-checks=on ex03-ub-demo.rs -o /tmp/ex03-dbg`（debug 形态）<br>`rustc --edition 2021 -C opt-level=3 ex03-ub-demo.rs -o /tmp/ex03-rel`（release 形态） | `/tmp/ex03-dbg` / `/tmp/ex03-rel` |
| `ex04-borrow-check-still-on.rs` | 示例 4 | **「unsafe 不关闭借用检查」演示（故意编译失败，首行注释写明运行前提）**：unsafe 块/unsafe fn 内借用检查照常拦截，实测四个错误码 E0594 / E0502 / E0506 / E0133 | `rustc --edition 2021 -D warnings ex04-borrow-check-still-on.rs -o /tmp/ex04`（**预期失败**） | —（不运行） |
| `ex05-ffi-libc.rs` | 示例 5 | FFI 调用基础 ①：`extern "C"` 声明并调用 libc 函数（`strlen`/`malloc`/`free`/`abs`） | `rustc --edition 2021 -D warnings ex05-ffi-libc.rs -o /tmp/ex05` | `/tmp/ex05` |
| `ex06-ffi-c-library.rs` | 示例 6 | FFI 调用基础 ②：调**自建 C 库**（`mystrlib.c`，`cc` 编译 `.dylib` + `rustc` 链接，rpath 免环境变量） | 见下方「示例 6 完整构建步骤」 | `/tmp/ex06` |
| `mystrlib.c` | 示例 6 配套 | 自建 C 库源码：`add_i32` / `mul_u64` / `point_len`（结构体传参）/ `greet`（返回字符串） | `cc -Wall -Wextra -shared -fPIC -O2 -o /tmp/libmystrlib.dylib mystrlib.c` | —（被 ex06 链接） |

## 示例 6 完整构建步骤（cc 编译 .dylib + rustc 链接，已实测）

```bash
# 1. 编译 C 库为动态库（产物到 /tmp，仓库零二进制残留；-Wall -Wextra 零警告）
cc -Wall -Wextra -shared -fPIC -O2 -o /tmp/libmystrlib.dylib mystrlib.c
# 2. 编译 Rust 并链接：-L 指向库所在目录，-l dylib=mystrlib 链接 libmystrlib.dylib；
#    -C link-args="-Wl,-rpath,/tmp" 写入运行时搜索路径，运行无需 DYLD_LIBRARY_PATH
rustc --edition 2021 -D warnings -L /tmp -l dylib=mystrlib ex06-ffi-c-library.rs -o /tmp/ex06 -C link-args="-Wl,-rpath,/tmp"
# 3. 运行
/tmp/ex06
```

## 实测输出要点

- **ex01**：`2. 调用 unsafe fn: double(21) = 42`、`3. 调用 extern fn: strlen("hello") = 5`；`4. union 字段访问 = 1080033280`（f32 3.5 的位模式按 i32 读，**平台相关**）。
- **ex02**：7 段输出全部断言通过（`x 首字节 = 0x2B`、`diff = 3` 等，见文件内注释）。
- **ex03（UB，行为差异实测）**：
  - debug 形态（`overflow-checks=on`）：`1. 部分初始化读 = 0x6FB918AA`（低字节恒为 `0xAA`，高 3 字节为栈垃圾、**每次运行不同**）→ 随后移位溢出 panic，退出码 101（`attempt to shift left with overflow`）；
  - release 形态（O3）：`1. 部分初始化读 = 0x000000AA`（优化器把未初始化字节当 poison 折叠成 0，**恒定为该值**）、`2. shift = 33, 1 << 33 = 2`（处理器硬件对移位量取模 32）、`3. 悬垂解引用 = 2`（两种形态一致，未观察到差异——UB 不保证出现可见差异，这正是其危险）。
- **ex04（预期编译失败）**：实测 `error[E0594]: cannot assign to `*r`, which is behind a `&` reference`、`error[E0502]: cannot borrow `x` as mutable because it is also borrowed as immutable`、`error[E0506]: cannot assign to `*r` because it is borrowed`、`error[E0133]: call to unsafe function `danger` is unsafe and requires unsafe function or block`。
- **ex05**：`strlen("hello") = 5`、`malloc(16) 后首字节 = 0xAB`、`abs(-42) = 42`。
- **ex06**：`add_i32(3, 4) = 7`、`mul_u64(6, 7) = 42`、`point_len(Point2D{3.0, 4.0}) = 5`、`greet() = "hello from C"`。

## 运行注意事项

- **ex03 包含 UB，仅在了解后果的前提下运行**（首行注释已写明）；其输出随编译器版本/平台/优化级别变化，文档记录的是 rustc 1.92.0 macOS arm64 实测值。
- **ex04 不会编译通过**——它是「借用检查在 unsafe 内依然生效」的实测证据文件；单独观察某个错误码可注释掉 `main` 中其它调用。
- ex01 的 union 读取、ex03 的未初始化高字节均**平台相关**（本机小端 + 栈垃圾）；ex06 的 rpath 写法仅适用于 macOS/Linux（Windows 需 `-C link-args="/LIBPATH:..."` 或拷贝 dll）。
- 全部编译产物输出到 `/tmp/`，仓库内零二进制残留。

## 验证状态汇总

- ex01/ex02/ex05/ex06：`rustc --edition 2021 -D warnings` 编译零警告并运行验证（已验证）。
- ex03：两种编译形态均实测，行为差异（poison 折叠 / 移位溢出 panic vs 静默出值）记录如上（已验证）。
- ex04：预期编译失败，四个错误码与错误文本实测后写入（已验证）。
- mystrlib.c：Apple clang 21.0.0 编译通过（-Wall -Wextra 零警告），与 ex06 联调实测（已验证）。
