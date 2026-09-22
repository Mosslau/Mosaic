// 来源：04-stl.md 第 6 章示例 5 —— 迭代器失效演示与安全模式
// 一句话说明：演示两种迭代器失效场景——遍历删除必须用 it = erase(it) 安全模式；
//             push_back 扩容会使迭代器失效，reserve 可预防。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex05-iterator-invalidation.cpp -o ex05-iterator-invalidation
// 运行：./ex05-iterator-invalidation
// 验证状态：已验证
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
