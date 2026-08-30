// examples/ex01-shallow-copy.cpp —— 浅拷贝危害演示（double-free）
// 教学性「故意出错」示例：DangerString 只定义了析构、未定义拷贝构造/拷贝赋值，
// 编译器逐成员浅拷贝导致两个对象的 data_ 指向同一块堆内存，析构时 double-free。
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译（推荐，ASan 报告更清晰）：g++ -Wall -Wextra -std=c++17 -fsanitize=address ex01-shallow-copy.cpp -o ex01
// 编译（普通）：g++ -Wall -Wextra -std=c++17 ex01-shallow-copy.cpp -o ex01
// 运行：./ex01（预期：析构时 double-free 崩溃）
// 已验证：本环境两种方式编译均零警告；普通运行触发 double-free 崩溃（exit 133）。
//         ASan 在本环境受沙箱限制无法运行（进程被 SIGKILL），ASan 编译命令仅供读者在本机使用。
#include <cstring>
#include <iostream>

struct DangerString {
    char* data_;
    explicit DangerString(const char* s) {
        data_ = new char[std::strlen(s) + 1];
        std::strcpy(data_, s);
    }
    ~DangerString() { delete[] data_; }
    // 无拷贝构造/拷贝赋值 → 编译器逐成员浅拷贝（Rule of 3 违规）
};

int main() {
    std::cout << "=== shallow copy double-free demo ===\n";
    DangerString s1("hello");
    std::cout << "s1.data_ = " << static_cast<void*>(s1.data_) << "\n";
    {
        DangerString s2 = s1;  // 浅拷贝：两个 data_ 指向同一地址
        std::cout << "s2.data_ = " << static_cast<void*>(s2.data_) << " (same as s1)\n";
    }  // s2 析构，释放 data_
    std::cout << "s1.data_ = " << static_cast<void*>(s1.data_) << " (dangling)\n";
    return 0;
}  // s1 析构，double-free → 运行时 crash
