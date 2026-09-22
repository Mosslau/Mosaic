// test_path.cpp —— path_util 自测：同一份测试代码，两个分支各跑一遍
// 注意：期望值用 separator() 动态构造，这样同一份代码在 POSIX 与 -D_WIN32 分支都成立。
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra path_util.cpp test_path.cpp -o /tmp/test_path
//           c++ -D_WIN32 -std=c++20 -Wall -Wextra path_util.cpp test_path.cpp -o /tmp/test_path_win
// 运行：    /tmp/test_path  与  /tmp/test_path_win
// 验证状态：已验证（两个分支均零警告、全部断言通过，输出见 project/README.md）
#include <cstdio>
#include <string>

#include "path_util.h"

static int g_fail = 0;

static void expect_eq(const std::string& got, const std::string& want,
                      const char* what) {
    if (got != want) {
        std::printf("FAIL: %s: got \"%s\" want \"%s\"\n", what, got.c_str(), want.c_str());
        ++g_fail;
    } else {
        std::printf("PASS: %s -> \"%s\"\n", what, got.c_str());
    }
}

int main() {
    const std::string sep(1, ftool::separator());

    // join：空 base、已带分隔符、正常拼接
    expect_eq(ftool::join("", "a.txt"), "a.txt", "join(empty, a.txt)");
    expect_eq(ftool::join("data", "a.txt"), "data" + sep + "a.txt", "join(data, a.txt)");
    expect_eq(ftool::join("data" + sep, "a.txt"), "data" + sep + "a.txt", "join(data/, a.txt)");

    // normalize：重复分隔符合并、去结尾分隔符、空串
    expect_eq(ftool::normalize("a//b///c"), "a" + sep + "b" + sep + "c", "normalize(a//b///c)");
    expect_eq(ftool::normalize("a/b/"), "a" + sep + "b", "normalize(a/b/)");
    expect_eq(ftool::normalize(""), ".", "normalize(empty)");

    // extension：普通扩展名、无扩展名、点开头的隐藏文件、结尾点、点位于目录名中
    expect_eq(ftool::extension("data/config.json"), ".json", "extension(config.json)");
    expect_eq(ftool::extension("README"), "", "extension(README)");
    expect_eq(ftool::extension("dir/.hidden"), "", "extension(.hidden)");
    expect_eq(ftool::extension("file."), "", "extension(file.)");
    expect_eq(ftool::extension("a.b/c"), "", "extension(a.b/c)");                       // 点属于目录名，不算扩展名
    expect_eq(ftool::extension("dir.with.dot/file.txt"), ".txt", "extension(dir.with.dot/file.txt)");  // 目录名含点不影响文件名扩展名

    std::printf("separator = '%c'\n", ftool::separator());
    if (g_fail == 0) {
        std::printf("ALL TESTS PASSED\n");
        return 0;
    }
    std::printf("%d TEST(S) FAILED\n", g_fail);
    return 1;
}
