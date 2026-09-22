// project/student_manager.cpp —— 阶段项目：学生管理系统（增删查改 + 简单菜单）
// 验证环境：Apple clang 17.0.0（g++ 兼容），C++17
// 编译：g++ -Wall -Wextra -std=c++17 student_manager.cpp -o student_manager
// 运行：./student_manager（交互式菜单；自动测试：echo -e "2\n6" | ./student_manager）
// 已验证：本环境编译零警告，交互流程与增删查改行为符合验收标准
#include <iostream>
#include <string>
#include <vector>

class Student {
public:
    Student(const std::string& name, int id, double score)
        : name_(name), id_(id), score_(score) {}

    void print() const {
        std::cout << "  " << name_ << " [id=" << id_ << "]: " << score_ << "\n";
    }
    int id() const { return id_; }
    double score() const { return score_; }
    void set_score(double score) { score_ = score; }
    void set_name(const std::string& name) { name_ = name; }

private:
    std::string name_;
    int id_;
    double score_;
};

class StudentManager {
public:
    // 增：学号重复则拒绝
    bool add(const Student& s) {
        if (find_index(s.id()) != npos) return false;
        students_.push_back(s);
        return true;
    }

    // 删：按学号删除，返回是否删到
    bool remove(int id) {
        const std::size_t i = find_index(id);
        if (i == npos) return false;
        students_.erase(students_.begin() + static_cast<std::ptrdiff_t>(i));
        return true;
    }

    // 改：按学号修改姓名与成绩，返回是否找到
    bool update(int id, const std::string& name, double score) {
        const std::size_t i = find_index(id);
        if (i == npos) return false;
        students_[i].set_name(name);
        students_[i].set_score(score);
        return true;
    }

    // 查：打印全部 / 按学号查 / 只打印及格学生
    void print_all() const {
        if (students_.empty()) {
            std::cout << "  (empty)\n";
            return;
        }
        for (const auto& s : students_) s.print();
    }

    bool print_by_id(int id) const {
        const std::size_t i = find_index(id);
        if (i == npos) return false;
        students_[i].print();
        return true;
    }

    void print_passed() const {
        bool any = false;
        for (const auto& s : students_) {
            if (s.score() >= kPassScore) {
                s.print();
                any = true;
            }
        }
        if (!any) std::cout << "  (none)\n";
    }

private:
    static constexpr double kPassScore = 60.0;  // ES.45：不用魔法数
    static constexpr std::size_t npos = static_cast<std::size_t>(-1);

    std::size_t find_index(int id) const {
        for (std::size_t i = 0; i < students_.size(); ++i)
            if (students_[i].id() == id) return i;
        return npos;
    }

    std::vector<Student> students_;
};

namespace {

void print_menu() {
    std::cout << "\n==== Student Manager ====\n"
              << "1. Add student\n"
              << "2. List all students\n"
              << "3. Find by id\n"
              << "4. Update by id\n"
              << "5. Remove by id\n"
              << "6. Quit\n"
              << "choice: ";
}

}  // namespace

int main() {
    StudentManager mgr;

    int choice = 0;
    while (true) {
        print_menu();
        if (!(std::cin >> choice)) break;  // EOF 或非法输入：退出

        switch (choice) {
            case 1: {
                std::string name;
                int id = 0;
                double score = 0.0;
                std::cout << "name id score: ";
                std::cin >> name >> id >> score;
                std::cout << (mgr.add(Student{name, id, score}) ? "added\n"
                                                                : "id exists\n");
                break;
            }
            case 2:
                mgr.print_all();
                break;
            case 3: {
                int id = 0;
                std::cout << "id: ";
                std::cin >> id;
                if (!mgr.print_by_id(id)) std::cout << "not found\n";
                break;
            }
            case 4: {
                std::string name;
                int id = 0;
                double score = 0.0;
                std::cout << "id new_name new_score: ";
                std::cin >> id >> name >> score;
                std::cout << (mgr.update(id, name, score) ? "updated\n"
                                                          : "not found\n");
                break;
            }
            case 5: {
                int id = 0;
                std::cout << "id: ";
                std::cin >> id;
                std::cout << (mgr.remove(id) ? "removed\n" : "not found\n");
                break;
            }
            case 6:
                return 0;
            default:
                std::cout << "unknown choice\n";
                break;
        }
    }
    return 0;
}
