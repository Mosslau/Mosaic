// 来源：exercises/ 练习 4 —— 简单 Optional（题目见 exercises/README.md，题解分离）
// 一句话说明：用 std::unique_ptr<T> 持有值实现最小 Optional<T>：
//             拷贝=深拷贝（Rule of Five），移动=默认，空态 value() 抛异常。
// 说明：std::unique_ptr 完整语义属于 ph06 智能指针阶段，这里只借用其 RAII 释放能力。
// 验证环境：Apple clang 17（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-04-simple-optional.cpp -o sol-04-simple-optional
// 运行：./sol-04-simple-optional
// 验证状态：已验证
#include <cassert>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>

template<typename T>
class Optional {
public:
    Optional() = default;                                       // 空

    Optional(const T& value) : ptr_(std::make_unique<T>(value)) {}
    Optional(T&& value)      : ptr_(std::make_unique<T>(std::move(value))) {}

    // 拷贝：unique_ptr 不可拷贝 → 手写深拷贝（C.21 Rule of Five）
    Optional(const Optional& other)
        : ptr_(other.ptr_ ? std::make_unique<T>(*other.ptr_) : nullptr) {}

    Optional& operator=(const Optional& other) {
        if (this != &other) {
            if (other.ptr_) ptr_ = std::make_unique<T>(*other.ptr_);
            else            ptr_.reset();
        }
        return *this;
    }

    // 移动：unique_ptr 原生支持，交给默认实现
    Optional(Optional&&) noexcept = default;
    Optional& operator=(Optional&&) noexcept = default;

    bool has_value() const { return ptr_ != nullptr; }
    explicit operator bool() const { return has_value(); }

    T& value() {
        if (!ptr_) throw std::logic_error("Optional<T>::value() on empty Optional");
        return *ptr_;
    }
    const T& value() const {
        if (!ptr_) throw std::logic_error("Optional<T>::value() on empty Optional");
        return *ptr_;
    }

    // 前置条件：非空（快速路径，不做检查）
    T& operator*()             { return *ptr_; }
    const T& operator*() const { return *ptr_; }

    void reset() { ptr_.reset(); }

private:
    std::unique_ptr<T> ptr_;
};

int main() {
    // 空态
    Optional<int> empty;
    assert(!empty.has_value());

    // 值态
    Optional<int> oi(42);
    assert(oi.has_value());
    assert(*oi == 42);
    assert(oi.value() == 42);
    assert(static_cast<bool>(oi));

    // 空态 value() 抛 std::logic_error
    bool threw = false;
    try {
        (void)empty.value();
    } catch (const std::logic_error&) {
        threw = true;
    }
    assert(threw);

    // 拷贝互不影响（深拷贝）
    Optional<int> copy = oi;
    *copy = 100;
    assert(*oi == 42);
    assert(*copy == 100);

    // 移动转移
    Optional<int> moved = std::move(copy);
    assert(moved.has_value());
    assert(*moved == 100);

    // string 值 + reset
    Optional<std::string> os(std::string("hello"));
    assert(os.value() == "hello");
    os.reset();
    assert(!os.has_value());

    std::cout << "简单 Optional 全部断言通过\n";
    return 0;
}
