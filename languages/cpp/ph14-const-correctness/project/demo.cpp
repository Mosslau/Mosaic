// demo.cpp —— 配置读取只读接口 CLI（ph14 project）
// 用法：./build/config-demo <配置文件> [key ...]
//   - 只给文件：打印条目数与全部键（keys）
//   - 带 key 参数：逐个查询并打印（缺失显示 <缺失>），最后打印查询统计
// 设计展示：const Config 对象 + 全程 const 接口；无任何修改路径。
#include <cstdio>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>

#include "config.hpp"

std::string read_file(const char* path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error(std::string("无法打开: ") + path);
    }
    std::ostringstream ss;
    ss << in.rdbuf();                       // RAII：fstream 析构自动关闭
    return ss.str();
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr, "用法: config-demo <配置文件> [key ...]\n");
        return 2;
    }
    try {
        const Config cfg(read_file(argv[1]));   // const 对象：整条链路只读
        std::printf("[config-demo] 条目数 = %zu\n", cfg.size());

        if (argc == 2) {
            std::printf("[config-demo] keys: ");
            bool first = true;
            for (std::string_view k : cfg.keys()) {
                if (!first) {
                    std::printf(", ");
                }
                first = false;
                std::printf("%s", std::string(k).c_str());
            }
            std::printf("\n");
        } else {
            for (int i = 2; i < argc; ++i) {
                const auto v = cfg.get(argv[i]);    // 返回 string_view（观察不拥有）
                if (v) {
                    std::printf("  %s = %s\n", argv[i], std::string(*v).c_str());
                } else {
                    std::printf("  %s = <缺失>\n", argv[i]);
                }
            }
            std::printf("[config-demo] lookup_count = %zu（const 接口内 mutable 统计）\n",
                        cfg.lookup_count());
        }
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "config-demo: %s\n", e.what());
        return 1;
    }
}
