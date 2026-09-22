// sol-02-const-ref-params.cpp —— 练习 2 参考实现：用 const 引用优化函数参数
// 练习 2 要求：把"按值接收大对象"的旧函数改成 const& 接收（F.16），
//              用拷贝计数实测优化前后差异；"需要拿走所有权"的 sink 情形按值 + std::move。
//
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致）：
//   [1] 旧代码：按值传大对象 —— 每次调用复制一次
//     Doc ctor（body 2048 字节）
//     Doc copy-ctor（旧代码按值传参触发拷贝）
//     按值统计 = 2048
//     拷贝计数 = 1
//   [2] 优化后：const& 传参 —— 零拷贝
//     const& 统计 = 2048（无 copy-ctor 打印）
//     拷贝计数 = 1（未增加）
//   [3] 需要「拿走」数据时：按值 + std::move（sink 模式，一次移动）
//     Doc move-ctor
//     sink 结束（body.size=2048）
//     拷贝计数 = 1（仍只有 [1] 那一次）
//   [4] 拷贝计数实测：by_value = 1 次拷贝，const_ref = 0 次拷贝
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra sol-02-const-ref-params.cpp -o /tmp/ph14-sol-02
// 运行：    /tmp/ph14-sol-02
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cstdio>
#include <string>
#include <utility>
#include <vector>

// 拷贝计数：把"发生了拷贝"变成可观测数字
static int g_copy_count = 0;   // 演示用全局计数（正常工程避免，I.2；此处仅为测量）

struct Doc {
    std::string title;
    std::vector<char> body;

    Doc(std::string t, std::size_t n)
        : title(std::move(t)), body(n, 'x') {
        std::printf("  Doc ctor（body %zu 字节）\n", body.size());
    }
    Doc(const Doc& o) : title(o.title), body(o.body) {
        g_copy_count += 1;
        std::printf("  Doc copy-ctor（旧代码按值传参触发拷贝）\n");
    }
    Doc(Doc&& o) noexcept : title(std::move(o.title)), body(std::move(o.body)) {
        std::printf("  Doc move-ctor\n");
    }
};

// 旧代码：按值接收大对象 —— 每次调用复制整个 body（F.16 反例）
std::size_t count_by_value(Doc d) {
    return d.body.size();
}

// 优化后：const& 接收 —— 零拷贝，且函数体内无法修改实参（F.16 正例）
std::size_t count_by_const_ref(const Doc& d) {
    return d.body.size();
}

// sink 情形：调用方真的要把数据"交给"函数（函数拥有它）——按值 + std::move
void sink(Doc d) {
    std::printf("  sink 结束（body.size=%zu）\n", d.body.size());
}

int main() {
    std::printf("[1] 旧代码：按值传大对象 —— 每次调用复制一次\n");
    Doc doc("report", 2048);
    std::printf("  按值统计 = %zu\n", count_by_value(doc));
    std::printf("  拷贝计数 = %d\n", g_copy_count);

    std::printf("[2] 优化后：const& 传参 —— 零拷贝\n");
    std::printf("  const& 统计 = %zu（无 copy-ctor 打印）\n", count_by_const_ref(doc));
    std::printf("  拷贝计数 = %d（未增加）\n", g_copy_count);

    std::printf("[3] 需要「拿走」数据时：按值 + std::move（sink 模式，一次移动）\n");
    sink(std::move(doc));                // 显式转移所有权，零拷贝（一次移动）
    std::printf("  拷贝计数 = %d（仍只有 [1] 那一次）\n", g_copy_count);

    std::printf("[4] 拷贝计数实测：by_value = %d 次拷贝，const_ref = 0 次拷贝\n",
                g_copy_count);
    return 0;
}
