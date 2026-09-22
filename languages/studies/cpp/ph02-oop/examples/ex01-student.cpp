// examples/ex01-student.cpp —— Student 类：封装、成员初始化列表、const 成员函数
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex01-student.cpp -o ex01
// 运行：./ex01
// 已验证：本环境编译零警告，输出 Bob [2001]: 78.5 / passed
#include <iostream>
#include <string>

class Student {
public:
    Student(const std::string& name, int id, double score)
        : name_(name), id_(id), score_(score) {}  // 成员初始化列表（C.41）

    void print() const {  // Con.2：不修改状态的成员函数标 const
        std::cout << name_ << " [" << id_ << "]: " << score_ << "\n";
    }
    bool passed() const { return score_ >= 60.0; }

private:
    std::string name_;
    int id_;
    double score_;
};

int main() {
    const Student s{"Bob", 2001, 78.5};
    s.print();
    std::cout << (s.passed() ? "passed" : "failed") << "\n";
    return 0;
}
