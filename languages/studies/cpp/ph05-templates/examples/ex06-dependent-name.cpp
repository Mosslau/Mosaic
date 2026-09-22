// 来源：05-templates.md 第 6 章示例 6 —— 依赖名称消歧义（typename / template）
// 一句话说明：C::value_type 是依赖类型名需要 typename；w.template to<U> 标记依赖成员模板；
//             两阶段名称查找在实例化点解析这两类依赖名称。
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex06-dependent-name.cpp -o ex06-dependent-name
// 运行：./ex06-dependent-name
// 验证状态：已验证
#include <iostream>
#include <vector>

template<typename C>
void show_first(const C& c) {
    if (c.empty()) return;
    typename C::value_type v = c.front();   // typename：value_type 是依赖类型名
    std::cout << "first: " << v << "\n";
}

template<typename T>
struct Wrap {
    template<typename U>
    U to(const T& val) const { return static_cast<U>(val); }
};

template<typename W>
void demo(const W& w, int x) {
    auto d = w.template to<double>(x);      // template：to 是依赖成员模板
    std::cout << "to<double>: " << d << "\n";
}

int main() {
    std::vector<int> v = {10, 20, 30};
    show_first(v);
    Wrap<int> w;
    demo(w, 42);
    return 0;
}
