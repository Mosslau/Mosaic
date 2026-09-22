// exercises/sol-01-student-class.cpp —— 练习 1 参考实现：学生类
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 sol-01-student-class.cpp -o sol01
// 运行：./sol01
// 已验证：本环境编译零警告，输出 Alice [101]: 85 / passed 与 Bob [102]: 55 / failed
#include <iostream>
#include <string>

class Student {
public:
    Student(const std::string& name, int id, double score)
        : name_(name), id_(id), score_(score) {}

    void print() const {
        std::cout << name_ << " [" << id_ << "]: " << score_ << "\n";
    }
    bool passed() const { return score_ >= 60.0; }

private:
    std::string name_;
    int id_;
    double score_;
};

int main() {
    const Student a{"Alice", 101, 85.0};
    const Student b{"Bob", 102, 55.0};
    a.print();
    std::cout << (a.passed() ? "passed" : "failed") << "\n";
    b.print();
    std::cout << (b.passed() ? "passed" : "failed") << "\n";
    return 0;
}
