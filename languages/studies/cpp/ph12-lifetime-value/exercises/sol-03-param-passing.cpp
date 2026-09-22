// sol-03-param-passing.cpp —— 练习 3 参考实现：对比传值 / 引用 / 移动的拷贝与移动次数
// 练习 3 要求：统计"按值传参"、"const& 传参"、"右值引用传参"在传入左值/右值时
//   各发生几次拷贝、几次移动，形成对比表；解释何时按值传参反而更优。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   by_value(lvalue)             copy=1 move=0
//   by_value(rvalue)             copy=0 move=1
//   by_const_ref(lvalue)         copy=0 move=0
//   by_const_ref(rvalue)         copy=0 move=0
//   by_rvalue_ref(rvalue)        copy=0 move=0
//   Counted b = make()           copy=0 move=0
//   结论：
//   - by_value 传入左值 → 1 次拷贝（最贵）；传入右值 → 1 次移动（便宜）
//   - by_const_ref 无论左值右值都 0 拷贝 0 移动（引用不产生新对象）
//   - by_rvalue_ref 只能绑定右值，0 拷贝 0 移动——它把"参数是临时对象"的约定写进类型
//   - Counted b = make() 是保证省略：0 拷贝 0 移动，直接构造在 b
//   - 何时按值更优：调用方本来就要"让出"对象（sink 语义）时，by_value + std::move
//     只花 1 次移动；若调用方还需要保留原对象，按值会多 1 次拷贝，不如 const& + 拷贝
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-03-param-passing.cpp -o /tmp/sol-03
// 运行：    /tmp/sol-03
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cstdio>
#include <string>
#include <utility>

struct Counted {
    std::string payload;
    explicit Counted(const char* p) : payload(p) {}
    Counted(const Counted& o) : payload(o.payload) { ++copies; }
    Counted(Counted&& o) noexcept : payload(std::move(o.payload)) { ++moves; }
    static int copies;
    static int moves;
};
int Counted::copies = 0;
int Counted::moves = 0;

void reset() { Counted::copies = 0; Counted::moves = 0; }

void report(const char* label) {
    std::printf("%-28s copy=%d move=%d\n", label, Counted::copies, Counted::moves);
}

void by_value(Counted c) { (void)c; }       // 传值：从实参拷贝/移动到形参
void by_const_ref(const Counted& c) { (void)c; } // const&：不产生新对象
void by_rvalue_ref(Counted&& c) { (void)c; } // 右值引用：只能绑定右值，不产生新对象

Counted make() { return Counted("data"); }

int main() {
    Counted a("hello");

    reset();
    by_value(a);                       // 左值 → 拷贝进形参
    report("by_value(lvalue)");

    reset();
    by_value(std::move(a));            // 右值 → 移动进形参（sink 惯用法）
    report("by_value(rvalue)");

    reset();
    by_const_ref(a);
    report("by_const_ref(lvalue)");

    reset();
    by_const_ref(Counted("t"));        // 临时对象直接被引用绑定，调用期间存活
    report("by_const_ref(rvalue)");

    reset();
    by_rvalue_ref(std::move(a));
    report("by_rvalue_ref(rvalue)");

    reset();
    Counted b = make();                // C++17 保证省略：直接构造在 b
    report("Counted b = make()");
    return 0;
}
