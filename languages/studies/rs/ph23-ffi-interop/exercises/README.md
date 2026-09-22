# exercises —— Rust FFI 与跨语言接口设计阶段练习

四题与 roadmap 第 23 节练习一一对应（前 3 题），第 4 题补充「必会概念」中的所有权维度。每题一个参考实现目录 `sol-XX/`，**先自己做，做完再看**。每题标注难度（★~★★★）。

**本阶段铁律（贯穿全部练习）**：跨边界函数不得 panic、不把 `Result`/`String`/`Vec` 直接放上边界；内存「谁分配谁释放」必须在接口文档里写清——这正是 roadmap 验收「能让跨语言内存释放规则明确」「能让错误处理不跨 FFI 直接 panic」的训练形态。

验证环境：rustc/cargo **1.92.0**、Apple clang **21.0.0**（macOS arm64）、Python **3.13.12**；cbindgen **0.27.0**、pyo3 **0.23.5**。构建产物统一落 `/tmp`，仓库零二进制残留。所有 sol-XX 均已本机实测，标注「已验证」。

## 练习 1：导出一个 C 可调用函数（★★）

**目标**：独立完成「Rust 导出 → C 链接 → 运行验证」的最小闭环（roadmap 练习「导出一个 C 可调用函数」）。

**要求**：写一个 Cargo cdylib crate，导出两个 `#[no_mangle] pub extern "C"` 函数：`gcd(a, b)`（最大公约数）与 `lcm(a, b)`（最小公倍数），参数与返回值均为 `i64`；函数体不得 panic（输入 `lcm(0, x)` 按约定返回 0）。再写一个 C 程序声明并调用它们，编译时**同时尝试静态与动态链接各一次**。

**提示**：`crate-type` 一次声明 `["staticlib", "cdylib"]` 即可双形态；C 侧手写 `extern` 声明别把符号名写错（对照 ex01）；链接动态库的 `-Wl,-rpath` 别忘了（见 examples/README 的 ex01）。

**验收**：C 程序对 `gcd(1071, 462)` 输出 21、对 `lcm(12, 18)` 输出 36；静态链接与动态链接两种运行方式退出码均为 0。

参考实现：`sol-01-c-callable/`。

## 练习 2：用 cbindgen 生成头文件（★★★）

**目标**：让 C 侧通过**生成的头文件**而非手工声明来消费 Rust 导出（roadmap 练习「用 cbindgen 生成头文件」）。

**要求**：写一个 Rust 库 crate，导出 `#[repr(C)]` 结构体 `Fraction { num: i64, den: i64 }` 与函数 `fraction_add(a, b) -> Fraction`（分数相加，不做约分即可）。配 `cbindgen.toml`，用 `cbindgen` 生成 C 头文件到 `/tmp`；再写一个 C 程序 `#include` 该头文件，计算 `1/2 + 1/3` 并断言分子 5、分母 6。Rust 侧为相关类型/函数写 doc 注释，验证它们出现在头文件里。

**提示**：cbindgen 需在 crate 目录内运行、`--crate` 传**包名**；`#[repr(C)]` 之外的布局（`#[repr(Rust)]`）不会被导出（对照 ex05 与主文档 3.9）。

**验收**：`cbindgen` 生成的 `.h` 含 `Fraction`、`fraction_add` 及 doc 注释；C 程序编译零警告、运行输出 `5/6` 且退出码 0；把 `den` 字段改成 `u32` 后重新生成，C 侧编译器应立即报类型错误（演示「签名漂移在编译期暴露」）。

参考实现：`sol-02-cbindgen-header/`。

## 练习 3：把 Rust 函数包装成 Python 扩展（★★★）

**目标**：用 pyo3 把一个「数单词」函数包装成 Python 扩展并冒烟验证（roadmap 练习「把 Rust 函数包装成 Python 扩展」）。

**要求**：写 cdylib crate，`#[pyfunction] fn count_words(text: &str) -> usize`（按空白切分计数）与 `#[pyfunction] fn top_k_words(text: &str, k: usize) -> Vec<(String, usize)>`（出现次数前 k 的单词，平局按字典序）。用 `#[pymodule]` 注册。构建后把 `.dylib` 改名 `.so`，用 Python 冒烟：与 `text.split()` 的结果对照 `count_words`，检查 `top_k_words` 的形状。

**提示**：macOS 手动构建 `extension-module` 需 `RUSTFLAGS="-C link-arg=-Wl,-undefined,dynamic_lookup"`（见 ex06 与主文档 3.10）；`Vec<(String, usize)>` 会自动转成 `list[tuple[str,int]]`。

**验收**：Python 冒烟脚本全部断言通过且退出码 0；输入含空串或全空白文本时 `count_words` 返回 0（不 panic、不抛异常）。

参考实现：`sol-03-pyo3-extension/`。

## 练习 4：不透明句柄模式（谁分配谁释放，★★★）

**目标**：用「Rust 分配结构体句柄 → C 通过句柄调用方法 → C 调 destroy 归还」的模式，把所有权责任约束在接口层面（补充题，对应必会概念「内存由谁分配谁释放」）。

**要求**：Rust 侧定义私有结构体 `VecStore { data: Vec<f64> }`（字段**不** `pub`、**不** `#[repr(C)]`——句柄就是不透明指针）。导出：
- `vecstore_new(n) -> *mut VecStore`（空句柄，失败返回 null）
- `vecstore_push(h, v) -> c_int`（错误码：0 成功 / -1 null / -2 越界之类按你设计）
- `vecstore_get(h, i, *out) -> c_int`（读回，校验越界）
- `vecstore_len(h) -> i64`
- `vecstore_destroy(h)`（唯一合法归还通道）

写 C 程序：push 5 个值 → 全部 get 读回断言 → len=5 → destroy。**禁止** C 侧 `free()` 句柄或用 `sizeof` 访问内部——句柄对 C 是不透明类型。

**提示**：句柄方法的 null 检查放最外层；结构体字段不公开，`vecstore_get` 的越界用返回码而非 panic 表达（对照 ex03 的错误码纪律）；可先写 `cargo test` 把 Rust 内部逻辑测绿再写 C 端。

**验收**：C 程序运行断言全过、退出码 0；在 Rust 侧测试里能断言「destroy 后内存被回收」不易直接观察——改为用错误码契约证明：传入 null 句柄到任一方法都应返回负错误码而不是崩溃。

参考实现：`sol-04-opaque-handle/`。

做完四题后，「导出 → 头文件 → Python 包装 → 所有权句柄」四种边界形态都亲手搭过一遍——去 `project/` 把它们合体成一个带性能对比的 Python 加速库。
