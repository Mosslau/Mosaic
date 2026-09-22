// examples/ex05-rvo-noexcept.cpp —— RVO 与 noexcept 综合演示
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex05-rvo-noexcept.cpp -o ex05
// 运行：./ex05
// 已验证：本环境编译零警告，输出体现 NRVO/RVO 省略与 noexcept 移动扩容
#include <iostream>
#include <vector>

struct Tracker {
    int id;
    explicit Tracker(int i) : id(i) { std::cout << "ctor " << id << "\n"; }
    Tracker(const Tracker& o) : id(o.id) { std::cout << "copy " << id << "\n"; }
    Tracker(Tracker&& o) noexcept : id(o.id) {
        std::cout << "move " << id << "\n";
        o.id = -1;
    }
    ~Tracker() { std::cout << "dtor " << id << "\n"; }
};

Tracker create(int i) { Tracker t(i); return t; }          // NRVO：t 直接构造在返回槽
Tracker create_rvo(int i) { return Tracker(i); }           // RVO：C++17 强制省略

int main() {
    std::cout << "=== NRVO ===\n";
    Tracker t1 = create(1);
    std::cout << "\n=== RVO ===\n";
    Tracker t2 = create_rvo(2);
    std::cout << "\n=== vector with noexcept move ===\n";
    std::vector<Tracker> v;
    v.reserve(1);
    v.emplace_back(3);
    std::cout << "resize (will move due to noexcept):\n";
    v.emplace_back(4);  // 扩容 → 移动旧元素（因 noexcept）
    std::cout << "\n=== done ===\n";
    return 0;
}
