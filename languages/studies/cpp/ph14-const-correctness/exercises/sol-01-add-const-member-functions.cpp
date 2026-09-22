// sol-01-add-const-member-functions.cpp —— 练习 1 参考实现：给旧类补 const 成员函数
// 练习 1 要求：把 LegacyDevice 中"只读"的成员函数全部标 const（Con.2），
//              可变句柄 label() 保留非 const 版本并补 const 版本（const& 返回），
//              用成员指针类型断言 + const 对象实测验证。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   [A] 修复前：name() 未标 const，const 对象调用是编译错误
//     （旧代码 Device::name 没有 const 限定——cs.name() 无法编译）
//   [B] 修复后：只读成员全部 const，成员指针类型断言通过
//     &Device::name    类型 = std::string (Device::*)() const
//     &Device::version 类型 = int (Device::*)() const
//     &Device::online  类型 = bool (Device::*)() const
//   [C] const 对象实测：只读接口全部可用
//     const 设备: name=alpha version=2 online=true
//   [D] 可变句柄保留：非 const 对象可改 label，const 对象只能读
//     label 已改为 main-pump
//     非 const 句柄 = std::string&；const 句柄 = const std::string&
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-01-add-const-member-functions.cpp -o /tmp/ph14-sol-01
// 运行：    /tmp/ph14-sol-01
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cstdio>
#include <string>
#include <type_traits>
#include <utility>

// 旧代码（修复前）：全部成员函数都没标 const —— const 对象无法调用任何查询
class Device {
public:
    explicit Device(std::string name, int version, bool online)
        : name_(std::move(name)), version_(version), online_(online) {}

    // 修复 1：只读查询全部标 const（Con.2）—— 不修改对象状态的成员函数应标 const
    std::string name() const { return name_; }
    int version() const { return version_; }
    bool online() const { return online_; }

    // 修复 2：可变句柄 label() 保留非 const 版本（std::string&），
    //         同时补 const 版本（const std::string&，只读句柄）
    std::string& label() { return label_; }
    const std::string& label() const { return label_; }

private:
    std::string name_;
    int version_;
    bool online_;
    std::string label_{"pump"};
};

// 编译期验证：成员指针类型把 const 编码进类型（未标 const 时类型不含 const）
static_assert(std::is_same_v<decltype(&Device::name), std::string (Device::*)() const>);
static_assert(std::is_same_v<decltype(&Device::version), int (Device::*)() const>);
static_assert(std::is_same_v<decltype(&Device::online), bool (Device::*)() const>);

int main() {
    std::printf("[A] 修复前：name() 未标 const，const 对象调用是编译错误\n");
    std::printf("  （旧代码 Device::name 没有 const 限定——cs.name() 无法编译）\n");

    std::printf("[B] 修复后：只读成员全部 const，成员指针类型断言通过\n");
    std::printf("  &Device::name    类型 = std::string (Device::*)() const\n");
    std::printf("  &Device::version 类型 = int (Device::*)() const\n");
    std::printf("  &Device::online  类型 = bool (Device::*)() const\n");

    Device dev("alpha", 2, true);
    const Device& cdev = dev;            // const 对象/句柄
    std::printf("[C] const 对象实测：只读接口全部可用\n");
    std::printf("  const 设备: name=%s version=%d online=%s\n",
                cdev.name().c_str(), cdev.version(), cdev.online() ? "true" : "false");

    std::printf("[D] 可变句柄保留：非 const 对象可改 label，const 对象只能读\n");
    dev.label() = "main-pump";           // 非 const 句柄：可写
    std::printf("  label 已改为 %s\n", cdev.label().c_str());
    static_assert(std::is_same_v<decltype(dev.label()), std::string&>);
    static_assert(std::is_same_v<decltype(cdev.label()), const std::string&>);
    std::printf("  非 const 句柄 = std::string&；const 句柄 = const std::string&\n");
    return 0;
}
