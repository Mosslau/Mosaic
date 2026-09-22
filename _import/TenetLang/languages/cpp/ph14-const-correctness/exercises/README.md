# exercises —— const 正确性与接口设计阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。验证环境：Apple clang 21.0.0（`c++`，g++ 兼容）+ Homebrew clang 21.1.8（`clang++`），编译命令 `c++ -std=c++20 -Wall -Wextra`。练习 1/2/3 与 roadmap ph14「练习」小节的三个承诺（给旧类补 const 成员函数、用 const 引用优化函数参数、设计只读配置接口）一一对应，练习 4/5 覆盖「学习内容」与「必会概念」中的 mutable 谨慎使用 / 逻辑 const 与物理 const / 只读视图设计 / const_cast 气味。

## 练习 1：给旧类补 const 成员函数（★）

- **目标**：给定一个"全部成员函数都没标 const"的旧类，把只读查询标 const（Con.2），为可变句柄补 const 重载（返回 `const&`），并证明修复后 const 对象可以正常使用
- **要求**：
  - 旧类 `Device`：`name()` / `version()` / `online()` 是只读查询，`label()` 是可变句柄（`std::string&`）
  - 只读查询标 const；`label()` 保留非 const 版本并补 const 版本
  - 用成员指针类型断言验证（`decltype(&Device::name)` 应为 `std::string (Device::*)() const`）
  - const 对象/`const Device&` 实测全部只读接口可用；非 const 对象仍可改 label
- **验收**：运行输出与 `sol-01-add-const-member-functions.cpp` 文件头一致（[B] 三个成员指针类型断言、[C] const 对象实测、[D] 可变句柄对照）
- **提示**：成员函数的 const 限定会进入成员指针类型；返回引用时 const 版本返回 `const&` 才能让 const 对象安全持有只读句柄（参考实现 `sol-01-add-const-member-functions.cpp`）

## 练习 2：用 const 引用优化函数参数（★★）

- **目标**：把"按值接收大对象"的旧函数改成 `const&` 接收（F.16），用拷贝计数实测优化前后差异；理解"需要拿走所有权"的 sink 情形
- **要求**：
  - 给 `Doc`（含 `vector<char>` 大成员）写拷贝计数（copy-ctor 里 `++`），把"发生了拷贝"变成可观测数字
  - 旧函数 `count_by_value(Doc d)` 按值；新函数 `count_by_const_ref(const Doc& d)` 零拷贝
  - 演示 sink 情形：调用方要把数据交给函数时按值 + `std::move`（一次移动、零拷贝）
  - 注释回答：只读参数什么时候用 `const&`、什么时候按值？sink 为什么要按值？
- **验收**：运行输出与 `sol-02-const-ref-params.cpp` 文件头一致（拷贝计数：by_value=1、const_ref=0）
- **提示**：`const&` 承诺"只读"由编译器执行；按值只适合廉价拷贝类型（int/double/指针）；所有权转移用按值 + move（参考实现 `sol-02-const-ref-params.cpp`）

## 练习 3：设计只读配置接口（★★★）

- **目标**：实现一个 `Config` 类，对外只暴露 const 操作（`get` / `contains` / `size` / `keys`），`get` 返回 `std::string_view`，内部查找统计用 mutable 计数；用 const 对象 + `const&` 参数的辅助函数实测整条只读链路
- **要求**：
  - 构造时一次性解析 `key=value` 文本（跳过 `#` 注释与空行），条目用 `string_view` 指向自有的原始文本（零拷贝）
  - 全部 public 接口 const；**没有任何 public 修改方法**——"改配置"只能构造新对象
  - `get` 用 `std::optional<std::string_view>` 表达"可能不存在"；查询统计 `lookup_count()` 是 mutable 物理状态
  - 写一个 `void dump(const Config&)` 辅助函数，全程只走 const 接口
- **验收**：运行输出与 `sol-03-readonly-config.cpp` 文件头一致（解析 3 条、查询/缺失、keys、lookup_count=4、只读快照）
- **提示**：`string_view` 视图的生命周期绑定 `Config` 对象；拷贝即只读快照（值语义 + const 接口）；线性扫描即可，不必建索引（参考实现 `sol-03-readonly-config.cpp`）

## 练习 4：mutable 与逻辑 const 判断（★★）

- **目标**：给定一个"只读聚合视图"的遥测类，判断哪些成员属于逻辑状态（const 成员函数不可改）、哪些属于物理状态（缓存/计数，用 mutable），实现懒计算缓存并实测
- **要求**：
  - 类 `Telemetry`：`sample_count()` / `max_value()` 是懒计算查询，内部缓存 `optional<size_t>` / `optional<int>`；`cache_hits()` 统计命中次数
  - 判断并注释：哪个成员是逻辑状态、哪些是物理状态（mutable）？为什么？
  - const 成员函数内写缓存位；实测"首次计算 / 命中缓存"的交替输出
  - 注释解释：把缓存成员改成非 mutable 会发生什么（编译错误）
- **验收**：运行输出与 `sol-04-mutable-logical-const.cpp` 文件头一致（懒计算首次/命中交替、cache_hits=2）
- **提示**：逻辑 const = 语义不变；物理 const = 位不变。缓存/互斥锁/计数是"物理可变、逻辑不变"的正当 mutable 场景——但 mutable 是特例，不是默认（参考实现 `sol-04-mutable-logical-const.cpp`）

## 练习 5：const_cast 气味识别与只读视图（★★★）

- **目标**：识别"通过 `const&` 参数用 const_cast 改写实参"的设计气味，用诚实的接口重构（正例对照）；再用 `string_view` / `span` 把只读接口改成"观察不拥有"的视图形态
- **要求**：
  - 反例：`to_upper_sneaky(const std::string& s)` 内部 `const_cast<std::string&>(s)` 改写——注释说明为什么这是气味（合法但破坏调用方假设）
  - 正例重构：`to_upper(std::string& s)` 非 const 引用参数，零 cast——实测两种写法的行为差异
  - 只读视图：`count_letters(std::string_view)` 接受 `std::string` 与 C 字面量（零拷贝）；`average(std::span<const double>)` 覆盖 vector 与 C 数组
- **验收**：运行输出与 `sol-05-const-cast-views.cpp` 文件头一致（气味版 s 被改、诚实版同样可达目的、视图计数正确）
- **提示**：**const_cast 通常是设计气味**（roadmap 必会概念）——"需要修改"应该由签名表达；视图参数要保证调用方数据的生命周期覆盖整个调用（参考实现 `sol-05-const-cast-views.cpp`）

**提示**：参考实现仅作对照，先独立完成再复盘。sol-* 文件头都带本机实测输出与验证状态（两种编译器一致）；练习 3 的 lookup_count、练习 4 的 cache_hits 均为实测记录。进阶玩法（可选）：给练习 3 的 Config 加 `find_prefix(key)` 只读接口；给练习 4 加一个 mutable 互斥锁成员并演示并发读（承接 ph08 并发编程阶段的 RAII 锁）。
