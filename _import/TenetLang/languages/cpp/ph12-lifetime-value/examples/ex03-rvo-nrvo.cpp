// ex03-rvo-nrvo.cpp —— 返回值优化实测：RVO（保证省略）/ NRVO / return std::move 反模式
// 主题：C++17 起纯右值返回的拷贝省略是"保证"的（guaranteed copy elision）；
//       命名对象的 NRVO 是"允许但不保证"的优化；return std::move(w) 反而阻止 NRVO
//       （clang 会直接告警 -Wpessimizing-move）。
//       本文件只用 C++11 兼容写法，可在 -std=c++14/17/20 与 -O0/-O2/-O3、
//       -fno-elide-constructors 下交叉编译，对比拷贝/移动计数。
//       定义 PH12_ANTIPATTERN 后额外编译 make_move 反模式用例（产生 1 条预期告警）。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++）
// 编译：    c++ -std=c++20 -Wall -Wextra -O0 ex03-rvo-nrvo.cpp -o /tmp/ex03-O0
//           c++ -std=c++20 -Wall -Wextra -O2 ex03-rvo-nrvo.cpp -o /tmp/ex03-O2
//           c++ -std=c++20 -Wall -Wextra -fno-elide-constructors ex03-rvo-nrvo.cpp -o /tmp/ex03-noelide
//           c++ -std=c++20 -Wall -Wextra -DPH12_ANTIPATTERN ex03-rvo-nrvo.cpp -o /tmp/ex03-anti  （预期 1 条告警）
// 运行：    /tmp/ex03-O0   （各二进制分别运行对比）
// 验证状态：已验证（实测输出见文件底部注释与 examples/README.md）
#include <cstdio>
#include <utility>   // std::move

struct Payload {
    int id = 0;
    Payload() { std::printf("  ctor\n"); }
    Payload(const Payload&) { std::printf("  COPY\n"); }
    Payload(Payload&&) noexcept { std::printf("  MOVE\n"); }
    ~Payload() { std::printf("  dtor\n"); }
};

// RVO：返回 prvalue，C++17 起保证省略——无论什么优化级别都零拷贝零移动
Payload make_prvalue() { return Payload{}; }

// NRVO：返回命名对象，编译器"允许"省略；是否省略取决于编译器与优化级别
Payload make_named() {
    Payload p;
    return p;
}

#if defined(PH12_ANTIPATTERN)
// 反模式：return std::move(p) 把 p 变成 xvalue，编译器无法再做 NRVO，必然一次移动
Payload make_move() {
    Payload p;
    return std::move(p);   // 告警：moving a local object in a return statement prevents copy elision
}
#endif

void run(const char* label, Payload (*factory)()) {
    std::printf("[%s]\n", label);
    Payload p = factory();      // 从 prvalue 初始化：C++17 保证省略，直接构造在 p
    std::printf("  got id=%d\n", p.id);
    (void)p;
}

int main() {
    run("RVO prvalue", make_prvalue);
    run("NRVO named", make_named);
#if defined(PH12_ANTIPATTERN)
    run("return std::move", make_move);
#else
    std::printf("[return std::move 反模式用例未启用]\n");
    std::printf("  编译时加 -DPH12_ANTIPATTERN 可观察：1 条预期告警 + 必然一次 MOVE\n");
#endif
    return 0;
}
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   c++ -std=c++20 -Wall -Wextra -O0/-O2/-O3（默认构建，零警告）：
//     [RVO prvalue]   ctor / got id=0 / dtor                    ← 0 拷贝 0 移动（C++17 保证省略）
//     [NRVO named]    ctor / got id=0 / dtor                    ← 0 拷贝 0 移动（clang 21 在 -O0 也做 NRVO）
//   c++ -std=c++20 -fno-elide-constructors（默认构建）：
//     [RVO prvalue]   ctor / got id=0 / dtor                    ← 保证省略不受 -fno-elide-constructors 影响
//     [NRVO named]    ctor / MOVE / dtor / got id=0 / dtor      ← NRVO 被关闭 → 出现一次移动
//   c++ -std=c++20 -DPH12_ANTIPATTERN（预期 1 条告警 -Wpessimizing-move）：
//     [return std::move]  ctor / MOVE / dtor / got id=0 / dtor  ← 反模式：必然一次移动
//   c++ -std=c++14 -fno-elide-constructors（默认构建，演示 C++17 之前的行为）：
//     [RVO prvalue]   ctor / MOVE / dtor / MOVE / dtor / got id=0 / dtor   ← 两次移动
//     [NRVO named]    ctor / MOVE / dtor / MOVE / dtor / got id=0 / dtor   ← 两次移动
//     （C++14 无保证省略，-fno-elide-constructors 把省略全部关闭 → 全程移动）
