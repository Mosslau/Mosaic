// 来源：languages/cpp/ph07-exception-safety/07-exception-safety.md 第 6 章示例 2
// 说明：copy-and-swap 实现强异常保证的类
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 examples/ex02-copy-swap.cpp -o ex02
// 运行：./ex02
// 验证状态：已验证
#include <cstring>
#include <iostream>
#include <utility>

class StringBuf {
public:
    explicit StringBuf(const char* s = "") {
        size_ = std::strlen(s);
        data_ = new char[size_ + 1];
        std::strcpy(data_, s);
    }
    StringBuf(const StringBuf& other) : StringBuf(other.data_) {}  // 深拷贝
    StringBuf(StringBuf&& other) noexcept
        : data_(other.data_), size_(other.size_) {
        other.data_ = nullptr;
        other.size_ = 0;
    }
    ~StringBuf() { delete[] data_; }
    StringBuf& operator=(StringBuf other) noexcept {  // 强保证赋值
        swap(other);
        return *this;
    }
    void swap(StringBuf& other) noexcept {
        using std::swap;
        swap(data_, other.data_);
        swap(size_, other.size_);
    }
    const char* c_str() const { return data_ ? data_ : ""; }
    size_t size() const { return size_; }
private:
    char* data_;
    size_t size_;
};

int main() {
    StringBuf a("hello"), b("world");
    a = b;                                  // 拷贝赋值
    std::cout << "a=" << a.c_str() << "\n";
    StringBuf c("temp");
    c = std::move(b);                       // 移动赋值（走移动构造参数）
    std::cout << "c=" << c.c_str() << " b.size=" << b.size() << "\n";
    StringBuf d("self");
    StringBuf& self = d;
    d = self;                               // 自赋值安全（传值拷贝 + swap；经引用绕过 -Wself-assign）
    std::cout << "self-assign ok: " << d.c_str() << "\n";
    return 0;
}
