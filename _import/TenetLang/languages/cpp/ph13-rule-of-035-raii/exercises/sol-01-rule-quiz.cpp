// sol-01-rule-quiz.cpp —— 练习 1 参考实现：判断类是否需要自定义特殊成员函数
// 练习 1 要求：对 4 个类做出 Rule of 0/3/5 抉择，并用 static_assert 验证判断。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   [A] 纯值成员 struct       → Rule of 0：五个都不用写
//     is_copy_constructible: 1  is_move_constructible: 1
//   [B] 持有裸 FILE*          → 必须自定义：move-only（或 Rule of 5）
//     is_copy_constructible: 0  is_move_constructible: 1
//   [C] 含 mutex 成员          → Rule of 0 仍成立；拷贝被 mutex 隐式删除
//     is_copy_constructible: 0  is_move_constructible: 0
//   [D] 多态基类               → 必须写 virtual 析构；派生类 Rule of 0
//     基类虚析构: 已声明  派生类无需任何手写特殊成员
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-01-rule-quiz.cpp -o /tmp/ph13-sol-01
// 运行：    /tmp/ph13-sol-01
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cstdio>
#include <mutex>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

// [A] 纯值成员：Rule of 0（C.20）—— 编译器生成的五个特殊成员就是正确答案
struct Record {
    std::string key;
    std::vector<int> values;
};
static_assert(std::is_copy_constructible_v<Record>);
static_assert(std::is_move_constructible_v<Record>);
static_assert(std::is_copy_assignable_v<Record>);
static_assert(std::is_move_assignable_v<Record>);

// [B] 持有裸资源（FILE*）：析构要 fclose ⇒ 按 C.21 必须处理拷贝/移动。
//     选择 move-only（所有权唯一最贴切）：=delete 拷贝，手写 noexcept 移动。
class LogFile {
public:
    explicit LogFile(const char* path) : fp_(std::fopen(path, "a")) {}
    ~LogFile() { if (fp_ != nullptr) std::fclose(fp_); }
    LogFile(const LogFile&) = delete;
    LogFile& operator=(const LogFile&) = delete;
    LogFile(LogFile&& o) noexcept : fp_(std::exchange(o.fp_, nullptr)) {}
    LogFile& operator=(LogFile&& o) noexcept {
        if (this != &o) {
            if (fp_ != nullptr) std::fclose(fp_);
            fp_ = std::exchange(o.fp_, nullptr);
        }
        return *this;
    }
private:
    std::FILE* fp_;
};
static_assert(!std::is_copy_constructible_v<LogFile>);
static_assert(std::is_move_constructible_v<LogFile>);

// [C] 含 mutex：Rule of 0 仍然成立——std::mutex 不可拷贝不可移动，
//     编译器自动删除本类的拷贝与移动。不需要手写任何东西。
class Counter {
public:
    void add(int v) {
        std::lock_guard<std::mutex> lk(mu_);
        total_ += v;
    }
    int total() const {
        std::lock_guard<std::mutex> lk(mu_);
        return total_;
    }
private:
    mutable std::mutex mu_;
    int total_{0};
};
static_assert(!std::is_copy_constructible_v<Counter>);   // mutex 隐式删除
static_assert(!std::is_move_constructible_v<Counter>);

// [D] 多态基类：必须 public virtual 析构（C.35）；派生类回到 Rule of 0
class Shape {
public:
    virtual ~Shape() = default;
    virtual double area() const = 0;
};
class Circle : public Shape {
public:
    explicit Circle(double r) : r_(r) {}
    double area() const override { return 3.14 * r_ * r_; }
private:
    double r_;
};
static_assert(std::has_virtual_destructor_v<Shape>);
static_assert(std::is_copy_constructible_v<Circle>);   // 派生类什么都没写

int main() {
    std::printf("[A] 纯值成员 struct       → Rule of 0：五个都不用写\n");
    std::printf("  is_copy_constructible: %d  is_move_constructible: %d\n",
                std::is_copy_constructible_v<Record>,
                std::is_move_constructible_v<Record>);

    std::printf("[B] 持有裸 FILE*          → 必须自定义：move-only（或 Rule of 5）\n");
    std::printf("  is_copy_constructible: %d  is_move_constructible: %d\n",
                std::is_copy_constructible_v<LogFile>,
                std::is_move_constructible_v<LogFile>);

    std::printf("[C] 含 mutex 成员          → Rule of 0 仍成立；拷贝被 mutex 隐式删除\n");
    std::printf("  is_copy_constructible: %d  is_move_constructible: %d\n",
                std::is_copy_constructible_v<Counter>,
                std::is_move_constructible_v<Counter>);

    std::printf("[D] 多态基类               → 必须写 virtual 析构；派生类 Rule of 0\n");
    Circle c(2.0);
    Shape& s = c;
    std::printf("  基类虚析构: 已声明  派生类无需任何手写特殊成员（area=%.2f）\n",
                s.area());

    // 判断口诀（见 exercises/README.md 练习 1 的验收标准）：
    //   1. 成员是否自己管理资源？是 → Rule of 0
    //   2. 类自己持有裸资源？是 → 析构 + 拷贝/移动（C.21），通常 move-only
    //   3. 要当多态基类？是 → public virtual 析构（C.35）
    return 0;
}
