// ex01-rule-of-zero.cpp —— Rule of Zero（C.20）：让编译器生成特殊成员函数
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex01-rule-of-zero.cpp -o /tmp/ph13-ex01
// 运行：/tmp/ph13-ex01
#include <cstdio>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

// 带打印的成员类型：观察"逐成员"的拷贝/移动如何发生
struct Tracer {
    std::string tag;
    explicit Tracer(std::string t) : tag(std::move(t)) {
        std::printf("  Tracer ctor %s\n", tag.c_str());
    }
    Tracer(const Tracer& o) : tag(o.tag) {
        std::printf("  Tracer copy-ctor %s\n", tag.c_str());
    }
    Tracer(Tracer&& o) noexcept : tag(std::move(o.tag)) {
        std::printf("  Tracer move-ctor %s\n", tag.c_str());
    }
    Tracer& operator=(const Tracer& o) {
        tag = o.tag;
        std::printf("  Tracer copy= %s\n", tag.c_str());
        return *this;
    }
    Tracer& operator=(Tracer&& o) noexcept {
        tag = std::move(o.tag);
        std::printf("  Tracer move= %s\n", tag.c_str());
        return *this;
    }
    ~Tracer() { std::printf("  Tracer dtor %s\n", tag.c_str()); }
};

// Rule of Zero：成员全是值类型（string/vector/Tracer），一个特殊成员都不写
// —— 编译器生成的拷贝 = 逐成员深拷贝，移动 = 逐成员移动，析构 = 逐成员析构
struct Widget {
    std::string id;
    Tracer tracer;
    std::vector<int> data;
};

// 编译期验证：Rule of Zero 类型自动获得全部五个特殊成员
static_assert(std::is_copy_constructible_v<Widget>);
static_assert(std::is_copy_assignable_v<Widget>);
static_assert(std::is_move_constructible_v<Widget>);
static_assert(std::is_move_assignable_v<Widget>);
static_assert(std::is_nothrow_destructible_v<Widget>);

Widget make_widget() {
    Widget w{"motor", Tracer{"motor"}, {1, 2, 3}};  // NRVO：直接构造到返回槽（返回 prvalue 才是保证省略）
    return w;
}

int main() {
    std::printf("[1] 按值返回（ph12 的保证省略，此处 0 拷贝 0 移动）\n");
    Widget a = make_widget();

    std::printf("[2] 拷贝构造：逐成员深拷贝（tracer 被 copy，data 内容独立）\n");
    Widget b = a;
    b.data.push_back(4);
    b.id += "-copy";
    std::printf("  a.id=%s a.data.size=%zu | b.id=%s b.data.size=%zu\n",
                a.id.c_str(), a.data.size(), b.id.c_str(), b.data.size());

    std::printf("[3] 移动构造：逐成员移动（tracer 被 move，源置空）\n");
    Widget c = std::move(b);
    std::printf("  moved-from b.id 长度=%zu（合法但未指定，实测为空）\n", b.id.size());
    std::printf("  c.id=%s c.data.size=%zu\n", c.id.c_str(), c.data.size());

    std::printf("[4] 作用域结束：c/a 逆序析构，成员逐个体面释放\n");
    return 0;
}
