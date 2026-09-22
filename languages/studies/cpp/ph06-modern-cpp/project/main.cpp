// 来源：project/ —— 配置管理模块：自测 + CLI 入口
// 一句话说明：无参数时生成样例配置 sample.conf 并跑 assert 自测；
//             带参数时加载并 dump 指定配置文件。
// 验证环境：Apple clang 17（g++ 兼容），C++23（涉及 <format>）
// 编译：g++ -Wall -Wextra -std=c++23 config.cpp main.cpp -o config_app
// 运行：./config_app [配置文件]   （无参数：生成 sample.conf 并自测）
// 验证状态：已验证
#include "config.h"

#include <cassert>
#include <fstream>
#include <iostream>
#include <string>

namespace {

// 生成样例配置文件（含注释 / 空行 / 各种类型 / 坏行）
void write_sample(const char* path) {
    std::ofstream out(path);
    out << "# 数据库连接配置（# 注释）\n"
        << "\n"
        << "host = 127.0.0.1\n"
        << "port = 5432\n"
        << "timeout_ms = 5000\n"
        << "ratio = 0.85\n"
        << "debug = true\n"
        << "password = s3cr3t\n"
        << "this line has no equal sign\n";   // 坏行：缺 '='，应被跳过
}

// assert 自测
void run_self_test() {
    tenet::Config cfg;
    const std::size_t loaded = cfg.load("sample.conf");
    assert(loaded == 6);                      // 7 行有效内容，1 条坏行被跳过
    assert(cfg.size() == 6);

    assert(cfg.get_string("host").value() == "127.0.0.1");
    assert(cfg.get_int("port").value() == 5432);
    assert(cfg.get_int("timeout_ms").value() == 5000);
    assert(cfg.get_double("ratio").value() == 0.85);
    assert(cfg.get_bool("debug").value() == true);
    assert(cfg.get_string("password").value() == "s3cr3t");

    // 缺失配置项：optional 表达，value_or 给出默认值
    assert(!cfg.get("missing").has_value());
    assert(cfg.get_int("missing").value_or(-1) == -1);
    assert(cfg.get_int("missing").value_or(3) == 3);

    // 类型不匹配：host 存的是 string，get_int 应返回 nullopt
    assert(!cfg.get_int("host").has_value());

    std::cout << "Config 自测全部通过（" << cfg.size() << " 条配置）\n";
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc < 2) {
            write_sample("sample.conf");
            run_self_test();
            return 0;
        }

        tenet::Config cfg;
        const std::size_t loaded = cfg.load(argv[1]);
        std::cout << "已加载 " << loaded << " 条配置：\n";
        std::cout << cfg.dump();
    } catch (const std::exception& e) {
        std::cerr << "错误: " << e.what() << "\n";
        return 1;
    }
    return 0;
}
