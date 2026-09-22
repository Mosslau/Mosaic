// sol-01-lifetime-predict.cpp —— 练习 1 参考实现：预测并验证临时对象生命周期
// 练习 1 要求：写出三种场景（未绑定临时对象 / const& 绑定 / 作为函数参数）的
//   观察程序，先预测打印顺序，再运行验证，并解释每条规则。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   场景 A：未绑定临时对象
//     ctor A
//     dtor A
//   场景 B：const& 延长
//     ctor B
//     inside
//     dtor B
//   B scope end
//   场景 C：函数参数
//     ctor C
//     use C
//     dtor C
//   C call end
//   预测要点：
//   - 场景 A：make("A") 的临时对象在完整表达式（语句）结束时析构 → ctor 紧接 dtor
//   - 场景 B：const Item& r 绑定临时对象 → 生命周期延长到引用所在作用域结束
//     （dtor 出现在 "inside" 之后、"B scope end" 之前）
//   - 场景 C：作为 const& 参数传入的临时对象活到调用语句结束 → ctor→use→dtor
//     （调用期间读取安全；但若把参数引用"逃逸"出去则会悬空，见 ex05）
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-01-lifetime-predict.cpp -o /tmp/sol-01
// 运行：    /tmp/sol-01
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cstdio>
#include <string>
#include <utility>

struct Item {
    std::string tag;
    explicit Item(const char* t) : tag(t) {
        std::printf("  ctor %s\n", tag.c_str());
    }
    Item(const Item& o) : tag(o.tag + "(c)") {
        std::printf("  copy %s\n", tag.c_str());
    }
    Item(Item&& o) noexcept : tag(std::move(o.tag) + "(m)") {
        std::printf("  move %s\n", tag.c_str());
    }
    ~Item() { std::printf("  dtor %s\n", tag.c_str()); }
};

// 按值返回：C++17 保证省略，Item(t) 直接构造到返回槽
Item make(const char* t) { return Item(t); }

// const& 参数：只借用，不拥有
void use(const Item& it) { std::printf("  use %s\n", it.tag.c_str()); }

int main() {
    std::printf("场景 A：未绑定临时对象\n");
    make("A");                      // 临时对象在语句结束析构
    std::printf("场景 B：const& 延长\n");
    {
        const Item& r = make("B");  // 延长到本作用域结束
        std::printf("  inside\n");
    }
    std::printf("B scope end\n");
    std::printf("场景 C：函数参数\n");
    use(make("C"));                 // 参数临时对象活到调用语句结束
    std::printf("C call end\n");
    return 0;
}
