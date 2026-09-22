// test_config.cpp —— 值语义配置对象自测（ph12 project）
// 覆盖：解析（含注释/空行/CRLF/缺 '=' 异常）、借用式查询、值语义 with/merged_with
//       （原对象不变）、拷贝独立、移动转移、借用稳定性。
// 编译：  c++ -std=c++20 -Wall -Wextra test_config.cpp config.cpp -o build/test_config
// 运行：  ./build/test_config
// 验证状态：已验证（Apple clang 21.0.0 与 Homebrew clang 21.1.8 均零警告，
//           10 组 33 条断言全部通过，退出码 0）
#include "config.h"

#include <cstdio>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>

static int g_failures = 0;
static int g_checks = 0;
static int g_groups = 0;

#define CHECK(cond)                                                          \
    do {                                                                     \
        ++g_checks;                                                          \
        if (!(cond)) {                                                       \
            std::printf("  FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);    \
            ++g_failures;                                                    \
        }                                                                    \
    } while (0)

#define TEST_GROUP(name)          \
    std::printf("[%s]\n", name);  \
    ++g_groups

int main() {
    TEST_GROUP("parse：基础键值对与顺序");
    {
        const cfg::Config c = cfg::parse("host=127.0.0.1\nport=8080\nname=motor\n");
        CHECK(c.size() == 3);
        CHECK(std::string(c.find("host")) == "127.0.0.1");
        CHECK(std::string(c.find("port")) == "8080");
        CHECK(std::string(c.find("name")) == "motor");
        CHECK(c.entries()[0].key == "host");   // 顺序保留
        CHECK(c.entries()[2].key == "name");
    }

    TEST_GROUP("parse：注释、空行、CRLF、首尾空白");
    {
        const cfg::Config c =
            cfg::parse("# comment\r\n\r\n  host = 1.2.3.4  \r\nlevel= debug \n");
        CHECK(c.size() == 2);
        CHECK(std::string(c.find("host")) == "1.2.3.4");   // 键值首尾空白被去除
        CHECK(std::string(c.find("level")) == "debug");
    }

    TEST_GROUP("parse：缺 '=' 抛异常");
    {
        bool threw = false;
        try {
            (void)cfg::parse("host=1\nbroken-line\n");
        } catch (const std::runtime_error& e) {
            threw = true;
            CHECK(std::string(e.what()).find("missing '='") != std::string::npos);
        }
        CHECK(threw);
    }

    TEST_GROUP("find：缺失键返回空视图");
    {
        const cfg::Config c = cfg::parse("a=1\n");
        const std::string_view v = c.find("nope");
        CHECK(v.empty());
    }

    TEST_GROUP("with：值语义——原对象不变，返回新对象");
    {
        const cfg::Config c = cfg::parse("host=127.0.0.1\n");
        const cfg::Config c2 = c.with("port", "9090");     // 新增键
        const cfg::Config c3 = c.with("host", "0.0.0.0");  // 覆盖键
        CHECK(std::string(c.find("host")) == "127.0.0.1"); // 原对象完全不变
        CHECK(c.size() == 1);
        CHECK(std::string(c2.find("port")) == "9090");
        CHECK(c2.size() == 2);
        CHECK(std::string(c3.find("host")) == "0.0.0.0");
        CHECK(std::string(c.find("host")) == "127.0.0.1"); // 再次确认 c 未被污染
    }

    TEST_GROUP("拷贝独立：副本修改不影响原件");
    {
        const cfg::Config c = cfg::parse("a=1\nb=2\n");
        const cfg::Config copy = c;                        // 拷贝构造：深拷贝
        const cfg::Config modified = copy.with("a", "99");
        CHECK(std::string(c.find("a")) == "1");            // 原件不变
        CHECK(std::string(modified.find("a")) == "99");    // 副本的分叉
        CHECK(std::string(copy.find("a")) == "1");         // 拷贝本身也不变
    }

    TEST_GROUP("移动转移：新对象持有数据，原对象不再使用");
    {
        cfg::Config c = cfg::parse("x=1\ny=2\n");
        const cfg::Config moved = std::move(c);            // 移动构造：廉价转移
        CHECK(moved.size() == 2);
        CHECK(std::string(moved.find("x")) == "1");
        // c 现在是"合法但未指定"状态——不访问其内容（见 ph15 use-after-move）
    }

    TEST_GROUP("merged_with：覆盖同名、保留独有");
    {
        const cfg::Config a = cfg::parse("host=a\nport=1\n");
        const cfg::Config b = cfg::parse("host=b\nextra=2\n");
        const cfg::Config m = a.merged_with(b);
        CHECK(std::string(m.find("host")) == "b");         // 同名被 b 覆盖
        CHECK(std::string(m.find("port")) == "1");         // a 独有保留
        CHECK(std::string(m.find("extra")) == "2");        // b 独有并入
        CHECK(m.size() == 3);
        CHECK(std::string(a.find("host")) == "a");         // a 本身不变
        CHECK(std::string(b.find("host")) == "b");         // b 本身不变
    }

    TEST_GROUP("借用稳定性：Config 不可变 → string_view 在对象存活期内稳定");
    {
        const cfg::Config c = cfg::parse("host=127.0.0.1\n");
        const std::string_view host = c.find("host");      // 借用
        const cfg::Config derived = c.with("port", "80");  // 值语义分叉
        CHECK(host == "127.0.0.1");                        // 借用仍有效（c 未变）
        CHECK(std::string(derived.find("host")) == "127.0.0.1");
    }

    TEST_GROUP("容器友好：值语义对象可直接放进 vector");
    {
        std::vector<cfg::Config> configs;
        configs.push_back(cfg::parse("a=1\n"));
        configs.push_back(cfg::parse("b=2\n"));
        CHECK(configs.size() == 2);
        CHECK(std::string(configs[1].find("b")) == "2");
        // 扩容时元素整体搬移（noexcept 移动）——值语义让容器管理零负担
    }

    if (g_failures == 0) {
        std::printf("全部断言通过（%d 组测试 / %d 条断言）\n", g_groups, g_checks);
        return 0;
    }
    std::printf("%d 条断言失败\n", g_failures);
    return 1;
}
