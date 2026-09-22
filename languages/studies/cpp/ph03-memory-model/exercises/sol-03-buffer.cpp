// exercises/sol-03-buffer.cpp —— 支持移动构造的 Buffer 参考实现
// 教学性例外：为演示「手写资源类」内部实现使用裸 new[]/delete[]（Rule of 5 的目标场景）。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-03-buffer.cpp -o sol03
// 运行：./sol03
// 已验证：本环境编译零警告，全部断言通过
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstring>
#include <iostream>
#include <type_traits>
#include <utility>

class Buffer {
public:
    explicit Buffer(size_t size)
        : data_(size > 0 ? new char[size] : nullptr), size_(size) {}
    ~Buffer() { delete[] data_; }

    Buffer(const Buffer& other)
        : data_(other.size_ > 0 ? new char[other.size_] : nullptr),
          size_(other.size_) {
        std::copy(other.data_, other.data_ + other.size_, data_);   // 深拷贝
    }
    Buffer& operator=(const Buffer& other) {
        if (this == &other) return *this;
        char* tmp = other.size_ > 0 ? new char[other.size_] : nullptr;
        std::copy(other.data_, other.data_ + other.size_, tmp);
        delete[] data_;
        data_ = tmp;
        size_ = other.size_;
        return *this;
    }
    Buffer(Buffer&& other) noexcept
        : data_(other.data_), size_(other.size_) {
        other.data_ = nullptr;                     // 窃取后清空源对象
        other.size_ = 0;
    }
    Buffer& operator=(Buffer&& other) noexcept {
        if (this == &other) return *this;
        delete[] data_;
        data_ = other.data_;
        size_ = other.size_;
        other.data_ = nullptr;
        other.size_ = 0;
        return *this;
    }

    char* data() { return data_; }
    const char* data() const { return data_; }
    size_t size() const { return size_; }

private:
    char* data_ = nullptr;
    size_t size_ = 0;
};

// 编译期验证：移动构造 / 移动赋值必须是 noexcept
static_assert(std::is_nothrow_move_constructible<Buffer>::value,
              "Buffer 移动构造必须 noexcept");
static_assert(std::is_nothrow_move_assignable<Buffer>::value,
              "Buffer 移动赋值必须 noexcept");

int main() {
    Buffer a(8);
    std::memset(a.data(), 'A', a.size());

    Buffer b = std::move(a);                       // 移动构造
    assert(b.size() == 8);
    assert(a.size() == 0);                         // 源对象被移空
    assert(a.data() == nullptr);
    assert(b.data()[0] == 'A');

    Buffer c = b;                                  // 拷贝构造（深拷贝）
    assert(c.data() != b.data());                  // 底层地址不同
    c.data()[0] = 'B';
    assert(b.data()[0] == 'A');                    // 拷贝独立性

    std::cout << "sol-03 全部断言通过\n";
    return 0;
}
