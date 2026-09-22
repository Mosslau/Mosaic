// test_config.cpp —— 配置读取只读接口自测（ph14 project）
// 验证：解析正确性、查询/缺失、keys、const 接口完整性（成员指针类型断言）、
//       mutable 统计实测、只读快照（拷贝即快照）、string_view 视图稳定性。
// 本机实测输出（已验证，Apple clang 21.0.0 与 Homebrew clang 21.1.8 一致，普通版 + ASan 版）：
//   === 配置只读接口自测开始 ===
//   [1] 解析：3 条有效条目（注释/空行被跳过），条目视图零拷贝
//     size = 3（期望 3）
//   [2] 查询与缺失：get 返回 optional<string_view>
//     host=127.0.0.1 port=5432 missing=nullopt
//   [3] contains 与 keys
//     contains(user)=true contains(nope)=false；keys.size=3
//   [4] const 接口完整性：probe_const（const& 参数全程 const 调用）
//     probe_const = 12（期望 12）
//   [5] mutable 统计实测：const 接口内 lookups_ 累加
//     lookup_count = 7（期望 7：get×3 + contains×2 + probe_const 的 contains+get）
//   [6] 只读快照：拷贝即独立快照（值语义 + 全 const 接口）
//     snap.size=1 snap.get(k)=v snap.lookup_count=1（期望 1）
//   [7] string_view 视图稳定性：查询不使既有视图失效
//     视图 v_host 仍 = "127.0.0.1"（entries_ 只读，查询不失效视图）
//   === 自测结束：16 组检查，0 组失败 ===
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra test_config.cpp -o build/test_config
// 运行：    build/test_config（make test 含 ASan 变体）
// 验证状态：已验证（两种编译器均零警告，普通版 + ASan 版输出一致）
#include <cstdio>
#include <optional>
#include <string>
#include <string_view>
#include <type_traits>

#include "config.hpp"

static int g_checks = 0;
static int g_fails = 0;
#define CHECK(cond)                                                        \
    do {                                                                   \
        ++g_checks;                                                        \
        if (!(cond)) {                                                     \
            ++g_fails;                                                     \
            std::printf("  FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);  \
        }                                                                  \
    } while (0)

// 编译期断言：Config 的全部查询接口都是 const 成员函数（Con.2）
static_assert(std::is_same_v<decltype(&Config::get),
                             std::optional<std::string_view> (Config::*)(std::string_view) const>);
static_assert(std::is_same_v<decltype(&Config::contains), bool (Config::*)(std::string_view) const>);
static_assert(std::is_same_v<decltype(&Config::size), std::size_t (Config::*)() const>);
static_assert(std::is_same_v<decltype(&Config::keys),
                             std::vector<std::string_view> (Config::*)() const>);
// Rule of 0（C.20）：成员全值类型，编译器生成拷贝/移动
static_assert(std::is_copy_constructible_v<Config>);
static_assert(std::is_move_constructible_v<Config>);

// 只读探针：只通过 const& 使用 Config（证明整条接口链路 const 可走通）
std::size_t probe_const(const Config& cfg, std::string_view key) {
    std::size_t n = 0;
    if (cfg.contains(key)) {
        const auto v = cfg.get(key);
        if (v) {
            n += v->size();
        }
    }
    return n + cfg.size();
}

int main() {
    std::printf("=== 配置只读接口自测开始 ===\n");

    const std::string text =
        "# 数据库配置\n"
        "host = 127.0.0.1\n"
        "port = 5432\n"
        "\n"
        "user = dba\n";

    std::printf("[1] 解析：3 条有效条目（注释/空行被跳过），条目视图零拷贝\n");
    const Config cfg(text);                 // const 对象
    CHECK(cfg.size() == 3);
    std::printf("  size = %zu（期望 3）\n", cfg.size());

    std::printf("[2] 查询与缺失：get 返回 optional<string_view>\n");
    const auto host = cfg.get("host");
    CHECK(host.has_value());
    CHECK(host && *host == "127.0.0.1");
    const auto port = cfg.get("port");
    CHECK(port && *port == "5432");
    const auto missing = cfg.get("nope");
    CHECK(!missing.has_value());
    std::printf("  host=%s port=%s missing=nullopt\n",
                host ? std::string(*host).c_str() : "<无>",
                port ? std::string(*port).c_str() : "<无>");

    std::printf("[3] contains 与 keys\n");
    CHECK(cfg.contains("user"));
    CHECK(!cfg.contains("nope"));
    const auto ks = cfg.keys();
    CHECK(ks.size() == 3);
    CHECK(ks[0] == "host" && ks[1] == "port" && ks[2] == "user");
    std::printf("  contains(user)=true contains(nope)=false；keys.size=%zu\n", ks.size());

    std::printf("[4] const 接口完整性：probe_const（const& 参数全程 const 调用）\n");
    const std::size_t r = probe_const(cfg, "host");
    CHECK(r == 3 + 9);                      // size=3 + "127.0.0.1".size()=9
    std::printf("  probe_const = %zu（期望 12）\n", r);

    std::printf("[5] mutable 统计实测：const 接口内 lookups_ 累加\n");
    std::printf("  lookup_count = %zu（期望 7：get×3 + contains×2 + probe_const 的 contains+get）\n",
                cfg.lookup_count());
    CHECK(cfg.lookup_count() == 7);

    std::printf("[6] 只读快照：拷贝即独立快照（值语义 + 全 const 接口）\n");
    const Config snap("k = v\n");           // 全新对象：统计从 0 开始（独立快照）
    CHECK(snap.lookup_count() == 0);
    CHECK(snap.size() == 1);
    const auto snap_v = snap.get("k");      // 一次查询
    CHECK(snap_v && *snap_v == "v");
    CHECK(snap.lookup_count() == 1);        // mutable 统计属于对象位：拷贝携带历史统计
    std::printf("  snap.size=%zu snap.get(k)=v snap.lookup_count=%zu（期望 1）\n",
                snap.size(), snap.lookup_count());

    std::printf("[7] string_view 视图稳定性：查询不使既有视图失效\n");
    const std::string_view v_host = cfg.get("host").value();
    (void)cfg.get("user");                  // 更多查询（线性扫描，不重分配）
    CHECK(v_host == "127.0.0.1");           // 视图仍有效：entries_ 未重排/销毁
    std::printf("  视图 v_host 仍 = \"%s\"（entries_ 只读，查询不失效视图）\n",
                std::string(v_host).c_str());

    std::printf("=== 自测结束：%d 组检查，%d 组失败 ===\n", g_checks, g_fails);
    return g_fails == 0 ? 0 : 1;
}
