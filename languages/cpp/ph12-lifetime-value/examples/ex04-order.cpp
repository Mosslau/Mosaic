// ex04-order.cpp —— 构造顺序与销毁顺序实测
// 主题：派生类构造 = 基类 → 按声明顺序的成员 → 构造函数体；销毁严格逆序。
//       初始化列表的书写顺序不改变成员构造顺序（编译器 -Wreorder-ctor 会告警提醒）。
//       函数局部静态对象：首次调用时构造、程序退出时析构（多个静态按构造完成逆序析构）。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex04-order.cpp -o /tmp/ex04
// 运行：    /tmp/ex04
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cstdio>

struct Base {
    Base() { std::printf("  Base ctor\n"); }
    ~Base() { std::printf("  Base dtor\n"); }
};

struct MemberA {
    MemberA() { std::printf("  MemberA ctor\n"); }
    ~MemberA() { std::printf("  MemberA dtor\n"); }
};

struct MemberB {
    MemberB() { std::printf("  MemberB ctor\n"); }
    ~MemberB() { std::printf("  MemberB dtor\n"); }
};

// 声明顺序：b_ 在 a_ 前 → 构造顺序 Base → b_ → a_（与初始化列表书写顺序无关）
struct Derived : Base {
    MemberB b_;
    MemberA a_;
    Derived() : b_{}, a_{} { std::printf("  Derived body\n"); }
    ~Derived() { std::printf("  Derived body end\n"); }
};

struct StaticA {
    StaticA() { std::printf("  StaticA ctor\n"); }
    ~StaticA() { std::printf("  StaticA dtor\n"); }
};

struct StaticB {
    StaticB() { std::printf("  StaticB ctor\n"); }
    ~StaticB() { std::printf("  StaticB dtor\n"); }
};

// 函数局部静态：只在首次调用时构造；多个静态按"构造完成"的逆序析构
void use_static(const char* tag) {
    static StaticA a;
    static StaticB b;
    std::printf("  %s: statics ready\n", tag);
}

// 命名空间作用域静态：main 之前构造；与函数局部静态按"构造完成逆序"统一析构
static StaticB g_file_b;
static StaticA g_file_a;

int main() {
    std::printf("[1] 作用域局部对象：按声明序构造、逆序析构\n");
    {
        MemberA a1;
        MemberB b1;
        std::printf("  scope body\n");
    }
    std::printf("[1] scope end\n");

    std::printf("[2] 派生类：基类 → 成员（声明序）→ 构造体；析构逆序\n");
    {
        Derived d;
        std::printf("  using d\n");
    }
    std::printf("[2] scope end\n");

    std::printf("[3] 函数局部静态：首次调用构造，退出时析构（构造完成逆序）\n");
    use_static("first call");
    use_static("second call");   // 不再构造，直接复用

    std::printf("[4] 命名空间作用域静态：main 之前已构造\n");
    std::printf("  main body end\n");
    return 0;
}
