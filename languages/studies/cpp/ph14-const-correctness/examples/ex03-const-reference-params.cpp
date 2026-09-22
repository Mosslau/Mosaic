// ex03-const-reference-params.cpp —— const 引用参数：接口承诺"只读"，且大对象零拷贝（F.16）
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex03-const-reference-params.cpp -o /tmp/ph14-ex03
// 运行：/tmp/ph14-ex03
#include <cstdio>
#include <string>
#include <utility>
#include <vector>

// 带打印的"大对象"：观察按值传参的拷贝次数
struct Payload {
    std::string name;
    std::vector<int> data;

    Payload(std::string n, std::size_t n_data)
        : name(std::move(n)), data(n_data, 1) {
        std::printf("  Payload ctor（data.size=%zu）\n", data.size());
    }
    Payload(const Payload& o) : name(o.name), data(o.data) {
        std::printf("  Payload copy-ctor（拷贝了 %zu 个 int）\n", data.size());
    }
    Payload(Payload&& o) noexcept : name(std::move(o.name)), data(std::move(o.data)) {
        std::printf("  Payload move-ctor\n");
    }
};

// 反例：按值接收大对象 —— 每次调用复制一次（F.16 只对"廉价拷贝类型"允许按值）
std::size_t sum_by_value(Payload p) {
    std::size_t s = 0;
    for (int v : p.data) {
        s += static_cast<std::size_t>(v);
    }
    return s;
}

// 正例：const& 接收 —— 零拷贝，且函数体内部无法修改实参（只读承诺由编译器执行）
std::size_t sum_by_const_ref(const Payload& p) {
    std::size_t s = 0;
    for (int v : p.data) {
        s += static_cast<std::size_t>(v);
    }
    return s;
}

int main() {
    std::printf("[1] 反例：按值传大对象（每次调用一次拷贝）\n");
    Payload big("payload", 4);
    std::printf("  sum_by_value = %zu\n", sum_by_value(big));

    std::printf("[2] 正例：const& 传大对象（零拷贝）\n");
    std::printf("  sum_by_const_ref = %zu\n", sum_by_const_ref(big));

    std::printf("[3] const& 绑定临时对象：表达式直接用，无需先造具名变量\n");
    const std::string& r = std::string("motor") + "-v1";  // 临时对象生命周期延长（详见 ph12）
    std::printf("  r = %s（const& 可绑定右值临时对象）\n", r.c_str());

    std::printf("[4] const& 的只读承诺：函数体内无法修改实参\n");
    std::printf("  sum_by_const_ref 内部若写 p.data[0] = 0 会编译失败——接口即契约\n");
    return 0;
}
