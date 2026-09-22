// ex02-const-member-functions.cpp —— const 成员函数与 const 对象（Con.2）
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex02-const-member-functions.cpp -o /tmp/ph14-ex02
// 运行：/tmp/ph14-ex02
#include <cstdio>
#include <string>
#include <type_traits>
#include <utility>

class Sensor {
public:
    explicit Sensor(std::string id, double reading)
        : id_(std::move(id)), reading_(reading) {}

    // Con.2：不修改对象状态的成员函数标 const。
    // 返回引用时，const 版本返回 const&（只读句柄），非 const 版本返回 &（可变句柄）。
    const std::string& id() const { return id_; }
    std::string& id() { return id_; }
    double reading() const { return reading_; }

    // const / 非 const 重载：同一签名加 const 是两个不同函数；非 const 对象优先选非 const 版
    const char* access() const { return "const access()"; }
    const char* access() { return "non-const access()"; }

    // 修改状态：只有非 const 对象/句柄能调用（const 对象调用是编译错误）
    void calibrate(double offset) { reading_ += offset; }

private:
    std::string id_;
    double reading_;
};

// 只读接口：const& 参数，只能调 const 成员（本函数内无法修改 s）
void print_reading(const Sensor& s) {
    std::printf("  %s reading=%.1f\n", s.id().c_str(), s.reading());
}

int main() {
    Sensor s("sensor-1", 36.5);          // 非 const 对象：全部成员可用
    const Sensor cs("sensor-const", 22.0);  // const 对象：只能调 const 成员

    std::printf("[1] 非 const 对象：可变与非可变成员都能调\n");
    s.calibrate(1.5);
    print_reading(s);
    std::printf("  s.access() -> %s\n", s.access());   // 选非 const 重载

    std::printf("[2] const 对象：只能调 const 成员（cs.calibrate 编译期拒绝）\n");
    print_reading(cs);                                  // 走 const 版本 id()
    std::printf("  cs.access() -> %s\n", cs.access());  // 选 const 重载

    std::printf("[3] 返回引用：const 版本返回 const&（可变句柄被没收）\n");
    static_assert(std::is_same_v<decltype(cs.id()), const std::string&>);
    static_assert(std::is_same_v<decltype(s.id()), std::string&>);
    std::printf("  cs.id() 类型 = const std::string&；s.id() 类型 = std::string&\n");

    std::printf("[4] 可变句柄的后果：非 const 对象可改名，const 对象不可\n");
    s.id() = "renamed";                 // 可变句柄：允许
    // cs.id() = "x";                   // 编译错误：const std::string& 不可赋值
    std::printf("  s.id() 被改为 %s（非 const 句柄）；cs.id() 只能读\n", s.id().c_str());

    std::printf("[5] std::as_const（C++17）：把可变句柄临时当 const 用\n");
    std::printf("  std::as_const(s).access() -> %s\n", std::as_const(s).access());
    return 0;
}
