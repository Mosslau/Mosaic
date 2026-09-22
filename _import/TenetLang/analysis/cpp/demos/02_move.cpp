// 02 · 移动语义与右值引用演示
// 编译运行：make && ./demos/02_move

#include <iostream>
#include <string>
#include <utility>
#include <vector>

struct Counter {
    static int copies;
    static int moves;
    std::string data;

    explicit Counter(std::string d) : data(std::move(d)) {}
    Counter(const Counter& o) : data(o.data) { ++copies; }
    Counter(Counter&& o) noexcept : data(std::move(o.data)) { ++moves; }
};

int Counter::copies = 0;
int Counter::moves = 0;

Counter make_counter() {
    return Counter(std::string(1000, 'x'));  // 返回临时对象（右值）
}

int main() {
    std::cout << "== 拷贝 vs 移动 ==\n";

    Counter a = make_counter();  // 临时对象 → 移动（C++17 甚至可能省略）
    std::cout << "构造 a: copies=" << Counter::copies << " moves=" << Counter::moves << "\n";

    Counter b = a;               // 左值 a → 拷贝（复制 1000 字符）
    std::cout << "拷贝 b = a: copies=" << Counter::copies << " moves=" << Counter::moves << "\n";

    Counter c = std::move(a);    // std::move 标记 → 移动（换指针，O(1)）
    std::cout << "移动 c = move(a): copies=" << Counter::copies << " moves=" << Counter::moves << "\n";

    std::cout << "\n== vector 扩容：移动让重新分配变便宜 ==\n";
    std::vector<Counter> v;
    for (int i = 0; i < 4; ++i) {
        v.push_back(make_counter());
    }
    std::cout << "push_back 4 次后: copies=" << Counter::copies
              << " moves=" << Counter::moves << "\n";
    std::cout << "（moves 增长 = 扩容时资源被转移而非复制）\n";
}
