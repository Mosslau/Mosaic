// 来源：languages/cpp/ph07-exception-safety/project/main.cpp
// 说明：自测入口——assert 覆盖正常路径、文件不存在、格式非法、类型不匹配
// 验证环境：Apple clang 17（g++ 兼容）
// 编译：g++ -Wall -Wextra -std=c++17 main.cpp config.o error.o logger.o -o config_app -pthread
// 运行：./config_app
// 验证状态：已验证
#include "config.h"
#include "error.h"
#include "logger.h"

#include <cassert>
#include <fstream>
#include <iostream>

namespace {

void write_file(const char* path, const std::string& content) {
    std::ofstream out(path);
    out << content;
}

void test_error_codes() {
    using ph07::ErrCode;
    assert(ph07::err_code_to_string(ErrCode::Ok) == std::string("ok"));
    assert(ph07::err_code_to_string(ErrCode::NotFound) == std::string("not found"));
    assert(ph07::err_code_to_string(ErrCode::ParseError) == std::string("parse error"));

    bool caught = false;
    try {
        ph07::throw_if_error(ErrCode::NotFound, "read config");
    } catch (const ph07::AppError& e) {
        caught = true;
        assert(e.code() == ErrCode::NotFound);
        assert(std::string(e.what()).find("not found") != std::string::npos);
    }
    assert(caught);
    ph07::throw_if_error(ErrCode::Ok, "no-op");   // 不应抛
    std::cout << "test_error_codes ok\n";
}

void test_config_normal() {
    const char* path = "/tmp/ph07_proj_ok.conf";
    write_file(path, "# comment\nhost = 127.0.0.1\nport = 8080\nratio = 0.75\n");
    const ph07::Config cfg = ph07::Config::load(path);
    assert(cfg.get_string("host") == "127.0.0.1");
    assert(cfg.get_int("port", -1) == 8080);
    assert(cfg.get_double("ratio", 0.0) == 0.75);
    assert(cfg.get_int("missing", 42) == 42);
    std::cout << "test_config_normal ok\n";
}

void test_config_not_found() {
    bool caught = false;
    try {
        ph07::Config::load("/tmp/no_such_ph07_proj.conf");
    } catch (const ph07::ConfigError& e) {
        caught = true;
        assert(std::string(e.what()).find("cannot open") != std::string::npos);
    }
    assert(caught);
    std::cout << "test_config_not_found ok\n";
}

void test_config_bad_format() {
    const char* path = "/tmp/ph07_proj_bad.conf";
    write_file(path, "host=127.0.0.1\nno_equal_sign_here\n");
    bool caught = false;
    try {
        ph07::Config::load(path);
    } catch (const ph07::ConfigError& e) {
        caught = true;
        assert(std::string(e.what()).find("missing '='") != std::string::npos);
    }
    assert(caught);
    std::cout << "test_config_bad_format ok\n";
}

void test_config_bad_type() {
    const char* path = "/tmp/ph07_proj_type.conf";
    write_file(path, "port=not_a_number\n");
    const ph07::Config cfg = ph07::Config::load(path);
    bool caught = false;
    try {
        cfg.get_int("port", -1);
    } catch (const ph07::ConfigError&) {
        caught = true;
    } catch (const std::invalid_argument&) {
        caught = true;
    }
    assert(caught);
    std::cout << "test_config_bad_type ok\n";
}

void test_logger() {
    ph07::Logger log(std::cout);
    log.set_min_level(ph07::LogLevel::Info);
    log.log(ph07::LogLevel::Debug, "filtered");      // 被过滤
    log.log(ph07::LogLevel::Info, "config loaded");
    log.log(ph07::LogLevel::Warn, "disk usage high");
    log.log(ph07::LogLevel::Error, "write failed: disk full");
    std::cout << "test_logger ok\n";
}

}  // namespace

int main() {
    test_error_codes();
    test_config_normal();
    test_config_not_found();
    test_config_bad_format();
    test_config_bad_type();
    test_logger();
    std::cout << "all project tests passed\n";
    return 0;
}
