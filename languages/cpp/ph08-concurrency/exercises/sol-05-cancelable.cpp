// sol-05-cancelable.cpp —— 练习 5 参考实现：jthread + stop_token 可取消任务
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra -pthread sol-05-cancelable.cpp -o sol-05
// 运行：./sol-05（若干 tick 后清理退出，断言通过、退出码 0）
#include <atomic>
#include <cassert>
#include <chrono>
#include <iostream>
#include <thread>

int main() {
    std::atomic<int> ticks{0};

    std::jthread worker([&ticks](std::stop_token st) {   // 第一个参数接收 stop_token
        while (!st.stop_requested()) {
            std::cout << "tick " << ticks.fetch_add(1) << "\n";
            std::this_thread::sleep_for(std::chrono::milliseconds(200));
        }
        std::cout << "cleanup: work cancelled\n";        // 优雅收尾
    });

    std::this_thread::sleep_for(std::chrono::milliseconds(650));
    assert(ticks.load() >= 1);               // 取消前任务确实执行过
    worker.request_stop();                   // 协作式取消：请求，不是强杀
    return 0;                                // 不手动 join：jthread 析构自动 join
}
