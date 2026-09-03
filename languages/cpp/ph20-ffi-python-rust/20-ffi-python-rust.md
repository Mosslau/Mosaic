# C++ 与 C / Python / Rust 互操作阶段

> 面向「跨语言系统集成」方向：从 ph19 的 C ABI 边界出发，把 C++ 能力安全地暴露给 C / Python / Rust——先学会 C 包装层（opaque 句柄 + 错误码 + 生命周期纪律）这门通用手艺，再分别走 ctypes/cffi、pybind11、extern "C" FFI 与 cxx 双向桥四条路径，最后用 CMake 把跨语言构建收进同一套构建系统。核心只有一句话：**边界上的每一件事——错误、字符串、容器、内存所有权——都要有一份显式约定，C++ 的便利（异常、std::string、RAII）全部留在边界之内**。

## 1. 概述

本阶段是学习路线的第 20 步（roadmap ph20 目标：能在跨语言系统中安全暴露 C++ 能力）。ph19 把「单个进程内的 C++ 二进制边界」讲完了：ABI、extern "C"、动态库、opaque 句柄、谁创建谁销毁。当时的预告是：**这些纪律一旦把接收方从「宿主插件」换成「另一种语言」，就变成互操作的全部地基**。本阶段兑现这条预告——C 包装层不再是「给 dlopen 宿主用的接口风格」，而是一种被 C 编译器、CPython 的 ctypes、Rust 的 `extern "C"` 共同消费的通用协议；pybind11 与 cxx 则是在这份协议之上、为「少写胶水」而生的高层绑定。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 语言边界协议 | extern "C" + opaque 句柄 + 错误码 + 接口版本检查；一份 C 头被 C / Python / Rust 三种接收方消费 |
| C 包装层 | 把 C++ 类映射成 C 句柄 API 的模式：create/destroy 成对、方法变函数、异常变错误码 |
| Python 侧 | ctypes / cffi 两条「无编译胶水」路径调 C ABI；pybind11 一条「编译期强类型」路径绑 C++ 类与 STL |
| Rust 侧 | 裸 `extern "C"` FFI（unsafe 边界 + RAII 包装）；cxx crate 双向桥（bridge 宏 + 类型翻译 + C++ 回调 Rust） |
| 跨语言构建 | CMake 多目标统一构建（add_library 的 C ABI 库 + Python 扩展 + C/Rust 宿主），与 cargo build.rs 的配合 |
| 错误与异常 | 异常不穿 C ABI：C 包装层 catch 转错误码；pybind11 异常翻译成 Python 异常；Rust 侧错误码 → Result |
| 字符串与容器 | `std::string` / `std::vector` 不出边界；UTF-8 字节、尺寸 + 指针、定长 struct 的跨语言约定 |
| 内存所有权 | 谁分配谁释放：opaque create/destroy、调用者缓冲 vs 库内分配 + 释放函数、各语言侧的 RAII 收口 |
| 心智模型 | 公共边界越简单越稳定；互操作测试必须覆盖错误路径；跨语言所有权靠约定与语言侧 RAII 双重落实 |

这个阶段只涉及**把 C++ 能力暴露给 C / Python / Rust 的 FFI 与绑定工程**：C 包装层、ctypes/cffi、pybind11、extern "C" FFI、cxx 双向桥、CMake 跨语言构建、异常/字符串/容器/所有权的跨语言转换，**不涉及 ph21 数据结构与算法（roadmap 第 21 节，目录待建——本阶段的示例只用最简单的数组与线性扫描，任何「用哪种数据结构」的讨论都留给它）、ph22 存储引擎与数据库内核在 C ABI 层的商业化（roadmap 第 22 节，目录待建——真实 WAL/SSTable/Compaction 引擎对外暴露稳定 C ABI 的工程结合，本阶段 project 的「向量检索库」只是玩具级 C ABI demo）、ph23 向量检索与 AI 推理的完整产品化（roadmap 第 23 节，目录待建——HNSW/IVF-PQ 近似索引、SIMD 距离、Faiss/TensorRT 的工程体系，本阶段只做 brute-force 距离计算与线性 top-k，且仅作为 FFI 的教学载体）**。动态库的加载机制、符号可见性、dlopen 细节属于 ph19，本阶段引用结论不再展开；本阶段是 ph21~ph23 的「跨语言前置课」——届时把存储引擎、向量检索库卖给 Python 生态时，走的正是这里学的 C ABI + 绑定。

## 2. 来源与演变

互操作的历史不是「某家语言征服别的语言」的历史，而是**「C ABI 成为所有语言共同的汇合点」的历史**。设计哲学一句话：**每种语言都有自己的运行时、类型系统与对象模型，但几乎所有语言的编译器都能调用 C 函数、都被 C 的函数调用约定与内存布局约束——于是「以 C 为中间语言」成为跨语言互操作的事实标准；高层绑定库的本质，都是在这条 C 边界上把「类型翻译、错误翻译、所有权翻译」做自动化**。

1980 年代末 System V ABI 让同一平台上的 C 编译器彼此兼容后，C 就成了 Unix 世界的 Lingua Franca。1990 年代脚本语言（Tcl/Python/Perl）崛起，需要调用 C/C++ 库，早期只能手写 CPython C API 胶水（每个函数手写引用计数、拆包参数）；**SWIG**（1996，David Beazley）第一个把「从接口描述文件生成多种语言胶水」做成工具——一条 `.i` 文件同时产出 Python/Perl/Java 绑定，代价是生成代码黑盒、出问题难调试。C++ 侧真正滋养绑定库的是 **boost.python**（David Abrahams，2002）：首次用模板元编程在 C++ 里声明式地描述绑定，让「写绑定的代码」接近「写普通 C++」。它太重太慢，促成了 **pybind11**（Wenzel Jakob，2016 前后）——用 C++11 的变参模板与完美转发重做同一思路，头文件即库、一套代码同时支持类绑定/STL 自动转换/异常翻译。Python 侧还有一条「不要编译器」的支流：**ctypes**（2002 年进标准库，Thomas Heller）让 Python 在运行期按声明加载 dylib/.so 并调用，靠 `argtypes/restype` 把类型检查做在 Python 层；**cffi**（2013，PyPy 资助）提供「C 声明即文档」的 ABI/API 双模式，比 ctypes 更接近原生性能。Rust 侧，2015 年 1.0 稳定后 FFI 一直是第一公民：早期靠裸 `extern "C"` + **bindgen**（从 C/C++ 头自动生成 Rust 绑定）；**cxx**（David Tolnay，2019）则更进一步——用 `#[cxx::bridge]` 宏在一个模块里同时声明 C++ 与 Rust 两侧接口，构建期生成双向桥接代码，把「&str↔String、Vec、shared struct」的类型翻译与所有权（`rust::Box`）自动化，让 Rust 安全地调用 C++ 类、C++ 侧也能安全地回调 Rust。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| System V ABI | 1988~ | C 调用约定与结构体布局标准化——所有后续互操作的物理底座 |
| CPython 扩展 API | 1991~ | Python 首次能以 C 扩展形态调用 C 库；手写胶水时代 |
| SWIG | 1996 | 从接口描述文件自动生成多语言（Python/Perl/Java）胶水；生成代码黑盒 |
| boost.python | 2002 | C++ 模板元编程声明式绑定库；启发了 pybind11 的语法面 |
| ctypes 进标准库 | 2002 | Python 运行期加载并调用 C ABI，无需编译胶水；`argtypes/restype` 显式签名 |
| cffi | 2013 | C 声明字符串驱动；ABI 与 API 双模式；PyPy 生态主力 |
| pybind11 | 2016 | C++11 变参模板重做 boost.python：类绑定 + STL 自动转换 + 异常翻译，头文件即库 |
| Rust FFI 稳定 | 2015~2016 | `extern "C"` / `#[link]` 稳定；bindgen 自动从 C/C++ 头生成 Rust 绑定 |
| cxx | 2019 | `#[cxx::bridge]` 双向桥：类型翻译与所有权自动化，C++ 可安全回调 Rust |
| CMake pybind11/FetchContent 生态 | 2015~ | `find_package(pybind11 CONFIG)` 让「C++ 库 + Python 扩展」进同一套 CMake 构建 |

本文示例以 **C++20** 为基线（互操作机制本身与语言标准版本关系弱——决定它的是 C ABI、工具链与绑定库；C++20 决定示例语法面与 libc++ 运行时版本），验证工具链为 **Apple clang 21.0.0**（`clang++`/`clang`，默认 PATH；Homebrew clang 21.1.8 已做 dylib 交叉编译核对）、**Python 3.13.12**（`/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3`）、**rustc/cargo 1.92.0**（`~/.cargo/bin`）、**cxx crate 1.0.199**（本机 cargo fetch 拉取成功）、macOS arm64 + libc++ + dyld。环境实况：**CMake 未安装、pybind11 与 cffi 未 pip 安装**——凡涉及三者的构建命令一律标注「未在本环境验证」并给出安装步骤，其余 C ABI 包装层、ctypes、Rust FFI、cxx 双向桥均在本机做了真实双向编译验证。这套知识的跨语言差异集中在「语法面与工具名」一层，机制（C ABI 边界、错误翻译、所有权约定）完全互通。

## 3. 语法与参数

> 本节代码块为**教学骨架**：聚焦单个主题做了裁剪。完整可运行文件见第 6 节与 [`examples/`](./examples/)，构建/运行命令见 examples/README.md（C ABI / ctypes / Rust FFI / cxx 示例已在本环境实测；pybind11 / cffi / CMake 示例因依赖未安装标「未在本环境验证」，但命令与文件头均给出完整安装与构建步骤）。文档内嵌片段标注来源文件与验证状态。

### 3.1 C 包装层：把 C++ 类翻译成 C 句柄 API

跨语言边界上第一条铁律（ph19 已立）：**`std::string`、`std::vector`、异常、引用、vtable 一律不出边界，边界上只走 C ABI**。于是把 C++ 能力暴露给任何语言，第一步永远是写一层「C 包装层」——它把 C++ 类「擦」成三件 C 能表达的东西：**opaque 句柄**（类实例的地址，外面只知道它是不透明指针）、**C 链接函数**（extern "C"，无 mangling、可被 dlsym/ctypes/Rust 按名找到）、**int 错误码**（替代异常）。逐条映射规则：

| C++ 侧 | C ABI 侧 | 说明 |
|--------|---------|------|
| `class running_stats { ... }` | `struct vtest_stats;`（前向声明）+ `typedef` | opaque：完整类型只活在 C++ 翻译单元 |
| 构造函数 / 析构函数 | `vtest_stats* create(void)` / `void destroy(vtest_stats*)` | 谁创建谁销毁，new/delete 永远留在库内同一侧 |
| 成员函数 `void add(double)` | `int vtest_stats_add(vtest_stats*, double)` | 首参变句柄；返回错误码 |
| 成员函数 `double mean() const` | `int vtest_stats_mean(const vtest_stats*, double* out)` | out 参数显式化（F.20 在 C ABI 上的反例——但 C ABI 没有返回值结构，约定俗成用 out） |
| 异常 `throw std::runtime_error(...)` | `return VTEST_ERR_EMPTY;` | 异常在 C ABI 函数体内被 catch，转错误码（3.6 展开） |

```c
// examples/ex01-stats-c-api.h —— C 包装层对外头文件（节选，全量见 examples/）
// 验证环境：Apple clang 21.0.0（C++20 dylib 侧）交叉编译实测通过
#ifdef __cplusplus
extern "C" {
#endif
/* 错误码：跨 C ABI 的错误一律走它，异常不出库 */
enum {
    VTEST_OK = 0,
    VTEST_ERR_NULL = 1,     /* 收到空句柄/空输出指针 */
    VTEST_ERR_EMPTY = 2,    /* 尚无样本，mean 无定义 */
    VTEST_ERR_INTERNAL = 99 /* 其余异常兜底 */
};
/* opaque 句柄：完整类型藏在 C++ 侧，本头只有前向声明 */
struct vtest_stats;
typedef struct vtest_stats vtest_stats;

vtest_stats* vtest_stats_create(void);   /* 谁创建谁销毁 */
void vtest_stats_destroy(vtest_stats* s);
int vtest_stats_add(vtest_stats* s, double value);      /* 0=成功，其余=错误码 */
int vtest_stats_mean(const vtest_stats* s, double* out);
int vtest_stats_version(void);                          /* 版本检查（ph19 3.7） */
#ifdef __cplusplus
}
#endif
```

头文件用 `__cplusplus` 守卫包住 `extern "C"`，C 编译器与 C++ 编译器读到各自正确形态；句柄类型在 C 侧是不完整 `struct` 指针、在 C++ 侧是同一前向声明——**任何一侧想直接 `delete` 它都会被编译器拒绝**，销毁的唯一合法路径是库导出的 `vtest_stats_destroy`（ph19 的 opaque 纪律原样搬进语言边界）。包装实现里每个函数 `try { ... } catch` 转错误码、指针先判空，保证边界上永不抛异常：

```cpp
// examples/ex01-stats-wrap.cpp —— 包装实现（节选）
extern "C" int vtest_stats_mean(const vtest_stats* s, double* out) {
    if (s == nullptr || out == nullptr) return VTEST_ERR_NULL;
    try {
        *out = reinterpret_cast<const vtest::running_stats*>(s)->mean();
        return VTEST_OK;
    } catch (const std::runtime_error&) { return VTEST_ERR_EMPTY; }  // 语义化错误码
    catch (...) { return VTEST_ERR_INTERNAL; }                        // 兜底，绝不外抛
}
```

**为什么这层值得为每一种语言重写一次**：C 包装层是所有接收方的最小公分母——C 宿主 include 头直接调；Python 用 ctypes/cffi 按名找；Rust 用 `extern "C"` 声明同款签名。三种接收方共享同一份「错误码 + opaque + create/destroy」约定，跨语言测试只需覆盖它。这也是 roadmap「公共边界越简单越稳定」的落地：C++ 侧越复杂的类型系统越难翻译，边界上只剩 C 能表达的三种东西，翻译成本反而最低。

> 教学性简化说明：为聚焦 FFI 主题，本阶段示例的 C++ 核心类刻意做成「Rule of Zero 的极简类」（内部只有一个 `std::vector`），R.11 的 new/delete 只出现在 C 包装层的 create/destroy 内部——那是「谁创建谁销毁」的教学主题而非规范违例，注释已说明。

### 3.2 Python 调 C ABI：ctypes 与 cffi 两条无编译路径

Python 调用 C++ 导出的 C 接口，最低摩擦的路径是 **ctypes**（标准库，零依赖）：它在运行期 `CDLL` 加载 dylib/.so，按名字取函数、按声明定签名，全程不需要 C 编译器。关键是把签名写对——`argtypes`/`restype` 声明就是你的类型安全护栏（不声明时 ctypes 默认把整数当 `int`、把指针当 `int`，在 arm64 上指针截断立刻崩）：

```python
# examples/ex02-stats-ctypes.py —— ctypes 调 C++ 导出的 C ABI（节选）
# 验证环境：Python 3.13.12，实测运行通过
import ctypes

lib = ctypes.CDLL("/tmp/libvtest.dylib")
# 声明签名：restype/argtypes 是 ctypes 的类型护栏，指针一律 c_void_p/c_poiner
lib.vtest_stats_create.restype = ctypes.c_void_p
lib.vtest_stats_destroy.argtypes = [ctypes.c_void_p]
lib.vtest_stats_add.argtypes = [ctypes.c_void_p, ctypes.c_double]
lib.vtest_stats_add.restype = ctypes.c_int
lib.vtest_stats_mean.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double)]

h = lib.vtest_stats_create()          # 句柄是 void*，Python 只存不解释
assert h, "create failed"
assert lib.vtest_stats_add(h, 2.0) == 0
mean = ctypes.c_double()
assert lib.vtest_stats_mean(h, ctypes.byref(mean)) == 0   # byref 传 out 指针
lib.vtest_stats_destroy(h)            # 谁创建谁销毁：库内释放
```

**cffi** 是同一件事的另一种做法：它把 C 声明写成字符串，由 cffi 在运行期解析并按声明绑定（ABI 模式，不需要编译器），声明本身即文档、签名错误在加载期就暴露；做 Python ↔ C++ 高吞吐数据交换时通常比 ctypes 快。二者取舍见 3.3 末的对比表。ctypes 能调通说明「这份 C ABI 对任意语言的运行期绑定器都成立」——**语言边界上别做任何 Python 特有假设**，这也是为什么 C 头里只有 `extern "C"`、指针和错误码。

> cffi 未在本环境 pip 安装，示例 `examples/ex02-stats-cffi.py` 标「未在本环境验证」；运行前先 `python3 -m pip install cffi`（安装命令见文件头）。ctypes 路径已实测，cffi 的教学点只多「ABI 模式声明即文档」一条，不影响主线理解。

### 3.3 pybind11：Python 侧的高层绑定

ctypes/cffi 是「无编译胶水」，代价是每个函数都要手工声明签名、类的方法要一个个包成函数。**pybind11** 是反面：一次编译生成原生 Python 扩展模块，类直接变成 Python 类、STL 容器自动转换、异常自动翻译——Python 调用方完全看不到 C ABI。绑定代码用 C++11 变参模板写「声明式」绑定：

```cpp
// examples/ex03-greeter-bindings.cpp —— pybind11 绑定模块（节选）
// 验证状态：未在本环境验证（pybind11 未 pip 安装）；安装与构建命令见文件头
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>          // STL 自动转换：vector/string <-> list/str
#include "ex03-greeter.h"          // 纯 C++ 核心类头（单头实现，无需单独 .cpp）

namespace py = pybind11;

PYBIND11_MODULE(greeter, m) {
    m.doc() = "pybind11 包装 C++ 类的示例";
    py::class_<greeter::greeter>(m, "Greeter")
        .def(py::init<std::string>())                    // 构造绑定
        .def("greet", &greeter::greeter::greet)          // 成员函数 → 方法
        .def("shout_all", &greeter::greeter::shout_all); // 返回 vector<string>
}
```

**`<pybind11/stl.h>` 一行打开 STL 自动转换**：`std::vector<std::string>` ↔ Python `list[str]`、`std::string` ↔ `str`，边界两侧各按自己的对象模型持有数据、转换即拷贝——这正是「std::string/vector 不出 C ABI 边界」在 pybind11 世界里的样子：**pybind11 的转换层替你完成了 3.7 要讲的字符串/容器翻译，翻译产物是原生 Python 对象**。绑定 C++ 类时几个必须懂的关键词：

| pybind11 机制 | 作用 | 对应本阶段心智 |
|--------------|------|---------------|
| `py::class_<T>(m, "Name")` | 把 C++ 类注册成 Python 类型 | opaque 句柄的高层化：Python 对象持有 C++ 对象指针 |
| `.def(py::init<Args...>())` | 绑定构造（单参构造注意 `py::init` 显式） | create/destroy 成对的语言侧自动化 |
| `<pybind11/stl.h>` | STL ↔ Python 内建容器拷贝转换 | 3.7 转换层：拷贝是默认安全策略 |
| `return_value_policy` | 返回值所有权策略：`automatic`/`take_ownership`/`copy`/`reference_internal` | 3.8 所有权：谁拥有返回值、谁负责释放 |
| `py::keep_alive<N, M>` | 把对象生命周期绑到另一对象上 | 引用型返回值的生命周期约定 |
| 异常翻译（3.6） | `std::exception` 自动映射内置异常；自定义 `py::register_exception` | 错误/异常跨语言翻译 |
| `py::gil_scoped_release` | 释放 GIL 让 C++ 长任务不被 Python 线程阻塞 | 4.3 GIL 纪律 |

**pybind11 的适用边界**：它要求一次完整编译、要求 Python 头文件与 pybind11 库、产出的扩展模块绑定具体 Python 版本（ABI 层面是 CPython 扩展，不是纯 C ABI）。若你的目标是「让 Python 生态调用一个纯 C ABI 库」——ctypes/cffi 足矣且零构建；若目标是「把 C++ 类原样变成 Python 类，让 Python 开发者调用 C++ 方法、容器、异常」——pybind11 是标准答案。它不解决「其他非 Python 语言调用」的问题，那条路仍回到 C 包装层（3.1）。

### 3.4 Rust 侧：extern "C" 裸 FFI 与 cxx 双向桥

Rust 调用 C++ 导出的 C 接口，最底层是 **extern "C" 裸 FFI**：在 Rust 侧声明与 C 头逐字一致的 `extern "C"` 函数签名，链接时把 dylib 交给链接器，调用处全部 `unsafe`。Rust 没有 C 头文件可 include，**签名必须手抄**（与 C++ 侧用同一份 C 头做人的核对；bindgen 类工具可自动生成，本阶段手写以看清机制）：

```rust
// examples/ex04-stats-ffi.rs —— Rust extern "C" 调 C++ 导出的 C ABI（节选）
// 验证环境：rustc/cargo 1.92.0，实测运行通过
extern "C" {
    fn vtest_stats_create() -> *mut VtestStats;
    fn vtest_stats_destroy(s: *mut VtestStats);
    fn vtest_stats_version() -> i32;
    fn vtest_stats_add(s: *mut VtestStats, value: f64) -> i32;
    fn vtest_stats_mean(s: *const VtestStats, out: *mut f64) -> i32;
}
```

Rust 的安全模型要求所有 FFI 调用 `unsafe`，于是工程惯例是**把裸 FFI 包进安全类型**：opaque 句柄存进结构体，`Drop` 里调用 `destroy`——等价于 C++ 的 RAII、Python 侧的 `__del__`，语言侧 RAII 收口（3.8）。错误码映射成 `Result<_, i32>`，把「C ABI 的错误码」翻译成 Rust 的 `?` 语法世界。这一层做厚之后，业务 Rust 代码零 `unsafe`。

**cxx** 则把整个「手抄签名 + unsafe 调用 + 手工所有权」再自动化一步。它的核心是 `#[cxx::bridge]` 模块：在同一个 Rust 文件里声明三类东西——`unsafe extern "C++"`（引用 C++ 侧头文件里实现好的函数/类，签名以 `include!` 的 C++ 头为准）、`extern "Rust"`（Rust 实现、生成 C++ 侧声明，让 C++ 能回调 Rust）、共享 struct（`repr(C)`，两语言各持一份）。构建期 `cxxbridge` 生成桥接 `.cc`/`.h`，类型翻译与所有权自动处理：

```rust
// examples/ex04-cxx-bridge/src/main.rs —— cxx 双向桥（节选）
// 验证环境：cxx crate 1.0.199 + rustc/cargo 1.92.0，实测双向调用通过
#[cxx::bridge]
mod ffi {
    unsafe extern "C++" {
        include!("cpp_side.h");
        fn cpp_sum(values: &Vec<i64>) -> i64;      // Rust → C++（Vec 自动翻译）
        fn cpp_describe(name: &str) -> String;
        fn cpp_compose(x: i32) -> i32;             // 内部会回调下面的 rust_triple
    }
    extern "Rust" {
        fn rust_triple(x: i32) -> i32;             // C++ → Rust（cxx 生成 C++ 声明）
    }
}
fn rust_triple(x: i32) -> i32 { x * 3 }
```

cxx 与裸 FFI 的本质差异：**裸 FFI 的边界是「你自己手写的 extern 块」，unsafe 与所有权全在你身上；cxx 的边界是「cxxbridge 生成的桥接层」，它把 `&str`/`String`/`Vec`/`Box<T>` 翻译成 `rust::Str`/`rust::String`/`rust::Vec`/`rust::Box<T>`（C++ 侧的 RAII 类型），所有权随值自动管理**。cxx 甚至允许 C++ 侧持有 Rust 类型（`rust::Box<...>`）并安全析构。选择上：只想「Rust 调一个 C ABI 库」——裸 FFI 最轻，一个文件搞定（本阶段 ex04 主路径）；要「C++ 与 Rust 双向、深类型（类、String、Vec）互操作、长期维护」——cxx 把 unsafe 面收敛到桥接模块声明处。**Roadmap 学习内容「Rust cxx/FFI」即这两条路径，主文档与 examples/ex04 双双落地**。

### 3.5 CMake 跨语言构建：一个构建系统管所有语言

跨语言工程的构建天然是「多种编译器的编排」：C++ 库是 clang++ 的活，Python 扩展也是 clang++（但带 Python 头与 pybind11），C 宿主是 clang，Rust 侧则是 cargo（rustc + cc 驱动 C++ 桥接编译）。**CMake 的价值不是替代这些编译器，而是把它们统一编排进一套目标图**：

```cmake
# examples/ex06-cmake-cross-build/CMakeLists.txt —— 跨语言构建（节选，源码路径用 ../ 指向 ex01-*）
# 验证状态：未在本环境验证（本机未安装 cmake）；无 CMake 等价 Makefile 已实测（见目录内 Makefile）
cmake_minimum_required(VERSION 3.20)
project(ph20_ex06 LANGUAGES CXX C)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(EX01_DIR ${CMAKE_CURRENT_SOURCE_DIR}/..)

add_library(vtest_core STATIC ${EX01_DIR}/ex01-stats-wrap.cpp)   # 1. C++ 包装层核心
target_include_directories(vtest_core PUBLIC ${EX01_DIR})
add_executable(c_host ${EX01_DIR}/ex01-host-main.c)              # 2. C 宿主
target_link_libraries(c_host PRIVATE vtest_core)

# 3. Python 侧：ctypes 路径零编译（只要解释器可查，运行期 CDLL 加载）……
find_package(Python3 COMPONENTS Interpreter REQUIRED)
add_test(NAME python_ctypes COMMAND ${Python3_EXECUTABLE} ${EX01_DIR}/ex02-stats-ctypes.py)
# ……pybind11 扩展路径才需要扩展目标（未装 pybind11 时 find 失败自动跳过）：
find_package(pybind11 CONFIG QUIET)
if(pybind11_FOUND)
    pybind11_add_module(greeter ${EX01_DIR}/ex03-greeter-bindings.cpp)
    target_include_directories(greeter PRIVATE ${EX01_DIR})
endif()
```

Rust 侧的构建编排略有不同：cargo 自己管 Rust 目标，C++ 依赖经 `build.rs` 的 `cxx_build::bridge(...)`/`println!("cargo:rustc-link-...")` 声明；与 CMake 的关系通常是**外层 CMake 把 C++ 库编好、cargo 用 build.rs 链接它，或 CMake 直接调 `cargo build` 把二进制纳入安装**（本阶段 project 用 Makefile 编排同构流程，见 project/README.md）。CMake 的三个高频用途记牢即可：**① C++ 库用 `add_library` 独立成目标供 C/Python/Rust 复用；② Python 扩展用 `pybind11_add_module`（需要 `find_package(pybind11 CONFIG)`）或对纯 C ABI 库干脆不建扩展目标、由 Python 侧 ctypes 运行期加载；③ 一切输出路径、安装规则由 CMake 统一，各语言产物各归其位**。

### 3.6 错误转换：异常不穿 C ABI，错误码不穿类型系统

ph19 的红线在语言边界上放大成一份完整的三段式翻译表——**C++ 的异常、C 的错误码、Python 的异常、Rust 的 Result，是同一种「失败」在四种语言里的四种表达**，跨语言边界时必须在每一层边界上显式转换一次：

| 边界 | 失败如何表达 | 翻译动作 |
|------|------------|---------|
| C++ 内部 | `throw` 异常（E.2/E.14） | 不跨任何语言边界，随便用 |
| C++ → C ABI | 必须 catch 干净，返回 int 错误码 | 每个 extern "C" 函数体 `try/catch`：语义化错误码 + 兜底 catch(...) |
| C ABI → Python ctypes | 错误码是 int | Python 侧 if 分支或封装成 `OSError` 子类；`ctypes.get_errno()` 可取 errno 风格细节 |
| C++ → pybind11 | 异常 | `std::exception` 派生自动翻译成对应 Python 内置异常；自定义异常 `py::register_exception` |
| C ABI → Rust | 错误码是 i32 | 映射成 `Result<T, i32>` 或强类型错误 enum |
| C ABI → C++（自己内部） | 错误码 | `switch` 后可选再抛回异常（还原成 C++ 世界） |

```cpp
// examples/ex01-stats-wrap.cpp —— 包装实现：异常 → 错误码（节选）
// 验证环境：Apple clang 21.0.0，实测运行通过
extern "C" int vtest_stats_add(vtest_stats* s, double value) {
    if (s == nullptr) return VTEST_ERR_NULL;      // 指针错误：先判空再进 try
    try {
        reinterpret_cast<vtest::running_stats*>(s)->add(value);
        return VTEST_OK;
    } catch (const std::invalid_argument&) {      // C++ 异常 → 语义化错误码
        return VTEST_ERR_VALUE;
    } catch (...) { return VTEST_ERR_INTERNAL; }  // 兜底：异常绝不穿 C ABI（ph19 红线 3）
}
```

为什么 C ABI 侧「必须 catch 干净」是硬规则而不是风格：C ABI 的调用约定没有异常展开信息——异常若穿过 extern "C" 函数跑到 C/Python/Rust 的栈帧上，那些栈帧不知道如何 unwind，轻则 `std::terminate` 重则未定义行为（Itanium ABI 的异常展开依赖 `.eh_frame` 与语言运行时配合，跨语言栈上没有这套合作机制）。**于是「哪个异常对应哪个错误码」本身就是 API 设计**：空样本的 mean → `VTEST_ERR_EMPTY`、NaN 输入 → `VTEST_ERR_VALUE`，C++ 侧的异常类型层次（`std::runtime_error` vs `std::invalid_argument`）直接翻译成错误码层次。错误细节若还需要给人看的文本，边界上再加一个「取最近错误消息」函数（调用者给缓冲、库填 UTF-8），错误码给程序分支用、消息给人诊断用。

**pybind11 侧的异常翻译是「自动」的**：绑定函数内抛出的 `std::exception` 派生会被 pybind11 转成对应 Python 异常（`std::runtime_error` → `RuntimeError` 等），无需 C 包装层那套错误码——因为它生成的扩展边界自带异常翻译表。但**理解 C 包装层那套手工 catch，是理解 pybind11 自动翻译的前提**：pybind11 只是在生成代码里替你做了「catch → 查翻译表 → `PyErr_SetString`」。Rust 侧若用裸 FFI 调 C ABI，错误码是回传的整数，翻译成 `Result` 是 Rust 侧一行 match 的事（ex04 的 `Err(rc)`）。**互操作测试必须覆盖错误路径**（roadmap 必会概念）：空输入、空指针、越界、版本不足、重复释放——错误翻译代码几乎不跑成功路径，只有测试错误路径才证明边界翻译是对的（project 的验收标准逐条列了错误路径断言）。

### 3.7 字符串与容器转换层：std::string/vector 不出边界

跨语言传字符串与容器，本质问题相同：**两侧的对象模型不同、内存布局不同、所有权语义不同**。`std::string`（SSO 缓冲 + 堆指针 + 长度，libc++ 特有布局）直接跨边界 = 按对方布局读你的内存，是 UB；`std::vector` 同理。唯一安全的共同表示是 **C 层的「指针 + 长度（或 NUL 结尾）+ 显式所有权」**。三种数据形态的约定：

| 数据形态 | C ABI 约定 | Python 侧 | Rust 侧 |
|---------|-----------|----------|---------|
| 定长数值（double/int/float） | 按值传 | ctypes `c_double` 等 | Rust `f64`/`i32`（`repr` 一致） |
| 字符串 | `const char*` UTF-8 + NUL（只读借用）或 `char* buf + size`（写入） | `ctypes.c_char_p` / `create_string_buffer`；Python `str.encode()` 传字节 | `std::ffi::CString`/`CStr`；cxx 里自动变 `rust::String` |
| 数值数组 | `const double* data + size_t n`（只读） | `(ctypes.c_double * n)()` 数组或 numpy `.ctypes` | `&[f64]`（as_ptr + len）；cxx 里自动变 `rust::Slice` |
| 结构体数组 | `struct result* out + size_t cap`（写入，见 project） | `ctypes.Structure` 子类数组 | `#[repr(C)]` struct + 指针/长度 |

字符串的三条工程纪律：**① 编码显式化——边界上统一 UTF-8 字节**，Python 侧 `str.encode('utf-8')`、Rust 侧 `CString::new`、C++ 侧 `std::string` 内部即 UTF-8，谁都不猜编码；**② 借用与所有权分开写进签名**——`const char*` 表示「只读借用、生命周期=调用期间」，写回则用「调用者给缓冲 + size，库填数据」；**③ NUL 截断陷阱**——C 风格字符串天然不能含 `'\0'`，二进制数据必须走「指针 + 长度」。数值数组同理：只读计算传 `(ptr, len)`；要回填结果数组，调用者分配、库写、显式传容量（project 的 `vec_index_search` 就是 `out + cap + &count` 形态，稍后 6 节展开）。

容器的「跨语言转换」因此总是一个**拷贝或借用**的动作，三种接收方各有默认策略：

| 语言侧 | 默认策略 | 后果 |
|--------|---------|------|
| ctypes | 显式构造 C 数组（`(c_double * n)()`）或 numpy `.ctypes` | 转换代码可见；零隐藏拷贝可控制 |
| pybind11（`<pybind11/stl.h>`） | 边界自动拷贝 std::vector ↔ list | Python 侧所见即所得；大数据来回拷贝有成本，用 `py::array`/numpy 时走缓冲区协议 |
| cxx | 类型翻译：`Vec<T>` ↔ `rust::Vec<T>`，自动管理 | 转换在生成代码里；大数据量大时考虑 slice |

> ⚠️ 一句话总纲：**「转不转、拷贝还是借用、谁拥有」必须在签名上显式**。凡是 C 头里出现 `const char*`/`const double*` 都默认「只读借用」；凡是写回数据的指针都默认「调用者分配的缓冲」；任何「库分配、调用者释放」的返回指针，都必须配一个库导出的释放函数（下一节）。模糊的签名是跨语言事故的温床——把约定写进 C 头注释，每种语言的绑定方各读各的语言版。

### 3.8 跨语言内存所有权：谁分配，谁释放

跨语言边界上最贵的事故永远是**资源在错误的一侧被释放**（ph19 红线 1 的跨语言版）。两侧若堆不同（Windows 跨 CRT、Rust 的默认分配器与 libc++ 的 operator new 在 macOS/Linux 上通常同源、能碰巧活着），跨侧释放就是 UB。所有权的三条硬规则 + 三个语言侧收口：

**规则 1：谁分配谁释放，且释放函数必须由分配侧导出。** C++ 库 `new` 的 opaque 对象，只允许库导出的 `destroy` 释放（ex01/ex05 的 create/destroy 成对）；Rust 若 `Box::into_raw` 把一个 Rust 对象交给 C++，则必须由 Rust 导出的 `extern "C"` 释放函数接回去（cxx 的 `rust::Box<T>` 自动做这件事）。释放函数跨语言传递时不随调用栈移动——它是**契约的一部分**，不是实现细节。

**规则 2：跨边界内存的三种归属形态，签名上写死。** ① opaque 句柄（create/destroy 持有）；② 调用者分配的缓冲（调用者分配、调用者释放、库只读写——零所有权转移，最安全，project 的回填数组即此形态）；③ 库内分配并返回指针（必须配套释放函数，返回结构体如 `{data, size, destroy_fn}` 或单独 release 入口）。

**规则 3：各语言侧用自己的 RAII 收口，让人「忘不掉」。**

```cpp
// Rust 侧 RAII（examples/ex04-stats-ffi.rs）：Drop 保证任何退出路径都归还库内销毁
impl Drop for Stats {
    fn drop(&mut self) {
        unsafe { vtest_stats_destroy(self.raw) }
    }
}
```

```python
# Python 侧收口（examples/ex02 的完整版驱动）：句柄包成类，__del__ 兜底归还
class Stats:
    def __init__(self) -> None:
        self._h = lib.vtest_stats_create()
        if not self._h:
            raise MemoryError("create failed")
    def __del__(self) -> None:          # 引用计数归零即归还（CPython 语义下确定性强）
        if self._h:
            lib.vtest_stats_destroy(self._h)
            self._h = None
```

Python 的 `__del__`（CPython 引用计数确定触发）、Rust 的 `Drop`（作用域退出确定触发）、C++ 自己的 RAII——**三种语言用三种机制表达同一条纪律：对象死在创建它的语言里，由语言运行时保证调用时机**。句柄在 Python 里就是 `c_void_p`（一个整数地址），在 Rust 里是 `*mut` 裸指针，在 C 里是 `struct tag*`——全部不可由接收方释放，语言侧 RAII 把「归还」绑定到对象生命周期。跨语言所有权还包含另一个方向：**谁借用了谁的生命周期**——ctypes 里把 `array` 传进库，库若缓存该指针、Python 侧 array 被 GC，库就悬空了（所以库的 API 要么拷贝要么声明「借用仅限调用期」）。互操作测试覆盖的典型错误路径：重复 destroy（double free）、destroy 空指针、忘 destroy（泄漏检测）、用后释放（use-after-free）——project 的验收清单用 ASan 逐一兜底。

## 4. 底层原理

### 4.1 C ABI 层传参与结构体布局：跨语言一致性的物理基础

跨语言调用能成立，物理前提是**两侧对「函数怎么被调用、数据在内存里怎么摆」有完全一致的假设**。单平台上这套假设就是 C ABI（macOS arm64 上为 Apple 平台的 ABI 文档，遵循 arm64 AAPCS 变体）：参数如何进寄存器/栈、返回值放哪、struct 按什么规则对齐与填充（padding）、`double`/`long` 占多少字节。C 编译器、C++ 编译器、Rust 编译器、CPython 扩展编译器在同一个 macOS 上产出同一套 C ABI 调用约定——所以 C 头里按值传的 `double`、`int`，四侧读到的是同一位型。**结构体布局是这套一致性的脆弱点**：

```text
跨语言 struct 布局一致性（必须在 C 头里定死）：
struct search_hit {
    int64_t id;     // 8 字节对齐起始
    float   score;  // 4 字节，随后按 struct 对齐填 4 字节 padding
};
// 内存总长：16 字节。C/C++/Python(ctypes.Structure)/Rust(#[repr(C)])
// 若任何一侧把 id 改成 int 或调整字段顺序，整张表错位。
```

Rust 侧必须写 `#[repr(C)]`（默认 Rust 布局可任意重排字段）；Python 侧 `ctypes.Structure` 的 `_fields_` 顺序即内存顺序；C/C++ 侧 struct 布局由编译器按 ABI 规则排。**只要声明一致，四侧共享同一份字节**；任何一侧偷偷改布局（字段顺序、宽度、加 padding 感知差异）就是 ph19 的 struct 布局事故跨语言重演——这就是为什么跨语言 struct 也要走「接口版本号」纪律（ph19 3.7）。另一个物理细节：**指针宽度**。arm64 上指针 8 字节，Python 侧不声明 `argtypes` 时默认按 `int`（4 字节）截断传参——3.2 强调签名声明的底层原因在此。

### 4.2 符号可见性：只有 C ABI 符号能被别的语言找到

语言边界上「dlsym/ctypes/CDLL 按字符串名字找符号」，所以**导出表就是你的公共接口清单**（ph19 3.6 结论的语言边界版）：别的语言能找到的只有你导出的符号——C++ 的 mangled 名（`__Z...`）也能找，但任何语言绑定都不该依赖它（绑死编译器版本）。工程姿势照搬 ph19：`-fvisibility=hidden` + 白名单 `extern "C"` 显式导出。绑定库的符号要求各不同：ctypes 只要 `CDLL` 能找到白名单函数即可；pybind11 产出的扩展模块（`.so`）本身就是给 Python 的，符号导出由模块机制管理；Rust 侧若反过来要导出给 C++ 用，则 `#[no_mangle] extern "C"` + 同样受可见性纪律约束。**一句话：语言边界 = 符号白名单 + C ABI 形态，缺一不可**。

### 4.3 GIL 与 Python 线程：长调用的两把钥匙

CPython 的全局解释器锁（GIL）保证同一时刻只有一个线程执行 Python 字节码。跨语言调用与 GIL 的交道分两把钥匙：

| 场景 | GIL 行为 | 后果与对策 |
|------|---------|-----------|
| ctypes 调用外部函数 | **ctypes 在调用期间自动释放 GIL**（外部 C 函数运行时不持锁） | Python 其他线程可并发跑；长 C++ 调用不卡死整个进程——但你的 C++ 函数若回调 Python（callback），需重新拿 GIL |
| pybind11 绑定函数 | 默认持有 GIL 进入 C++ | C++ 长任务会阻塞所有 Python 线程；对策：函数内 `py::gil_scoped_release` 释放、结束前 `py::gil_scoped_acquire` 拿回 |

```cpp
// pybind11 长计算释放 GIL（示意，pybind11 未安装故标未验证）
double heavy_calc() {
    py::gil_scoped_release release;   // 离开作用域即释放；C++ 计算期间不占 GIL
    return run_long_computation();    // 此时 Python 其他线程可运行
}
```

这把钥匙的深层含义：**GIL 保护的是 Python 对象的引用计数与内部状态**，一旦进入纯 C++/C ABI 世界（不碰 Python 对象），锁就不该再被持有。ctypes 默认帮你做对了；pybind11 需要显式声明，因为 C++ 代码随时可能回调 Python（那时必须持锁）。Rust FFI 与 GIL 无关（除非走 PyO3 绑 Python，属 ph20 之外的自选方向）。多线程 + 互操作的完整测试（TSan 能抓到跨语言数据竞争吗？）留给扩展，本阶段只要懂「谁在什么时候持锁」。

### 4.4 Rust unsafe 边界：把不安全关进最小笼子

Rust 的 FFI 全部 `unsafe`，安全模型要求**unsafe 面最小化**。裸指针生命周期、空指针、越界、悬垂——`extern "C"` 声明本身无法携带这些信息，编译器把责任全部交给程序员。工程惯例是「薄薄一层 unsafe 桥 + 厚厚的安全壳」：桥层只做「取指针、判空、调用、翻译错误码」（3.4 的 `Stats::new/add/mean`），所有裸指针在桥层内立即被安全类型（`Option`/`Result`/RAII 包装）吸收，业务代码零 unsafe。这条纪律与 C++ 的 RAII、Python 的 `__del__` 是同一种设计哲学的三种方言：**把「必须手动做对」的边界纪律收进语言机制能自动执行的壳里**。

### 4.5 cxx 生成层原理：bridge 宏之后的代码长什么样

cxx 的魔法不在运行时而在**构建期代码生成**。`#[cxx::bridge]` 模块经 `cxxbridge` 展开成两类产物：一是 Rust 侧对每个 `unsafe extern "C++"` 项的 FFI 声明（带类型翻译与 `rust::Vec`/`rust::String` 等 C++ RAII 包装类型的构造代码）；二是 C++ 侧对每个 `extern "Rust"` 项生成的 C++ 声明（放进 `main.rs.h` 之类桥接头），并在 C++ 里生成调用 Rust 函数所需的 FFI 桩。build.rs 里 `cxx_build::bridge("src/main.rs").file(...)` 把生成的 C++ 源与你的 `.cc` 一起编进静态库，链接进 Rust 二进制。**类型翻译表是理解 cxx 的钥匙**：Rust `&str` → C++ `rust::Str`（借用）、`String` → `rust::String`（拥有）、`Vec<T>` → `rust::Vec<T>`（拥有）、`Box<T>` → `rust::Box<T>`（拥有，跨侧析构安全）——与 3.7 的转换层是同一张表，只是 cxx 把它变成编译器检查过的生成代码而不是人肉约定。cxx 并没有消灭 C ABI：生成的桥接层底层仍是 extern "C" 函数与 C 布局结构，但那些函数由生成器保证两侧签名逐字一致——**把 3.4 里「手抄签名」这个最易错的动作自动化了**。

### 4.6 跨语言调用全景：从 C++ 类到 Python 对象

```text
C++ 核心类 running_stats（异常/vector/RAII，完全不出边界）
   │  C 包装层：extern "C" + opaque + 错误码（3.1/3.6，唯一被所有人消费的形态）
   ▼
C ABI dylib（导出表 = 白名单 C 符号）
   ├── C 宿主     include C 头，链接期绑定（ex01）          ←─ clang
   ├── Python     ctypes 运行期 CDLL + 签名声明（ex02）      ←─ 无编译
   │              pybind11 编译期绑定模块（ex03）            ←─ clang++ + pybind11
   └── Rust       extern "C" 裸 FFI（ex04 主路径）           ←─ rustc/cargo
                  cxx #[cxx::bridge] 双向桥（ex04-cxx）      ←─ cargo + cxxbridge
跨语言构建编排：CMake（ex06，本机未验证）或 Makefile（project，已实测）
```

四层视角值得各停一秒：**类型翻译**发生在语言边界（指针/长度/UTF-8 是共同语）；**错误翻译**发生在每一条边界上（catch→错误码→Result/异常）；**所有权翻译**发生在每一条边界上（谁分配谁释放 + 语言侧 RAII）；**构建翻译**发生在构建期（各编译器各管各的，CMake/cargo/Makefile 只是编排）。理解了这四张翻译表，互操作就不是魔法而是四份显式约定的叠加。

## 5. 使用场景

**选择哪条绑定的判断逻辑**，一张表说清：

| 场景 | 选什么 | 为什么 / 注意 |
|------|--------|--------------|
| 让 Python 调用一个已存在的纯 C ABI 库（本阶段 project 的形态） | **ctypes**（或 cffi） | 零编译、零依赖；库是 C ABI 就没有 Python 扩展要维护 |
| 想用一份 C 声明同时服务多种语言的运行期绑定器 | **cffi** | 声明即文档；性能通常好于 ctypes；需要 pip 安装 |
| 把 C++ 类原样变成 Python 类（方法、容器、异常、继承） | **pybind11** | 编译期强类型 + STL/异常自动翻译；绑定方要维护一套编译 |
| 只是给 Python 写一层薄加速，无跨语言类型要映射 | 先考虑 ctypes 指向的纯 C ABI 库 | 别为三个函数引入一套 pybind11 构建链 |
| Rust 调一个 C ABI 库（单向、接口小） | **extern "C" 裸 FFI** | 一个文件；手抄签名 + unsafe 桥最小化 |
| Rust 与 C++ 深度互操作：C++ 类/容器 + 双向回调 + 长期维护 | **cxx** | 生成代码保证签名一致；所有权自动化；首次拉 crate 需网络 |
| C++ 库的接口同时服务多种语言生态（C/Python/Rust 都要） | C 包装层 + 各语言自选高层 | 3.1 的最小公分母永远先建；高层绑定只是替各语言少写胶水 |
| 性能敏感的大量数据来回传 | ctypes + 缓冲区共享 / pybind11 + py::array | 别逐元素跨边界调用（ph18/4.x 的边界成本课）；批量化 + 大块缓冲 |

**反模式清单**：① 让 `std::string`/`std::vector`/异常直接穿过语言边界——跨语言版本 UB 且无编译器护栏；② 每个函数都走高层绑定库而库里其实只有几个数值运算——构建链成本大于收益；③ 没有版本检查的 C ABI 库给多个语言用——任何一侧改 struct 布局，所有接收方静默错位（ph19 3.7 跨语言版）；④ 逐元素跨边界调用（Python 里 for 循环里逐个调 C++ 函数）——每次调用付边界 + GIL 成本，应整批传数组；⑤ 互操作测试只跑成功路径——错误翻译代码几乎从不执行成功路径，错误路径不测等于没测（roadmap 必会概念）。判断口诀：**先问「这个 C ABI 库是否本来就该存在」（最小公分母），再问「哪种语言侧体验值得为此引入绑定层」**。

**与其他语言的对比**（为 analysis/ 与 Tenet 合成积累素材）：

| 维度 | C++ 本阶段做法 | C | Rust | Python（被调方视角） | Go |
|------|---------------|----|------|---------------------|-----|
| 暴露能力给其他语言 | C 包装层 + pybind11/cxx 等绑定 | 本身就是 C ABI | `#[no_mangle] extern "C"` + bindgen/cxx | 写 C 扩展 / Cython | cgo 的 C 互操作边界 |
| 异常/错误跨界 | catch 转错误码；pybind11 自动翻译 | 只有错误码/errno | Result ↔ 错误码（无异常跨 FFI） | 异常留在解释器内，扩展侧是 C 错误码 | panic 不跨 cgo 边界 |
| 类型翻译工具 | 手工 C 头 + 绑定库生成 | 手工头文件（即标准） | bindgen/cxx 生成 | ctypes 声明/numpy 缓冲 | cgo 类型映射约定 |
| 边界安全机制 | opaque 前向声明禁 delete（编译期） | 无（全约定） | unsafe 显式 + 所有权类型收口 | 解释器兜底（段错误在解释层难救） | 运行时/编译期混合 |
| 深层类比 | 本阶段四层翻译表 = 「互操作最小纪律集」 | 同左（源头） | 把翻译收进类型系统 | 用运行时便利换二进制自由度 | 绑定运行时最重 |

**给 Tenet 语言合成的启示**：跨语言互操作的全部成本集中在「类型翻译、错误翻译、所有权翻译、构建翻译」四张表上。C++ 选择「手工 + 绑定库」，绑定库（pybind11/cxx）的价值证明**编译器生成翻译层是可行的**——若语言自带「C ABI 导出是显式语言特性（extern 块）+ 翻译声明进类型系统（repr/自动桥）」的设施，可以把当前分散在三个工具链的纪律收进一份语言级契约。判断哪种做法最接近「语言原生」的标准：**边界纪律有多少能被编译器检查，而不是靠文档约定**。

## 6. 代码示例

> 说明：`examples/` 目录代码按主题编号，验证状态逐文件标注。**已在本环境实测**（Apple clang 21.0.0 + Python 3.13.12 + rustc/cargo 1.92.0，编译零警告、运行通过）：ex01（C 包装层 + C 宿主）、ex02（ctypes）、ex04（Rust extern "C"：rustc 直链 + ex04-cxx-bridge 的 cargo 双向桥工程）、ex05（异常转错误码）、project（Python 调 C++ 向量检索库）。**未在本环境验证**（依赖未安装，命令与安装步骤已给出）：ex02-cffi、ex03（pybind11）、ex06（CMake——本机未装 cmake，附等价手工命令）。ex04-cxx 子目录依赖 cxx crate（本机 cargo fetch 拉取成功并实测通过）。完整命令见 [`examples/README.md`](./examples/README.md)，以下展示关键片段。

### 示例 1：C 包装层 + C 宿主（examples/ex01-stats-c-api.h + ex01-stats-wrap.cpp + ex01-host-main.c）

对应 3.1 与 roadmap 学习内容「C 包装层」。C++ `running_stats` 类经 opaque 句柄 + 错误码暴露，C 宿主 include 头链接调用，并覆盖空样本错误路径：

```bash
# 1. 编 dylib（C++ 包装层）：
clang++ -std=c++20 -Wall -Wextra -dynamiclib ex01-stats-wrap.cpp -o /tmp/libvtest.dylib
# 2. 编 C 宿主并运行（输出 count=3 mean=4.0 err_empty=2，退出码 0）：
clang -std=c11 -Wall -Wextra ex01-host-main.c -L/tmp -lvtest -o /tmp/ph20-ex01-host && /tmp/ph20-ex01-host
```

### 示例 2：Python ctypes（与 cffi）调同一 C ABI（examples/ex02-stats-ctypes.py + ex02-stats-cffi.py）

对应 3.2 与 roadmap 练习「C++ 动态库给 Python 调用」。ctypes 路径已实测；cffi 依赖未安装，标未验证并给出 `pip install cffi` 命令：

```bash
# 1. 先按示例 1 编出 /tmp/libvtest.dylib，然后运行 ctypes 驱动：
/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3 ex02-stats-ctypes.py
# 预期：count=3 mean=4.0 err=2（错误路径返回错误码而非崩溃），最后打印 ctypes driver OK
```

### 示例 3：pybind11 绑定类（examples/ex03-greeter.h/.cpp + ex03-greeter-bindings.cpp + ex03-test.py）

对应 3.3 与 roadmap 练习「pybind11 包装类」。绑定 `Greeter` 类 + STL 自动转换 + 异常自动翻译。**pybind11 未在本环境安装**，标「未在本环境验证」，安装与构建命令在文件头：

```bash
# 1. 安装 pybind11（选择其一；装进示例使用的解释器）：
/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -m pip install pybind11
# 2. 编译扩展模块（-shared 产物进当前目录，Python 才能 import；命令见文件头）：
#    PY=/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3
#    EXT=$($PY -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')
#    clang++ -std=c++20 -Wall -Wextra -O3 -shared -fPIC $( $PY -m pybind11 --includes ) \
#        ex03-greeter-bindings.cpp -o greeter$EXT
# 3. 运行测试：
#    python3 ex03-test.py
```

### 示例 4：Rust FFI 与 cxx 双向桥（examples/ex04-stats-ffi.rs + ex04-cxx-bridge/）

对应 3.4 与 roadmap 学习内容「Rust cxx/FFI」、练习「Rust 调 C++ C 接口」。`ex04-stats-ffi.rs` 是裸 extern "C" + RAII 包装，rustc 直链单文件即可验证（已实测）；`ex04-cxx-bridge/` 是完整 cargo 工程（bridge 宏双向 + 类型翻译），已实测双向调用通过：

```bash
# 1. rustc 直链（先编好 /tmp/libvtest.dylib）：
export PATH="$HOME/.cargo/bin:$PATH"
rustc -O ex04-stats-ffi.rs -L /tmp -l vtest -o /tmp/ph20-ex04 && /tmp/ph20-ex04
# 2. cxx 双向桥（子目录内 cargo run，首次拉取 cxx 1.0.199 需要网络，本机已拉取成功）：
cd ex04-cxx-bridge && cargo run
```

### 示例 5：异常 → 错误码 → 各语言错误路径（examples/ex05-error-host.cpp）

对应 3.6 与 roadmap 必会概念「异常不要直接穿过 C ABI」「互操作测试必须覆盖错误路径」。把 ex01 库的错误路径（空样本 / NaN / 空指针）逐一触发并打印错误码，演示 catch 转换后边界上永远干净：

```bash
# 1. 复用 ex01 的库，编译 C++ 错误路径宿主：
clang++ -std=c++20 -Wall -Wextra ex05-error-host.cpp -L/tmp -lvtest -o /tmp/ph20-ex05 && /tmp/ph20-ex05
# 预期：err(NULL)=1 err(empty)=2 err(nan)=3 ok_add=0，退出码 0
```

### 示例 6：CMake 跨语言构建（examples/ex06-cmake-cross-build/）

对应 3.5 与 roadmap 学习内容「CMake 跨语言构建」。一个 CMakeLists 把「C++ 包装层静态库 + C 宿主 + Python 侧测试」编排进同一目标图。**本机未安装 CMake，构建未在本环境验证**；同目录的 Makefile 给出了无 CMake 的等价编排（已在本机 `make test` 验证）：

```bash
# 1. CMake 路径（需要 cmake；本机未装，可 brew install cmake）：
#    cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure
# 2. 无 CMake 的等价路径（目录内 Makefile，命令与 ex01/ex02 实测一致，已在本机验证）：
#    make clean && make test && make clean
```

## 7. 总结

### 关键要点

1. **跨语言互操作的最小公分母是 C 包装层**：extern "C" + opaque 句柄 + 错误码 + 版本检查，C/Python/Rust 三种接收方共享同一份约定（3.1）
2. **`std::string`/`std::vector`/异常/引用不出任何语言边界**；边界上只传 C 能表达的东西（数值、指针+长度、UTF-8 字节、定长 struct）（3.7）
3. **异常不穿 C ABI**：每个 extern "C" 函数 catch 干净、转错误码，「哪个异常 → 哪个错误码」是 API 设计的一部分；pybind11 的异常翻译是这条规则在生成代码里的自动化（3.6）
4. **Python 的三条路径按需选**：ctypes（运行期、零编译、最省事）、cffi（声明即文档、性能更近原生）、pybind11（编译期、类/STL/异常自动翻译）——先有 C ABI 库再谈绑定（3.2/3.3）
5. **Rust 的裸 extern "C" 与 cxx 是互补的**：前者一层文件搞定单向调用、unsafe 面靠 RAII 壳收敛；后者用 bridge 宏 + 生成代码把签名一致性、类型翻译、所有权自动化，支持 C++ 回调 Rust（3.4/4.5）
6. **谁分配谁释放 + 语言侧 RAII 收口**：opaque create/destroy 成对、调用者缓冲最安全、库内分配必须配释放函数；C++ RAII / Python `__del__` / Rust `Drop` 表达同一条纪律（3.8）
7. **跨语言 struct 布局、符号白名单、GIL、指针宽度**是四类物理细节，任何一侧改错都会静默错位（4.1/4.2/4.3）
8. **CMake/cargo/Makefile 只是编排**：真正的跨语言构建难题在各编译器的「产物形态」——C ABI 库、Python 扩展、Rust 二进制各归其位（3.5/4.6）
9. **互操作测试必须覆盖错误路径**：空输入、空指针、版本不足、double-free、use-after-free——错误翻译代码只在错误路径被执行（3.6/ex05/project）
10. **ph19 预告兑现**：ph19 的 C ABI + opaque + 版本检查 + 生命周期纪律原样成为跨语言绑定地基，每条纪律换一个接收方就是一套新绑定（3.1~3.8）

### 阶段验收清单

- [ ] 能**明确跨语言所有权**（roadmap 验收）：对任意跨语言函数签名能说出「谁分配、谁释放、借用还是拷贝、生命周期到哪为止」，并指出违反的后果（3.8）
- [ ] 能**处理异常到错误码转换**（roadmap 验收）：徒手写一个 extern "C" 包装函数，把 C++ 类异常翻译成语义化错误码并兜底 catch(...)；说出为什么异常不能穿 C ABI（3.6）
- [ ] 能**构建并测试跨语言调用**（roadmap 验收）：从 C++ 核心类 → C 包装层 → ctypes/Python 调用完整跑通，并让错误路径有断言（3.1/3.2/ex01/ex02/project）
- [ ] 能说清 pybind11 与 ctypes/cffi 的适用边界：何时值得引入一次编译的绑定层，何时 ctypes 就够了（3.2/3.3/5 节表）
- [ ] 能写出 Rust 裸 extern "C" 调 C ABI 的最小 unsafe 桥 + RAII 包装，并解释为什么 unsafe 面要最小化（3.4/4.4）
- [ ] 能画出 cxx 双向桥的调用方向：Rust → C++ 与 C++ → Rust 各走什么声明，`rust::Vec/String` 与 `std::vector/std::string` 的关系（3.4/4.5）
- [ ] 能解释 ctypes 调用时 GIL 被释放、pybind11 长任务需 `gil_scoped_release`，以及指针宽度不声明 argtypes 为什么崩（4.3/4.1）
- [ ] 能给自己的 C ABI 库写跨语言 struct 与版本检查，并解释任何一侧改布局的后果（4.1/ph19 3.7）

### 跨语言对比

见第 5 节末的对比表与第 4.6 节四张翻译表。给 analysis/ 与 Tenet 合成的启示：**互操作的全部工程成本集中在四张翻译表（类型/错误/所有权/构建），而 pybind11 与 cxx 证明了「编译器生成翻译层」能把这些成本大幅回收**。C++ 目前靠「手工 C 头 + 绑定库」双轨：C 头是唯一权威契约，绑定库各自发明翻译；C 用最简协议（无异常无类型系统），换来任何语言都能消费；Rust 尝试把翻译与所有权收进类型系统（unsafe 显式 + repr(C) + cxx 生成桥）；Python 用运行时便利（解释器兜底、GIL）换二进制自由度。若 Tenet 语言能把「C ABI 导出块（显式 extern 声明）+ repr(C) 布局标注 + 翻译声明进类型系统」做成语言原生设施，本阶段分散在三工具链的纪律就有机会收成一份编译器检查的契约。

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 4 题，前 3 题与 roadmap §20「练习」小节一一对应（C++ 动态库给 Python 调用 / pybind11 包装类 / Rust 调 C++ C 接口），第 4 题扩展覆盖错误路径与字符串转换层（对应 roadmap 必会概念）。每题标注验证状态，实测的标「已验证」、依赖 pybind11 的标「未在本环境验证」并给安装命令。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**Python 调用 C++ 向量检索库**——C++ 核心实现 brute-force 最近邻检索（add/search），经 C 包装层（opaque + 错误码 + 版本检查）暴露，Python 侧用 ctypes 建索引、查询并断言 top-k 正确，C 驱动测试覆盖错误路径；构建用 Makefile 编排（等价的 CMake 编排思路见 examples/ex06）。roadmap §20 另三个推荐项目——「Rust 调用 C++ 距离计算模块」与本项目共享全部 C 包装层手法、把 Python 驱动换成 ex04 的 Rust FFI 即可落地；「C++ 存储引擎暴露 C ABI」是同一接口形状在真实存储内核上的商业化（衔接 roadmap 第 22 节存储引擎与数据库内核，目录待建）；「pybind11 包装 C++ 查询执行组件」把 ex03 的类绑定手法套到查询算子类上即可起步。project/README 的扩展方向都给出了继续路径。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`make clean && make test` 退出码 0、ctypes 检索断言全绿、错误路径断言通过）

### 下一阶段

下一阶段是 **ph21 数据结构与算法阶段**（roadmap 第 21 节，目录待建）：本阶段学会的「C ABI + 绑定」将服务于真实数据结构——当存储引擎、向量索引开始用 LRU/HNSW/SkipList 这些结构时，本阶段的教训（谁拥有内存、谁翻译类型、谁在边界测试错误）会决定每个结构能否被 Python/Rust 生态真正用起来；届时 roadmap 的「Bloom Filter」「HNSW toy」等项目若想暴露成库，走的正是本阶段的 C 包装层路线。数据结构本身的复杂度分析、STL 容器选型、边界输入处理是 ph21 的主体，本阶段只把「结构内部实现的效率」留给了它。
