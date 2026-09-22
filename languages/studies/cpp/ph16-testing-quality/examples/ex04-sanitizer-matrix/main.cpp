// examples/ex04-sanitizer-matrix/main.cpp —— Sanitizer 工程化矩阵的被测程序
// 承接 ph15 的结论（vector 越界靠 ASan、数据竞争靠 TSan），本示例把它工程化：
// 同一份源码配 Makefile 一键构建「normal / ASan / ASan+UBSan / TSan」四种变体。
//
// 运行前提：默认构建是安全版（任何构建方式下都应零报告）；
//           -DEX04_OOB 是故意出错版（越界写，必须用 ASan 构建运行，勿裸跑）。
//
// 验证环境：macOS arm64，Apple clang 21.0.0（c++）+ Homebrew clang 21.1.8（clang++）
// 构建/运行：见同目录 Makefile（make check / make demo-oob）
#include <cstdio>
#include <mutex>
#include <thread>
#include <vector>

namespace {

// 多线程累加（scoped_lock 保护，CP.20）：给 TSan 构建准备的「应零报告」负载
int parallel_sum(const std::vector<int>& values) {
    int shared = 0;
    std::mutex mtx;
    auto worker = [&values, &shared, &mtx] {
        int local = 0;
        for (const int v : values) {
            local += v;
        }
        std::lock_guard<std::mutex> lock(mtx);
        shared += local;
    };
    std::thread t1(worker);
    std::thread t2(worker);
    t1.join();
    t2.join();
    return shared;
}

}  // namespace

int main() {
    std::vector<int> values{1, 2, 3, 4, 5};

#ifdef EX04_OOB
    // 故意出错：越界写（承接 ph15 ex01 的结论——vector 越界用 ASan 抓）
    // 必须用 -fsanitize=address 构建运行，勿裸跑
    const std::size_t idx = values.size();
    values[idx] = 100;  // UB: heap-buffer-overflow
    std::printf("oob: values[%zu]=%d\n", idx, values[idx]);
#else
    for (std::size_t i = 0; i < values.size(); ++i) {
        values[i] *= 2;  // 下标有界：0 <= i < size，定义行为
    }
#endif

    std::printf("parallel_sum=%d\n", parallel_sum(values));
    return 0;
}
