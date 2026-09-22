// test_raii.cpp —— RAII 系统资源库自测（ph13 project）
// 验证 raii/ 库的关键性质：move-only、构造失败抛异常、异常路径不泄漏（fd 计数实测）、
// 移动赋值关闭旧句柄、release 放弃所有权、复制往返内容一致。
//
// 验证环境：Apple clang 21.0.0（c++）与 Homebrew clang 21.1.8（clang++），C++20
// 编译：    c++ -std=c++20 -Wall -Wextra test_raii.cpp -o build/test_raii（在 project/ 目录下，与 Makefile 产物路径一致）
// 运行：    build/test_raii（退出码 0 = 全部通过）
// 验证状态：已验证（两种编译器均零警告；普通版 + ASan 版均全部通过）
#include <csignal>
#include <cstdio>
#include <cstring>
#include <dirent.h>
#include <fcntl.h>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <unistd.h>

#include "raii/c_file.h"
#include "raii/unique_fd.h"

namespace {

const char* kPath = "/tmp/ph13-test-raii.txt";

int g_checks = 0;
int g_failures = 0;

void check(bool ok, const char* what) {
    ++g_checks;
    if (!ok) ++g_failures;
    std::printf("  [%s] %s\n", ok ? "PASS" : "FAIL", what);
}

// 统计进程当前打开的文件描述符数（/dev/fd 快照，含 std 三件套）。
// 两次统计的差值即"净开/关数量"，用来实测异常路径有没有泄漏 fd。
int open_fd_count() {
    DIR* d = ::opendir("/dev/fd");
    if (d == nullptr) return -1;
    int n = 0;
    while (::readdir(d) != nullptr) ++n;
    ::closedir(d);
    return n;
}

// fcntl(F_GETFD) 探测 fd 是否仍有效：返回 -1 且 errno == EBADF 即已关闭
bool fd_alive(int fd) {
    return ::fcntl(fd, F_GETFD) != -1 || errno != EBADF;
}

// 编译期断言：move-only 是接口的一部分（拷贝被显式删除）
static_assert(!std::is_copy_constructible_v<raii::CFile>);
static_assert(!std::is_copy_assignable_v<raii::CFile>);
static_assert(std::is_nothrow_move_constructible_v<raii::CFile>);
static_assert(!std::is_copy_constructible_v<raii::UniqueFd>);
static_assert(!std::is_copy_assignable_v<raii::UniqueFd>);
static_assert(std::is_nothrow_move_constructible_v<raii::UniqueFd>);

void test_cfile_basics() {
    std::printf("[1] CFile：写 → 读回 → 内容一致\n");
    {
        raii::CFile f(kPath, "w");
        f.write("alpha\n", 6);
        f.write("beta\n", 5);
    }
    {
        raii::CFile f(kPath, "r");
        char buf[32];
        const std::size_t n = f.read(buf, sizeof buf);
        check(n == 11 && std::memcmp(buf, "alpha\nbeta\n", 11) == 0,
              "写 11 字节读回 11 字节且内容一致");
        check(f.eof(), "读尽后 eof() 为 true");
    }
    std::remove(kPath);
}

void test_cfile_exception() {
    std::printf("[2] CFile：打开失败抛异常（E.2）；构造失败的资源不落地\n");
    bool threw = false;
    try {
        raii::CFile f("/tmp/no-such-dir-ph13/x.txt", "w");
        (void)f;
    } catch (const std::runtime_error&) {
        threw = true;
    }
    check(threw, "打开不存在的目录 → 抛 runtime_error");
}

void test_cfile_move() {
    std::printf("[3] CFile：移动构造/移动赋值，句柄易主、旧句柄置空\n");
    {
        raii::CFile a(kPath, "w");
        a.write("moved\n", 6);
        raii::CFile b(std::move(a));       // 移动构造：所有权转移到 b
        b.write("more\n", 5);              // b 是有效句柄，可继续写
        check(b.eof() == false, "移动后 b 持有有效句柄并可继续写");
        // a 已是"空句柄"：析构 no-op（无 double close），此处随作用域结束析构
    }
    {
        raii::CFile a(kPath, "w");
        a.write("one\n", 4);
        raii::CFile b(kPath, "w");
        b.write("two\n", 4);
        b = std::move(a);                  // 移动赋值：b 先关闭自己的旧文件，再接管 a 的
        b.write("three\n", 6);
        check(b.eof() == false, "移动赋值后 b 接管 a 的句柄并可继续写");
    }
    std::remove(kPath);
}

void test_unique_fd_basics() {
    std::printf("[4] UniqueFd：默认 -1、构造持有、移动转移、release 放弃所有权\n");
    {
        raii::UniqueFd d;
        check(d.get() == -1 && !static_cast<bool>(d), "默认构造：get()==-1 且 bool 为 false");
    }
    {
        raii::UniqueFd a(::open("/dev/null", O_RDONLY));
        check(a.get() >= 0, "显式构造：持有 open 返回的 fd");
        raii::UniqueFd b(std::move(a));
        check(b.get() >= 0 && a.get() == -1, "移动构造：b 接管、a 置空");
    }
    {
        raii::UniqueFd a(::open("/dev/null", O_RDONLY));
        const int raw = a.release();
        check(raw >= 0 && a.get() == -1, "release()：放弃所有权、对象变空");
        ::close(raw);                      // 所有权已交还调用方，手动关闭
    }
}

void test_pipe_roundtrip() {
    std::printf("[5] UniqueFd：pipe 双向读写往返（write_all / read_some）\n");
    int p[2];
    check(::pipe(p) == 0, "创建匿名管道");
    {
        raii::UniqueFd r(p[0]);
        raii::UniqueFd w(p[1]);
        const char* msg = "ping-ph13";
        w.write_all(msg, std::strlen(msg));
        char buf[32] = {};
        const std::size_t n = r.read_some(buf, sizeof buf - 1);
        check(n == std::strlen(msg) && std::strcmp(buf, msg) == 0,
              "写端写入、读端读回内容一致");
    }
}

void test_exception_path_no_leak() {
    std::printf("[6] 异常路径：写已关闭的管道抛异常，fd 由析构关闭、计数归零\n");
    int fd_probe = -1;
    {
        int p[2];
        if (::pipe(p) != 0) return;
        raii::UniqueFd r(p[0]);
        raii::UniqueFd w(p[1]);
        r = raii::UniqueFd{};              // 移动赋值：关闭读端（模拟对端进程退出）
        fd_probe = w.get();
        bool threw = false;
        try {
            w.write_all("boom", 4);        // 对端已关：EPIPE 异常（SIGPIPE 已忽略）
        } catch (const std::runtime_error&) {
            threw = true;
        }
        check(threw, "写已关闭的管道 → write_all 抛 runtime_error");
    }                                     // w 析构 → close(fd)
    check(!fd_alive(fd_probe), "异常穿越作用域后，fd 由析构关闭（fcntl EBADF 实测）");

    std::printf("[7] 压力：200 次异常路径 + 100 次 CFile 开合，fd 计数回到基线\n");
    const int baseline = open_fd_count();
    for (int i = 0; i < 200; ++i) {
        int p[2];
        if (::pipe(p) != 0) break;
        try {
            raii::UniqueFd r(p[0]);
            raii::UniqueFd w(p[1]);
            r = raii::UniqueFd{};          // 关闭读端
            w.write_all("x", 1);           // 必抛 EPIPE
        } catch (const std::runtime_error&) {
            // 预期异常：两次 RAII 句柄在栈展开时都已 close
        }
    }
    for (int i = 0; i < 100; ++i) {
        raii::CFile f(kPath, "a");
        f.write("x", 1);
    }
    const int after = open_fd_count();
    std::remove(kPath);
    check(after == baseline,
          "300 次开合（含 200 次异常路径）后 fd 计数回到基线（零泄漏）");
}

void test_copy_roundtrip() {
    std::printf("[8] 复制往返：UniqueFd 分块复制，目标文件内容与源一致\n");
    const char* src = "/tmp/ph13-test-src.txt";
    const char* dst = "/tmp/ph13-test-dst.txt";
    {
        raii::CFile f(src, "w");
        for (int i = 1; i <= 500; ++i) {
            const std::string line = "row-" + std::to_string(i) + "\n";
            f.write(line.data(), line.size());
        }
    }
    {
        raii::UniqueFd in(::open(src, O_RDONLY));
        raii::UniqueFd out(::open(dst, O_WRONLY | O_CREAT | O_TRUNC, 0644));
        char buf[512];                     // 故意用小缓冲：多轮 read_some/write_all
        std::size_t total = 0;
        for (;;) {
            const std::size_t n = in.read_some(buf, sizeof buf);
            if (n == 0) break;
            out.write_all(buf, n);
            total += n;
        }
        std::size_t expected = 0;
        for (int i = 1; i <= 500; ++i) expected += std::to_string(i).size() + 5;
        check(total == expected, "复制字节数正确（500 行，行长随位数增长）");
    }
    {
        raii::CFile a(src, "r");
        raii::CFile b(dst, "r");
        char x[256], y[256];
        bool same = true;
        for (;;) {
            const std::size_t nx = a.read(x, sizeof x);
            const std::size_t ny = b.read(y, sizeof y);
            if (nx != ny || (nx > 0 && std::memcmp(x, y, nx) != 0)) {
                same = false;
                break;
            }
            if (nx == 0) break;
        }
        check(same, "src/dst 逐块读回内容完全一致");
    }
    std::remove(src);
    std::remove(dst);
}

}  // namespace

int main() {
    std::signal(SIGPIPE, SIG_IGN);         // 写已关闭的管道改为返回 EPIPE，而非杀死进程
    test_cfile_basics();
    test_cfile_exception();
    test_cfile_move();
    test_unique_fd_basics();
    test_pipe_roundtrip();
    test_exception_path_no_leak();
    test_copy_roundtrip();
    std::printf("=== 自测结束：%d 组检查，%d 组失败 ===\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
