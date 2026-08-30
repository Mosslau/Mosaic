# exercises —— STL 标准库阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：Apple clang 17.0.0（g++ 兼容），标准 C++17。编译统一加 `-Wall -Wextra -std=c++17`。
> 建议完成顺序：1 → 2 → 3 → 4，第 5 题是工具链实践（故意出错示例），放在最后。

## 练习 1：词频统计与 Top-K（★★）

**目标**：用 `std::map` / `std::unordered_map` 统计词频，按频率降序输出 Top-3 高频词。

**要求**：

- 从给定词序列统计每个词的出现次数，统计用 `++freq[w]` 一行完成，禁止手写双重循环
- 用 `std::unordered_map<std::string, int>` 做统计，再拷贝到 `std::vector` 按频率降序排序
- 输出 Top-3；**频次并列时按词典序（字母序）稳定排序**
- 用 `-Wall -Wextra` 编译零警告

**验收**：给定输入词表，输出的 Top-3 频次正确；频次并列的词按词典序排列。

## 练习 2：ID 查询表（★★）

**目标**：用 `std::unordered_map<int, User>` 建用户表，支持插入/更新与批量查询。

**要求**：

- `struct User { std::string name; int age; };`
- 实现 `insert`：ID 已存在时**更新**记录（可用 C++17 的 `insert_or_assign`）
- 批量查询一组 ID：命中输出 `name` 与 `age`，未命中归入 `not found` 列表
- 展示输出前**不关心哈希顺序**（不要打印整个表）

**验收**：查询结果与预期一致；未命中 ID 全部列出；更新后再次查询返回新值。

## 练习 3：优先级任务调度（★★★）

**目标**：用 `std::priority_queue` 实现小顶堆调度，正确处理**同优先级 FIFO**。

**要求**：

- `struct Job { int priority; int seq; std::string name; };`，`seq` 为入队序号
- 自定义 `operator<`：`priority` 小的先执行；`priority` 相同则 `seq` 小的先执行（`priority_queue` 不保证稳定性，必须显式加 tie-breaker）
- 依次 push 一组任务，再 pop 输出执行顺序
- 必须用优先队列，禁止 sort

**验收**：输出按 `priority` 升序；`priority` 相同时严格按 `seq` 升序。

## 练习 4：用 STL 重写链表项目（★★★）

**目标**：把「手写链表」的工作交给 `std::list` + `<algorithm>`，并对比 `std::vector` 写法的复杂度差异。

**要求**：

- 用 `std::list<std::string>` 实现联系人名单：尾部追加、在指定名字**之前**插入、删除指定名字、按名字查找
- 中间插入/删除必须通过迭代器完成（`find` 定位后 `insert`/`erase`）
- 再写一个 `std::vector<std::string>` 版本实现相同逻辑
- 用注释说明两者复杂度差异：list 中间插入 O(1)（定位后）vs vector 中间插入 O(n)
- 遍历输出用 range-based for

**验收**：两个容器经过相同操作序列后内容一致；list 版使用迭代器完成插入删除。

## 练习 5：迭代器失效实验（★★，故意出错）

**目标**：亲眼观察 `vector` 扩容后迭代器失效导致的未定义行为，理解 `reserve()` 的价值。

**要求**：

- 写**错误代码**：保存 `v.begin()` 后连续 `push_back` 直到触发扩容，再解引用旧迭代器 —— 用 `g++ -Wall -Wextra -std=c++17 -fsanitize=address -g` 编译运行，观察 ASan 报告（预期 `heap-use-after-free`）
- 再写**正确代码**：先 `reserve()` 预留容量，再 `push_back`，旧迭代器保持有效
- 能说清错误代码的 UB 来源（旧缓冲区被释放，迭代器悬垂）

**验收**：能复述 ASan 报告的错误类型与源码位置；正确代码运行无异常、输出正确。

**注意**：`sol-05-iterator-invalidation.cpp` 是故意出错示例，**必须**用 `-fsanitize=address` 编译运行，否则勿运行；本仓库验证环境编译零警告通过，但沙箱限制 ASan 二进制运行，报错输出请在本机验证。
