// exercises/sol-01-string.cpp —— 简单 String 类参考实现（五函数）
// 教学性例外：为演示「手写资源类」内部实现使用裸 new[]/delete[]（Rule of 5 的目标场景）。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-01-string.cpp -o sol01
// 运行：./sol01
// 已验证：本环境编译零警告，全部断言通过
#include <cassert>
#include <cstring>
#include <iostream>
#include <utility>

class String {
public:
    explicit String(const char* s = "") {
        size_ = std::strlen(s);
        data_ = new char[size_ + 1];
        std::strcpy(data_, s);
    }
    String(const String& other)
        : data_(new char[other.size_ + 1]), size_(other.size_) {
        std::strcpy(data_, other.data_);           // 深拷贝
    }
    String& operator=(const String& other) {
        if (this == &other) return *this;          // 自赋值检查
        char* tmp = new char[other.size_ + 1];
        std::strcpy(tmp, other.data_);
        delete[] data_;
        data_ = tmp;
        size_ = other.size_;
        return *this;
    }
    String(String&& other) noexcept
        : data_(other.data_), size_(other.size_) {
        other.data_ = nullptr;                     // 窃取后清空源对象
        other.size_ = 0;
    }
    String& operator=(String&& other) noexcept {
        if (this == &other) return *this;          // 自移动检查
        delete[] data_;
        data_ = other.data_;
        size_ = other.size_;
        other.data_ = nullptr;
        other.size_ = 0;
        return *this;
    }
    ~String() { delete[] data_; }

    const char* c_str() const { return data_ ? data_ : ""; }
    size_t size() const { return size_; }

private:
    char* data_ = nullptr;
    size_t size_ = 0;
};

int main() {
    // 构造 + 拷贝构造
    String a("hello");
    String b = a;
    assert(std::strcmp(a.c_str(), "hello") == 0);
    assert(std::strcmp(b.c_str(), "hello") == 0);
    assert(a.c_str() != b.c_str());                // 深拷贝：底层地址不同

    // 拷贝赋值
    String c("world");
    c = a;
    assert(std::strcmp(c.c_str(), "hello") == 0);

    // 移动构造：源对象被移空
    String d = std::move(a);
    assert(std::strcmp(d.c_str(), "hello") == 0);
    assert(a.size() == 0);
    assert(std::strcmp(a.c_str(), "") == 0);

    // 移动赋值
    String e("temp");
    e = std::move(d);
    assert(std::strcmp(e.c_str(), "hello") == 0);
    assert(d.size() == 0);

    // 自赋值 / 自移动安全
    const String& ref = b;
    b = ref;
    assert(std::strcmp(b.c_str(), "hello") == 0);
    String* p = &b;
    b = std::move(*p);
    assert(std::strcmp(b.c_str(), "hello") == 0);

    std::cout << "sol-01 全部断言通过\n";
    return 0;
}
