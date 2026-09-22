# ph05 阶段项目：泛型 Ring Buffer（RingBuffer<T, N>）

对应 Roadmap「5. 模板与泛型编程、元编程阶段」推荐项目第一个「泛型 Ring Buffer」。用 `ring_buffer.h`（模板类）+ `main.cpp`（assert 自测）多文件组织，是 `examples/ex05-ring-buffer.cpp` 的完整工程版。

## 需求

实现一个固定容量的环形缓冲区（circular buffer）：容量 N 作为**非类型模板参数**在编译期确定，`push` / `pop` 均 O(1)；`pop` 用 `std::optional<T>` 表达「空」结果。

核心是 `std::array<T, N>` + 读写双指针 + `full_` 标记：

- `read_`：下一次 `pop` 的位置；`write_`：下一次 `push` 的位置
- 读写指针推进时对 N 取模，越过数组尾部自动回绕
- `write_ == read_` 时用 `full_` 区分「空」与「满」两个状态

## 功能清单

| 功能 | 说明 |
|------|------|
| 编译期容量 | 非类型模板参数 N + `requires (N > 0)`，`capacity()` 为 `static constexpr` |
| 元素约束 | `requires std::default_initializable<T>`，`std::array<T, N>` 需要元素可默认构造 |
| push（const 与移动） | 满时返回 `false` 拒绝写入，不覆盖旧数据 |
| pop | 返回 `std::optional<T>`：空时 `std::nullopt`，非空时移出队首元素 |
| front / back | const 与非 const 重载，前置条件非空 |
| 状态查询 | `empty()` / `full()` / `size()` / `capacity()` |
| 自测 | `main.cpp` 内 assert 覆盖 FIFO / 满态拒绝 / 环形回绕 / 空态 pop / front-back / 满态首尾 |

## 验收标准

- [ ] `g++ -Wall -Wextra -std=c++20 main.cpp -o ring_buffer` 编译零警告
- [ ] 运行 `./ring_buffer` 全部 assert 通过（输出「Ring Buffer 全部 assert 通过」）
- [ ] 容量 4：push 1~4 后第 5 次 push 返回 `false`；pop 两个再 push 5、6 时读写指针回绕，出队顺序仍为 1~6
- [ ] 代码遵循 C++ Core Guidelines：无裸 `new`/`delete`（Rule of Zero）、能 `const` 的成员函数全 `const`、`std::optional` 表达可缺失返回值

## 扩展方向

- 满态「覆盖最旧元素」的 `push_overwrite` 变体，满足流式采样场景
- 暴露只读迭代器与 `clear()`，支持 range-based for 遍历
- 对比 `std::deque<T>` 无容量上限版本，观察内存布局差异
- 加 `std::mutex` 变成线程安全版本 —— 属于 ph08 并发阶段

## 验证环境

- Apple clang 17（g++ 兼容），标准 C++20（requires 约束子句）
- 编译：`g++ -Wall -Wextra -std=c++20 main.cpp -o ring_buffer`
- 运行：`./ring_buffer`
- 验证状态：已验证
