// examples/ex02-string.cpp —— 完整 String 类（五函数 + 测试）
// 教学性例外：为演示「手写资源类」内部实现使用裸 new[]/delete[]（Rule of 5 的目标场景），
// 业务代码应改用 std::string（Rule of 0）。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex02-string.cpp -o ex02
// 运行：./ex02
// 已验证：本环境编译零警告，输出与注释中期望一致
#include <cstring>
#include <iostream>
#include <utility>

class String {
public:
    explicit String(const char* s = "") {
        size_ = std::strlen(s);
        data_ = new char[size_ + 1];
        std::strcpy(data_, s);
        std::cout << "ctor: \"" << data_ << "\"\n";
    }
    // 拷贝构造：深拷贝（独立堆内存），避免浅拷贝 double-free
    String(const String& other)
        : data_(new char[other.size_ + 1]), size_(other.size_) {
        std::strcpy(data_, other.data_);
        std::cout << "copy ctor: \"" << data_ << "\"\n";
    }
    // 拷贝赋值：先分配新内存再释放旧内存（异常安全的强保证）
    String& operator=(const String& other) {
        std::cout << "copy assign: \"" << other.data_ << "\"\n";
        if (this == &other) return *this;        // 自赋值检查
        char* tmp = new char[other.size_ + 1];
        std::strcpy(tmp, other.data_);
        delete[] data_;
        data_ = tmp;
        size_ = other.size_;
        return *this;
    }
    // 移动构造：窃取源对象指针后清空源对象，noexcept 保证容器扩容走移动
    String(String&& other) noexcept
        : data_(other.data_), size_(other.size_) {
        std::cout << "move ctor\n";
        other.data_ = nullptr;
        other.size_ = 0;
    }
    // 移动赋值：释放自身旧资源 → 窃取源对象资源 → 清空源对象
    String& operator=(String&& other) noexcept {
        std::cout << "move assign\n";
        if (this == &other) return *this;        // 自移动检查
        delete[] data_;
        data_ = other.data_;
        size_ = other.size_;
        other.data_ = nullptr;
        other.size_ = 0;
        return *this;
    }
    ~String() {
        std::cout << "dtor: " << (data_ ? data_ : "(moved-from)") << "\n";
        delete[] data_;
    }
    const char* c_str() const { return data_ ? data_ : ""; }
    size_t size() const { return size_; }

private:
    char* data_ = nullptr;   // 管理堆内存的裸指针（教学演示）
    size_t size_ = 0;
};

int main() {
    std::cout << "--- copy ---\n";
    String s1("hello");
    String s2 = s1;                    // 拷贝构造
    String s3("world");
    s3 = s1;                           // 拷贝赋值

    std::cout << "\n--- move ---\n";
    String s4 = std::move(s1);         // 移动构造，s1 被移空
    std::cout << "s1 after move: \"" << s1.c_str() << "\" (size=" << s1.size() << ")\n";
    String s5("temp");
    s5 = std::move(s4);                // 移动赋值
    std::cout << "s4 after move: \"" << s4.c_str() << "\" (size=" << s4.size() << ")\n";

    std::cout << "\n--- self-assign ---\n";
    const String& ref = s2;
    s2 = ref;                          // 自赋值安全
    String* ptr = &s2;
    s2 = std::move(*ptr);              // 自移动安全
    std::cout << "s2 after self tests: \"" << s2.c_str() << "\"\n";

    std::cout << "\n--- destroying ---\n";
    return 0;
}
