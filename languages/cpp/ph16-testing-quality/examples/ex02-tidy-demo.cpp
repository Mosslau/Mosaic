// examples/ex02-tidy-demo.cpp —— clang-tidy 演示：坏版本触发 4 条告警，-DEX02_FIXED 为修复版
// 验证环境：clang-tidy 21.1.8（/opt/homebrew/opt/llvm/bin/clang-tidy），Apple clang 21.0.0
// 运行前提：坏版本（默认）专门给 clang-tidy 看，刻意违反 4 条规范
//           （编译时还会自带 1 条 -Wrange-loop-construct 警告——教学点：编译器自身
//           是第一道静态分析，clang-tidy 是第二道、规则更多）；
//           修复版加 -DEX02_FIXED，clang-tidy 零告警、双编译器 -Wall -Wextra 零警告。
//
// 用法（已验证）：
//   clang-tidy ex02-tidy-demo.cpp --config-file=ex02.clang-tidy -- -std=c++20
//   clang-tidy ex02-tidy-demo.cpp --config-file=ex02.clang-tidy -- -std=c++20 -DEX02_FIXED
#ifdef EX02_FIXED
#include <string>
#include <vector>

namespace ex02 {

// 修复点 1（cppcoreguidelines-special-member-functions）：基类析构 =default（C.35），
// 成员全是值类型 → Rule of Zero，不手写任何特殊成员函数
class Shape {
public:
    virtual ~Shape() = default;
    virtual double area() const = 0;
};

// 修复点 2（modernize-use-override）：虚函数重写必须标 override（C.128）
class Circle final : public Shape {
public:
    explicit Circle(double r) : radius_(r) {}
    double area() const override { return 3.14159265358979 * radius_ * radius_; }

private:
    double radius_;
};

// 修复点 3（modernize-use-nullptr）：空指针用 nullptr（ES.47）
inline const char* lookup_env() {
    return nullptr;
}

// 修复点 4（performance-for-range-copy）：范围 for 按 const& 取元素
inline double total_label_len(const std::vector<std::string>& names) {
    double total = 0;
    for (const std::string& name : names) {
        total += static_cast<double>(name.size());
    }
    return total;
}

}  // namespace ex02

int main() {
    const ex02::Circle c(2.0);
    std::printf("area=%.2f\n", c.area());
    std::printf("env=%s\n", ex02::lookup_env() == nullptr ? "null" : "set");
    const std::vector<std::string> names{"alpha", "beta", "gamma"};
    std::printf("total=%.0f\n", ex02::total_label_len(names));
    return 0;
}

#else  // ---- 坏版本：触发 4 条 clang-tidy 告警（教学性覆盖，见首行注释） ----

#include <cstdio>
#include <string>
#include <vector>

// 告警 1（cppcoreguidelines-special-member-functions）：
// 自定义了析构函数却没有处理拷贝/移动（违反 Rule of Five，C.21）
class Shape {
public:
    virtual ~Shape() {}                       // 用户提供的空析构 → 触发检查
    virtual double area() const { return 0.0; }
};

// 告警 2（modernize-use-override）：重写虚函数没标 override（C.128）
class Circle : public Shape {
public:
    explicit Circle(double r) : radius_(r) {}
    double area() const { return 3.14159265358979 * radius_ * radius_; }  // 应标 override

private:
    double radius_;
};

// 告警 3（modernize-use-nullptr）：C 风格空指针（ES.47）
static const char* lookup_env() {
    return NULL;                              // 应为 nullptr
}

// 告警 4（performance-for-range-copy）：范围 for 按值拷贝 std::string
static double total_label_len(const std::vector<std::string>& names) {
    double total = 0;
    for (const std::string name : names) {    // 应为 const std::string&
        total += static_cast<double>(name.size());
    }
    return total;
}

int main() {
    const Circle c(2.0);
    std::printf("area=%.2f\n", c.area());
    std::printf("env=%s\n", lookup_env() == NULL ? "null" : "set");
    const std::vector<std::string> names{"alpha", "beta", "gamma"};
    std::printf("total=%.0f\n", total_label_len(names));
    return 0;
}

#endif  // EX02_FIXED
