# ph23 阶段项目：Rust 加速库 rspeed（Python 调用）

对应 roadmap 第 23 节推荐项目「Rust 加速库：为 Python 提供高性能解析、向量距离计算或 RAG chunk 处理函数，并附带测试」。落地为完整 cargo 工程 `rspeed/`：**纯 Rust 核心（可 cargo test）+ pyo3 薄绑定（feature 门控）+ Python 冒烟测试 + 纯 Python vs Rust 扩展性能实测**。

## 需求

给 Python 一个用 Rust 写的加速模块，提供两类函数并给出**真实的性能对比**：

- **向量距离**：`euclidean(a, b)`、`cosine_similarity(a, b)` —— 逐元素浮点运算，Python 逐元素循环的解释开销远大于算术本身；
- **RAG chunk 处理**：`chunk_text(text, chunk_size, overlap)` —— 按字符窗口切分文本（重叠窗口），最小可用的 RAG 预处理函数。

选这个组合是刻意的：第 2 类「看似该加速」的负载实测结果**出乎意料**（见验收表），它比「Rust 全赢」更能回答 ph23 的核心问题——**跨语言边界不是自动加速器，负载是否该过 FFI 必须由测量决定**（主文档 5 节）。

## 目录与功能清单

```text
rspeed/
├── Cargo.toml              # default 无第三方依赖；pyo3 0.23.5 由 feature "python" 门控
├── src/
│   ├── lib.rs              # 模块声明 + #[cfg(feature="python")] 的 pyo3 绑定层
│   ├── distance.rs         # 纯 Rust 核心：euclidean / cosine（Option 语义，含单测）
│   └── chunk.rs            # 纯 Rust 核心：字符窗口切分（Result 语义，含单测）
├── smoke_test.py           # Python 冒烟：与纯 Python 参考实现逐值对照 + 错误路径
└── bench.py                # 性能对比：纯 Python vs Rust 扩展（best-of-5，含正确性对照）
```

- [x] Rust 单测 10 个：正常值、None/Err 边界、Unicode 按字符切分、大向量与朴素循环对照
- [x] Python 冒烟：余弦/欧氏/chunk 与纯 Python 参考实现一致；错误路径抛 `ValueError` 而非崩溃
- [x] 性能对比脚本输出「纯 Python / Rust 扩展 / 加速比」实测表（含「Rust 反而慢」的诚实反例）
- [x] fmt / clippy `-D warnings` / test 全绿；构建产物落 `/tmp`，仓库零二进制残留

## 验证环境

cargo/rustc **1.92.0**（macOS arm64）、pyo3 **0.23.5**、Python **3.13.12**（`/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3`）。macOS 手动构建 `extension-module` 需放开动态查找（主文档 3.10 说明）。全部命令本机实测，标注「已验证」。

## 验收标准

在 `project/rspeed/` 目录内执行：

```bash
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_TARGET_DIR=/tmp/ph23-rspeed-target

# ① Rust 单测：核心算法 10 个测试（不需要 Python 绑定）
cargo test --release
cargo fmt --check && cargo clippy --all-targets --release -- -D warnings

# ② 构建 Python 扩展（cdylib），并改名 .so 供 Python import
export RUSTFLAGS="-C link-arg=-Wl,-undefined,dynamic_lookup"
cargo build --release --features python
PY=/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3
cp /tmp/ph23-rspeed-target/release/librspeed.dylib ./rspeed.so

# ③ Python 冒烟：与纯 Python 参考实现逐值对照（-B 防止生成 __pycache__）
$PY -B smoke_test.py            # 期望输出 ALL OK

# ④ 性能对比：纯 Python vs Rust 扩展
$PY -B bench.py                 # 期望输出下表（数字见下）

rm -f rspeed.so
```

**④ 实测性能表（本机 macOS arm64 / cargo 1.92.0 / Python 3.13.12，best-of-5 两轮实测范围）：**

| 工作负载 | 纯 Python (ms) | Rust 扩展 (ms) | 加速比 |
|---------|---------------|---------------|--------|
| `euclidean`（dim=200,000） | 10.1–12.2 | 1.9–2.3 | **≈ 5–6x** |
| `chunk_text`（222 KB 中文文档，256/32） | 0.05 | 0.33–0.34 | ≈ 0.15x（Rust 反而慢） |

**验收口径（对应 roadmap「能让接口只暴露 ABI 稳定类型」「能让错误处理不跨 FFI 直接 panic」，并兑现 ph22 预告的「把性能纪律带过 FFI 边界」）：** 交付物必须给出**真实**的性能对比并能解释差异——

- **为什么 euclidean 该过 FFI**：向量距离是「逐元素浮点运算 + 一个归约」，Python 把每次循环迭代都付给解释器；Rust 把算力花在算术本身。即便计入 Python list → `Vec<f64>` 的一次性转换，仍有 ~5–6x 收益。转换是一次性 O(n)，计算也是 O(n)，比例固定。
- **为什么 chunk_text 不该过 FFI（本项目的诚实反例）**：`chunk_text` 本质是「切片复制」——CPython 的字符串切片是 C 级 memcpy，纯 Python 参考实现已经贴着内存复制的速度下限；Rust 版反而要先把全文解码成 `Vec<char>` 再逐片重新收集（char 解码 + 每片一次堆分配）。结论不是「Rust 慢」，而是**这个负载没有给 Rust 留下可优化的解释开销**——FFI 的收益 = Python 侧被消除的解释开销，chunk 的场景里 Python 几乎没有解释开销。
- **边界纪律的验证**：所有错误（长度不一致、零向量、`chunk_size=0`、`overlap≥chunk_size`）在 Rust 侧用 `Option`/`Result` 表达、由 pyo3 层翻译成 `ValueError`，全程无 panic 跨边界（可用 `RUST_BACKTRACE=1` 跑 smoke 确认无 unwinding 泄漏）；数据转换由 pyo3 的类型提取完成，Rust 侧不持有 Python 对象。

> **对照说明（诚实的边界条件）**：若 Python 侧允许引入 numpy，euclidean 用 `np.linalg.norm(a-b)` 约 0.1 ms 级，Rust 的 5x 就消失了——Rust 加速模块的适用前提是「没有现成 C 加速库、或需要无依赖/可嵌入分发」。这正是主文档 5 节决策表的实证：**先用测量决定要不要 FFI，而不是先 FFI 再证明**。

## 扩展方向

- **换 C ABI + ctypes 通道**：若目标环境没有 pyo3/maturin，可把同一核心用 `extern "C"` 导出 + ctypes `CDLL` 调用（examples ex01 的形态）；对比 pyo3 与 ctypes 两条通道的转换开销差异。
- **向量负载放大**：加批量（n×d 矩阵）接口，用 ph19/ph22 的 SoA/缓存纪律优化热路径，并接入 criterion 做回归基线。
- **chunk 负载改造**：把字符窗口换成**词窗口**（`chunk_words`，按空白切分），Python 侧需逐词 Python 级循环时，Rust 优势才显性——可自行用 bench.py 的骨架验证「换负载后加速比翻正」。
- **接 ph25 数据基础设施专项**（roadmap 第 25 节，目录待建）：ph25 的 pyo3 模块工程化（maturin 打包、`pyproject.toml`、多 Python 版本构建）在这里的代码形态上继续——本工程的 feature 门控结构可以直接被 maturin 项目复用。
- **绑定类型深化**：用 `Bound<PyAny>`/`numpy` 数组零拷贝视图替代 `Vec<f64>` 提取，把转换成本从 O(n) 降到 O(1)（引入 numpy 依赖，属于进阶）。
