# C++ STL 标准库阶段

> 面向现代 C++、高性能系统、数据库内核方向，掌握容器选择、迭代器、算法与零开销视图，写出高效且正确的 STL 代码。

## 1. 概述

STL 标准库阶段的定位是：**从"手写数据结构"推进到"选对容器 + 用对算法"——掌握六大组件（容器/算法/迭代器/适配器/函数对象/分配器）与迭代器失效规则**。STL 的核心理念是"泛型编程 + 零开销抽象"：容器不关心你存什么类型，算法不关心你用什么容器，而 `std::string_view` / `std::span` 则把"不拥有数据"的零开销推向极致。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 顺序容器 | vector、array、deque、list、forward_list |
| 关联容器 | map、set、multimap、multiset（有序）；unordered_map、unordered_set、unordered_multimap、unordered_multiset（无序） |
| 适配器 | stack、queue、priority_queue |
| 零开销视图 | std::string_view（C++17）、std::span（C++20） |
| 算法 | sort、find、count、for_each、accumulate、copy、remove_if |
| 现代算法 | std::ranges（C++20 管道式操作） |
| 迭代器 | 五种迭代器类别、迭代器失效规则、erase 返回值惯用法 |

本阶段不涉及自定义分配器、PMR 和多线程并发容器。目标是为模板与泛型编程打好"会用标准库"的基础。

## 2. 来源与演变

| 阶段 | 代表 | 贡献 |
|------|------|------|
| 前 STL 时代 | C with Classes | 无标准容器，手动链表/动态数组，类型不安全 |
| STL 诞生 | Stepanov（HP Labs），1994 纳入 C++ 标准草案 | 泛型编程思想：算法与数据结构解耦，迭代器为胶水 |
| C++98 | ISO C++98 | 第一代标准库：vector、list、deque、map、set、algorithm |
| C++11 | ISO C++11 | unordered_map/set 进标准、移动语义赋能容器、emplace 系列、initializer_list |
| C++17 | ISO C++17 | string_view 零开销字符串视图、CTAD 类模板参数推导、std::optional |
| C++20 | ISO C++20 | std::span 零开销数组视图、std::ranges 管道式算法、erase_if 统一容器删除 |

STL 的设计哲学是"正交分解"：容器只管存储，算法只管逻辑，迭代器是二者之间的协议。这一思想影响了 Java Collections、Rust std::collections 和 Python itertools。

## 3. 语法与参数

### 3.1 顺序容器：选型与复杂度

```cpp
#include <vector>       // 连续内存，默认顺序容器
#include <deque>        // 分段连续，双端 O(1) 插入
#include <list>         // 双向链表，任意位置 O(1) 插入/删除
#include <array>        // 固定大小栈数组，零开销
#include <forward_list> // 单向链表，内存更省
```

| 容器 | 底层结构 | 随机访问 | 头插 | 尾插 | 中间插入 | 查找 | 内存布局 |
|------|---------|:-------:|:----:|:----:|:-------:|:----:|---------|
| `vector` | 动态连续数组 | O(1) | O(n) | O(1)* | O(n) | O(n) | 连续，cache 友好 |
| `array` | 固定栈数组 | O(1) | — | — | — | O(n) | 连续，无堆分配 |
| `deque` | 分段数组（多块） | O(1) | O(1) | O(1) | O(n) | O(n) | 分块，迭代器稍重 |
| `list` | 双向链表 | — | O(1) | O(1) | O(1)** | O(n) | 节点分散，指针开销 |
| `forward_list` | 单向链表 | — | O(1) | — | O(1)** | O(n) | 每节点一个指针 |

\* vector 尾插均摊 O(1)；扩容时 O(n)。\*\*需要先迭代到目标位置。

**vector 是默认选择**——连续内存对 CPU cache 最友好。只有在频繁头端插入（deque）或频繁中间插入删除（list）时才考虑其他容器。**不要凭直觉选 list**：在 100 万元素上遍历，list 的指针跳转比 vector 连续扫描慢 10-50 倍（cache miss）。

### 3.2 vector 扩容策略

gcc（libstdc++）采用 ×2 扩容，MSVC 采用 ×1.5。×1.5 的优势是旧释放的内存块之和有机会满足下一次分配，减少内存碎片。

```cpp
#include <iostream>
#include <vector>

int main() {
    std::vector<int> v;
    size_t prev = v.capacity();
    std::cout << "initial capacity: " << prev << "\n";
    for (int i = 0; i < 17; ++i) {
        v.push_back(i);
        if (v.capacity() != prev) {
            std::cout << "size=" << v.size() << " capacity: "
                      << prev << " -> " << v.capacity()
                      << " (ratio=" << static_cast<double>(v.capacity())/prev << ")\n";
            prev = v.capacity();
        }
    }
    return 0;
}
```

关键影响：`push_back` 可能导致所有迭代器和引用失效（扩容重新分配）；`reserve(n)` 可提前分配以避免多次扩容。

### 3.3 关联容器：有序 vs 无序

```cpp
#include <map>            // 红黑树，O(log n)，键有序
#include <unordered_map>  // 哈希表，O(1) 均摊，键无序
#include <set>            // 有序键集合；unordered_set 无序键集合
```

| 维度 | `std::map` | `std::unordered_map` |
|------|-----------|---------------------|
| 底层结构 | 红黑树（平衡 BST） | 哈希表（桶 + 链表/开放寻址） |
| 键顺序 | 按 `operator<` 有序 | 无序 |
| 查找 | O(log n)，最坏 O(log n) | O(1) 均摊，最坏 O(n) |
| 插入/删除 | O(log n) | O(1) 均摊 |
| 内存 | 节点分散，每节点额外 3 个指针 | 桶数组 + 节点链表，负载因子 < 1.0 |
| 适用场景 | 需要有序遍历/范围查询/前驱后继 | 纯键值查找，不关心顺序 |
| 迭代器失效 | 插入不失效，仅被删元素失效 | rehash 时全部失效 |

选择矩阵：需要范围查询（如 `lower_bound`）→ `map`；纯 O(1) 键值查找 → `unordered_map`；需要自定义哈希时提供特化 `std::hash` 或传入自定义 `Hasher`。

### 3.4 容器适配器

```cpp
#include <stack>   // 默认 deque 底层，LIFO
#include <queue>   // 默认 deque 底层，FIFO；priority_queue 也在此头文件
```

| 适配器 | 默认底层 | 核心操作 | 典型场景 |
|--------|---------|---------|---------|
| `stack<T>` | `deque<T>` | push/pop/top | 括号匹配、DFS、撤销栈 |
| `queue<T>` | `deque<T>` | push/pop/front/back | BFS、消息缓冲 |
| `priority_queue<T>` | `vector<T>` | push/pop/top | 任务调度、Top-K、Dijkstra |

priority_queue 默认大顶堆（`std::less` → 最大值优先）。小顶堆写法：`std::priority_queue<int, std::vector<int>, std::greater<int>>`。

### 3.5 零开销视图：string_view（C++17）与 span（C++20）

```cpp
#include <string_view>   // C++17：不拥有字符串数据
#include <span>          // C++20：不拥有数组数据
```

`std::string_view` 存储 `{const char* data; size_t size;}`，是对字符串数据的非拥有引用。函数参数首选 `std::string_view`（传值即可，无需 `const&`）：

```cpp
#include <iostream>
#include <string_view>
// 接受 string / const char* / char[N] 无拷贝
void print(std::string_view sv) { std::cout << sv << "\n"; }
```

`std::span<T>`（C++20）是相同思想在数组上的推广——连续内存的非拥有视图。C++17 下可用 `{T* data; size_t size;}` 手动实现等价的轻量视图。

### 3.6 算法与 std::ranges

常用算法头文件 `<algorithm>`（find/count/sort/copy/remove_if）和 `<numeric>`（accumulate/iota）。**std::ranges（C++20）** 直接把容器传给算法，消除 `v.begin(), v.end()` 的噪音：

```cpp
// C++17 写法
std::sort(v.begin(), v.end());
auto it = std::find(v.begin(), v.end(), 42);

// C++20 ranges 写法
std::ranges::sort(v);
auto it = std::ranges::find(v, 42);
```

ranges 还支持管道操作符（`|`）组合过滤和变换（`views::filter` / `views::transform`），且编译错误信息比传统算法清晰——传统 `std::sort` 传错迭代器时模板错误长达数百行，ranges 用 concept 约束在调用点直接报错。

#### 3.6.1 三个高频算法：count / for_each / accumulate

```cpp
#include <algorithm>
#include <numeric>
#include <vector>
#include <iostream>

int main() {
    std::vector<int> v = {1, 5, 3, 5, 7, 5};

    // count：统计等于某值的元素个数（count_if 按条件统计）
    int fives = std::count(v.begin(), v.end(), 5);
    int evens = std::count_if(v.begin(), v.end(), [](int x){ return x % 2 == 0; });

    // for_each：对每个元素执行操作（C++20 ranges 更常用 views/transform）
    std::for_each(v.begin(), v.end(), [](int& x){ x *= 2; });   // 就地翻倍

    // accumulate：归约求和（在 <numeric> 而非 <algorithm>！）
    int sum = std::accumulate(v.begin(), v.end(), 0);           // 初始值 0
    int product = std::accumulate(v.begin(), v.end(), 1,
                                  [](int a, int b){ return a * b; });

    std::cout << "fives=" << fives << " evens=" << evens
              << " sum=" << sum << " product=" << product << "\n";
    return 0;
}
```

| 算法 | 头文件 | 返回值 | 典型陷阱 |
|------|--------|--------|---------|
| `count` / `count_if` | `<algorithm>` | 元素个数 | 统计"存在与否"别手写循环 |
| `for_each` | `<algorithm>` | 传入的函数对象 | 带状态 lambda 需注意返回值使用 |
| `accumulate` | `<numeric>` | 归约结果 | **初始值类型决定结果类型**——`accumulate(v.begin(), v.end(), 0)` 对 `double` 容器会截断为 int，应写 `0.0` |

注意 `accumulate` 的初始值陷阱：`std::accumulate(dv.begin(), dv.end(), 0)` 对 `vector<double>` 会把每次累加截断成 int——初始值类型即归约类型，浮点容器务必传 `0.0`。

### 3.7 迭代器类别与失效规则

| 类别 | 支持操作 | 典型容器 |
|------|---------|---------|
| 输入迭代器 | `++`、`*`（读一次） | istream_iterator |
| 前向迭代器 | `++`、`*`（可多次读） | forward_list |
| 双向迭代器 | `++`、`--` | list、map、set |
| 随机访问迭代器 | `++`、`--`、`+n`、`-n`、`[]` | vector、deque、array |
| 连续迭代器 | 随机访问 + 连续内存保证（C++17） | vector、array、string |

**迭代器失效是最常见的 STL bug 来源：**

| 容器 | 操作 | 失效范围 |
|------|------|---------|
| `vector` | `push_back`（触发扩容） | **全部**迭代器/引用/指针 |
| `vector` | `push_back`（未扩容） | `end()` 失效 |
| `vector` | `erase` / `pop_back` | 被删元素及之后全部 |
| `deque` | 两端操作 | 全部迭代器；引用不失效（但 `end()` 失效） |
| `deque` | 中间 `erase` | 全部迭代器 |
| `list` | `insert` / `erase` | 仅被操作节点失效 |
| `map/unordered_map` | `insert` | 不失效（unordered_map rehash 除外） |
| `map/unordered_map` | `erase` | 仅被删元素失效 |

**安全模式**：`it = container.erase(it);` —— erase 返回被删元素的下一个有效迭代器。

## 4. 底层原理

### 4.1 vector 内存布局

`std::vector<T>` 是三个指针的薄包装（gcc sizeof = 24 字节 on 64-bit）：

```
[data_ 指向堆连续内存] [data_ + size_] [data_ + capacity_]
|<--------- 已构造元素 ------->|<-- 未初始化预留空间 -->|
```

连续内存意味着：`&v[0]` 即底层数组起始地址，可传递给 C API；`push_back` 触发扩容时，分配新内存 → 移动/拷贝旧元素 → 释放旧内存。

### 4.2 deque 分段数组

`std::deque<T>` 维护一个**中控指针数组**（map of pointers），每个指针指向一块固定大小的连续块（通常 512 字节或单元素大小，取较大者）。两端插入只需在新块首尾分配——元素本身不移动，因此引用不失效。

```
map: [*block0] [*block1] [*block2] ...
          ↓         ↓         ↓
       [元素块]  [元素块]  [元素块]
```

代价：`deque` 的下标访问需要两次指针解引用（先定位块，再定位块内偏移），比 `vector` 的一次解引用稍慢。

### 4.3 unordered_map 哈希桶结构

`std::unordered_map` 底层维护一个**指针数组（桶）**，每个桶指向节点链表（libstdc++ 用分离链接法）。查找时：`hash(key) → 桶索引 → 遍历链表比较 key`。

负载因子（元素数 / 桶数）超过 `max_load_factor()`（默认 1.0）时触发 rehash：扩容桶数组，重新哈希**所有元素**到新桶。rehash 导致**全部迭代器失效**。`reserve(n)` 可提前分配合适桶数，规避多次 rehash。

### 4.4 string_view 和 span 的零开销本质

```cpp
// sizeof(std::string_view) = 16 (64-bit)：指针 + 长度
// sizeof(std::string)       = 32 (gcc libstdc++ SSO 优化后)
// sizeof(std::span<int>)    = 16：指针 + 长度
```

它们不分配、不释放、不拥有数据。值传递等于传两个寄存器——比 `const std::string&` 少一次间接寻址。代价是使用者必须保证底层数据在视图生命周期内有效。

### 4.5 算法与容器的正交解耦

STL 的核心设计：算法通过迭代器操作数据，不依赖具体容器类型。`std::sort` 要求随机访问迭代器，接受 `vector`/`deque`/`array`，拒绝 `list`（`list` 有成员 `sort()`）。这种"最小能力约束"让每个算法签名精确表达需求，也为 C++20 ranges 的设计提供了基础。

## 5. 使用场景

| 场景 | 推荐容器/工具 | 原因 |
|------|-------------|------|
| 动态数组，大量随机访问 | `vector` | 连续内存，cache 友好 |
| 函数参数只读字符串 | `string_view` | 零拷贝，接受 string/char* 统一接口 |
| 键值查找，不关心顺序 | `unordered_map` | O(1) 均摊查找 |
| 需要有序遍历、范围查询 | `map` | 红黑树保序，`lower_bound` |
| LRU Cache | `list` + `unordered_map` | list 维护访问序，map 做 O(1) 定位 |
| 任务优先级调度 | `priority_queue` | 堆顶 O(1)，插入 O(log n) |
| 双端插入删除 | `deque` | 两端 O(1)，引用不失效 |
| 固定大小编译期确定 | `array` | 栈分配，零堆开销 |
| 管道式过滤变换 | `ranges::views`（C++20） | 惰性求值，组合零开销 |
| 遍历容器时删除 | `erase` 返回值 | `it = v.erase(it)` 获取有效迭代器 |

不适合本阶段：自定义 allocator、并发容器、pmr 多态分配器（均为更高阶主题）。

## 6. 代码示例

### 示例 1：词频统计（map vs unordered_map）

```cpp
#include <algorithm>
#include <iostream>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>

int main() {
    const std::vector<std::string> words = {
        "apple", "banana", "apple", "cherry", "banana", "apple", "date"
    };

    // map：红黑树，输出自动按 key 排序
    std::map<std::string, int> freq_ordered;
    for (const auto& w : words) ++freq_ordered[w];
    std::cout << "=== map (ordered by key) ===\n";
    for (const auto& [word, count] : freq_ordered)
        std::cout << word << ": " << count << "\n";

    // unordered_map：哈希表，O(1) 均摊，输出无序
    std::unordered_map<std::string, int> freq_hash;
    for (const auto& w : words) ++freq_hash[w];
    std::cout << "\n=== unordered_map (any order) ===\n";
    for (const auto& [word, count] : freq_hash)
        std::cout << word << ": " << count << "\n";

    // 按频率降序排序输出
    std::vector<std::pair<std::string, int>> sorted(
        freq_hash.begin(), freq_hash.end());
    std::sort(sorted.begin(), sorted.end(),
        [](const auto& a, const auto& b) { return a.second > b.second; });
    std::cout << "\n=== sorted by frequency desc ===\n";
    for (const auto& [word, count] : sorted)
        std::cout << word << ": " << count << "\n";

    return 0;
}
```

### 示例 2：ID 查询表（unordered_map 带 struct 值）

```cpp
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

struct Record {
    std::string name;
    int score;
};

int main() {
    std::unordered_map<int, Record> table;
    table[101] = {"alice", 95};
    table[102] = {"bob", 87};
    table[103] = {"carol", 92};

    const std::vector<int> queries = {102, 105, 101};
    for (int id : queries) {
        auto it = table.find(id);
        if (it != table.end())
            std::cout << "id=" << id << " name=" << it->second.name
                      << " score=" << it->second.score << "\n";
        else
            std::cout << "id=" << id << " not found\n";
    }
    return 0;
}
```

### 示例 3：优先级任务调度（priority_queue + 自定义比较）

```cpp
#include <iostream>
#include <queue>
#include <string>
#include <vector>

struct Task {
    int priority;     // 数字越小优先级越高
    std::string name;
    // 小顶堆：priority 小的在堆顶
    bool operator<(const Task& other) const {
        return priority > other.priority; // 故意反向：min-heap
    }
};

int main() {
    std::vector<Task> tasks = {
        {3, "log-sync"}, {1, "heartbeat"}, {2, "gc-trigger"}, {0, "emergency"}
    };
    std::priority_queue<Task> pq;
    for (const auto& t : tasks) pq.push(t);

    std::cout << "=== processing by priority ===\n";
    while (!pq.empty()) {
        const auto& t = pq.top();
        std::cout << "[" << t.priority << "] " << t.name << "\n";
        pq.pop();
    }
    return 0;
}
```

### 示例 4：用 STL 重写链表操作（list vs vector 对比）

ph02 手动实现的链表查找/插入/删除，在 STL 中由 `std::list` 和 `<algorithm>` 直接提供：

```cpp
#include <algorithm>
#include <iostream>
#include <list>
#include <string>
#include <vector>

int main() {
    // std::list 替代手动链表
    std::list<std::string> names = {"alice", "bob", "carol", "dave"};

    // O(n) 查找
    auto it = std::find(names.begin(), names.end(), "carol");
    if (it != names.end()) std::cout << "found: " << *it << "\n";

    // O(1) 插入（在找到位置之前）
    names.insert(it, "inserted");
    // O(1) 删除
    names.remove("bob");

    std::cout << "after insert/remove:";
    for (const auto& n : names) std::cout << " " << n;
    std::cout << "\n";

    // std::vector 实现相同逻辑（更好的默认选择）
    std::vector<std::string> v = {"alice", "bob", "carol", "dave"};
    auto vit = std::find(v.begin(), v.end(), "carol");
    if (vit != v.end()) v.insert(vit, "inserted"); // O(n)
    v.erase(std::remove(v.begin(), v.end(), "bob"), v.end()); // erase-remove idiom
    std::cout << "vector result:";
    for (const auto& n : v) std::cout << " " << n;
    std::cout << "\n";

    return 0;
}
```

### 示例 5：迭代器失效演示与安全模式

```cpp
#include <iostream>
#include <vector>

int main() {
    // 错误模式：erase 后继续使用失效迭代器
    std::vector<int> v1 = {1, 2, 3, 4, 5, 6};
    std::cout << "=== erase with correct pattern ===\n";
    // 正确模式：it = v.erase(it)
    for (auto it = v1.begin(); it != v1.end(); ) {
        if (*it % 2 == 0)
            it = v1.erase(it);  // 返回下一个有效迭代器
        else
            ++it;
    }
    std::cout << "after removing evens:";
    for (int x : v1) std::cout << " " << x;
    std::cout << "\n";

    // push_back 可能导致迭代器失效
    std::vector<int> v2 = {1, 2, 3};
    auto it = v2.begin();
    std::cout << "before push: *it=" << *it << " capacity=" << v2.capacity() << "\n";
    // 如果扩容触发，it 失效 —— reserve 可预防
    v2.reserve(100); // 预留空间，后续 push_back 不会扩容
    it = v2.begin(); // reserve 后重新获取
    v2.push_back(4);
    std::cout << "after push (with reserve): *it=" << *it << "\n";

    return 0;
}
```

### 示例 6：string_view / span / ranges 组合（C++20）

```cpp
// 编译：g++ -std=c++20 -Wall -Wextra
#include <algorithm>
#include <iostream>
#include <ranges>
#include <span>
#include <string_view>
#include <vector>

void print_sv(std::string_view sv) {
    std::cout << "string_view: \"" << sv << "\" size=" << sv.size() << "\n";
}

int sum(std::span<const int> data) {
    int s = 0;
    for (int x : data) s += x;
    return s;
}

int main() {
    print_sv("C-string literal");  // const char* 隐式转换
    std::string s = "std::string";
    print_sv(s);                   // std::string → string_view
    print_sv(s.substr(0, 3));      // 临时 string 的安全视图

    int arr[] = {1, 2, 3, 4, 5};
    std::vector<int> v = {10, 20, 30};
    std::cout << "sum(arr)=" << sum(arr) << "\n";
    std::cout << "sum(v)=" << sum(v) << "\n";

    // ranges 管道式组合：过滤偶数 → 平方
    std::vector<int> nums = {1, 2, 3, 4, 5, 6, 7, 8};
    auto view = nums
              | std::views::filter([](int x) { return x % 2 == 0; })
              | std::views::transform([](int x) { return x * x; });
    std::cout << "even squares:";
    for (int x : view) std::cout << " " << x;
    std::cout << "\n";

    std::ranges::sort(nums);  // 直接传容器，无需 begin/end
    std::cout << "sorted:";
    for (int x : nums) std::cout << " " << x;
    std::cout << "\n";

    return 0;
}
```

## 7. 总结

### 关键要点

1. **vector 是默认顺序容器**：连续内存 > 链表 cache locality；仅高频头端操作（deque）或频繁中间插入/删除（list）时才偏离默认
2. **unordered_map 依赖哈希质量**：O(1) 均摊前提是哈希分布均匀 + 无频繁 rehash；用 `reserve()` 预分配规避
3. **map vs unordered_map 是语义对决，不是性能对决**：需有序遍历 → map；纯查找 → unordered_map
4. **string_view / span 不拥有数据**：函数参数首选值传递 `string_view`，调用方必须保证底层数据存活
5. **迭代器失效是 bug 高产地**：vector push_back 扩容 → 全部失效；安全模式 `it = v.erase(it)`
6. **扩容策略影响性能**：gcc ×2 vs MSVC ×1.5；`reserve(n)` 可预分配避免摊销波动
7. **std::ranges 不光是语法糖**：concept 约束让错误信息从数百行变成一行，管道操作让逻辑组合可读

### 跨语言对比：容器

| 维度 | C++ STL | Java Collections | Go | Rust |
|------|---------|-----------------|-----|------|
| 默认顺序容器 | `vector`（连续） | `ArrayList`（连续） | `slice`（连续，引用语义） | `Vec`（连续，所有权） |
| 有序映射 | `map`（红黑树） | `TreeMap`（红黑树） | 无内置（需第三方） | `BTreeMap`（B 树） |
| 无序映射 | `unordered_map`（哈希） | `HashMap`（哈希） | `map`（哈希，内置） | `HashMap`（哈希） |
| 零开销视图 | `string_view` / `span` | `CharSequence`（接口） | `[]byte` 切片（引用） | `&str` / `&[T]`（借用） |
| 迭代器模型 | 五种类别 + 首尾对 | Iterator / ListIterator | 无（range 关键字） | Iterator trait + 适配器 |
| 算法方式 | 自由函数（`std::sort`） | `Collections.sort()` | `sort` 包函数 | `Vec::sort()` 方法 |
| 失效处理 | 手动遵守规则 | `ConcurrentModificationException` | 不适用（无迭代器对象） | 编译器借用检查防止悬垂 |

### 阶段验收标准

- 能按场景（随机访问/头插/有序遍历/纯查找）选择正确容器并解释复杂度
- 能写出遍历 vector 时安全删除元素的正确写法（`it = erase(it)`）
- 能解释 deque 分段数组与 vector 连续内存的本质差异，以及 `string_view` 为何值传递
- 能用 `priority_queue` + 自定义比较器实现任务调度，用 `std::ranges` 写现代 C++ 风格代码

### 进入下一阶段前

词频统计（map vs unordered_map）、ID 查询表、优先级任务调度、用 STL 重写 ph02 手动链表、迭代器失效实验（验证 vector 扩容失效 + erase 返回值模式）。

### 推荐项目

- **词频统计与排序工具**：读文本 → 分词 → unordered_map 统计 → vector 排序输出 Top-K
- **LRU Cache**：list（访问序）+ unordered_map（key → list::iterator）O(1) 读写
- **简易任务调度器**：priority_queue 驱动，Task 含优先级、回调、延迟字段

### 下一阶段

[模板与泛型编程阶段](../ph05-templates/05-templates.md)——函数模板、类模板、concept 约束、编译期计算、模板元编程基础。
