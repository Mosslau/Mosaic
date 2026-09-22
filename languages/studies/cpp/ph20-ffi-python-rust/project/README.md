# ph20 阶段项目：Python 调用 C++ 向量检索库

对应 roadmap §20「推荐项目」第一项「Python 调用 C++ 向量检索库」（其余推荐项的落地方案见「扩展方向」）。**边界声明：本项目是「稳定 C ABI + 跨语言绑定」的机制 demo，不是真向量检索库**——只做 brute-force 线性扫描 + 平方 L2 距离，无 ANN 近似索引、无 SIMD、无持久化、无并发，样本量停留在「玩具级」（那些属于 roadmap 第 23 节向量检索与 AI 推理引擎方向 C++ 阶段）；本项目只回答一件事：**一个 C++ 写的索引类，如何经 C 包装层被 Python（ctypes）与 C 同时安全地使用，且错误路径与所有权都有断言兜底**。

## 需求

C++ 核心类 `vindex::flat_index`（`add` 累加向量、`search` 按平方 L2 距离升序取 top-k，等距靠 stable_sort 保插入序），经 C 包装层暴露成 C ABI：opaque 句柄 + 错误码 + 版本检查 + 调用者分配的结果缓冲。C 驱动与 Python 驱动各跑一份相同的确定性数据（dim=3，id 100/200/300/400），互证 top3 与全部错误路径：

| 消费者 | 文件 | 教学点 |
|--------|------|--------|
| C 驱动 | `driver_test.c` | include C 头 + 链接期绑定；C 是这份 ABI 的「母语」接收方 |
| Python | `search_python.py` | ctypes.Structure 描述 vec_hit（4.1 布局一致性）；索引类 `__del__` 归还句柄（3.8） |

## 功能清单

- [x] C++ 核心 `vec_index_core.h`：纯 C++ 类（异常/vector 随意用，不出边界），`stable_sort` 确定性排序
- [x] C ABI 头 `vec_index_api.h`：extern "C" + opaque 句柄 + `int64_t`/`float` 定宽类型 + 显式错误码 + 版本检查（C/C++ 双编译器可 include）
- [x] 包装层 `vec_index_wrap.cpp`：create/destroy 成对、异常全 catch 转错误码、search 结果写调用者缓冲（零所有权转移）
- [x] 检索结果跨语言结构 `vec_hit { int64_t id; float dist; }`：C/Python 两侧同一份字节（Rust 侧扩展见下）
- [x] C 驱动与 Python 驱动覆盖错误路径：维度错 / 空索引 / cap<topk / 空指针 / 非法 dim create
- [x] `make clean && make test` 一键验收（C 驱动 + Python 驱动双绿）

## 验收标准

- [ ] `make clean && make test` 退出码 0：C 驱动输出 `[PASS] ... top3 = [100, 400, 200]`，Python 驱动输出 `search_python.py PASS`，二者断言互证
- [ ] `make` 双编译器零警告（`clang++ -std=c++20 -Wall -Wextra` 与 `clang -std=c11 -Wall -Wextra`）
- [ ] Python 侧覆盖的错误路径都以 `OSError`（含错误码）而非崩溃表达：维度不匹配 code=2、空索引 code=3
- [ ] C 侧能口头说清：为什么结果写调用者缓冲（零所有权转移）而不返回库内 malloc 指针；为什么 opaque 句柄不能直接 delete；为什么版本检查要先于业务调用
- [ ] 能画出跨语言调用链：`search_python.py` → ctypes → `_vec_index_search` → `flat_index::search` → 结果回填缓冲 → Python 读 `VecHit` 数组（每层各做了什么翻译）

## 扩展方向（可选）

- **Rust 消费同一 ABI**：`vec_index_api.h` 手抄成 extern "C"（参考 examples/ex04-stats-ffi.rs 手法，单文件 rustc 直链 `-L /tmp -l vecindex`）——roadmap 推荐项目「Rust 调用 C++ 距离计算模块」的等价物，README 的顶格项目落法一致
- **cxx 深绑定**：把 `flat_index` 用 `#[cxx::bridge]` 暴露成 Rust 类（`&Vec<f32>` 自动翻译 rust::Vec），对比手工 C ABI 的胶水量（examples/ex04-cxx-bridge 手法）
- **pybind11 包装查询组件**：改用 `py::class_<flat_index>` + `<pybind11/stl.h>` 绑类（参考 examples/ex03），让 Python 拿到原生类而不是 ctypes 句柄——roadmap 推荐项目「pybind11 包装 C++ 查询执行组件」的索引版
- **上游接口升级**：给 `vec_index_api.h` 加 `bulk_add`（一次传 `(ids, dim, data, n)`）并递增版本号，观察绑定方与调用方如何同步升级——把 ph19 版本兼容纪律放到多语言场景重演
- **错误注入测试**：用 Python 侧构造 cap=topk 边界、超大 topk、dim=0 的查询等输入跑一遍互操作错误路径矩阵；若配 ASan 构建可顺带验证跨语言 use-after-free 是否被抓到
- **真向量库方向**：换 HNSW/IVF-PQ 实现、加 SIMD 距离、做持久化——正式进入 roadmap 第 23 节向量检索与 AI 推理引擎方向，本项目的 C ABI 头可原样成为它的对外契约

## 验证环境与状态

- 实测环境：macOS arm64，Apple clang 21.0.0 + Python 3.13.12，make 3.81+
- 构建：`make`；测试：`make clean && make test`；清理：`make clean`（产物一律在 /tmp，仓库不落二进制）
- 验证状态：**已验证**（`make clean && make test` 退出码 0：C 驱动 `[PASS]`、Python 驱动 `PASS`、编译零警告、错误路径断言全绿）
