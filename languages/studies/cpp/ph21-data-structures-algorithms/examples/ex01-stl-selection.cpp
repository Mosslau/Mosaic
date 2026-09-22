// ex01-stl-selection.cpp —— 线性结构工程选型：array/vector/deque/list/queue/stack
// 对应主文档 3.1。教学点：vector 是默认容器（连续内存 + O(1) 下标 + 摊还 O(1) 尾插）；
// deque 双端 O(1)；list 只有「迭代器稳定 + O(1) 删除」硬需求才用；queue/stack 是适配器。
// 验证环境：Apple clang 21.0.0（/usr/bin/clang++），macOS arm64 + libc++
// 编译/运行：clang++ -std=c++20 -Wall -Wextra ex01-stl-selection.cpp -o /tmp/ph21-ex01 && /tmp/ph21-ex01
// 验证状态：已验证（编译零警告、断言全绿、退出码 0）
#include <array>
#include <deque>
#include <iostream>
#include <list>
#include <queue>
#include <stack>
#include <string>
#include <vector>

namespace {

void require(bool cond, const char* what) {
    if (!cond) {
        std::cerr << "FAIL: " << what << '\n';
        std::exit(1);
    }
}

void show_capacity_growth() {
    // 观察 vector 的翻倍扩容：capacity 在 size 超过时跳跃式增长（libc++ 约 2 倍）
    std::vector<int> v;
    std::cout << "vector capacity growth (no reserve):\n";
    for (int i = 1; i <= 8; ++i) {
        v.push_back(i);
        std::cout << "  size=" << v.size() << " capacity=" << v.capacity() << '\n';
    }
    require(v.capacity() >= v.size(), "capacity >= size always");
}

void demo_vector() {
    std::vector<int> v;
    v.reserve(8);                       // 预分配：知道量级就 reserve，免扩容搬移
    v.push_back(3);
    v.push_back(1);
    v[0] = 2;                           // O(1) 下标访问是 vector 的核心优势
    v.push_back(5);
    require(v.size() == 3 && v[0] == 2 && v[2] == 5, "vector push/subscript");

    // 中间插入 O(n)：n 小时 cache 优势盖过搬移成本，别急着换 list
    v.insert(v.begin() + 1, 9);
    require(v[1] == 9, "vector middle insert shifts");
}

void demo_deque_list() {
    std::deque<int> dq{1, 2, 3};
    dq.push_front(0);                   // deque 头尾都 O(1)，内存分块连续
    dq.push_back(4);
    require(dq.front() == 0 && dq.back() == 4, "deque both ends O(1)");

    std::list<int> lst{1, 2, 3, 4};
    auto it = lst.begin();
    ++it;                                // 指向 2
    lst.insert(it, 20);                  // 拿到迭代器后 O(1) 插入
    lst.erase(std::next(lst.begin()));   // 删回 2
    lst.splice(lst.begin(), lst, std::prev(lst.end()));  // 把 4 移到头部：list 专长
    require(lst.front() == 4 && lst.size() == 4, "list splice/insert/erase");
}

void demo_adaptors() {
    std::queue<int> q;                   // 容器适配器：默认 deque 打底
    q.push(10);
    q.push(20);
    require(q.front() == 10 && q.back() == 20, "queue FIFO view");
    q.pop();
    require(q.front() == 20, "queue pop front");

    std::stack<int> st;
    st.push(1);
    st.push(2);
    require(st.top() == 2, "stack LIFO view");
    st.pop();
    require(st.top() == 1, "stack pop top");

    std::array<int, 4> a{1, 2, 3, 4};    // 定长、栈上/内嵌：优先于 C 数组（SL.con.1）
    require(a.size() == 4 && a[3] == 4, "std::array fixed size");
}

}  // namespace

int main() {
    show_capacity_growth();
    demo_vector();
    demo_deque_list();
    demo_adaptors();
    std::cout << "ex01-stl-selection OK\n";
    return 0;
}
