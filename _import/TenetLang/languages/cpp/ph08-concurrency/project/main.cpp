// main.cpp —— 异步日志系统自测入口：多线程压测 + 结果校验
// 验证环境：Apple clang 21（g++ 兼容），C++20
// 构建：make；运行：./async_logger_demo
#include "async_logger.h"

#include <cassert>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

namespace {

std::uint64_t count_lines(const std::string& path) {
    std::ifstream in(path);
    std::uint64_t lines = 0;
    std::string line;
    while (std::getline(in, line)) ++lines;
    return lines;
}

}  // namespace

int main() {
    const std::string path = "async_logger_demo.log";
    constexpr int kProducers = 4;
    constexpr int kPerProducer = 250;              // 共 1000 条，远小于容量 4096

    ph08::LogStats st{};
    {
        ph08::AsyncLogger logger(path, 4096);
        logger.set_min_level(ph08::LogLevel::debug);

        {
            std::vector<std::jthread> producers;   // jthread：离开作用域自动 join
            for (int p = 0; p < kProducers; ++p)
                producers.emplace_back([&logger, p] {
                    for (int i = 0; i < kPerProducer; ++i)
                        logger.log(ph08::LogLevel::info,
                                   "producer " + std::to_string(p) +
                                   " message " + std::to_string(i));
                });
        }                                          // 全部业务线程结束

        st = logger.stats();
        assert(st.produced == kProducers * kPerProducer);
        assert(st.dropped == 0);                   // 容量足够，不应有丢弃
    }                                              // logger 析构：停止 → 排空 → join

    const std::uint64_t lines = count_lines(path);
    assert(lines == st.produced);                  // 文件行数 = 投递条数，无丢失
    std::cout << "produced=" << st.produced << " written=" << st.written
              << " dropped=" << st.dropped << " file_lines=" << lines << " OK\n";
    return 0;
}
