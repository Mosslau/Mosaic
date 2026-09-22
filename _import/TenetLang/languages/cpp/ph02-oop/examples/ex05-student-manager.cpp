// examples/ex05-student-manager.cpp —— 学生管理系统：用 std::vector 组合多个对象
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 ex05-student-manager.cpp -o ex05
// 运行：./ex05
// 已验证：本环境编译零警告，输出全部 3 名学生 + 2 名及格学生
#include <iostream>
#include <string>
#include <vector>

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

class StudentManager {
public:
    void add(const Student& s) { students_.push_back(s); }

    void print_all() const {
        for (const auto& s : students_) s.print();
    }

    void print_passed() const {
        for (const auto& s : students_)
            if (s.passed()) s.print();
    }

private:
    std::vector<Student> students_;  // 组合：管理类持有多个 Student
};

int main() {
    StudentManager mgr;
    mgr.add({"Alice", 101, 85.0});
    mgr.add({"Bob", 102, 55.0});
    mgr.add({"Carol", 103, 92.0});

    std::cout << "All students:\n";
    mgr.print_all();

    std::cout << "\nPassed students:\n";
    mgr.print_passed();
    return 0;
}
