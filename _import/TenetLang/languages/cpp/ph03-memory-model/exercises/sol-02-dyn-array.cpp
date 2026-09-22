// exercises/sol-02-dyn-array.cpp —— 动态数组类参考实现（深拷贝）
// 教学性例外：为演示「手写动态容器」内部实现使用裸 new[]/delete[]（Rule of 5 的目标场景）。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-02-dyn-array.cpp -o sol02
// 运行：./sol02
// 已验证：本环境编译零警告，全部断言通过
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <iostream>

class DynArray {
public:
    explicit DynArray(size_t cap)
        : data_(cap > 0 ? new int[cap] : nullptr), capacity_(cap), size_(0) {}
    ~DynArray() { delete[] data_; }

    DynArray(const DynArray& other)
        : data_(other.capacity_ > 0 ? new int[other.capacity_] : nullptr),
          capacity_(other.capacity_), size_(other.size_) {
        std::copy(other.data_, other.data_ + other.size_, data_);   // 深拷贝
    }
    DynArray& operator=(const DynArray& other) {
        if (this == &other) return *this;
        int* tmp = other.capacity_ > 0 ? new int[other.capacity_] : nullptr;
        std::copy(other.data_, other.data_ + other.size_, tmp);
        delete[] data_;
        data_ = tmp;
        capacity_ = other.capacity_;
        size_ = other.size_;
        return *this;
    }

    bool push(int val) {
        if (size_ >= capacity_) return false;      // 容量满则失败（本阶段不做扩容）
        data_[size_++] = val;
        return true;
    }
    int at(size_t i) const { return (i < size_) ? data_[i] : -1; }
    size_t size() const { return size_; }
    size_t capacity() const { return capacity_; }

private:
    int* data_ = nullptr;
    size_t capacity_ = 0;
    size_t size_ = 0;
};

int main() {
    DynArray a(3);
    assert(a.push(1) && a.push(2) && a.push(3));
    assert(!a.push(4));                            // 满返回 false

    DynArray b = a;                                // 深拷贝构造
    assert(b.size() == 3 && b.at(0) == 1 && b.at(2) == 3);

    // 深拷贝独立性：a 被拷贝赋值重写后，b 不受影响（各自独立内存）
    DynArray c(2);
    assert(c.push(7) && c.push(8));
    a = c;                                         // 拷贝赋值
    assert(a.size() == 2 && a.at(0) == 7);
    assert(b.size() == 3 && b.at(0) == 1);         // b 保持原值

    assert(a.at(99) == -1);                        // 越界返回 -1

    std::cout << "sol-02 全部断言通过\n";
    return 0;
}
