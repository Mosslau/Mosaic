// 来源：05-templates.md 第 6 章示例 2 —— 类模板 Stack<T> + 全特化/偏特化
// 一句话说明：同一个模板家族三个版本 —— 主模板（vector）、bool 全特化（deque 位压缩）、
//             指针偏特化（自动解引用），演示编译器选「最特化」版本。
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex02-class-template.cpp -o ex02-class-template
// 运行：./ex02-class-template
// 验证状态：已验证
#include <cstddef>
#include <deque>
#include <iostream>
#include <utility>
#include <vector>

template<typename T>
class Stack {
public:
    void push(const T& v) { data_.push_back(v); }
    T pop() { T v = std::move(data_.back()); data_.pop_back(); return v; }
    bool empty() const { return data_.empty(); }
    std::size_t size() const { return data_.size(); }
private:
    std::vector<T> data_;
};

// 全特化：bool → deque<bool> 位压缩（每个 bool 只占 1 bit）
template<>
class Stack<bool> {
public:
    void push(bool v) { data_.push_back(v); }
    bool pop() { bool v = data_.back(); data_.pop_back(); return v; }
    bool empty() const { return data_.empty(); }
    std::size_t size() const { return data_.size(); }
private:
    std::deque<bool> data_;
};

// 偏特化：指针版本 → 存储裸指针，对外自动解引用
template<typename T>
class Stack<T*> {
public:
    void push(T* p) { data_.push_back(p); }
    T* pop() { T* v = data_.back(); data_.pop_back(); return v; }
    T& top() { return *data_.back(); }
    bool empty() const { return data_.empty(); }
    std::size_t size() const { return data_.size(); }
private:
    std::vector<T*> data_;
};

int main() {
    Stack<int> si; si.push(42);
    Stack<bool> sb; sb.push(true); sb.push(false);
    int a = 10, b = 20;
    Stack<int*> sp; sp.push(&a); sp.push(&b);
    std::cout << "int=" << si.size()
              << " bool=" << sb.size()
              << " ptr-top=" << sp.top() << "\n";
    return 0;
}
