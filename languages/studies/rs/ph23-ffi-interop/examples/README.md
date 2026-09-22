# examples —— Rust FFI 与跨语言接口设计阶段完整示例

对应主文档 `23-ffi-interop.md` 第 6 章。七个示例覆盖 roadmap 第 23 节全部学习内容：从「C 调 Rust 导出库」起步，依次经过字符串跨边界、错误处理跨边界、所有权转移、bindgen（C→Rust）、cbindgen（Rust→C）、pyo3（Rust→Python）——全程围绕同一纪律：**边界上只暴露 ABI 稳定类型，内存归谁分配谁释放，panic 绝不跨边界**。

验证环境：rustc/cargo **1.92.0**、Apple clang **21.0.0**（macOS arm64）、Python **3.13.12**（`/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3`）。依赖 crate 版本：bindgen **0.71.1**、cbindgen **0.27.0**（`cargo install`）、pyo3 **0.23.5**。构建产物统一落 `/tmp`（`CARGO_TARGET_DIR`），仓库零二进制残留（`.so`/`.dylib`/`.pyc`/`target/` 均不落盘，Python 一律用 `-B` 运行）。

全部示例**均已验证**（fmt / clippy `-D warnings` / cargo test / C 端链接运行全绿；数字与命令为实测）。

## 示例清单与验证状态

| 示例 | 对应主文档 | 一句话说明 | 验证状态 |
|------|-----------|-----------|---------|
| `ex01-export-c-function` | 3.1/3.2 | 把 Rust 函数导出成 C 库，C 主程序分别以**动态链接**与**静态链接**两种方式消费 | 已验证 |
| `ex02-cstring-boundary` | 3.3 | CString/CStr 三种形态：C→Rust 借用（字节数 vs UTF-8 字符数）、内嵌 NUL 截断、Rust 分配 C 归还 | 已验证 |
| `ex03-error-code-outparam` | 3.5 | 错误处理跨边界：错误码 + out 参数 + `catch_unwind` 护栏（故意 panic 也被翻译成错误码） | 已验证 |
| `ex04-bindgen-from-c` | 3.8 | bindgen 从 C 头文件生成绑定：构建期自动扫描头文件 + 编译 C 实现，Rust 安全封装后调用 | 已验证 |
| `ex05-cbindgen-header` | 3.9 | cbindgen 从 Rust 生成 C 头文件：头文件直接进 C 代码 include，签名漂移在编译期暴露 | 已验证 |
| `ex06-pyo3-module` | 3.10 | pyo3 把 Rust 函数包装成 Python 扩展：`cargo build` 产物改名 `.so` 即被 `import` | 已验证 |
| `ex07-ownership-box-transfer` | 3.6/3.7 | Box 所有权跨边界转移：Rust 分配 → C 改写 → Rust 校验 → Rust 释放（`ptr+len` 协议） | 已验证 |

## 通用质量闸门（每个含 Cargo.toml 的目录内执行）

```bash
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR=/tmp/ph23-<示例>-target   # 仓库零二进制残留的关键
cargo fmt --check
cargo clippy --<目标> --release -- -D warnings   # 见各示例说明
cargo test --release                              # ex02/ex03/ex04/ex07 有单元测试
```

> ⚠️ crate-type 只有 `staticlib`/`cdylib` 的纯导出库（ex01/ex05/ex06）**没有 rlib，`cargo test` 无测试目标可链接**——这正是「导出库的测试落在消费方」的教学点：ex01/ex05 的测试在 C 侧，ex06 的测试在 `smoke_test.py`。ex02/ex03/ex07 配了 `crate-type = ["cdylib", "rlib"]`，内部纯逻辑可直接 `cargo test`。

## 运行命令与实测输出

### ex01：C 调 Rust（动态 + 静态）

```bash
cd examples/ex01-export-c-function
export CARGO_TARGET_DIR=/tmp/ph23-ex01-target
cargo build --release                        # 同时产出 .a 与 .dylib
# 动态链接（-Wl,-rpath 让运行时找得到 dylib）
clang -Wall -Wextra -O2 caller/main.c -o /tmp/ph23-ex01-main-dyn \
    -L/tmp/ph23-ex01-target/release -lex01_export \
    -Wl,-rpath,/tmp/ph23-ex01-target/release
# 静态链接
clang -Wall -Wextra -O2 caller/main.c /tmp/ph23-ex01-target/release/libex01_export.a \
    -o /tmp/ph23-ex01-main-static
/tmp/ph23-ex01-main-dyn
/tmp/ph23-ex01-main-static
# 输出（两种链接方式一致）：
#   add(20,22)=42 mul(6,7)=42 impl=ex01-rust-cdylib (strlen=16)
```

### ex02：字符串跨边界

```bash
cd examples/ex02-cstring-boundary
export CARGO_TARGET_DIR=/tmp/ph23-ex02-target
cargo test --release            # 3 passed（字节 vs 字符 / 往返释放 / 非法 UTF-8）
cargo build --release
clang -Wall -Wextra -O2 caller/main.c -o /tmp/ph23-ex02-main \
    -L/tmp/ph23-ex02-target/release -lex02_cstring \
    -Wl,-rpath,/tmp/ph23-ex02-target/release
/tmp/ph23-ex02-main
# 输出：
#   zh: C strlen=13 bytes=13 chars=7        ← 中文字符串：字节数与字符数不同
#   with_nul: bytes=2 chars=2 (C strlen=2)  ← 内嵌 NUL：两侧都只认到第一个 NUL
#   greeting: hello from rust               ← Rust 分配 → C 读 → C 调回 Rust 释放
#   bad-utf8: bytes=2 chars=-1              ← CStr 层不报错，&str 层拒绝
```

### ex03：错误码 + out 参数 + panic 护栏

```bash
cd examples/ex03-error-code-outparam
export CARGO_TARGET_DIR=/tmp/ph23-ex03-target
cargo test --release            # 5 passed（成功/失败不写 out/null/panic 翻译/越界）
cargo build --release
clang -Wall -Wextra -O2 caller/main.c -o /tmp/ph23-ex03-main \
    -L/tmp/ph23-ex03-target/release -lex03_error \
    -Wl,-rpath,/tmp/ph23-ex03-target/release
/tmp/ph23-ex03-main
# 输出（panic 消息会打到 stderr，但进程不崩、返回 -3）：
#   "8080"   -> OK, port=8080
#   "0"      -> err=-2 (out 未被写入, 哨兵保留=57005)
#   "70000"  -> err=-2 (out 未被写入, 哨兵保留=57005)
#   "abc"    -> err=-2 (out 未被写入, 哨兵保留=57005)
#   NULL, NULL -> err=-1
#   panic_probe(0)=0 panic_probe(1)=-3 (护栏生效=yes)
```

### ex04：bindgen（C → Rust）

```bash
cd examples/ex04-bindgen-from-c
export CARGO_TARGET_DIR=/tmp/ph23-ex04-target
cargo test --release            # 3 passed（绑定 vs 纯 Rust 参考一致/长度不匹配 None/空切片）
cargo run --release
# 输出：
#   doc0: dot=20.0000 euclidean=4.4721 (C 实现经 bindgen 调用)
#   doc1: dot=25.0000 euclidean=1.0000 (C 实现经 bindgen 调用)
#   bindgen 绑定与纯 Rust 参考实现结果一致，验证通过
# build.rs 同时把生成物落在 OUT_DIR：可用以下命令查看 bindgen 0.71.1 的真实输出
find /tmp/ph23-ex04-target -name bindings.rs -exec cat {} \;
```

### ex05：cbindgen（Rust → C）

```bash
cargo install cbindgen --version 0.27.0 --locked   # 只需一次
cd examples/ex05-cbindgen-header
export CARGO_TARGET_DIR=/tmp/ph23-ex05-target
cargo build --release --manifest-path rust_lib/Cargo.toml
cd rust_lib
cbindgen --config cbindgen.toml --crate ex05-rust-lib \
    --output /tmp/ph23-ex05-target/ex05_rust_lib.h
cd ..
clang -Wall -Wextra -O2 -I/tmp/ph23-ex05-target caller/main.c \
    /tmp/ph23-ex05-target/release/libex05_rust_lib.a -o /tmp/ph23-ex05-main
/tmp/ph23-ex05-main
# 输出：
#   distance((0,0),(3,4)) = 5.0
#   quadrant((3,4)) = 1
#   tag = ex05-rust-lib
```

### ex06：pyo3（Rust → Python）

```bash
cd examples/ex06-pyo3-module
export CARGO_TARGET_DIR=/tmp/ph23-ex06-target
# macOS 手动构建 extension-module 需放开动态查找（maturin 内部同样处理）
export RUSTFLAGS="-C link-arg=-Wl,-undefined,dynamic_lookup"
cargo build --release
# 产物改名 .so 后即可被 Python import
PY=/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3
cp /tmp/ph23-ex06-target/release/libex06_geo.dylib ./ex06_geo.so
$PY -B smoke_test.py          # 冒烟：import + 3 函数 + 错误路径断言
rm -f ex06_geo.so
# smoke 输出：smoke: chunks(len=8) / cos(3,4,0 vs 0,1,0)=0.8000 / ALL OK
```

### ex07：Box 所有权跨边界转移

```bash
cd examples/ex07-ownership-box-transfer
export CARGO_TARGET_DIR=/tmp/ph23-ex07-target
cargo test --release            # 3 passed
cargo build --release
clang -Wall -Wextra -O2 caller/main.c -o /tmp/ph23-ex07-main \
    -L/tmp/ph23-ex07-target/release -lex07_ownership \
    -Wl,-rpath,/tmp/ph23-ex07-target/release
/tmp/ph23-ex07-main
# 输出：
#   allocated buf=0x… len=16
#   sum after C writes = 1240 (expect 1240)   ← C 写、Rust 读同一块内存
```

## 每个示例的看点

- **ex01**：`#[no_mangle]` + `extern "C"` 是导出的最小充分条件；`staticlib`（归档，链接进 C 可执行文件）与 `cdylib`（动态库，`-l` 链接或运行时加载）的产物差异通过两种 clang 链接命令直观对比。C 侧的手工 `extern` 声明是隐患源头——ex05 的 cbindgen 正是为此而生。
- **ex02**：同一个 C 字符串在 CStr 层（只管 NUL 结尾的字节）与 `&str` 层（必须 UTF-8 合法）是两个世界；Rust→C 的字符串必须经 `CString::into_raw` 移交所有权、并由配套的释放函数回收——**「返回字符串」不是免费的**。
- **ex03**：`Result` 不上边界，翻译规则是「返回值 = 错误码，out 参数 = 结果，成功才写 out」；`catch_unwind` 把「不该发生的 panic」也翻译成错误码——panic 穿越 `extern "C"` 是 UB（主文档 4.2），这是边界的最后一道保险。
- **ex04**：bindgen 的惯用姿势是 build.rs 构建期扫描；生成的绑定只是 `unsafe extern` 裸声明，安全封装层负责长度检查等不变量。与纯 Rust 参考实现逐位对照是本示例的自检手段——绑定调的是不是那份 C 库，用结果说话。
- **ex05**：cbindgen 把 Rust 的 `#[repr(C)]` 类型与 `extern "C"` 函数变成 C 头文件，连 doc 注释都搬过去；与 ex01 手工声明对照，自动生成的价值在于「Rust 签名一变、C 侧编译器立刻报警」。
- **ex06**：pyo3 让 Rust 函数直接变成 Python 可调函数，错误用 `PyResult`（Python 侧是异常）而不是错误码；`extension-module` 意味着产物不链接 libpython——macOS 手动构建要补 `dynamic_lookup` 链接参数，生产用 maturin 会替你处理。
- **ex07**：大块缓冲跨边界的最优载体是转移堆分配的所有权而非拷贝；`Box<[T]>::into_raw` 会丢掉长度元数据，所以协议必须是 `ptr + len` 成对传递、成对归还——「谁分配谁释放」在 slice 场景的具体形态。

## 阅读顺序建议

按主文档 3.1→3.10 推进：ex01/ex02 建立「边界长什么样」，ex03 学错误翻译，ex07 学所有权转移（这两块是「必会概念」的核心），ex04/ex05 理解两个方向的生成器（绑定 vs 头文件），最后 ex06/pyo3 看到完整的「加速模块」雏形——project 会把 ex06 的形态放大成可交付的加速库。

## 验证状态汇总

- ex01~ex07：**全部已验证**（cargo 1.92.0 + clang 21.0.0 + Python 3.13.12，本机实测；bindgen 0.71.1 / cbindgen 0.27.0 / pyo3 0.23.5，crate 均从 crates.io 在线拉取成功）
- 无任何命令输出为虚构；运行数字以你本机复现为准（工具链不同可能导致细节差异，例如静态库符号表、dylib 安装名）
