// 03 · 多范式设计演示
// 编译运行：make && ./demos/03_multiparadigm
// 同一个"求和"，用四种范式实现——C++ 让它们并存于一门语言。

#include <algorithm>
#include <iostream>
#include <numeric>
#include <vector>

// ① 过程式：C 风格循环
int sum_procedural(const std::vector<int>& v) {
    int s = 0;
    for (size_t i = 0; i < v.size(); ++i) s += v[i];
    return s;
}

// ② 泛型：模板，任何可迭代类型都行
template <typename Container>
int sum_generic(const Container& c) {
    int s = 0;
    for (int x : c) s += x;
    return s;
}

// ③ 函数式：lambda + 标准算法
int sum_functional(const std::vector<int>& v) {
    return std::accumulate(v.begin(), v.end(), 0,
                           [](int a, int b) { return a + b; });
}

// ④ 面向对象：对象封装数据与行为
class SumBox {
public:
    void add(int x) { total_ += x; }
    int get() const { return total_; }

private:
    int total_ = 0;
};

int main() {
    std::vector<int> v = {1, 2, 3, 4, 5};

    std::cout << "过程式: " << sum_procedural(v) << "\n";
    std::cout << "泛型:   " << sum_generic(v) << "\n";
    std::cout << "函数式: " << sum_functional(v) << "\n";

    SumBox box;
    for (int x : v) box.add(x);
    std::cout << "面向对象: " << box.get() << "\n";

    std::cout << "\n四种范式共存于一门语言——灵活，但也要求使用者自律。\n";
}
