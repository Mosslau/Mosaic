// examples/ex03-dyn-array.cpp —— 动态数组类（布隆过滤器位数组语义）
// 教学性例外：为演示「手写动态容器」内部实现使用裸 new[]/delete[]（Rule of 5 的目标场景），
// 业务代码应改用 std::vector（Rule of 0）。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex03-dyn-array.cpp -o ex03
// 运行：./ex03
// 已验证：本环境编译零警告，输出与注释中期望一致
#include <algorithm>
#include <cstddef>
#include <iostream>
#include <utility>

class DynArray {
public:
    explicit DynArray(size_t cap = 0)
        : data_(cap > 0 ? new int[cap] : nullptr), capacity_(cap), size_(0) {}
    ~DynArray() { delete[] data_; }

    // 拷贝构造：深拷贝，两个对象各自持有独立堆内存
    DynArray(const DynArray& other)
        : data_(other.capacity_ > 0 ? new int[other.capacity_] : nullptr),
          capacity_(other.capacity_), size_(other.size_) {
        std::copy(other.data_, other.data_ + other.size_, data_);
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
    // 移动构造/赋值：窃取 + 清空源对象，noexcept 保证容器扩容走移动
    DynArray(DynArray&& other) noexcept
        : data_(other.data_), capacity_(other.capacity_), size_(other.size_) {
        other.data_ = nullptr;
        other.capacity_ = 0;
        other.size_ = 0;
    }
    DynArray& operator=(DynArray&& other) noexcept {
        if (this == &other) return *this;
        delete[] data_;
        data_ = other.data_;
        capacity_ = other.capacity_;
        size_ = other.size_;
        other.data_ = nullptr;
        other.capacity_ = 0;
        other.size_ = 0;
        return *this;
    }

    bool push(int val) {
        if (size_ >= capacity_) return false;   // 容量满则失败（本阶段不做扩容）
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
    DynArray buf(5);
    buf.push(10);
    buf.push(20);
    buf.push(30);

    DynArray copy = buf;                       // 深拷贝
    std::cout << "copy[0]=" << copy.at(0) << " copy[1]=" << copy.at(1) << "\n";

    DynArray moved = std::move(buf);           // 移动构造
    std::cout << "buf.size() after move: " << buf.size() << "\n";
    std::cout << "moved.size(): " << moved.size() << "\n";

    return 0;
}
