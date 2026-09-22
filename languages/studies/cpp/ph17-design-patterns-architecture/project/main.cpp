// project/main.cpp —— 查询执行器 demo 入口：演示模式 + 自测模式（--selftest）
// 演示分层 demo 的完整用法：建表 → 注册（DI）→ 组装查询（工厂）→ 执行 → 完成事件。
// 自测模式把关键查询跑成断言（退出码即 CI 信号，ph16 纪律）。
//
// 验证环境：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），macOS arm64，libc++
// 构建：make（产物 build/query_demo）
// 运行：make run  或  ./build/query_demo
// 测试：make test 或  ./build/query_demo --selftest（退出码 0 = 全过）
// 验证状态：已验证（Apple clang 21.0.0，-std=c++17 -Wall -Wextra 本机实测：编译零警告、运行通过）
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "engine.h"
#include "storage.h"

namespace {

using querydemo::FilterSpec;
using querydemo::MemoryTable;
using querydemo::QueryEngine;
using querydemo::QuerySpec;
using querydemo::make_row;

// ============ 数据（演示用「字符串承载」行；真引擎是类型化列） ============
std::shared_ptr<MemoryTable> build_users() {
    std::vector<querydemo::Row> rows{
        make_row({{"id", "1"}, {"name", "alice"}, {"age", "30"}, {"city", "hz"}}),
        make_row({{"id", "2"}, {"name", "bob"}, {"age", "17"}, {"city", "hz"}}),
        make_row({{"id", "3"}, {"name", "carol"}, {"age", "25"}, {"city", "sh"}}),
        make_row({{"id", "4"}, {"name", "dave"}, {"age", "41"}, {"city", "bj"}}),
        make_row({{"id", "5"}, {"name", "erin"}, {"age", "19"}, {"city", "sh"}}),
    };
    return std::make_shared<MemoryTable>("users", std::move(rows));
}

std::shared_ptr<MemoryTable> build_products() {
    std::vector<querydemo::Row> rows{
        make_row({{"sku", "p1"}, {"category", "keyboard"}, {"price", "299"}}),
        make_row({{"sku", "p2"}, {"category", "mouse"}, {"price", "99"}}),
        make_row({{"sku", "p3"}, {"category", "keyboard"}, {"price", "599"}}),
        make_row({{"sku", "p4"}, {"category", "monitor"}, {"price", "1299"}}),
    };
    return std::make_shared<MemoryTable>("products", std::move(rows));
}

// ============ 演示模式 ============
void demo(QueryEngine& engine) {
    std::cout << "== 查询 1：users 成年用户前 3 名（投影 name, age） ==\n";
    {
        QuerySpec spec;
        spec.table = "users";
        spec.select_columns = {"name", "age"};
        spec.filter = FilterSpec{"age", ">=", "18"};
        spec.limit = 3;
        (void)querydemo::run_query(engine, spec, std::cout);
    }

    std::cout << "\n== 查询 2：users 城市 = sh（全列） ==\n";
    {
        QuerySpec spec;
        spec.table = "users";
        spec.filter = FilterSpec{"city", "=", "sh"};
        (void)querydemo::run_query(engine, spec, std::cout);
    }

    std::cout << "\n== 查询 3：products 键盘类，按价格下限（数值比较生效） ==\n";
    {
        QuerySpec spec;
        spec.table = "products";
        spec.select_columns = {"sku", "price"};
        spec.filter = FilterSpec{"price", ">=", "300"};
        (void)querydemo::run_query(engine, spec, std::cout);
    }
}

// ============ 自测模式 ============
int g_failures = 0;
void check(bool condition, const char* what) {
    std::cout << (condition ? "[通过] " : "[失败] ") << what << '\n';
    if (!condition) {
        ++g_failures;
    }
}

// 组装并执行，返回统计（不打印计划行，便于断言）
querydemo::QueryStats run_quiet(QueryEngine& engine, const QuerySpec& spec,
                                std::ostringstream& out) {
    const QueryEngine::Pipeline pipeline = engine.build(spec);
    return engine.execute(spec, pipeline, out);
}

int run_selftest(QueryEngine& engine) {
    // 用例 1：过滤 + 投影 + 限量
    {
        QuerySpec spec;
        spec.table = "users";
        spec.select_columns = {"name", "age"};
        spec.filter = FilterSpec{"age", ">=", "18"};
        spec.limit = 3;
        std::ostringstream out;
        const auto stats = run_quiet(engine, spec, out);
        check(stats.rows_in == 5, "用例1: 扫描输入 5 行");
        check(stats.rows_out == 3, "用例1: 过滤+限量输出 3 行");
        check(out.str().find("name=alice") != std::string::npos &&
                  out.str().find("age=30") != std::string::npos,
              "用例1: 首行内容 alice/30");
        check(out.str().find("bob") == std::string::npos,
              "用例1: 未成年 bob 被过滤");
    }
    // 用例 2：等值过滤（city = sh）
    {
        QuerySpec spec;
        spec.table = "users";
        spec.filter = FilterSpec{"city", "=", "sh"};
        std::ostringstream out;
        const auto stats = run_quiet(engine, spec, out);
        check(stats.rows_out == 2, "用例2: sh 用户 2 行（carol/erin）");
    }
    // 用例 3：数值比较（age < 18，字符串 "17" 参与数值比较）
    {
        QuerySpec spec;
        spec.table = "users";
        spec.select_columns = {"name"};
        spec.filter = FilterSpec{"age", "<", "18"};
        std::ostringstream out;
        const auto stats = run_quiet(engine, spec, out);
        check(stats.rows_out == 1 && out.str().find("name=bob") != std::string::npos,
              "用例3: 数值比较 age < 18 命中 bob");
    }
    // 用例 4：products 上做数值比较（price >= 300 → 299 被排除）
    {
        QuerySpec spec;
        spec.table = "products";
        spec.select_columns = {"sku", "price"};
        spec.filter = FilterSpec{"price", ">=", "300"};
        std::ostringstream out;
        const auto stats = run_quiet(engine, spec, out);
        check(stats.rows_out == 2, "用例4: 价格 >= 300 命中 p3/p4");
    }
    // 用例 5：失败要可诊断（未知列 / 未知表 / 非法操作符）
    {
        bool threw = false;
        try {
            QuerySpec spec;
            spec.table = "users";
            spec.select_columns = {"nope"};
            std::ostringstream out;
            (void)run_quiet(engine, spec, out);
        } catch (const std::invalid_argument&) {
            threw = true;
        }
        check(threw, "用例5a: 未知投影列抛 invalid_argument");

        threw = false;
        try {
            QuerySpec spec;
            spec.table = "ghost";
            std::ostringstream out;
            (void)run_quiet(engine, spec, out);
        } catch (const std::invalid_argument&) {
            threw = true;
        }
        check(threw, "用例5b: 未知表抛 invalid_argument");

        threw = false;
        try {
            QuerySpec spec;
            spec.table = "users";
            spec.filter = FilterSpec{"age", "~=", "18"};
            std::ostringstream out;
            (void)run_quiet(engine, spec, out);
        } catch (const std::invalid_argument&) {
            threw = true;
        }
        check(threw, "用例5c: 非法操作符抛 invalid_argument");
    }

    std::cout << (g_failures == 0 ? "自测全部通过，退出码 0" : "自测存在失败")
              << '\n';
    return g_failures == 0 ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
    QueryEngine engine;
    engine.add_table(build_users());
    engine.add_table(build_products());

    const bool selftest_mode =
        argc > 1 && std::string(argv[1]) == "--selftest";
    if (selftest_mode) {
        return run_selftest(engine);
    }

    // 演示模式：注册完成事件（观察者/事件驱动的最小形态）
    engine.set_listener([](const querydemo::QueryStats& stats) {
        std::cout << "  [事件] 查询完成: rows_in=" << stats.rows_in
                  << " rows_out=" << stats.rows_out << '\n';
    });
    demo(engine);
    return 0;
}
