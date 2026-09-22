// 来源：exercises/ 练习 2 —— 泛型 Stack（题目见 exercises/README.md，题解分离）
// 一句话说明：Stack<T> 类模板，底层 std::vector<T>（Rule of Zero），
//             能 const 的成员函数全标 const。
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-02-generic-stack.cpp -o sol-02-generic-stack
// 运行：./sol-02-generic-stack
// 验证状态：已验证
#include <cassert>
#include <cstddef>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

template<typename T>
class Stack {
public:
    void push(const T& val) { data_.push_back(val); }
    void push(T&& val)      { data_.push_back(std::move(val)); }

    // 前置条件：栈非空。pop 移出栈顶元素并弹掉。
    T pop() {
        T v = std::move(data_.back());
        data_.pop_back();
        return v;
    }

    T& top()             { return data_.back(); }
    const T& top() const { return data_.back(); }

    bool empty() const { return data_.empty(); }
    std::size_t size() const { return data_.size(); }

private:
    std::vector<T> data_;   // Rule of Zero：标准库成员自己管理生命周期
};

int main() {
    // int 栈：LIFO
    Stack<int> si;
    si.push(10); si.push(20); si.push(30);
    assert(si.size() == 3);
    assert(si.top() == 30);
    assert(si.pop() == 30);
    assert(si.pop() == 20);
    assert(si.pop() == 10);
    assert(si.empty());

    // string 栈：非平凡类型（移动语义生效）
    Stack<std::string> ss;
    ss.push("hello");
    ss.push("world");
    assert(ss.pop() == "world");
    assert(ss.pop() == "hello");
    assert(ss.empty());

    std::cout << "泛型 Stack 全部断言通过\n";
    return 0;
}
