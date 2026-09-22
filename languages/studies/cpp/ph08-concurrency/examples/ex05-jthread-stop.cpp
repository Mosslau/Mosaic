// ex05-jthread-stop.cpp —— jthread + stop_token 协作式取消（C++20）
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 编译：c++ -std=c++20 -Wall -Wextra -pthread ex05-jthread-stop.cpp -o ex05
// 运行：./ex05（输出若干 tick 后打印 cleanup 并退出，无需手动 join）
#include <chrono>
#include <iostream>
#include <thread>

void background_work(std::stop_token st) {   // 第一个参数接收 stop_token
    int i = 0;
    while (!st.stop_requested()) {
        std::cout << "tick " << i++ << "\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
    std::cout << "cleanup: work cancelled\n";  // 优雅退出，可做收尾
}

int main() {
    std::jthread worker(background_work);
    std::this_thread::sleep_for(std::chrono::milliseconds(650));
    worker.request_stop();                 // 协作式取消请求（是请求，不是强杀）
    return 0;                              // jthread 析构自动 join，等待清理完成
}
