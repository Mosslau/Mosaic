// ex02-temp-lifetime.cpp —— 临时对象生命周期：全表达式边界、const&/&& 延长
// 主题：临时对象的析构时机由 C++ 标准规定——默认在"完整表达式"结束时销毁；
//       绑定到 const 左值引用 / 右值引用时，生命周期延长到引用离开作用域，
//       但延长有明确边界（不跨函数返回、不跨函数参数）。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex02-temp-lifetime.cpp -o /tmp/ex02
// 运行：    /tmp/ex02
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cstdio>
#include <string>
#include <utility>

struct Token {
    std::string name;
    explicit Token(const char* n) : name(n) {
        std::printf("  ctor %s\n", name.c_str());
    }
    Token(const Token& o) : name(o.name + "(copy)") {
        std::printf("  copy-ctor %s\n", name.c_str());
    }
    Token(Token&& o) noexcept : name(std::move(o.name) + "(move)") {
        std::printf("  move-ctor %s\n", name.c_str());
    }
    ~Token() { std::printf("  dtor %s\n", name.c_str()); }
};

// 按值返回：C++17 保证省略，Token(n) 直接构造到返回槽，不产生额外拷贝/移动
Token make(const char* n) { return Token(n); }

void observe(const Token& t) {
    std::printf("  observe %s\n", t.name.c_str());
}

int main() {
    std::printf("[1] 完整表达式边界：未绑定的临时对象在语句结束时析构\n");
    {
        std::printf("  before\n");
        make("expr-temp");            // 临时对象在完整表达式（本语句）结束时销毁
        std::printf("  after\n");
    }

    std::printf("[2] const& 绑定：生命周期延长到引用离开作用域\n");
    {
        const Token& r = make("extended");   // 延长规则生效
        std::printf("  using r: %s\n", r.name.c_str());
    }                                       // 作用域结束，临时对象才析构
    std::printf("[2] scope end\n");

    std::printf("[3] && 绑定：右值引用同样延长\n");
    {
        Token&& r = make("rref-ext");
        std::printf("  using r: %s\n", r.name.c_str());
    }
    std::printf("[3] scope end\n");

    std::printf("[4] 函数参数：临时对象活到调用语句结束（不跨语句延长）\n");
    observe(make("arg-temp"));        // 参数临时对象在完整表达式结束时销毁
    std::printf("[4] after call\n");

    std::printf("[5] 绑定到临时对象的成员：延长的是整个临时对象\n");
    {
        struct Holder { Token t; };   // 局部聚合类型
        const Token& r = Holder{Token("sub")}.t;   // 绑定子对象 → 完整临时对象延长
        std::printf("  using member: %s\n", r.name.c_str());
    }
    std::printf("[5] scope end\n");

    std::printf("[6] 边界：延长只作用于绑定的引用本身（悬空场景见 ex05）\n");
    // 演示完 [1]~[5] 的规则后，悬空场景（函数返回引用、参数引用逃逸）见 ex05（故意出错）。
    std::printf("  done\n");
    return 0;
}
