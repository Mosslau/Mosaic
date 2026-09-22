// ex04-custom-deleter.cpp —— 自定义 deleter：unique_ptr 的删除策略是类型的一部分
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：c++ -std=c++20 -Wall -Wextra ex04-custom-deleter.cpp -o /tmp/ph13-ex04
// 运行：/tmp/ph13-ex04
#include <cstdio>
#include <cstdlib>
#include <memory>

struct Widget { int value{0}; };

// 方式 1：无状态仿函数 deleter（零开销，推荐）
struct WidgetDeleter {
    void operator()(Widget* p) const noexcept {
        std::printf("  WidgetDeleter: delete %p\n", static_cast<void*>(p));
        delete p;
    }
};

// 方式 2：有状态仿函数（带配置/日志的删除策略）
struct LoggingFree {
    const char* label;
    void operator()(void* p) const noexcept {
        std::printf("  LoggingFree[%s]: free %p\n", label, p);
        std::free(p);
    }
};

void raw_delete(Widget* p) noexcept {
    std::printf("  raw_delete(函数指针 deleter): delete %p\n", static_cast<void*>(p));
    delete p;
}

int main() {
    std::printf("[1] 默认 deleter：sizeof(unique_ptr<Widget>) = %zu（一个裸指针）\n",
                sizeof(std::unique_ptr<Widget>));

    std::printf("[2] 函数指针 deleter：类型编码进 unique_ptr，占两词\n");
    {
        std::unique_ptr<Widget, decltype(&raw_delete)> p(new Widget{1}, &raw_delete);
        std::printf("  sizeof = %zu（指针 + 函数指针）\n", sizeof p);
    }

    std::printf("[3] 无状态仿函数 deleter：空基类优化（EBO），仍是一词\n");
    {
        std::unique_ptr<Widget, WidgetDeleter> p(new Widget{2}, WidgetDeleter{});
        std::printf("  sizeof = %zu（实测与裸指针相同）\n", sizeof p);
    }

    std::printf("[4] 无捕获 lambda deleter：同样零开销\n");
    {
        auto lambda_deleter = [](Widget* p) noexcept {
            std::printf("  lambda deleter: delete %p\n", static_cast<void*>(p));
            delete p;
        };
        std::unique_ptr<Widget, decltype(lambda_deleter)> p(new Widget{3},
                                                            lambda_deleter);
        std::printf("  sizeof = %zu（实测与裸指针相同）\n", sizeof p);
    }

    std::printf("[5] 有状态 deleter：大小随状态增长（指针 + label）\n");
    {
        std::unique_ptr<void, LoggingFree> p(std::malloc(64),
                                             LoggingFree{"malloc-64B"});
        std::printf("  sizeof = %zu（指针 + 状态成员）\n", sizeof p);
    }

    std::printf("[6] 对照：shared_ptr 的 deleter 走类型擦除（存进控制块）\n");
    {
        std::shared_ptr<Widget> p(new Widget{4}, raw_delete);   // 类型不变
        std::shared_ptr<Widget> q(new Widget{5}, WidgetDeleter{});
        std::printf("  两者同为 shared_ptr<Widget>，sizeof 均为 %zu\n", sizeof p);
    }   // q、p 析构时各自调用自己的 deleter
    std::printf("（共享所有权完整语义属 ph06，这里只对照 deleter 的类型差异）\n");
    return 0;
}
