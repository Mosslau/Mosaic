// ex06-ownership.cpp —— 所有权转移与借用式接口
// 主题：所有权应通过类型体现——unique_ptr 表达独占所有权（转移靠移动语义），
//       裸指针 / const& / string_view / span 表达"借用"（不拥有、不负责释放）。
//       值语义（按值返回、拷贝独立）通常让代码更简单。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra ex06-ownership.cpp -o /tmp/ex06
// 运行：    /tmp/ex06
// 验证状态：已验证（两种编译器均零警告，输出一致）
#include <cstdio>
#include <memory>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

struct Blob {
    std::string payload;
    explicit Blob(std::string p) : payload(std::move(p)) {}
    void touch() const { std::printf("  Blob{%s}\n", payload.c_str()); }
};

// 所有权转移（sink）：按值接收 unique_ptr——调用方把所有权交给本函数
void sink(std::unique_ptr<Blob> b) {
    b->touch();
    // 函数结束：unique_ptr 析构 → Blob 随所有权人生命周期结束而释放
}

// 借用：const& 只读借用，不拥有、不释放
void borrow(const Blob& b) {
    b.touch();
}

// 借用：string_view 只读借用字符串数据，不拥有
void show(std::string_view sv) {
    std::printf("  view: %.*s\n", static_cast<int>(sv.size()), sv.data());
}

// 借用：span 只读借用连续内存，不拥有
void sum_span(std::span<const int> xs) {
    int total = 0;
    for (int x : xs) {
        total += x;
    }
    std::printf("  span sum = %d\n", total);
}

// 所有权转移（产出）：按值返回 unique_ptr——移动语义 + C++17 保证省略，零拷贝
std::unique_ptr<Blob> make_blob(std::string p) {
    return std::make_unique<Blob>(std::move(p));
}

int main() {
    std::printf("[1] 按值返回 unique_ptr：所有权从工厂转移给调用方\n");
    auto b = make_blob("motor");     // C++17 保证省略，prvalue 直接构造
    borrow(*b);                      // 借用：b 仍拥有

    std::printf("[2] string_view 借用：不拷贝、不拥有\n");
    show(b->payload);

    std::printf("[3] sink 转移：所有权交给函数，之后 b 为空\n");
    sink(std::move(b));              // 转移后 b 变为"合法但空"
    std::printf("  b == nullptr: %s\n", b ? "no" : "yes");
    // b 现在是空 unique_ptr，析构安全（无双重释放）

    std::printf("[4] span 借用容器内存\n");
    const std::vector<int> xs{1, 2, 3, 4};
    sum_span(xs);

    std::printf("[5] 值语义：拷贝是深拷贝，互不影响\n");
    Blob a = *make_blob("original");
    Blob c = a;                      // 拷贝构造：payload 独立副本
    c.payload += "!";                // 修改副本不影响原件
    std::printf("  a=%s  c=%s\n", a.payload.c_str(), c.payload.c_str());
    return 0;
}
